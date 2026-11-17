import logging
import asyncio
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import ResponseEnvelope
from app.schemas.sync import InitFoldersRequest, InitFoldersResponse, SyncStatusData
from app.services.drive_sync import drive_sync_service
from app.services.google_drive import google_drive_client

logger = logging.getLogger("enterprise_hub.api.sync")

router = APIRouter(prefix="/sync", tags=["Google Drive Synchronization"])
_sync_tasks: set[asyncio.Task] = set()


def _drive_root_link(company_id: UUID) -> str | None:
    root_folder_id = settings.GOOGLE_DRIVE_ROOT_FOLDER_ID
    if root_folder_id and company_id == settings.GOOGLE_DRIVE_COMPANY_ID:
        return f"https://drive.google.com/drive/folders/{root_folder_id}"
    return None


@router.post(
    "/init-folders",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[InitFoldersResponse],
    summary="Автоматическая инициализация структуры папок на Google Диске (Task BE-1.1)",
)
async def init_drive_folders(
    payload: Optional[InitFoldersRequest] = None,
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[InitFoldersResponse]:
    """
    Checks or creates the standard folder hierarchy on Google Drive / Mock Drive:
    - 01_Сметы_и_Тендеры
    - 02_Счета_Снабжения
    - 03_Банк_и_Касса
    - 04_Путевые_листы
    - 05_Обработано
    - 99_Ошибки_парсинга
    """
    if settings.INTEGRATIONS_ENABLED:
        raise HTTPException(404, "Управление папками выполняется через интеграции")
    root_id = payload.root_folder_id if payload else None
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Инициализировать папки может только администратор")
    if not google_drive_client.is_mock:
        raise HTTPException(403, "Google Диск подключён только для чтения")
    logger.info("Initializing Drive folders requested by %s (root_id: %s)", current_user.email, root_id)
    folders = google_drive_client.for_company(current_user.company_id).init_folders(root_folder_id=root_id)
    return ResponseEnvelope.ok(
        data=InitFoldersResponse(status="ok", folders=folders),
        meta={"company_id": str(current_user.company_id)},
    )


@router.post(
    "/drive-now",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[SyncStatusData],
    summary="Принудительный запуск синхронизации Google Диска для текущей компании",
)
async def trigger_drive_sync(
    background: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ResponseEnvelope[SyncStatusData]:
    """
    Scans incoming folders on Google Drive (or Mock Drive), detects changed/new files,
    applies fast deterministic parsing, updates financial & operational models,
    and runs the analytical alert engine.
    """
    if settings.INTEGRATIONS_ENABLED:
        raise HTTPException(404, "Запросите повтор в разделе источников")
    # The import can roll back the request session and expire ORM attributes.
    company_id = current_user.company_id
    user_id = current_user.id
    logger.info("Manual Drive sync initiated by user %s (company: %s)", current_user.email, company_id)

    if not google_drive_client.is_mock and company_id != settings.GOOGLE_DRIVE_COMPANY_ID:
        raise HTTPException(403, "Google Диск не подключён к этой организации")

    if background:
        current_status = drive_sync_service.get_status(company_id).to_dict()
        if current_status["status"] != "syncing":
            task = asyncio.create_task(drive_sync_service.sync_company_drive(
                company_id=company_id, user_id=user_id,
            ))
            _sync_tasks.add(task)
            task.add_done_callback(_sync_tasks.discard)
        return ResponseEnvelope.ok(
            SyncStatusData(
                **{**current_status, "status": "syncing"},
                root_folder_link=_drive_root_link(company_id),
            )
        )
    
    result = await drive_sync_service.sync_company_drive(
        company_id=company_id,
        user_id=user_id,
        db=db,
    )
    
    return ResponseEnvelope.ok(
        data=SyncStatusData(**result, root_folder_link=_drive_root_link(company_id)),
        meta={"company_id": str(company_id)},
    )


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[SyncStatusData],
    summary="Текущий статус синхронизации Google Диска",
)
async def get_drive_sync_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ResponseEnvelope[SyncStatusData]:
    """
    Returns time of last synchronization, number of processed/skipped files,
    and operational state (idle, syncing, error).
    """
    company_id = current_user.company_id
    if settings.INTEGRATIONS_ENABLED:
        from app.services.integration_jobs import list_integrations

        sources = await list_integrations(db, company_id)
        last_successes = [source["last_success_at"] for source in sources if source["last_success_at"]]
        failed = next((source for source in sources if source["status"] == "needs_attention"), None)
        state = "syncing" if any(source["status"] == "running" for source in sources) else "idle"
        if failed and state == "idle":
            state = "error"
        result = {
            "status": state,
            "last_sync_time": max(last_successes).isoformat() if last_successes else None,
            "last_error": failed["error"]["message"] if failed and failed["error"] else None,
        }
    else:
        result = drive_sync_service.get_status(company_id).to_dict()
    return ResponseEnvelope.ok(
        data=SyncStatusData(**result, root_folder_link=_drive_root_link(company_id)),
        meta={"company_id": str(company_id)},
    )
