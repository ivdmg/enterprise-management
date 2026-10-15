import io
import time
import uuid
from decimal import Decimal
from pathlib import Path
import pytest

from app.core.database import async_session_factory
from app.models.company import Company
from app.models.dispatch import FleetDispatchRecord
from app.models.finance import CashflowOperation
from app.models.procurement import ProcurementItem
from app.models.project import TenderProject
from app.models.task import OperationalTask
from app.services.template_parser import (
    StandardTemplateParser,
    clean_date,
    clean_decimal,
    standard_template_parser,
)
from sqlalchemy import select


def test_clean_decimal_utility():
    """Validates robust parsing of messy Russian currency and numeric values."""
    assert clean_decimal("1 500 000 руб.") == Decimal("1500000.00")
    assert clean_decimal("250 450,50 ₽") == Decimal("250450.50")
    assert clean_decimal("12,345.67") == Decimal("12345.67")
    assert clean_decimal(150000) == Decimal("150000.00")
    assert clean_decimal(15.99) == Decimal("15.99")
    assert clean_decimal(None, default=Decimal("0.00")) == Decimal("0.00")
    assert clean_decimal("", default=Decimal("0.00")) == Decimal("0.00")


def test_clean_date_utility():
    """Validates parsing of dates in ISO and DD.MM.YYYY formats."""
    from datetime import date
    assert clean_date("2026-10-15") == date(2026, 10, 15)
    assert clean_date("15.10.2026") == date(2026, 10, 15)
    assert clean_date(date(2026, 5, 20)) == date(2026, 5, 20)
    assert clean_date(None) is None
    assert clean_date("invalid") is None


def test_detect_template_types():
    """Validates 100% accurate template type detection by file name and headers."""
    parser = StandardTemplateParser()
    assert parser.detect_template_type("01_Реестр_Тендеров_и_Контрактов.xlsx", []) == "tender_registry"
    assert parser.detect_template_type("02_ДДС_Касса_и_Взаиморасчеты.xlsx", []) == "cashflow_sheet"
    assert parser.detect_template_type("03_План_Закупок_и_Материалов.xlsx", []) == "procurement_sheet"
    assert parser.detect_template_type("04_Диспетчерский_График_и_Техника.xlsx", []) == "dispatch_sheet"
    assert parser.detect_template_type("05_Операционные_Задачи_и_Алерты.xlsx", []) == "operational_tasks"

    # Header-based detection fallback
    assert parser.detect_template_type("unknown.xlsx", ["Номер_Закупки", "Сумма_Контракта_Руб"]) == "tender_registry"
    assert parser.detect_template_type("unknown.xlsx", ["Статья_ДДС", "Расчетный_Счет"]) == "cashflow_sheet"
    assert parser.detect_template_type("unknown.xlsx", ["Наименование_ТМЦ", "Сумма_Счета_Руб"]) == "procurement_sheet"
    assert parser.detect_template_type("unknown.xlsx", ["Тип_Ресурса", "Наименование_Единицы"]) == "dispatch_sheet"
    assert parser.detect_template_type("unknown.xlsx", ["Ответственная_Роль", "Крайний_Срок_Дедлайн"]) == "operational_tasks"


def test_parsing_speed_strictly_under_30ms():
    """Validates that python-calamine parses each template in strictly < 30ms."""
    mock_dir = Path(__file__).resolve().parent.parent.parent / "storage" / "mock_drive"
    files = [f for f in mock_dir.rglob("*.xlsx") if f.name.startswith("0") and not f.name.startswith("~$")]
    assert len(files) >= 5
    for f in files:
        t0 = time.perf_counter()
        rows = standard_template_parser._read_rows(f)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert len(rows) >= 20
        assert elapsed_ms < 30, f"File {f.name} took {elapsed_ms:.2f} ms (expected < 30 ms)"


