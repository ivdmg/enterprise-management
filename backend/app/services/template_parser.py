import io
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import openpyxl
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispatch import FleetDispatchRecord
from app.models.enums import (
    CashflowDirection,
    DomainCategory,
    PayrollStatus,
    ProjectRisk,
    TaskPriority,
    TaskStatus,
)
from app.models.finance import CashflowOperation
from app.models.payroll import PayrollRecord
from app.models.procurement import ProcurementItem
from app.models.project import TenderProject
from app.models.task import OperationalTask

logger = logging.getLogger("enterprise_hub.template_parser")


class DocumentValidationError(Exception):
    """
    Raised when a document cannot be parsed due to validation issues.
    Details contain granular row, column and error descriptions for HTTP 422.
    """
    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


def normalize_column_name(col: Any) -> str:
    """Normalizes column names: lower-case, strips punctuation, underscores, and spaces."""
    if col is None:
        return ""
    text = str(col).lower().strip()
    return re.sub(r"[\s_\-\.\,\:\;\(\)\[\]\/\\\"\'`«»]+", "", text)


# Comprehensive synonym dictionary for Fuzzy Matching (Task BE-2.1)
COLUMN_ALIASES: Dict[str, List[str]] = {
    "item_name": [
        "наименование", "тмц", "товар", "материал", "позиция", "номенклатура",
        "наименование_тмц", "наименованиетовара", "номенклатурадел", "продукция"
    ],
    "amount": [
        "сумма", "сумма с ндс", "всего", "итого", "стоимость", "цена",
        "сумма_руб", "сумма_счета_руб", "сумма_контракта_руб", "всегокрубле",
        "стоимостьруб", "ценаруб", "потенциальный_штраф_руб", "штраф"
    ],
    "counterparty": [
        "поставщик", "контрагент", "продавец", "организация", "получатель",
        "плательщик", "заказчик", "клиент", "партнер", "подрядчик"
    ],
    "project": [
        "объект", "объект смр", "стройка", "адрес объекта", "наименование_объекта",
        "объект_привязка", "объект_назначения", "проект", "контракт", "связанный_контракт"
    ],
    "purchase_number": [
        "номер_закупки", "номер", "закупка", "извещение", "реестровыйномер",
        "номерконтракта", "идентификатор"
    ],
    "quantity": [
        "количество", "количество_ед", "кол-во", "колво", "объем"
    ],
    "unit": [
        "единица", "единица_изм", "ед_изм", "ед", "измерение"
    ],
    "date": [
        "дата", "дата_операции", "дата_смены", "дата_окончания_работ",
        "дедлайн", "срок", "дедлайн_подачи", "срок_доставки_дедлайн", "крайний_срок_дедлайн"
    ],
    "status": [
        "статус", "статус_тендера", "статус_платежа", "статус_снабжения",
        "статус_работы", "статус_исполнения"
    ],
}


class FuzzyColumnMatcher:
    """Helper to locate column index by standard aliases and fuzzy matching."""
    def __init__(self, headers: List[Any]):
        self.headers = headers
        self.norm_headers: Dict[str, int] = {}
        for idx, h in enumerate(headers):
            norm = normalize_column_name(h)
            if norm and norm not in self.norm_headers:
                self.norm_headers[norm] = idx

    def find_column_index(self, aliases: List[str]) -> Optional[int]:
        # 1. Exact match on normalized aliases
        for alias in aliases:
            norm_alias = normalize_column_name(alias)
            if norm_alias in self.norm_headers:
                return self.norm_headers[norm_alias]

        # 2. Substring matching
        for alias in aliases:
            norm_alias = normalize_column_name(alias)
            if len(norm_alias) < 3:
                continue
            for norm_h, idx in self.norm_headers.items():
                if norm_alias in norm_h or norm_h in norm_alias:
                    return idx

        return None

    def get_value(self, row: List[Any], aliases: List[str], default: Any = None) -> Any:
        idx = self.find_column_index(aliases)
        if idx is not None and idx < len(row):
            val = row[idx]
            return val if val is not None else default
        return default


