from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.google_drive import GoogleDriveClient
from app.services.storage import LocalStorageService, build_tenant_storage_key


@pytest.mark.asyncio
async def test_tenant_storage_requires_matching_file_namespace(tmp_path):
    storage = LocalStorageService(tmp_path / "storage")
    company_a, company_b = uuid4(), uuid4()
    key_a = build_tenant_storage_key(company_a, "same")
    key_b = build_tenant_storage_key(company_b, "same")

    await storage.save_tenant_file(b"A", key_a, company_a)
    await storage.save_tenant_file(b"B", key_b, company_b)
    assert storage.get_tenant_file_path(key_a, company_a).read_bytes() == b"A"
    assert storage.get_tenant_file_path(key_b, company_b).read_bytes() == b"B"
    with pytest.raises(FileNotFoundError):
        storage.get_tenant_file_path(key_b, company_a)
    with pytest.raises(ValueError):
        storage.get_local_file_path("../storage-other/file.xlsx")


def test_mock_drive_protected_mode_uses_distinct_roots(tmp_path, monkeypatch):
    drive = GoogleDriveClient(mock_mode=True, mock_dir=tmp_path / "drive")
    monkeypatch.setattr(settings, "DATABASE_RUNTIME_URL", "postgresql://runtime@localhost/test")
    client_a, client_b = drive.for_company(uuid4()), drive.for_company(uuid4())
    folder = "01_Сметы_и_Тендеры"
    uploaded_a = client_a.upload_file(folder, "same.xlsx", b"A")
    uploaded_b = client_b.upload_file(folder, "same.xlsx", b"B")

    assert client_a.download_file_bytes(uploaded_a.id) == b"A"
    assert client_b.download_file_bytes(uploaded_b.id) == b"B"
    with pytest.raises(ValueError):
        client_a.download_file_bytes(str(client_b.mock_dir / folder / "same.xlsx"))
    with pytest.raises(ValueError):
        client_a.upload_file("../outside", "escape.xlsx", b"X")
    with pytest.raises(ValueError):
        client_a.upload_file(folder, "../escape.xlsx", b"X")
