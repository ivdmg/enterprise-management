from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from app.core.config import settings
from app.services.google_drive import GoogleDriveClient
from app.schemas.common import ResponseEnvelope

def live_client(tmp_path):
    client = GoogleDriveClient(mock_mode=True, mock_dir=tmp_path)
    client.is_mock = False
    client._service = MagicMock()
    return client

def test_live_folder_resolution_and_pagination(tmp_path):
    client = live_client(tmp_path)
    files = client._service.files.return_value
    files.list.return_value.execute.side_effect = [
        {"files":[{"id":"real-folder-id"}]},
        {"files":[{"id":"sheet-id", "name":"ДДС", "mimeType":"application/vnd.google-apps.spreadsheet", "modifiedTime":"2026-10-24T08:00:00Z"}], "nextPageToken":"next"},
        {"files":[{"id":"xlsx-id", "name":"Счета.xlsx", "mimeType":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "modifiedTime":"2026-10-24T09:00:00Z"}]},
    ]
    with patch.object(settings, "GOOGLE_DRIVE_ROOT_FOLDER_ID", "root-id"):
        result = client.list_files_in_folder("03_Банк_и_Касса")
    assert [f.id for f in result] == ["sheet-id", "xlsx-id"]
    calls = files.list.call_args_list
    assert "'root-id' in parents" in calls[0].kwargs['q']
    assert "'real-folder-id' in parents" in calls[1].kwargs['q']
    assert calls[2].kwargs['pageToken'] == "next"

def test_google_sheets_are_exported_as_xlsx(tmp_path):
    client = live_client(tmp_path)
    files = client._service.files.return_value
    files.get.return_value.execute.return_value = {"mimeType":"application/vnd.google-apps.spreadsheet"}
    with patch("googleapiclient.http.MediaIoBaseDownload") as download:
        download.return_value.next_chunk.return_value = (None, True)
        client.download_file_bytes("sheet-id")
    files.export_media.assert_called_once_with(fileId="sheet-id",mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    files.get_media.assert_not_called()

def test_missing_live_credentials_never_fall_back_to_mock(tmp_path):
    with patch.object(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", None):
        with pytest.raises(RuntimeError, match="credentials are missing"):
            GoogleDriveClient(mock_mode=False, mock_dir=tmp_path, credentials_path=tmp_path/'absent.json')

def test_money_serializes_as_numbers_and_keeps_zero():
    result = ResponseEnvelope.ok({"amount":Decimal('123.45'),"zero":Decimal('0.00'),"id":"00123"}).model_dump(mode="json")
    assert result['data'] == {"amount":123.45,"zero":0,"id":"00123"}

@pytest.mark.asyncio
async def test_background_sync_returns_before_job_finishes():
    import asyncio
    import uuid
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.api.deps import get_current_user
    from app.core.database import get_db
    from app.models.user import User
    from app.models.enums import UserRole
    from app.api.v1.sync import _sync_tasks
    from app.services.drive_sync import drive_sync_service
    from unittest.mock import AsyncMock
    user=User(id=uuid.uuid4(), company_id=uuid.uuid4(), email='sync@example.com', role=UserRole.ADMIN)
    gate=asyncio.Event()
    async def job(**kwargs):
        await gate.wait()
    async def db_override(): yield AsyncMock()
    app.dependency_overrides[get_current_user]=lambda:user
    app.dependency_overrides[get_db]=db_override
    try:
        with patch.object(drive_sync_service,'sync_company_drive',side_effect=job):
            async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
                r=await client.post('/api/v1/sync/drive-now?background=true')
                assert r.status_code==200
                assert r.json()['data']['status']=='syncing'
                assert _sync_tasks and not all(task.done() for task in _sync_tasks)
            gate.set()
            await asyncio.gather(*tuple(_sync_tasks))
    finally:
        gate.set()
        app.dependency_overrides.clear()
