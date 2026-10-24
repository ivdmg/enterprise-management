import asyncio
import hashlib
import logging
from pathlib import Path
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.config import settings
from app.models.enums import FileStatus
from app.models.file import UploadedFile
from app.models.finance import CashflowOperation
from app.models.procurement import ProcurementItem
from app.models.dispatch import FleetDispatchRecord
from app.models.task import OperationalTask
from app.models.payroll import PayrollRecord
from app.models.alert import SystemAlert
from app.models.project import TenderProject
from app.services.alerts_engine import alerts_engine
from app.services.google_drive import DriveFileInfo, google_drive_client
from app.services.storage import build_tenant_storage_key, storage_service
from app.services.template_parser import standard_template_parser

logger = logging.getLogger("enterprise_hub.drive_sync")


class SyncStatusInfo:
    """In-memory tracking of drive synchronization runs."""
    def __init__(self):
        self.status: str = "idle"  # "idle" | "syncing" | "error"
        self.last_sync_time: Optional[datetime] = None
        self.processed_files_count: int = 0
        self.skipped_files_count: int = 0
        self.last_error: Optional[str] = None
        self.details: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "processed_files_count": self.processed_files_count,
            "skipped_files_count": self.skipped_files_count,
            "last_error": self.last_error,
            "details": self.details[-10:],  # last 10 file events
        }


