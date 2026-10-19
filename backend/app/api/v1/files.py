import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
import openpyxl

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.enums import DomainCategory, FileStatus, TaskPriority, TaskStatus, UserRole
from app.models.file import FileTemplate, ParsingJob, UploadedFile
from app.models.finance import CashflowOperation
from app.models.payroll import PayrollRecord
from app.models.project import TenderProject
from app.models.task import OperationalTask
from app.models.user import User
from app.schemas.common import MetaModel, ResponseEnvelope
from app.schemas.files import (
    CanonicalFieldDefinition,
    FileListItem,
    FileUploadResponseData,
    FileValidationErrorDetail,
    FileValidationErrorResponse,
    MappingConfirmRequest,
    MappingConfirmResponseData,
    MappingPreviewResponseData,
    UploadAndAssignResult,
)
from app.services.alerts_engine import alerts_engine
from app.services.google_drive import get_google_drive_client
from app.services.parser import CANONICAL_FIELDS, ExcelParserService
from app.services.storage import build_tenant_storage_key, storage_service
from app.services.template_parser import DocumentValidationError, StandardTemplateParser

router = APIRouter(prefix="/files", tags=["Files & Excel Ingestion"])


@router.post(
    "/upload-and-assign",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseEnvelope[UploadAndAssignResult],
    summary="Загрузка документа на Google Диск бухгалтером и передача менеджеру (BE-5.1)",
)
async def upload_and_assign_document(
    file: UploadFile = File(...),
    target_folder: str = Form(...),
    comment: str = Form(...),
    assignee_role: str = Form("manager"),
    contract_id_or_name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[UploadAndAssignResult]:
    """
    BE-5.1:
    - Accepts file, target_folder on Google Drive, comment, and assignee_role.
    - Saves file to Google Drive (Mock / API v3).
    - Parses financial indicators if Excel file, updating cash balance.
    - Creates task in operational_tasks with 'pending' status, drive link and comment.
    """
    orig_name = file.filename or "accounting_report.xlsx"
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недопустимый формат файла. Поддерживаются только .xlsx, .xls, .csv",
        )

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Размер файла превышает лимит {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)} МБ",
        )

    sha256_hash = hashlib.sha256(content).hexdigest()

    # 1. Upload to Google Drive (Mock / API v3)
    gdrive_client = get_google_drive_client()
    drive_upload = gdrive_client.upload_file(
        folder_name_or_id=target_folder,
        filename=orig_name,
        content=content,
    )

    # 2. Check if file record already exists or create new
    existing_q = select(UploadedFile).where(
        UploadedFile.company_id == current_user.company_id,
        UploadedFile.sha256_hash == sha256_hash,
        UploadedFile.deleted_at.is_(None),
    )
    uploaded_file = (await db.execute(existing_q)).scalar_one_or_none()

    if not uploaded_file:
        uploaded_file = UploadedFile(
            company_id=current_user.company_id,
            uploaded_by_user_id=current_user.id,
            original_name=orig_name,
            storage_path=f"google_drive:{drive_upload.id}",
            file_size_bytes=len(content),
            mime_type=file.content_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            sha256_hash=sha256_hash,
            status=FileStatus.PROCESSED,
        )
        db.add(uploaded_file)
        await db.flush()
    else:
        uploaded_file.storage_path = f"google_drive:{drive_upload.id}"
        uploaded_file.status = FileStatus.PROCESSED
        await db.flush()

    # 3. Deterministic parsing of financial/operational data if spreadsheet
    template_type = StandardTemplateParser.detect_template_type(orig_name, content)
    if template_type:
        try:
            if "cashflow" in template_type:
                await StandardTemplateParser.parse_cashflow_sheet(uploaded_file.id, current_user.company_id, content, db)
            elif "procurement" in template_type:
                await StandardTemplateParser.parse_procurement_sheet(uploaded_file.id, current_user.company_id, content, db)
            elif "tender" in template_type:
                await StandardTemplateParser.parse_tender_registry(uploaded_file.id, current_user.company_id, content, db)
            elif "dispatch" in template_type:
                await StandardTemplateParser.parse_dispatch_sheet(uploaded_file.id, current_user.company_id, content, db)
            elif "task" in template_type:
                await StandardTemplateParser.parse_operational_tasks(uploaded_file.id, current_user.company_id, content, db)

            # Recompute cash gap and systemic alerts after financial ingestion
            await alerts_engine.run_full_evaluation(current_user.company_id, db)
        except Exception:
            pass

    # 4. Create Operational Task for assignee_role
    today = datetime.now(timezone.utc).date()
    new_task = OperationalTask(
        company_id=current_user.company_id,
        file_id=uploaded_file.id,
        task_title=f"Согласование документа: {orig_name}",
        related_contract=contract_id_or_name,
        responsible_role=assignee_role or "manager",
        responsible_person="Менеджер проекта",
        due_date=today + timedelta(days=3),
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        description=comment,
        google_drive_link=drive_upload.web_view_link,
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    result_data = UploadAndAssignResult(
        file_id=str(uploaded_file.id),
        task_id=str(new_task.id),
        file_name=orig_name,
        google_drive_folder=target_folder,
        google_drive_link=drive_upload.web_view_link,
        assigned_to_role=assignee_role or "manager",
        status="transferred_to_manager",
        message="Файл успешно загружен на Google Диск и передан менеджеру проектов",
    )
    return ResponseEnvelope.ok(result_data)


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузка Excel-файла с потоковым расчетом SHA-256 и проверкой дубликатов",
)
async def upload_excel_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts raw multipart/form-data spreadsheet, verifies size (<= 25 MB),
    computes SHA-256 fingerprint, performs tenant deduplication check,
    persists bytes to local volume, and registers file in database.
    """
    # 1. Validate file extension
    # 1. Validate file extension
    orig_name = file.filename or "uploaded_spreadsheet.xlsx"
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in (".xlsx", ".xls", ".csv", ".txt"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "error",
                "message": "Недопустимый формат файла",
                "details": [{"error": f"Формат '{ext}' не поддерживается. Разрешены только .xlsx, .xls, .csv, .txt"}],
            },
        )

    # 2. Stream read and enforce 25 MB strict limit
    content = await file.read()
    file_size = len(content)
    if file_size > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Размер файла превышает допустимый лимит {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)} МБ",
        )

    # 3. Calculate SHA-256 hash
    sha256_hash = hashlib.sha256(content).hexdigest()

    # 4. Tenant deduplication check
    dup_query = select(UploadedFile).where(
        UploadedFile.company_id == current_user.company_id,
        UploadedFile.sha256_hash == sha256_hash,
        UploadedFile.deleted_at.is_(None),
    )
    dup_res = await db.execute(dup_query)
    existing_file = dup_res.scalar_one_or_none()

    if existing_file:
        error_payload = {
            "success": False,
            "data": None,
            "error": {
                "code": "DUPLICATE_FILE",
                "message": "Этот файл уже был загружен в систему ранее",
                "details": {
                    "existing_file_id": str(existing_file.id),
                    "original_name": existing_file.original_name,
                    "uploaded_at": existing_file.created_at.isoformat(),
                },
            },
            "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
        }
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error_payload)

    # 5. Save file to storage
    storage_key = build_tenant_storage_key(current_user.company_id, sha256_hash, ext)
    await storage_service.save_file(content, storage_key)
    local_path = storage_service.get_local_file_path(storage_key)

    # 6. Extract sheets and check template structure safely
    sheets = ["Лист1"]
    is_cached_template = False
    validation_err_payload = None

    if ext in (".xlsx", ".xls"):
        try:
            sheets = ExcelParserService.get_workbook_sheet_names(local_path)
            wb = openpyxl.load_workbook(local_path, data_only=True)
            ws = wb[sheets[0]]
            _, headers, _ = ExcelParserService.detect_table_structure(ws)
            wb.close()
            if headers:
                fp = ExcelParserService.calculate_headers_fingerprint(headers)
                tpl_query = select(FileTemplate).where(
                    FileTemplate.company_id == current_user.company_id,
                    FileTemplate.headers_fingerprint == fp,
                )
                tpl_res = await db.execute(tpl_query)
                is_cached_template = tpl_res.scalar_one_or_none() is not None
        except Exception as e:
            sheets = ["Лист1"]
            validation_err_payload = {
                "status": "error",
                "message": f"Поврежденный или нечитаемый файл: {orig_name}",
                "details": [{"error": f"Ошибка чтения Excel: {str(e)}"}],
            }
    elif ext == ".txt":
        sheets = ["1CClientBankExchange"]

    # If parsing or structure is corrupted, register error file record and return 422 (Task BE-2.3)
    if validation_err_payload:
        uploaded_file = UploadedFile(
            company_id=current_user.company_id,
            uploaded_by_user_id=current_user.id,
            original_name=orig_name,
            storage_path=storage_key,
            file_size_bytes=file_size,
            mime_type=file.content_type or "application/octet-stream",
            sha256_hash=sha256_hash,
            status=FileStatus.ERROR,
            error_message=validation_err_payload["message"],
        )
        db.add(uploaded_file)
        await db.commit()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=validation_err_payload)

    # 7. Create database record
    uploaded_file = UploadedFile(
        company_id=current_user.company_id,
        uploaded_by_user_id=current_user.id,
        original_name=orig_name,
        storage_path=storage_key,
        file_size_bytes=file_size,
        mime_type=file.content_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        sha256_hash=sha256_hash,
        status=FileStatus.AWAITING_CONFIRMATION,
    )
    db.add(uploaded_file)
    await db.commit()
    await db.refresh(uploaded_file)

    response_data = FileUploadResponseData(
        file_id=uploaded_file.id,
        original_name=uploaded_file.original_name,
        file_size_bytes=uploaded_file.file_size_bytes,
        sha256_hash=uploaded_file.sha256_hash,
        status=uploaded_file.status,
        sheets=sheets,
        is_cached_template=is_cached_template,
    )
    return ResponseEnvelope.ok(response_data)


@router.get(
    "/{file_id}/mapping-preview",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[MappingPreviewResponseData],
    summary="Получение предпросмотра структуры колонок и семантического маппинга",
)
async def get_mapping_preview(
    file_id: uuid.UUID,
    sheet_name: Optional[str] = Query(None, description="Имя листа для анализа"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[MappingPreviewResponseData]:
    """
    Analyzes sheet structure with unmerge & fill normalization, checks fingerprint template cache,
    or falls back to ontology inference. Returns column mapping proposals with sample values.
    """
    # 1. Fetch file strictly within tenant
    query = select(UploadedFile).where(
        UploadedFile.id == file_id,
        UploadedFile.company_id == current_user.company_id,
        UploadedFile.deleted_at.is_(None),
    )
    res = await db.execute(query)
    file_rec = res.scalar_one_or_none()
    if not file_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл не найден в вашей организации",
        )

    # 2. Open workbook
    local_path = storage_service.get_local_file_path(file_rec.storage_path)
    if not local_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Физический файл документа не найден в хранилище",
        )

    wb = openpyxl.load_workbook(local_path, data_only=True)
    target_sheet = sheet_name or wb.active.title
    if target_sheet not in wb.sheetnames:
        target_sheet = wb.sheetnames[0]
    ws = wb[target_sheet]

    # 3. Detect normalized table structure
    _, headers, data_rows = ExcelParserService.detect_table_structure(ws)
    wb.close()

    if not headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось определить заголовки таблицы в данном листе",
        )

    # 4. Check Template Fingerprint Cache
    fingerprint = ExcelParserService.calculate_headers_fingerprint(headers)
    tpl_query = select(FileTemplate).where(
        FileTemplate.company_id == current_user.company_id,
        FileTemplate.headers_fingerprint == fingerprint,
    )
    tpl_res = await db.execute(tpl_query)
    saved_template = tpl_res.scalar_one_or_none()

    if saved_template:
        suggested_domain = saved_template.domain_category
        confidence_score = float(saved_template.confidence_score)
        source_type = "template_cache"
        col_mappings = []
        for col_idx, col in enumerate(headers):
            target_f = saved_template.column_mapping.get(col)
            sample_vals = [
                str(r[col_idx])
                for r in data_rows[:3]
                if col_idx < len(r) and r[col_idx] is not None
            ]
            col_mappings.append(
                {
                    "source_column": col,
                    "sample_values": sample_vals,
                    "target_field": target_f if target_f != "ignore" else None,
                    "confidence": 1.00 if target_f else 0.20,
                    "is_required": False,
                }
            )
    else:
        # Run heuristic ontology inference
        suggested_domain, confidence_score, col_mappings = (
            ExcelParserService.infer_domain_and_mapping(headers, data_rows[:3])
        )
        source_type = "heuristic"

    # 5. Build available canonical fields
    avail_fields = [
        CanonicalFieldDefinition(
            field=f["field"],
            label=f["label"],
            required=f["required"],
        )
        for f in CANONICAL_FIELDS[suggested_domain]
    ]

    response_data = MappingPreviewResponseData(
        file_id=file_rec.id,
        sheet_name=target_sheet,
        suggested_domain=suggested_domain,
        confidence_score=confidence_score,
        source_type=source_type,
        total_rows_detected=len(data_rows),
        columns_mapping=col_mappings,
        available_canonical_fields=avail_fields,
    )
    return ResponseEnvelope.ok(response_data)


@router.post(
    "/{file_id}/mapping-confirm",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[MappingConfirmResponseData],
    summary="Подтверждение сопоставления колонок и загрузка строк в каноническую таблицу",
)
async def confirm_mapping_and_import(
    file_id: uuid.UUID,
    payload: MappingConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[MappingConfirmResponseData]:
    """
    Saves/updates template fingerprint cache, normalizes all rows,
    persists extracted records into canonical business domain table,
    and updates file status to processed.
    """
    # 1. Fetch file record
    query = select(UploadedFile).where(
        UploadedFile.id == file_id,
        UploadedFile.company_id == current_user.company_id,
        UploadedFile.deleted_at.is_(None),
    )
    res = await db.execute(query)
    file_rec = res.scalar_one_or_none()
    if not file_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл не найден в вашей организации",
        )

    # 2. Read workbook
    local_path = storage_service.get_local_file_path(file_rec.storage_path)
    wb = openpyxl.load_workbook(local_path, data_only=True)
    target_sheet = payload.sheet_name if payload.sheet_name in wb.sheetnames else wb.sheetnames[0]
    ws = wb[target_sheet]
    _, headers, data_rows = ExcelParserService.detect_table_structure(ws)
    wb.close()

    # 3. Save or update template cache
    fingerprint = ExcelParserService.calculate_headers_fingerprint(headers)
    tpl_query = select(FileTemplate).where(
        FileTemplate.company_id == current_user.company_id,
        FileTemplate.headers_fingerprint == fingerprint,
    )
    tpl_res = await db.execute(tpl_query)
    template = tpl_res.scalar_one_or_none()

    tpl_name = payload.template_name or f"Шаблон {payload.domain_category.value}"
    if template:
        template.column_mapping = payload.mappings
        template.domain_category = payload.domain_category
        template.match_count += 1
        template.template_name = tpl_name
    else:
        new_tpl = FileTemplate(
            company_id=current_user.company_id,
            template_name=tpl_name,
            sheet_name=target_sheet,
            headers_fingerprint=fingerprint,
            domain_category=payload.domain_category,
            column_mapping=payload.mappings,
            match_count=1,
        )
        db.add(new_tpl)

    # 4. Map columns indices
    header_to_field: Dict[int, str] = {}
    for idx, col_name in enumerate(headers):
        mapped_field = payload.mappings.get(col_name)
        if mapped_field and mapped_field != "ignore":
            header_to_field[idx] = mapped_field

    # 5. Ingest rows into canonical domain
    imported_count = 0
    now_dt = datetime.now(timezone.utc)

    for row in data_rows:
        row_dict: Dict[str, Any] = {}
        custom_attrs: Dict[str, Any] = {}

        for col_idx, cell_val in enumerate(row):
            if col_idx in header_to_field:
                field_name = header_to_field[col_idx]
                row_dict[field_name] = cell_val
            else:
                if col_idx < len(headers) and cell_val is not None:
                    custom_attrs[headers[col_idx]] = str(cell_val)

        # Domain 1: Tenders & Production
        if payload.domain_category == DomainCategory.PRODUCTION_TENDERS:
            p_name = str(row_dict.get("project_name") or "").strip()
            if not p_name:
                continue  # skip invalid empty entity rows

            project = TenderProject(
                company_id=current_user.company_id,
                file_id=file_rec.id,
                project_code=str(row_dict.get("project_code") or "")[:100] or None,
                project_name=p_name[:500],
                customer_name=str(row_dict.get("customer_name") or "")[:255] or None,
                curator_name=str(row_dict.get("curator_name") or "")[:255] or None,
                contract_sum=ExcelParserService.clean_decimal(row_dict.get("contract_sum")),
                completed_sum=ExcelParserService.clean_decimal(row_dict.get("completed_sum")),
                paid_sum=ExcelParserService.clean_decimal(row_dict.get("paid_sum")),
                debt_sum=ExcelParserService.clean_decimal(row_dict.get("debt_sum")),
                start_date=ExcelParserService.clean_date(row_dict.get("start_date")),
                deadline_date=ExcelParserService.clean_date(row_dict.get("deadline_date")),
                custom_attributes=custom_attrs,
            )
            db.add(project)
            imported_count += 1

        # Domain 2: Cashflow & Debt
        elif payload.domain_category == DomainCategory.CASHFLOW_DEBT:
            op_date = ExcelParserService.clean_date(row_dict.get("operation_date")) or now_dt.date()
            op = CashflowOperation(
                company_id=current_user.company_id,
                file_id=file_rec.id,
                operation_date=op_date,
                counterparty=str(row_dict.get("counterparty") or "")[:255] or None,
                direction=row_dict.get("direction") or "incoming",
                category=str(row_dict.get("category") or "")[:100] or None,
                planned_amount=ExcelParserService.clean_decimal(row_dict.get("planned_amount")),
                actual_amount=ExcelParserService.clean_decimal(row_dict.get("actual_amount")),
                payment_due_date=ExcelParserService.clean_date(row_dict.get("payment_due_date")),
                account_name=str(row_dict.get("account_name") or "")[:100] or None,
            )
            db.add(op)
            imported_count += 1

        # Domain 3: Payroll & HR
        elif payload.domain_category == DomainCategory.PAYROLL_HR:
            emp_name = str(row_dict.get("employee_name") or "").strip()
            if not emp_name:
                continue

            payroll = PayrollRecord(
                company_id=current_user.company_id,
                file_id=file_rec.id,
                payroll_period=str(row_dict.get("payroll_period") or now_dt.strftime("%Y-%m"))[:20],
                employee_name=emp_name[:255],
                department=str(row_dict.get("department") or "")[:150] or None,
                role_title=str(row_dict.get("role_title") or "")[:150] or None,
                accrued_amount=ExcelParserService.clean_decimal(row_dict.get("accrued_amount")),
                paid_amount=ExcelParserService.clean_decimal(row_dict.get("paid_amount")),
                debt_amount=ExcelParserService.clean_decimal(row_dict.get("debt_amount")),
            )
            db.add(payroll)
            imported_count += 1

        # Domain 4: Operational Tasks
        elif payload.domain_category == DomainCategory.OPERATIONAL_TASKS:
            title = str(row_dict.get("task_title") or "").strip()
            if not title:
                continue

            task = OperationalTask(
                company_id=current_user.company_id,
                file_id=file_rec.id,
                task_title=title[:500],
                responsible_person=str(row_dict.get("responsible_person") or "")[:255] or None,
                due_date=ExcelParserService.clean_date(row_dict.get("due_date")),
            )
            db.add(task)
            imported_count += 1

    # 6. Update File Status and Audit Log
    file_rec.status = FileStatus.PROCESSED
    job = ParsingJob(
        file_id=file_rec.id,
        status="completed",
        extracted_rows_count=imported_count,
        confidence_score=1.00,
        detected_headers=payload.mappings,
        finished_at=datetime.now(timezone.utc),
    )
    db.add(job)

    # 7. Run Financial Impact & Risk Engine evaluation
    from app.services.alerts_engine import alerts_engine
    await alerts_engine.run_full_evaluation(current_user.company_id, db)

    # Count active alerts
    alerts_count_q = select(func.count(SystemAlert.id)).where(
        SystemAlert.company_id == current_user.company_id,
        SystemAlert.is_resolved.is_(False),
    )
    alerts_count = (await db.execute(alerts_count_q)).scalar_one()

    await db.commit()

    return ResponseEnvelope.ok(
        MappingConfirmResponseData(
            file_id=file_rec.id,
            status=file_rec.status,
            imported_rows_count=imported_count,
            alerts_triggered_count=alerts_count,
            template_saved=True,
        )
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[List[FileListItem]],
    summary="Получение списка загруженных файлов компании с пагинацией",
)
async def list_files(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[FileStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[List[FileListItem]]:
    """Returns paginated list of uploaded files for the tenant."""
    base_query = select(UploadedFile).where(
        UploadedFile.company_id == current_user.company_id,
        UploadedFile.deleted_at.is_(None),
    )
    if status:
        base_query = base_query.where(UploadedFile.status == status)

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total_items = (await db.execute(count_query)).scalar_one()

    # Query items with pagination
    query = (
        base_query.options(joinedload(UploadedFile.uploader))
        .order_by(UploadedFile.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    res = await db.execute(query)
    files = res.scalars().all()

    items = [
        FileListItem(
            id=f.id,
            original_name=f.original_name,
            file_size_bytes=f.file_size_bytes,
            status=f.status,
            uploaded_by=f.uploader.full_name if f.uploader else None,
            created_at=f.created_at,
        )
        for f in files
    ]

    total_pages = (total_items + limit - 1) // limit if limit else 1
    meta = MetaModel(
        page=page,
        limit=limit,
        total_items=total_items,
        total_pages=total_pages,
    )
    return ResponseEnvelope.ok(items, meta=meta)


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_200_OK,
    summary="Мягкое удаление файла и всех связанных с ним канонических записей",
)
async def delete_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[dict]:
    """Soft-deletes file and cascades deleted_at to all extracted records."""
    query = select(UploadedFile).where(
        UploadedFile.id == file_id,
        UploadedFile.company_id == current_user.company_id,
        UploadedFile.deleted_at.is_(None),
    )
    res = await db.execute(query)
    file_rec = res.scalar_one_or_none()
    if not file_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл не найден",
        )

    now_dt = datetime.now(timezone.utc)
    file_rec.deleted_at = now_dt

    # Cascade soft-deletion across canonical domain tables
    for domain_model in (TenderProject, CashflowOperation, PayrollRecord, OperationalTask):
        await db.execute(
            update(domain_model)
            .where(
                domain_model.file_id == file_id,
                domain_model.company_id == current_user.company_id,
                domain_model.deleted_at.is_(None),
            )
            .values(deleted_at=now_dt)
        )

    await db.commit()
    return ResponseEnvelope.ok({"message": "Файл и связанные записи успешно помечены удаленными"})
