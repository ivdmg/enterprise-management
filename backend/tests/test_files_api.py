import io
import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.company import Company
from app.models.enums import UserRole
from app.models.file import UploadedFile
from app.models.user import User


@pytest.fixture
def mock_user():
    company_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        company_id=company_id,
        email="test@enterprise.ru",
        password_hash="hash",
        full_name="Тестовый Инженер",
        role=UserRole.ADMIN,
        is_active=True,
    )
    user.company = Company(id=company_id, name="ООО Тест", is_active=True)
    return user


@pytest.mark.asyncio
async def test_file_upload_duplicate_detection(mock_user):
    """
    Validates that uploading a duplicate file returns HTTP 409 Conflict
    with structured DUPLICATE_FILE error matching api_standards.md.
    """
    # Mock existing file in DB
    existing_file = UploadedFile(
        id=uuid.uuid4(),
        company_id=mock_user.company_id,
        original_name="test_report.xlsx",
        storage_path="tenants/dummy.xlsx",
        file_size_bytes=1000,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        sha256_hash="dummy_hash",
        created_at=datetime.now(timezone.utc),
    )

    db_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing_file
    db_mock.execute.return_value = result_mock

    async def override_get_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        file_content = b"Mock excel binary stream for deduplication test"
        files = {
            "file": (
                "test_report.xlsx",
                io.BytesIO(file_content),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }

        resp = await client.post("/api/v1/files/upload", files=files)
        assert resp.status_code == 409
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "DUPLICATE_FILE"
        assert "existing_file_id" in data["error"]["details"]
        assert data["error"]["details"]["original_name"] == "test_report.xlsx"

    app.dependency_overrides.clear()