class GoogleDriveSyncService:
    """
    Orchestrator for importing editable Google Drive sources (or Mock Drive)
    and the Smart Enterprise Hub database.
    """

    # Folders monitored for incoming files
    INCOMING_FOLDERS = [
        "root",
        "01_Сметы_и_Тендеры",
        "02_Счета_Снабжения",
        "03_Банк_и_Касса",
        "04_Путевые_листы",
        "01_Реестры_Тендеров",
        "02_Финансы_и_1С",
        "03_Снабжение_и_Закупки",
        "04_ПТО_и_Объекты",
        "05_Юридический_Отдел",
    ]

    PROCESSED_FOLDER = "05_Обработано"
    ERROR_FOLDER = "99_Ошибки_парсинга"

    def __init__(self):
        self._lock = asyncio.Lock()
        self._status_by_company: Dict[uuid.UUID, SyncStatusInfo] = {}

    def get_status(self, company_id: uuid.UUID) -> SyncStatusInfo:
        if company_id not in self._status_by_company:
            self._status_by_company[company_id] = SyncStatusInfo()
        return self._status_by_company[company_id]

    async def sync_company_drive(
        self,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Synchronizes incoming folders on Google Drive for the specified company.
        Performs 0-overhead hash skipping when files have not changed.
        Retains source documents in place for future edits and retry after errors.
        """
        status_info = self.get_status(company_id)
        if not google_drive_client.is_mock and settings.GOOGLE_DRIVE_COMPANY_ID != company_id:
            status_info.status = "error"
            status_info.last_error = "Google Диск не подключён к этой организации"
            return status_info.to_dict()
        if status_info.status == "syncing":
            logger.warning("Sync already in progress for company %s", company_id)
            return status_info.to_dict()

        async with self._lock:
            status_info.status = "syncing"
            status_info.last_error = None
            status_info.details = []
            
            processed = 0
            skipped = 0

            # Session lifecycle: either use passed session or create a dedicated one
            owns_session = db is None
            session = db if db is not None else async_session_factory()

            # Ensure local incoming storage directory exists (Task BE-1.2)
            incoming_dir = Path("storage/incoming")
            incoming_dir.mkdir(parents=True, exist_ok=True)

            try:
                # 1. Discover all files across incoming target folders
                all_drive_files: List[DriveFileInfo] = []
                for folder in self.INCOMING_FOLDERS:
                    if folder == "root" and google_drive_client.is_mock:
                        continue
                    try:
                        folder_files = await asyncio.to_thread(google_drive_client.list_files_in_folder, folder)
                        all_drive_files.extend(folder_files)
                    except Exception as e:
                        raise RuntimeError(f"Не удалось прочитать папку {folder}: {e}") from e

                logger.info(
                    "Drive sync started for company %s: found %d total files across folders",
                    company_id,
                    len(all_drive_files),
                )

                # A mock root scan and a child scan may return the same document.
                all_drive_files = list({f.id: f for f in all_drive_files}.values())
                # 2. Process each file
                for file_info in all_drive_files:
                    file_bytes = b""
                    sha256_hash = ""
                    try:
                        # Download raw file bytes with retry/backoff
                        file_bytes = await asyncio.to_thread(google_drive_client.download_file_bytes, file_info.id)
                        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

                        # Save copy to local temporary incoming storage (Task BE-1.2)
                        ext = Path(file_info.name).suffix or ".xlsx"
                        incoming_file_path = incoming_dir / f"{uuid.uuid4().hex}{ext}"
                        incoming_file_path.write_bytes(file_bytes)

                        # Check if this exact file version was already ingested
                        query = select(UploadedFile).where(
                            UploadedFile.company_id == company_id,
                            UploadedFile.google_drive_id == file_info.id,
                            UploadedFile.deleted_at.is_(None),
                        )
                        existing_file = (await session.execute(query)).scalar_one_or_none()

                        if existing_file and existing_file.sha256_hash == sha256_hash and existing_file.status == FileStatus.PROCESSED:
                            # 0 overhead: file content has not changed
                            skipped += 1
                            status_info.details.append({
                                "file": file_info.name,
                                "folder": file_info.parent_folder,
                                "action": "skipped",
                                "reason": "Hash unchanged",
                            })
                            continue

                        # File is new or updated: save to tenant storage
                        storage_key = build_tenant_storage_key(
                            company_id=company_id,
                            sha256_hash=sha256_hash,
                            extension=ext,
                        )
                        await storage_service.save_file(file_bytes, storage_key)

                        # Create or update UploadedFile record
                        uploaded_file = existing_file or UploadedFile(
                            company_id=company_id,
                            uploaded_by_user_id=user_id,
                            original_name=file_info.name,
                            storage_path=storage_key,
                            file_size_bytes=len(file_bytes),
                            mime_type=file_info.mime_type,
                            sha256_hash=sha256_hash,
                            status=FileStatus.UPLOADED,
                        )
                        uploaded_file.original_name = file_info.name
                        uploaded_file.storage_path = storage_key
                        uploaded_file.file_size_bytes = len(file_bytes)
                        uploaded_file.sha256_hash = sha256_hash
                        uploaded_file.google_drive_id = file_info.id
                        uploaded_file.google_drive_link = file_info.web_view_link
                        uploaded_file.error_message = None
                        session.add(uploaded_file)
                        await session.flush()

                        old_project_ids = (await session.execute(select(TenderProject.id).where(
                            TenderProject.company_id == company_id, TenderProject.file_id == uploaded_file.id,
                            TenderProject.deleted_at.is_(None),
                        ))).scalars().all() if existing_file else []
                        if old_project_ids:
                            await session.execute(update(TenderProject).where(TenderProject.id.in_(old_project_ids)).values(file_id=None))

                        # Each editable document owns a snapshot. Replace its dependent rows
                        # in the same transaction, so edits/deletions cannot double totals.
                        models_to_replace = (CashflowOperation, ProcurementItem, FleetDispatchRecord, OperationalTask, PayrollRecord) if existing_file else ()
                        for model in models_to_replace:
                            old_ids = select(model.id).where(model.company_id == company_id, model.file_id == uploaded_file.id, model.deleted_at.is_(None))
                            await session.execute(update(SystemAlert).where(
                                SystemAlert.company_id == company_id,
                                SystemAlert.entity_type == model.__tablename__,
                                SystemAlert.entity_id.in_(old_ids),
                                SystemAlert.is_resolved.is_(False),
                            ).values(is_resolved=True, resolved_at=datetime.now(timezone.utc)))
                            await session.execute(update(model).where(
                                model.company_id == company_id, model.file_id == uploaded_file.id,
                                model.deleted_at.is_(None),
                            ).values(deleted_at=datetime.now(timezone.utc)))

                        # Deterministic parsing into business models
                        tpl_type, count = await standard_template_parser.parse_and_persist(
                            file_source=file_bytes,
                            filename=file_info.name,
                            company_id=company_id,
                            file_id=uploaded_file.id,
                            db=session,
                        )

                        await session.flush()
                        if old_project_ids:
                            removed = select(TenderProject.id).where(TenderProject.id.in_(old_project_ids), TenderProject.file_id.is_(None))
                            await session.execute(update(SystemAlert).where(SystemAlert.company_id == company_id,
                                SystemAlert.entity_type == "tender_projects", SystemAlert.entity_id.in_(removed),
                                SystemAlert.is_resolved.is_(False)).values(is_resolved=True, resolved_at=datetime.now(timezone.utc)))
                            await session.execute(update(TenderProject).where(TenderProject.id.in_(old_project_ids),
                                TenderProject.file_id.is_(None)).values(deleted_at=datetime.now(timezone.utc)))

                        await session.execute(update(OperationalTask).where(
                            OperationalTask.company_id == company_id, OperationalTask.file_id == uploaded_file.id,
                            OperationalTask.deleted_at.is_(None),
                        ).values(google_drive_link=file_info.web_view_link))

                        uploaded_file.status = FileStatus.PROCESSED
                        await session.commit()
                        processed += 1

                        status_info.details.append({
                            "file": file_info.name,
                            "folder": file_info.parent_folder,
                            "action": "imported",
                            "records_extracted": count,
                            "template_type": tpl_type,
                        })

                    except Exception as fe:
                        await session.rollback()
                        error_msg = str(fe)
                        logger.error("Error processing Drive file '%s': %s", file_info.name, error_msg)

                        # Task BE-1.3 & BE-2.3: Move to 99_Ошибки_парсинга and mark status error
                        try:
                            # Register error record in DB
                            err_file = (await session.execute(select(UploadedFile).where(
                                UploadedFile.company_id == company_id,
                                UploadedFile.google_drive_id == file_info.id,
                            ))).scalar_one_or_none()
                            err_file = err_file or UploadedFile(
                                company_id=company_id,
                                uploaded_by_user_id=user_id,
                                original_name=file_info.name,
                                storage_path="unavailable",
                                file_size_bytes=len(file_bytes) if 'file_bytes' in locals() else 0,
                                mime_type=file_info.mime_type,
                                sha256_hash=sha256_hash if 'sha256_hash' in locals() else "error",
                                status=FileStatus.ERROR,
                                error_message=error_msg,
                            )
                            err_file.google_drive_id = file_info.id
                            err_file.google_drive_link = file_info.web_view_link
                            err_file.status = FileStatus.ERROR
                            err_file.error_message = error_msg
                            session.add(err_file)
                            await session.commit()
                        except Exception as dbe:
                            await session.rollback()
                            logger.error("Failed to record file error in DB: %s", dbe)

                        status_info.details.append({
                            "file": file_info.name,
                            "folder": file_info.parent_folder,
                            "action": "error",
                            "error": error_msg,
                        })

                # 3. Post-sync risk evaluation and alert updates
                try:
                    await alerts_engine.run_full_evaluation(company_id, session)
                    await session.commit()
                except Exception as ae:
                    await session.rollback()
                    raise RuntimeError(f"Не удалось пересчитать сводку: {ae}") from ae

                status_info.status = "idle"
                errors = [d for d in status_info.details if d.get("action") == "error"]
                if errors:
                    status_info.status = "error"
                    status_info.last_error = f"Не удалось импортировать файлов: {len(errors)}. {errors[0]['error']}"
                status_info.last_sync_time = datetime.now(timezone.utc)
                status_info.processed_files_count = processed
                status_info.skipped_files_count = skipped
                logger.info(
                    "Drive sync completed for company %s: %d processed, %d skipped",
                    company_id,
                    processed,
                    skipped,
                )

            except Exception as e:
                status_info.status = "error"
                status_info.last_error = str(e)
                logger.exception("Drive sync failed for company %s: %s", company_id, e)
            finally:
                if owns_session:
                    await session.close()

            return status_info.to_dict()


drive_sync_service = GoogleDriveSyncService()
