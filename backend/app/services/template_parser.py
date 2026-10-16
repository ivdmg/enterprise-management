import io
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import openpyxl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispatch import FleetDispatchRecord
from app.models.enums import (
    CashflowDirection,
    DomainCategory,
    ProjectRisk,
    TaskPriority,
    TaskStatus,
)
from app.models.finance import CashflowOperation
from app.models.procurement import ProcurementItem
from app.models.project import TenderProject
from app.models.task import OperationalTask

logger = logging.getLogger("enterprise_hub.template_parser")


def clean_decimal(value: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    """Robust conversion of numbers, currencies and messy strings to Decimal."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))

    # String cleanup
    clean_str = str(value).strip().replace(" ", "").replace("\xa0", "").replace("₽", "").replace("руб.", "").replace("руб", "")
    if not clean_str:
        return default

    # Handle thousands and decimal separators
    if "," in clean_str and "." in clean_str:
        if clean_str.find(",") < clean_str.find("."):
            clean_str = clean_str.replace(",", "")
        else:
            clean_str = clean_str.replace(".", "").replace(",", ".")
    elif "," in clean_str:
        clean_str = clean_str.replace(",", ".")

    clean_str = re.sub(r"[^0-9.-]", "", clean_str)
    if not clean_str or clean_str in ("-", "."):
        return default
    try:
        return Decimal(clean_str).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return default


def clean_date(value: Any) -> Optional[date]:
    """Robust conversion of Excel dates, datetime objects and string formats to date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    val_str = str(value).strip()
    if not val_str:
        return None

    # Try ISO YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val_str[:10], fmt).date()
        except ValueError:
            continue
    return None


class StandardTemplateParser:
    """
    Deterministic zero-LLM parser for the 5 standardized company Excel templates.
    Execution speed < 30ms per file using openpyxl in read_only/data_only mode.
    """

    @classmethod
    def detect_template_type(
        cls, filename: str, headers: Optional[Union[List[Any], bytes, str]] = None
    ) -> Optional[str]:
        """Identifies which of the 5 standard templates the file represents."""
        norm_name = filename.lower()
        if "тендер" in norm_name or "контракт" in norm_name:
            return "tender_registry"
        if "ддс" in norm_name or "касса" in norm_name or "взаиморасчет" in norm_name or "1c" in norm_name or "финанс" in norm_name:
            return "cashflow_sheet"
        if "закупок" in norm_name or "материал" in norm_name or "снабжен" in norm_name:
            return "procurement_sheet"
        if "диспетчер" in norm_name or "техник" in norm_name or "график" in norm_name:
            return "dispatch_sheet"
        if "задач" in norm_name or "алерт" in norm_name or "поручен" in norm_name:
            return "operational_tasks"

        # Check by headers signature
        if headers is not None:
            if isinstance(headers, (bytes, str)):
                h_str = str(headers).lower()
            else:
                h_str = " ".join([str(h) for h in headers if h is not None]).lower()

            if "номер_закупки" in h_str or "обеспечения_заявки" in h_str:
                return "tender_registry"
            if "статья_ддс" in h_str or "расчетный_счет" in h_str:
                return "cashflow_sheet"
            if "наименование_тмц" in h_str or "сумма_счета_руб" in h_str:
                return "procurement_sheet"
            if "тип_ресурса" in h_str or "наименование_единицы" in h_str:
                return "dispatch_sheet"
            if "ответственная_роль" in h_str or "крайний_срок" in h_str:
                return "operational_tasks"

        return None

    @classmethod
    def _read_rows(cls, file_source: Union[bytes, Path, str]) -> List[List[Any]]:
        """Reads rows from file source using ultrafast python-calamine (< 5ms) with openpyxl fallback."""
        try:
            import python_calamine
            if isinstance(file_source, bytes):
                wb = python_calamine.CalamineWorkbook.from_filelike(io.BytesIO(file_source))
            else:
                wb = python_calamine.CalamineWorkbook.from_path(str(file_source))
            return wb.get_sheet_by_index(0).to_python()
        except Exception as e:
            logger.debug("Falling back to openpyxl reader: %s", e)
            if isinstance(file_source, bytes):
                wb = openpyxl.load_workbook(io.BytesIO(file_source), read_only=True, data_only=True)
            else:
                wb = openpyxl.load_workbook(str(file_source), read_only=True, data_only=True)

            ws = wb.active
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            wb.close()
            return rows

    @classmethod
    async def parse_tender_registry(
        cls, file_source: Union[bytes, Path, str], company_id: Any, file_id: Optional[Any], db: AsyncSession
    ) -> int:
        """
        Parses Template 1: 01_Реестр_Тендеров_и_Контрактов.xlsx
        Columns: Номер_Закупки, Наименование_Объекта, Заказчик, Сумма_Контракта_Руб,
                 Сумма_Обеспечения_Заявки, Статус_Тендера, Дедлайн_Подачи, Дата_Окончания_Работ,
                 Сумма_Закрыто_КС_Руб, Оплачено_Заказчиком_Руб, Куратор_Ответственный, Банковская_Гарантия_До
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        header = [str(c or "").strip() for c in rows[0]]
        h_map = {name.lower(): idx for idx, name in enumerate(header)}

        # Pre-fetch existing projects in 1 single query to eliminate N+1 network latency
        existing_q = select(TenderProject).where(
            TenderProject.company_id == company_id,
            TenderProject.deleted_at.is_(None),
        )
        existing_projects = (await db.execute(existing_q)).scalars().all()
        existing_by_purchase = {p.purchase_number: p for p in existing_projects if p.purchase_number}
        existing_by_name = {p.project_name: p for p in existing_projects}

        inserted_or_updated = 0
        for r in rows[1:]:
            if not any(r):
                continue

            def get_col(field_variants: List[str]) -> Any:
                for variant in field_variants:
                    idx = h_map.get(variant.lower())
                    if idx is not None and idx < len(r):
                        return r[idx]
                return None

            purchase_number = str(get_col(["Номер_Закупки", "Номер"]) or "").strip() or None
            project_name = str(get_col(["Наименование_Объекта", "Объект"]) or "").strip()
            if not project_name:
                continue

            customer_name = str(get_col(["Заказчик", "Клиент"]) or "").strip() or None
            contract_sum = clean_decimal(get_col(["Сумма_Контракта_Руб", "Сумма_Контракта"]))
            app_guarantee = clean_decimal(get_col(["Сумма_Обеспечения_Заявки", "Обеспечение_Заявки"]))
            status_val = str(get_col(["Статус_Тендера", "Статус"]) or "Контракт").strip()
            sub_deadline = clean_date(get_col(["Дедлайн_Подачи", "Дедлайн"]))
            work_end = clean_date(get_col(["Дата_Окончания_Работ", "Срок_Работ"]))
            completed_sum = clean_decimal(get_col(["Сумма_Закрыто_КС_Руб", "Закрыто_КС"]))
            paid_sum = clean_decimal(get_col(["Оплачено_Заказчиком_Руб", "Оплачено"]))
            curator_name = str(get_col(["Куратор_Ответственный", "Куратор"]) or "").strip() or None
            bg_expiry = clean_date(get_col(["Банковская_Гарантия_До", "Срок_БГ"]))

            debt_sum = max(Decimal("0.00"), contract_sum - paid_sum)

            # O(1) in-memory lookup
            existing = existing_by_purchase.get(purchase_number) if purchase_number else existing_by_name.get(project_name)
            if existing:
                existing.file_id = file_id
                existing.project_name = project_name
                existing.customer_name = customer_name
                existing.contract_sum = contract_sum
                existing.application_guarantee_sum = app_guarantee
                existing.status = status_val
                existing.submission_deadline = sub_deadline
                existing.deadline_date = work_end
                existing.work_end_date = work_end
                existing.completed_sum = completed_sum
                existing.paid_sum = paid_sum
                existing.debt_sum = debt_sum
                existing.curator_name = curator_name
                existing.bank_guarantee_expiry = bg_expiry
            else:
                new_project = TenderProject(
                    company_id=company_id,
                    file_id=file_id,
                    purchase_number=purchase_number,
                    project_code=purchase_number,
                    project_name=project_name,
                    customer_name=customer_name,
                    contract_sum=contract_sum,
                    application_guarantee_sum=app_guarantee,
                    status=status_val,
                    submission_deadline=sub_deadline,
                    deadline_date=work_end,
                    work_end_date=work_end,
                    completed_sum=completed_sum,
                    paid_sum=paid_sum,
                    debt_sum=debt_sum,
                    curator_name=curator_name,
                    bank_guarantee_expiry=bg_expiry,
                    risk_level=ProjectRisk.NORMAL,
                )
                db.add(new_project)
                if purchase_number:
                    existing_by_purchase[purchase_number] = new_project
                existing_by_name[project_name] = new_project

            inserted_or_updated += 1

        return inserted_or_updated

    @classmethod
    async def parse_cashflow_sheet(
        cls, file_source: Union[bytes, Path, str], company_id: Any, file_id: Optional[Any], db: AsyncSession
    ) -> int:
        """
        Parses Template 2: 02_ДДС_Касса_и_Взаиморасчеты.xlsx
        Columns: Дата_Операции, Тип_Операции, Статья_ДДС, Контрагент, Сумма_Руб,
                 Статус_Платежа, Расчетный_Счет, Основание_Платежа
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        header = [str(c or "").strip() for c in rows[0]]
        h_map = {name.lower(): idx for idx, name in enumerate(header)}

        inserted_count = 0
        for r in rows[1:]:
            if not any(r):
                continue

            def get_col(field_variants: List[str]) -> Any:
                for variant in field_variants:
                    idx = h_map.get(variant.lower())
                    if idx is not None and idx < len(r):
                        return r[idx]
                return None

            op_date = clean_date(get_col(["Дата_Операции", "Дата"]))
            if not op_date:
                continue

            direction_raw = str(get_col(["Тип_Операции", "Тип"]) or "Поступление").strip()
            direction = (
                CashflowDirection.INCOMING
                if "поступл" in direction_raw.lower() or "приход" in direction_raw.lower()
                else CashflowDirection.OUTGOING
            )
            dds_article = str(get_col(["Статья_ДДС", "Статья"]) or "").strip() or None
            counterparty = str(get_col(["Контрагент", "Получатель"]) or "").strip() or None
            amount = clean_decimal(get_col(["Сумма_Руб", "Сумма"]))
            payment_status = str(get_col(["Статус_Платежа", "Статус"]) or "Факт_Исполнено").strip()
            account_name = str(get_col(["Расчетный_Счет", "Счет"]) or "").strip() or None
            payment_purpose = str(get_col(["Основание_Платежа", "Назначение", "Основание"]) or "").strip() or None

            is_paid = "факт" in payment_status.lower()
            actual_amount = amount if is_paid else Decimal("0.00")
            planned_amount = amount if not is_paid else Decimal("0.00")

            new_op = CashflowOperation(
                company_id=company_id,
                file_id=file_id,
                operation_date=op_date,
                payment_due_date=op_date,
                counterparty=counterparty,
                direction=direction,
                category=dds_article,
                dds_article=dds_article,
                amount=amount,
                actual_amount=actual_amount,
                planned_amount=planned_amount,
                payment_status=payment_status,
                is_paid=is_paid,
                account_name=account_name,
                payment_purpose=payment_purpose,
            )
            db.add(new_op)
            inserted_count += 1

        return inserted_count

    @classmethod
    async def parse_procurement_sheet(
        cls, file_source: Union[bytes, Path, str], company_id: Any, file_id: Optional[Any], db: AsyncSession
    ) -> int:
        """
        Parses Template 3: 03_План_Закупок_и_Материалов.xlsx
        Columns: Объект_Привязка, Наименование_ТМЦ, Количество_Ед, Единица_Изм,
                 Поставщик, Сумма_Счета_Руб, Статус_Снабжения, Срок_Доставки_Дедлайн
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        header = [str(c or "").strip() for c in rows[0]]
        h_map = {name.lower(): idx for idx, name in enumerate(header)}

        inserted_count = 0
        for r in rows[1:]:
            if not any(r):
                continue

            def get_col(field_variants: List[str]) -> Any:
                for variant in field_variants:
                    idx = h_map.get(variant.lower())
                    if idx is not None and idx < len(r):
                        return r[idx]
                return None

            project_name = str(get_col(["Объект_Привязка", "Объект"]) or "").strip()
            item_name = str(get_col(["Наименование_ТМЦ", "ТМЦ", "Товар"]) or "").strip()
            if not project_name or not item_name:
                continue

            quantity = clean_decimal(get_col(["Количество_Ед", "Количество"]), default=Decimal("1.000"))
            unit = str(get_col(["Единица_Изм", "Ед_Изм", "Единица"]) or "шт").strip()
            supplier = str(get_col(["Поставщик", "Контрагент"]) or "").strip() or None
            invoice_amount = clean_decimal(get_col(["Сумма_Счета_Руб", "Сумма_Счета", "Сумма"]))
            status_val = str(get_col(["Статус_Снабжения", "Статус"]) or "Заявка").strip()
            delivery_deadline = clean_date(get_col(["Срок_Доставки_Дедлайн", "Дедлайн_Доставки", "Срок"]))

            item = ProcurementItem(
                company_id=company_id,
                file_id=file_id,
                project_name=project_name,
                item_name=item_name,
                quantity=quantity,
                unit=unit,
                supplier=supplier,
                invoice_amount=invoice_amount,
                status=status_val,
                delivery_deadline=delivery_deadline,
            )
            db.add(item)
            inserted_count += 1

        return inserted_count

    @classmethod
    async def parse_dispatch_sheet(
        cls, file_source: Union[bytes, Path, str], company_id: Any, file_id: Optional[Any], db: AsyncSession
    ) -> int:
        """
        Parses Template 4: 04_Диспетчерский_График_и_Техника.xlsx
        Columns: Дата_Смены, Объект_Назначения, Тип_Ресурса, Наименование_Единицы,
                 Ответственный_Водитель_Бригадир, Статус_Работы, Замечания_Инциденты
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        header = [str(c or "").strip() for c in rows[0]]
        h_map = {name.lower(): idx for idx, name in enumerate(header)}

        inserted_count = 0
        for r in rows[1:]:
            if not any(r):
                continue

            def get_col(field_variants: List[str]) -> Any:
                for variant in field_variants:
                    idx = h_map.get(variant.lower())
                    if idx is not None and idx < len(r):
                        return r[idx]
                return None

            shift_date = clean_date(get_col(["Дата_Смены", "Дата"])) or date.today()
            target_object = str(get_col(["Объект_Назначения", "Объект"]) or "").strip()
            resource_type = str(get_col(["Тип_Ресурса", "Ресурс"]) or "Спецтехника").strip()
            unit_name = str(get_col(["Наименование_Единицы", "Единица", "Техника"]) or "").strip()
            if not target_object or not unit_name:
                continue

            responsible = str(get_col(["Ответственный_Водитель_Бригадир", "Ответственный"]) or "").strip() or None
            status_val = str(get_col(["Статус_Работы", "Статус"]) or "На_Объекте").strip()
            notes = str(get_col(["Замечания_Инциденты", "Замечания", "Инцидент"]) or "").strip() or None

            record = FleetDispatchRecord(
                company_id=company_id,
                file_id=file_id,
                shift_date=shift_date,
                target_object=target_object,
                resource_type=resource_type,
                unit_name=unit_name,
                responsible_person=responsible,
                status=status_val,
                incident_notes=notes,
            )
            db.add(record)
            inserted_count += 1

        return inserted_count

    @classmethod
    async def parse_operational_tasks(
        cls, file_source: Union[bytes, Path, str], company_id: Any, file_id: Optional[Any], db: AsyncSession
    ) -> int:
        """
        Parses Template 5: 05_Операционные_Задачи_и_Алерты.xlsx
        Columns: Заголовок_Задачи, Связанный_Контракт, Ответственная_Роль, ФИО_Исполнителя,
                 Крайний_Срок_Дедлайн, Приоритет_Срочность, Статус_Исполнения, Потенциальный_Штраф_Руб
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        header = [str(c or "").strip() for c in rows[0]]
        h_map = {name.lower(): idx for idx, name in enumerate(header)}

        inserted_count = 0
        for r in rows[1:]:
            if not any(r):
                continue

            def get_col(field_variants: List[str]) -> Any:
                for variant in field_variants:
                    idx = h_map.get(variant.lower())
                    if idx is not None and idx < len(r):
                        return r[idx]
                return None

            title = str(get_col(["Заголовок_Задачи", "Заголовок", "Задача"]) or "").strip()
            if not title:
                continue

            contract = str(get_col(["Связанный_Контракт", "Контракт"]) or "").strip() or None
            role = str(get_col(["Ответственная_Роль", "Роль"]) or "Менеджер").strip()
            person = str(get_col(["ФИО_Исполнителя", "Исполнитель"]) or "").strip() or None
            due_date = clean_date(get_col(["Крайний_Срок_Дедлайн", "Дедлайн", "Срок"]))
            priority_raw = str(get_col(["Приоритет_Срочность", "Приоритет"]) or "Обычный").strip()
            status_raw = str(get_col(["Статус_Исполнения", "Статус"]) or "В_Работе").strip()
            penalty = clean_decimal(get_col(["Потенциальный_Штраф_Руб", "Штраф"]))

            # Normalization to enums
            priority = TaskPriority.MEDIUM
            if "критическ" in priority_raw.lower() or "штраф" in priority_raw.lower():
                priority = TaskPriority.URGENT
            elif "высок" in priority_raw.lower():
                priority = TaskPriority.HIGH
            elif "низк" in priority_raw.lower():
                priority = TaskPriority.LOW

            status = TaskStatus.IN_PROGRESS
            if "проверк" in status_raw.lower() or "ожид" in status_raw.lower():
                status = TaskStatus.PENDING
            elif "закрыт" in status_raw.lower() or "выполн" in status_raw.lower():
                status = TaskStatus.COMPLETED

            task = OperationalTask(
                company_id=company_id,
                file_id=file_id,
                task_title=title,
                related_contract=contract,
                responsible_role=role,
                responsible_person=person,
                due_date=due_date,
                priority=priority,
                status=status,
                penalty_amount=penalty,
                estimated_penalty_amount=penalty,
            )
            db.add(task)
            inserted_count += 1

        return inserted_count

    @classmethod
    async def parse_and_persist(
        cls,
        file_source: Union[bytes, Path, str],
        filename: str,
        company_id: Any,
        file_id: Optional[Any],
        db: AsyncSession,
    ) -> Tuple[str, int]:
        """Auto-detects template and parses records directly into database session."""
        # Read header row for detection
        rows = cls._read_rows(file_source)
        headers = [str(c or "").strip() for c in rows[0]] if rows else []
        
        tpl_type = cls.detect_template_type(filename, headers)
        if not tpl_type:
            logger.warning("Unrecognized template structure for file: %s", filename)
            return ("unknown", 0)

        count = 0
        if tpl_type == "tender_registry":
            count = await cls.parse_tender_registry(file_source, company_id, file_id, db)
        elif tpl_type == "cashflow_sheet":
            count = await cls.parse_cashflow_sheet(file_source, company_id, file_id, db)
        elif tpl_type == "procurement_sheet":
            count = await cls.parse_procurement_sheet(file_source, company_id, file_id, db)
        elif tpl_type == "dispatch_sheet":
            count = await cls.parse_dispatch_sheet(file_source, company_id, file_id, db)
        elif tpl_type == "operational_tasks":
            count = await cls.parse_operational_tasks(file_source, company_id, file_id, db)

        logger.info("Parsed %d records from template '%s' (file: %s)", count, tpl_type, filename)
        return (tpl_type, count)


standard_template_parser = StandardTemplateParser()
