"""Exercise repeated edits, deletions and failed imports against real PostgreSQL."""
import io
from pathlib import Path
from unittest.mock import patch
import uuid
import openpyxl
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.models.company import Company
from app.models.file import UploadedFile
from app.models.finance import CashflowOperation
from app.models.project import TenderProject
from app.models.procurement import ProcurementItem
from app.models.dispatch import FleetDispatchRecord
from app.models.task import OperationalTask
from app.services.drive_sync import GoogleDriveSyncService
from app.services.google_drive import GoogleDriveClient

@pytest.mark.asyncio
async def test_edit_delete_and_invalid_source_are_atomic(tmp_path):
    drive = GoogleDriveClient(mock_mode=True, mock_dir=tmp_path)
    assets = sorted((Path(__file__).resolve().parents[2] / "demo-data").glob("*.xlsx"))
    assert len(assets) == 5
    for file in assets:
        drive.upload_file("01_Сметы_и_Тендеры", file.name, file.read_bytes())
    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    service = GoogleDriveSyncService()
    async with factory() as db:
        company = Company(id=uuid.uuid4(), name="Isolated Drive edit verification", is_active=False)
        db.add(company)
        await db.commit()
        company_id = company.id
        async def count(model):
            return (await db.execute(select(func.count()).select_from(model).where(model.company_id==company_id, model.deleted_at.is_(None)))).scalar_one()
        try:
            with patch("app.services.drive_sync.google_drive_client", drive):
                first = await service.sync_company_drive(company_id, db=db)
                assert first['status']=='idle', first
                assert first['processed_files_count']==5
                assert [await count(model) for model in (TenderProject,CashflowOperation,ProcurementItem,FleetDispatchRecord,OperationalTask)] == [22,24,22,23,22]
                assert (await service.sync_company_drive(company_id, db=db))['skipped_files_count']==5
                cash = tmp_path / "01_Сметы_и_Тендеры" / assets[1].name
                original = cash.read_bytes()
                wb = openpyxl.load_workbook(io.BytesIO(original))
                wb.active['E2'] = 999999
                wb.active.delete_rows(3)
                wb.save(cash)
                edited = await service.sync_company_drive(company_id, db=db)
                assert edited['processed_files_count']==1, edited
                assert await count(CashflowOperation)==23
                assert await count(UploadedFile)==5
                cash.write_bytes(b"invalid workbook")
                failed = await service.sync_company_drive(company_id, db=db)
                assert failed['status']=='error'
                assert await count(CashflowOperation)==23
                cash.write_bytes(original)
                restored = await service.sync_company_drive(company_id, db=db)
                assert restored['status']=='idle', restored
                assert await count(CashflowOperation)==24
                assert await count(UploadedFile)==5
                tenders = tmp_path / "01_Сметы_и_Тендеры" / assets[0].name
                wb = openpyxl.load_workbook(tenders)
                wb.active.delete_rows(3)
                wb.save(tenders)
                assert (await service.sync_company_drive(company_id, db=db))['status']=='idle'
                assert await count(TenderProject)==21
        finally:
            await db.rollback()
            target = await db.get(Company, company_id)
            await db.delete(target)
            await db.commit()
    await engine.dispose()