@pytest.mark.asyncio
async def test_parse_all_5_templates_speed_and_persistence():
    """
    Validates end-to-end parsing of all 5 standard Excel templates:
    1. Data correctly maps to SQLAlchemy models and persists into PostgreSQL.
    2. Upsert properly updates existing records without duplicate key crashes.
    """
    from sqlalchemy.pool import NullPool
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings

    test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    mock_dir = Path(__file__).resolve().parent.parent.parent / "storage" / "mock_drive"
    assert mock_dir.exists(), f"Mock drive not found at {mock_dir}"

    async with test_session_factory() as session:
        # Create isolated test tenant company
        company = Company(
            id=uuid.uuid4(),
            name=f"Template Test Company {uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        session.add(company)
        await session.commit()
        company_id = company.id

        try:
            # 1. Template 1: Tenders & Contracts
            f1 = mock_dir / "01_Реестры_Тендеров" / "01_Реестр_Тендеров_и_Контрактов.xlsx"
            count1 = await standard_template_parser.parse_tender_registry(f1, company_id, None, session)
            await session.commit()
            assert count1 >= 20, f"Expected >= 20 tenders, got {count1}"

            # Check upsert on duplicate purchase_number
            tenders = (await session.execute(select(TenderProject).where(TenderProject.company_id == company_id))).scalars().all()
            assert len(tenders) == count1
            first_tender = tenders[0]
            assert first_tender.contract_sum > Decimal("0.00")
            assert first_tender.purchase_number is not None

            # Re-parse to verify upsert
            recount1 = await standard_template_parser.parse_tender_registry(f1, company_id, None, session)
            await session.commit()
            assert recount1 == count1
            tenders_after = (await session.execute(select(TenderProject).where(TenderProject.company_id == company_id))).scalars().all()
            assert len(tenders_after) == count1, "Upsert should update existing records without creating duplicates"

            # 2. Template 2: Cashflow (ДДС)
            f2 = mock_dir / "02_Финансы_и_1С" / "02_ДДС_Касса_и_Взаиморасчеты.xlsx"
            t0 = time.perf_counter()
            count2 = await standard_template_parser.parse_cashflow_sheet(f2, company_id, None, session)
            t1 = time.perf_counter()
            await session.commit()
            elapsed_ms2 = (t1 - t0) * 1000
            assert count2 >= 20, f"Expected >= 20 cashflow records, got {count2}"
            assert elapsed_ms2 < 50, f"Parse too slow: {elapsed_ms2:.2f} ms"

            cashflows = (await session.execute(select(CashflowOperation).where(CashflowOperation.company_id == company_id))).scalars().all()
            assert len(cashflows) == count2
            sample_cf = cashflows[0]
            assert sample_cf.amount > Decimal("0.00")
            assert sample_cf.dds_article is not None

            # 3. Template 3: Procurement & Materials (Закупки)
            f3 = mock_dir / "03_Снабжение_и_Закупки" / "03_План_Закупок_и_Материалов.xlsx"
            t0 = time.perf_counter()
            count3 = await standard_template_parser.parse_procurement_sheet(f3, company_id, None, session)
            t1 = time.perf_counter()
            await session.commit()
            elapsed_ms3 = (t1 - t0) * 1000
            assert count3 >= 20, f"Expected >= 20 procurement items, got {count3}"
            assert elapsed_ms3 < 50, f"Parse too slow: {elapsed_ms3:.2f} ms"

            items = (await session.execute(select(ProcurementItem).where(ProcurementItem.company_id == company_id))).scalars().all()
            assert len(items) == count3
            sample_item = items[0]
            assert sample_item.project_name is not None
            assert sample_item.item_name is not None
            assert sample_item.invoice_amount > Decimal("0.00")

            # 4. Template 4: Fleet & Machinery Dispatch (Диспетчеризация)
            f4 = mock_dir / "04_ПТО_и_Объекты" / "04_Диспетчерский_График_и_Техника.xlsx"
            t0 = time.perf_counter()
            count4 = await standard_template_parser.parse_dispatch_sheet(f4, company_id, None, session)
            t1 = time.perf_counter()
            await session.commit()
            elapsed_ms4 = (t1 - t0) * 1000
            assert count4 >= 20, f"Expected >= 20 dispatch records, got {count4}"
            assert elapsed_ms4 < 50, f"Parse too slow: {elapsed_ms4:.2f} ms"

            records = (await session.execute(select(FleetDispatchRecord).where(FleetDispatchRecord.company_id == company_id))).scalars().all()
            assert len(records) == count4
            sample_rec = records[0]
            assert sample_rec.target_object is not None
            assert sample_rec.unit_name is not None

            # 5. Template 5: Operational Tasks & Alerts (Задачи)
            f5 = mock_dir / "05_Юридический_Отдел" / "05_Операционные_Задачи_и_Алерты.xlsx"
            t0 = time.perf_counter()
            count5 = await standard_template_parser.parse_operational_tasks(f5, company_id, None, session)
            t1 = time.perf_counter()
            await session.commit()
            elapsed_ms5 = (t1 - t0) * 1000
            assert count5 >= 20, f"Expected >= 20 tasks, got {count5}"
            assert elapsed_ms5 < 50, f"Parse too slow: {elapsed_ms5:.2f} ms"

            tasks = (await session.execute(select(OperationalTask).where(OperationalTask.company_id == company_id))).scalars().all()
            assert len(tasks) == count5
            sample_task = tasks[0]
            assert sample_task.task_title is not None
            assert sample_task.responsible_role is not None

        finally:
            target = await session.get(Company, company_id)
            if target:
                await session.delete(target)
                await session.commit()
            await test_engine.dispose()
