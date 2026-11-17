from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session, make_transient_to_detached

from app.api.deps import get_current_user
from app.api.v1 import sync
from app.core.database import get_db
from app.models.user import User


@pytest.mark.asyncio
async def test_manual_sync_returns_import_error_after_rollback_expires_user(monkeypatch):
    company_id = uuid4()
    user_id = uuid4()
    user = User(id=user_id, company_id=company_id, email="sync@example.test")
    make_transient_to_detached(user)

    # Expire a persistent ORM instance without opening a database connection.
    with Session() as session:
        session.add(user)
        db = object()

        async def import_with_rollback(**kwargs):
            assert kwargs == {"company_id": company_id, "user_id": user_id, "db": db}
            session.expire_all()
            return {"status": "error", "last_error": "Не удалось прочитать таблицу"}

        app = FastAPI()
        app.include_router(sync.router)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        monkeypatch.setattr(sync.google_drive_client, "is_mock", True)
        monkeypatch.setattr(sync.drive_sync_service, "sync_company_drive", import_with_rollback)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/sync/drive-now")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "error"
    assert response.json()["data"]["last_error"] == "Не удалось прочитать таблицу"


@pytest.mark.asyncio
async def test_sync_status_exposes_root_link_only_to_connected_company(monkeypatch):
    connected_company = uuid4()
    foreign_company = uuid4()
    monkeypatch.setattr(sync.settings, "GOOGLE_DRIVE_COMPANY_ID", connected_company)
    monkeypatch.setattr(sync.settings, "GOOGLE_DRIVE_ROOT_FOLDER_ID", "test-folder")
    monkeypatch.setattr(sync.settings, "GOOGLE_DRIVE_MOCK", False)

    app = FastAPI()
    app.include_router(sync.router)
    user = User(id=uuid4(), company_id=foreign_company)
    app.dependency_overrides[get_current_user] = lambda: user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        foreign_response = await client.get("/sync/status")
        user.company_id = connected_company
        connected_response = await client.get("/sync/status")

    assert foreign_response.status_code == connected_response.status_code == 200
    assert foreign_response.json()["data"]["root_folder_link"] is None
    assert connected_response.json()["data"]["root_folder_link"] == "https://drive.google.com/drive/folders/test-folder"