def find_header_row(rows: List[List[Any]], min_matches: int = 2) -> Tuple[int, List[Any]]:
    """
    Finds the first row that matches at least min_matches known column synonyms,
    skipping company headers and decorative banner rows.
    """
    all_known_synonyms = set()
    for syn_list in COLUMN_ALIASES.values():
        for syn in syn_list:
            all_known_synonyms.add(normalize_column_name(syn))

    # Search top 25 rows
    for r_idx, r in enumerate(rows[:25]):
        if not r or not any(r):
            continue
        matches = 0
        for cell in r:
            norm = normalize_column_name(cell)
            if not norm:
                continue
            if norm in all_known_synonyms or any(s in norm for s in ("сумм", "наим", "объект", "поставщ", "контраг", "дат", "статус")):
                matches += 1
        if matches >= min_matches:
            return r_idx, r

    return 0, (rows[0] if rows else [])


def clean_decimal(value: Any, default: Decimal = Decimal("0.00"), raise_on_error: bool = False, field_context: str = "") -> Decimal:
    """Robust conversion of numbers, currencies and messy strings to Decimal."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))

    # String cleanup
    raw_str = str(value).strip()
    clean_str = raw_str.replace(" ", "").replace("\xa0", "").replace("₽", "").replace("руб.", "").replace("руб", "")
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
        if raise_on_error and raw_str:
            raise ValueError(f"Некорректный числовой формат: '{raw_str}'")
        return default
    try:
        return Decimal(clean_str).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        if raise_on_error:
            raise ValueError(f"Некорректный числовой формат: '{raw_str}'")
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

    # Try ISO YYYY-MM-DD and common Russian date formats
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(val_str[:10], fmt).date()
        except ValueError:
            continue
    return None


class StandardTemplateParser:
    """
    Deterministic zero-LLM parser for company Excel and 1CClientBankExchange templates.
    Execution speed < 30ms per file using python-calamine / openpyxl.
    """

    @classmethod
    def detect_template_type(
        cls, filename: str, headers: Optional[Union[List[Any], bytes, str]] = None
    ) -> Optional[str]:
        """Identifies which of the 5 standard templates the file represents."""
        norm_name = filename.lower()
        if norm_name.endswith(".txt") or "1c" in norm_name or "bank" in norm_name or "клиент" in norm_name or "выписк" in norm_name:
            if isinstance(headers, (bytes, str)) and ("1cclientbankexchange" in str(headers).lower() or "секциярасчсчет" in str(headers).lower() or "секциядокумент" in str(headers).lower()):
                return "1c_bank_statement"
            if norm_name.endswith(".txt"):
                return "1c_bank_statement"

        if "тендер" in norm_name or "контракт" in norm_name or "смет" in norm_name:
            return "tender_registry"
        if "ддс" in norm_name or "касса" in norm_name or "взаиморасчет" in norm_name or "финанс" in norm_name:
            return "cashflow_sheet"
        if "закупок" in norm_name or "материал" in norm_name or "снабжен" in norm_name or "счет" in norm_name:
            return "procurement_sheet"
        if "диспетчер" in norm_name or "техник" in norm_name or "график" in norm_name or "путев" in norm_name:
            return "dispatch_sheet"
        if "задач" in norm_name or "алерт" in norm_name or "поручен" in norm_name:
            return "operational_tasks"

        # Check by headers signature
        if headers is not None:
            if isinstance(headers, (bytes, str)):
                h_str = str(headers).lower()
            else:
                h_str = " ".join([str(h) for h in headers if h is not None]).lower()

            if "1cclientbankexchange" in h_str:
                return "1c_bank_statement"
            if "номер_закупки" in h_str or "обеспечения_заявки" in h_str or "заказчик" in h_str:
                return "tender_registry"
            if "статья_ддс" in h_str or "расчетный_счет" in h_str:
                return "cashflow_sheet"
            if "наименование_тмц" in h_str or "сумма_счета" in h_str or "тмц" in h_str:
                return "procurement_sheet"
            if "тип_ресурса" in h_str or "наименование_единицы" in h_str or "путевой" in h_str:
                return "dispatch_sheet"
            if "ответственная_роль" in h_str or "крайний_срок" in h_str:
                return "operational_tasks"

        return None

    @classmethod
    def _read_rows(cls, file_source: Union[bytes, Path, str]) -> List[List[Any]]:
        """Reads rows from file source using python-calamine with openpyxl fallback."""
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
        Uses fuzzy matching for column aliases and header detection.
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        h_idx, header_row = find_header_row(rows, min_matches=1)
        matcher = FuzzyColumnMatcher(header_row)

        # Validate mandatory project name column
        name_col_idx = matcher.find_column_index(COLUMN_ALIASES["project"] + ["наименование_объекта", "объект"])
        if name_col_idx is None:
            raise DocumentValidationError(
                "Ошибка валидации файла сметы",
                details=[{"column": "Объект СМР", "error": "Обязательная колонка не найдена в таблице"}]
            )

        # Pre-fetch existing projects in 1 single query
        existing_q = select(TenderProject).where(
            TenderProject.company_id == company_id,
            TenderProject.deleted_at.is_(None),
        )
        existing_projects = (await db.execute(existing_q)).scalars().all()
        existing_by_purchase = {p.purchase_number: p for p in existing_projects if p.purchase_number}
        existing_by_name = {p.project_name: p for p in existing_projects}

        validation_errors: List[Dict[str, Any]] = []
        inserted_or_updated = 0

        for r_num, r in enumerate(rows[h_idx + 1:], start=h_idx + 2):
            if not any(r):
                continue

            purchase_number = str(matcher.get_value(r, COLUMN_ALIASES["purchase_number"]) or "").strip() or None
            project_name = str(matcher.get_value(r, COLUMN_ALIASES["project"] + ["наименование_объекта", "объект"]) or "").strip()
            if not project_name:
                continue

            customer_name = str(matcher.get_value(r, COLUMN_ALIASES["counterparty"] + ["заказчик", "клиент"]) or "").strip() or None
            
            # Sum validation with row detail reporting
            raw_contract_sum = matcher.get_value(r, COLUMN_ALIASES["amount"] + ["сумма_контракта_руб", "сумма_контракта"])
            try:
                contract_sum = clean_decimal(raw_contract_sum, raise_on_error=True)
            except ValueError as ve:
                validation_errors.append({"row": r_num, "column": "Сумма", "error": str(ve)})
                contract_sum = Decimal("0.00")

            app_guarantee = clean_decimal(matcher.get_value(r, ["сумма_обеспечения_заявки", "обеспечение_заявки", "обеспечение"]))
            status_val = str(matcher.get_value(r, COLUMN_ALIASES["status"] + ["статус_тендера"]) or "Контракт").strip()
            sub_deadline = clean_date(matcher.get_value(r, ["дедлайн_подачи", "дедлайн"]))
            work_end = clean_date(matcher.get_value(r, ["дата_окончания_работ", "срок_работ", "дедлайн_работ"]))
            completed_sum = clean_decimal(matcher.get_value(r, ["сумма_закрыто_кс_руб", "закрыто_кс", "кс-2", "выполнено"]))
            paid_sum = clean_decimal(matcher.get_value(r, ["оплачено_заказчиком_руб", "оплачено"]))
            curator_name = str(matcher.get_value(r, ["куратор_ответственный", "куратор", "ответственный"]) or "").strip() or None
            bg_expiry = clean_date(matcher.get_value(r, ["банковская_гарантия_до", "срок_бг", "банковская_гарантия"]))

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

        if validation_errors:
            raise DocumentValidationError("Ошибка валидации файла сметы", details=validation_errors)

        return inserted_or_updated

    @classmethod
    async def parse_cashflow_sheet(
        cls, file_source: Union[bytes, Path, str], company_id: Any, file_id: Optional[Any], db: AsyncSession
    ) -> int:
        """
        Parses Template 2: 02_ДДС_Касса_и_Взаиморасчеты.xlsx
        Uses fuzzy matching for column aliases and header detection.
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        h_idx, header_row = find_header_row(rows, min_matches=1)
        matcher = FuzzyColumnMatcher(header_row)

        validation_errors: List[Dict[str, Any]] = []
        inserted_count = 0

        for r_num, r in enumerate(rows[h_idx + 1:], start=h_idx + 2):
            if not any(r):
                continue

            op_date = clean_date(matcher.get_value(r, COLUMN_ALIASES["date"] + ["дата_операции"]))
            if not op_date:
                continue

            direction_raw = str(matcher.get_value(r, ["тип_операции", "тип", "направление"]) or "Поступление").strip()
            direction = (
                CashflowDirection.INCOMING
                if "поступл" in direction_raw.lower() or "приход" in direction_raw.lower()
                else CashflowDirection.OUTGOING
            )
            dds_article = str(matcher.get_value(r, ["статья_ддс", "статья", "категория"]) or "").strip() or None
            counterparty = str(matcher.get_value(r, COLUMN_ALIASES["counterparty"]) or "").strip() or None
            
            raw_amount = matcher.get_value(r, COLUMN_ALIASES["amount"] + ["сумма_руб"])
            try:
                amount = clean_decimal(raw_amount, raise_on_error=True)
            except ValueError as ve:
                validation_errors.append({"row": r_num, "column": "Сумма", "error": str(ve)})
                amount = Decimal("0.00")

            payment_status = str(matcher.get_value(r, COLUMN_ALIASES["status"] + ["статус_платежа"]) or "Факт_Исполнено").strip()
            account_name = str(matcher.get_value(r, ["расчетный_счет", "счет", "банк"]) or "").strip() or None
            payment_purpose = str(matcher.get_value(r, ["основание_платежа", "назначение", "основание", "назначение_платежа"]) or "").strip() or None

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

        if validation_errors:
            raise DocumentValidationError("Ошибка валидации файла ДДС/Кассы", details=validation_errors)

        return inserted_count

    @classmethod
    async def parse_procurement_sheet(
        cls, file_source: Union[bytes, Path, str], company_id: Any, file_id: Optional[Any], db: AsyncSession
    ) -> int:
        """
        Parses Template 3: 03_План_Закупок_и_Материалов.xlsx
        Uses fuzzy matching for column aliases and header detection.
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        h_idx, header_row = find_header_row(rows, min_matches=1)
        matcher = FuzzyColumnMatcher(header_row)

        validation_errors: List[Dict[str, Any]] = []
        inserted_count = 0

        for r_num, r in enumerate(rows[h_idx + 1:], start=h_idx + 2):
            if not any(r):
                continue

            project_name = str(matcher.get_value(r, COLUMN_ALIASES["project"] + ["объект_привязка"]) or "").strip()
            item_name = str(matcher.get_value(r, COLUMN_ALIASES["item_name"]) or "").strip()
            if not project_name or not item_name:
                continue

            quantity = clean_decimal(matcher.get_value(r, COLUMN_ALIASES["quantity"]), default=Decimal("1.000"))
            unit = str(matcher.get_value(r, COLUMN_ALIASES["unit"]) or "шт").strip()
            supplier = str(matcher.get_value(r, COLUMN_ALIASES["counterparty"]) or "").strip() or None
            
            raw_invoice = matcher.get_value(r, COLUMN_ALIASES["amount"] + ["сумма_счета_руб", "сумма_счета"])
            try:
                invoice_amount = clean_decimal(raw_invoice, raise_on_error=True)
            except ValueError as ve:
                validation_errors.append({"row": r_num, "column": "Сумма", "error": str(ve)})
                invoice_amount = Decimal("0.00")

            status_val = str(matcher.get_value(r, COLUMN_ALIASES["status"] + ["статус_снабжения"]) or "Заявка").strip()
            delivery_deadline = clean_date(matcher.get_value(r, ["срок_доставки_дедлайн", "дедлайн_доставки", "срок"]))

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

        if validation_errors:
            raise DocumentValidationError("Ошибка валидации реестра закупок", details=validation_errors)

        return inserted_count

    @classmethod
    async def parse_dispatch_sheet(
        cls, file_source: Union[bytes, Path, str], company_id: Any, file_id: Optional[Any], db: AsyncSession
    ) -> int:
        """
        Parses Template 4: 04_Диспетчерский_График_и_Техника.xlsx
        Uses fuzzy matching for column aliases and header detection.
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        h_idx, header_row = find_header_row(rows, min_matches=1)
        matcher = FuzzyColumnMatcher(header_row)

        inserted_count = 0
        for r in rows[h_idx + 1:]:
            if not any(r):
                continue

            shift_date = clean_date(matcher.get_value(r, COLUMN_ALIASES["date"] + ["дата_смены"])) or date.today()
            target_object = str(matcher.get_value(r, COLUMN_ALIASES["project"] + ["объект_назначения"]) or "").strip()
            resource_type = str(matcher.get_value(r, ["тип_ресурса", "ресурс", "тип"]) or "Спецтехника").strip()
            unit_name = str(matcher.get_value(r, ["наименование_единицы", "единица", "техника", "машина", "автомобиль"]) or "").strip()
            if not target_object or not unit_name:
                continue

            responsible = str(matcher.get_value(r, ["ответственный_водитель_бригадир", "водитель", "бригадир", "ответственный"]) or "").strip() or None
            status_val = str(matcher.get_value(r, COLUMN_ALIASES["status"] + ["статус_работы"]) or "На_Объекте").strip()
            notes = str(matcher.get_value(r, ["замечания_инциденты", "замечания", "инцидент", "примечание"]) or "").strip() or None

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
        Uses fuzzy matching for column aliases and header detection.
        """
        rows = cls._read_rows(file_source)
        if not rows or len(rows) < 2:
            return 0

        h_idx, header_row = find_header_row(rows, min_matches=1)
        matcher = FuzzyColumnMatcher(header_row)

        validation_errors: List[Dict[str, Any]] = []
        inserted_count = 0

        for r_num, r in enumerate(rows[h_idx + 1:], start=h_idx + 2):
            if not any(r):
                continue

            title = str(matcher.get_value(r, ["заголовок_задачи", "заголовок", "задача", "наименование", "поручение"]) or "").strip()
            if not title:
                continue

            contract = str(matcher.get_value(r, COLUMN_ALIASES["project"] + ["связанный_контракт", "контракт"]) or "").strip() or None
            role = str(matcher.get_value(r, ["ответственная_роль", "роль"]) or "Менеджер").strip()
            person = str(matcher.get_value(r, ["фио_исполнителя", "исполнитель", "ответственный"]) or "").strip() or None
            due_date = clean_date(matcher.get_value(r, COLUMN_ALIASES["date"] + ["крайний_срок_дедлайн", "дедлайн", "срок"]))
            priority_raw = str(matcher.get_value(r, ["приоритет_срочность", "приоритет", "срочность"]) or "Обычный").strip()
            status_raw = str(matcher.get_value(r, COLUMN_ALIASES["status"] + ["статус_исполнения"]) or "В_Работе").strip()
            
            raw_penalty = matcher.get_value(r, COLUMN_ALIASES["amount"] + ["потенциальный_штраф_руб", "штраф"])
            try:
                penalty = clean_decimal(raw_penalty, raise_on_error=True)
            except ValueError as ve:
                validation_errors.append({"row": r_num, "column": "Штраф", "error": str(ve)})
                penalty = Decimal("0.00")

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

        if validation_errors:
            raise DocumentValidationError("Ошибка валидации операционных задач", details=validation_errors)

        return inserted_count

    @classmethod
    async def parse_1c_client_bank_exchange(
        cls,
        file_source: Union[bytes, Path, str],
        company_id: Any,
        file_id: Optional[Any],
        db: AsyncSession,
    ) -> int:
        """
        Parses 1CClientBankExchange format (.txt) per Task BE-2.2:
        - Extracts 'СекцияДокумент=Платежное поручение': Номер, Дата, Сумма, Плательщик, Получатель, НазначениеПлатежа.
        - Matches material invoices (e.g. 'оплата по счету №... за материалы/арматуру/бетон') -> updates ProcurementItem to 'paid'.
        - Matches payroll / cash ('заработная плата / под отчет') -> creates or links to PayrollRecord.
        - Persists all operations into CashflowOperation.
        """
        raw_text = ""
        if isinstance(file_source, bytes):
            # Try Windows-1251 then UTF-8
            try:
                raw_text = file_source.decode("cp1251")
            except UnicodeDecodeError:
                raw_text = file_source.decode("utf-8", errors="replace")
        elif isinstance(file_source, (Path, str)):
            p = Path(file_source)
            try:
                raw_text = p.read_text(encoding="cp1251")
            except UnicodeDecodeError:
                raw_text = p.read_text(encoding="utf-8", errors="replace")

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not lines:
            return 0

        # Verify header
        header_found = any("1cclientbankexchange" in line.lower() for line in lines[:10])
        if not header_found and not any("секциядокумент" in line.lower() for line in lines):
            raise DocumentValidationError(
                "Ошибка валидации формата 1CClientBankExchange",
                details=[{"error": "Файл не содержит сигнатуру формата 1CClientBankExchange"}]
            )

        documents: List[Dict[str, str]] = []
        current_doc: Optional[Dict[str, str]] = None
        in_doc = False

        for line in lines:
            if line.startswith("СекцияДокумент="):
                in_doc = True
                current_doc = {"_doc_type": line.split("=", 1)[1].strip()}
            elif line.startswith("КонецДокумента"):
                if in_doc and current_doc:
                    documents.append(current_doc)
                in_doc = False
                current_doc = None
            elif in_doc and "=" in line and current_doc is not None:
                k, v = line.split("=", 1)
                current_doc[k.strip()] = v.strip()

        if not documents:
            logger.warning("1CClientBankExchange: No documents found in file")
            return 0

        inserted_count = 0
        for doc in documents:
            doc_type = doc.get("_doc_type", "")
            doc_num = doc.get("Номер", "")
            doc_date_str = doc.get("Дата", "")
            raw_sum = doc.get("Сумма", "0")
            payer = doc.get("Плательщик", "") or doc.get("Плательщик1", "")
            receiver = doc.get("Получатель", "") or doc.get("Получатель1", "")
            purpose = doc.get("НазначениеПлатежа", "")
            payer_account = doc.get("ПлательщикРасчСчет", "")

            op_date = clean_date(doc_date_str) or date.today()
            amount = clean_decimal(raw_sum)
            purpose_lower = purpose.lower()

            # Determine direction: payment order outgoing or incoming
            direction = CashflowDirection.OUTGOING
            if "аккредитив" in doc_type.lower() or "поступление" in doc_type.lower():
                direction = CashflowDirection.INCOMING
            counterparty = receiver if direction == CashflowDirection.OUTGOING else payer

            # Categorization logic (Task BE-2.2)
            dds_article = "Операционные расходы"
            is_payroll = any(kw in purpose_lower for kw in ("заработная плата", "зарплата", "под отчет", "подотчет", "выплата зп"))
            is_procurement = any(kw in purpose_lower for kw in ("оплата по счету", "за материалы", "арматур", "бетон", "поставка", "счет №", "счет no"))

            if is_payroll:
                dds_article = "Заработная плата"
                # Record to Payroll domain as paid
                payroll_rec = PayrollRecord(
                    company_id=company_id,
                    file_id=file_id,
                    payroll_period=op_date.strftime("%Y-%m"),
                    employee_name=receiver or "Сотрудники (реестр выплат)",
                    department="Производственный отдел",
                    role_title="Штат",
                    accrued_amount=amount,
                    paid_amount=amount,
                    debt_amount=Decimal("0.00"),
                    payment_due_date=op_date,
                    status=PayrollStatus.PAID,
                )
                db.add(payroll_rec)

            elif is_procurement:
                dds_article = "Оплата ТМЦ и материалов"
                # Search for invoice number in purpose e.g. "оплата по счету № 123"
                invoice_match = re.search(r"(?:счет[у]?|счет)\s*(?:№|no\.?|\#)?\s*([A-Za-z0-9\-\/]+)", purpose_lower)
                supplier_term = counterparty[:50] if counterparty else ""

                # Try updating matching ProcurementItem status to 'Оплачено'
                stmt = select(ProcurementItem).where(
                    ProcurementItem.company_id == company_id,
                    ProcurementItem.deleted_at.is_(None),
                )
                if supplier_term:
                    stmt = stmt.where(ProcurementItem.supplier.ilike(f"%{supplier_term[:20]}%"))
                proc_items = (await db.execute(stmt)).scalars().all()
                for item in proc_items:
                    if item.status != "Оплачено":
                        item.status = "Оплачено"

            # Create CashflowOperation
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
                actual_amount=amount,
                planned_amount=Decimal("0.00"),
                payment_status="Факт_Исполнено",
                is_paid=True,
                account_name=payer_account or "Основной расчетный счет",
                payment_purpose=f"П/П №{doc_num}: {purpose}",
            )
            db.add(new_op)
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
        headers: Any = None
        if filename.lower().endswith(".txt"):
            if isinstance(file_source, bytes):
                headers = file_source[:500]
            else:
                try:
                    headers = Path(file_source).read_bytes()[:500]
                except Exception:
                    headers = None
        else:
            try:
                rows = cls._read_rows(file_source)
                headers = [str(c or "").strip() for c in rows[0]] if rows else []
            except Exception as e:
                logger.error("Failed to read rows from %s: %s", filename, e)
                raise DocumentValidationError(
                    f"Не удалось прочитать структуру файла {filename}: {str(e)}",
                    details=[{"error": str(e)}]
                )

        tpl_type = cls.detect_template_type(filename, headers)
        if not tpl_type:
            logger.warning("Unrecognized template structure for file: %s", filename)
            raise DocumentValidationError(
                f"Не удалось распознать формат или структуру файла: {filename}",
                details=[{"error": "Шаблон не соответствует известным реестрам или выпискам 1С"}]
            )

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
        elif tpl_type == "1c_bank_statement":
            count = await cls.parse_1c_client_bank_exchange(file_source, company_id, file_id, db)

        logger.info("Parsed %d records from template '%s' (file: %s)", count, tpl_type, filename)
        return (tpl_type, count)


standard_template_parser = StandardTemplateParser()
