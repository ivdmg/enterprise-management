import io
import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.company import Company
from app.models.enums import UserRole
from app.models.user import User
from app.services.google_drive import GoogleDriveClient, google_drive_client
from app.services.drive_sync import GoogleDriveSyncService, drive_sync_service


@pytest.fixture
def test_user():
    company_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        company_id=company_id,
        email="sync_tester@enterprise.ru",
        password_hash="fakehash",
        full_name="Тестировщик Синхронизации",
        role=UserRole.ADMIN,
        is_active=True,
    )
    user.company = Company(id=company_id, name="АО Тендер Тест", is_active=True)
    return user


def test_google_drive_mock_client_operations():
    """Validates that GoogleDriveClient transparently operates on mock_drive folder."""
    client = GoogleDriveClient(mock_mode=True)
    assert client.is_mock is True

    # 1. List files in standard target folders
    files = client.list_files_in_folder("root")
    assert len(files) >= 5, "Expected at least 5 standard template files in mock drive"
    
    file_names = [f.name for f in files]
    assert any("01_" in name for name in file_names)
    assert any("02_" in name for name in file_names)

    # 2. Check download
    sample_file = files[0]
    content = client.download_file_bytes(sample_file.id)
    assert len(content) > 0
    assert len(content) == sample_file.size_bytes

    # 3. Check web view link
    link = client.get_web_view_link(sample_file.id)
    assert "https://drive.google.com/file/d/" in link

    # 4. Check upload
    dummy_data = b"Test Content for Drive Upload"
    upload_res = client.upload_file(
        folder_name_or_id="01_Реестры_Тендеров",
        filename="test_upload.xlsx",
        content=dummy_data,
    )
    assert upload_res.name == "test_upload.xlsx"
    assert upload_res.size_bytes == len(dummy_data)
    assert len(upload_res.md5_checksum) == 32


@pytest.mark.asyncio
async def test_drive_sync_api_endpoints(test_user):
    """Tests GET /api/v1/sync/status and POST /api/v1/sync/drive-now endpoints."""
    db_mock = AsyncMock()
    # Mock no existing files so it performs parsing
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    result_mock.scalars.return_value.all.return_value = []
    db_mock.execute.return_value = result_mock

    async def override_get_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET status
        status_resp = await client.get("/api/v1/sync/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["success"] is True
        assert "status" in data["data"]
        assert data["data"]["status"] in ("idle", "syncing")

        # 2. POST trigger sync
        with patch.object(drive_sync_service, "sync_company_drive", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {
                "status": "idle",
                "last_sync_time": datetime.now(timezone.utc).isoformat(),
                "processed_files_count": 5,
                "skipped_files_count": 0,
                "last_error": None,
                "details": [{"file": "01_test.xlsx", "action": "imported"}],
            }

            sync_resp = await client.post("/api/v1/sync/drive-now")
            assert sync_resp.status_code == 200
            sync_data = sync_resp.json()
            assert sync_data["success"] is True
            assert sync_data["data"]["processed_files_count"] == 5
            mock_sync.assert_called_once()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_drive_sync_end_to_end_real_db():
    """
    Live PostgreSQL integration test:
    Creates a temporary company, runs drive_sync_service against mock_drive,
    verifies records in all 5 business domain tables, and verifies 0-overhead deduplication.
    """
    from app.core.database import async_session_factory
    from app.models.project import TenderProject
    from app.models.finance import CashflowOperation
    from app.models.procurement import ProcurementItem
    from app.models.dispatch import FleetDispatchRecord
    from app.models.task import OperationalTask
    from sqlalchemy import select

    async with async_session_factory() as session:
        # Create isolated test company
        test_company = Company(
            id=uuid.uuid4(),
            name=f"E2E Sync Test {uuid.uuid4().hex[:6]}",
            inn="7700000000",
            is_active=True,
        )
        session.add(test_company)
        await session.commit()

        company_id = test_company.id
        try:
            # 1. First sync run: must import all 5 standard files
            res1 = await drive_sync_service.sync_company_drive(
                company_id=company_id,
                db=session,
            )
            assert res1["status"] == "idle"
            assert res1["processed_files_count"] == 5

            # Verify records were inserted into each domain table
            tenders = (await session.execute(select(TenderProject).where(TenderProject.company_id == company_id))).scalars().all()
            assert len(tenders) > 0, "Expected tenders imported"

            cashflows = (await session.execute(select(CashflowOperation).where(CashflowOperation.company_id == company_id))).scalars().all()
            assert len(cashflows) > 0, "Expected cashflow operations imported"

            procurements = (await session.execute(select(ProcurementItem).where(ProcurementItem.company_id == company_id))).scalars().all()
            assert len(procurements) > 0, "Expected procurement items imported"

            dispatches = (await session.execute(select(FleetDispatchRecord).where(FleetDispatchRecord.company_id == company_id))).scalars().all()
            assert len(dispatches) > 0, "Expected fleet dispatch records imported"

            tasks = (await session.execute(select(OperationalTask).where(OperationalTask.company_id == company_id))).scalars().all()
            assert len(tasks) > 0, "Expected operational tasks imported"

            # 2. Second sync run: files have not changed, must skip all with 0 overhead
            res2 = await drive_sync_service.sync_company_drive(
                company_id=company_id,
                db=session,
            )
            assert res2["skipped_files_count"] == 5

        finally:
            # Clean up company (cascades all related records)
            target = await session.get(Company, company_id)
            if target:
                await session.delete(target)
                await session.commit()
