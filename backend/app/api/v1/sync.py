import logging
import asyncio
from typing import Any, Dict, Optional

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
    root_id = payload.root_folder_id if payload else None
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Инициализировать папки может только администратор")
    if not google_drive_client.is_mock:
        if current_user.company_id != settings.GOOGLE_DRIVE_COMPANY_ID:
            raise HTTPException(403, "Google Диск не подключён к этой организации")
        if root_id and root_id != settings.GOOGLE_DRIVE_ROOT_FOLDER_ID:
            raise HTTPException(403, "Используйте настроенную корневую папку")
    logger.info("Initializing Drive folders requested by %s (root_id: %s)", current_user.email, root_id)
    folders = google_drive_client.init_folders(root_folder_id=root_id)
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
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[SyncStatusData]:
    """
    Scans incoming folders on Google Drive (or Mock Drive), detects changed/new files,
    applies fast deterministic parsing, updates financial & operational models,
    and runs the analytical alert engine.
    """
    logger.info("Manual Drive sync initiated by user %s (company: %s)", current_user.email, current_user.company_id)

    if background:
        current_status = drive_sync_service.get_status(current_user.company_id).to_dict()
        if current_status["status"] != "syncing":
            task = asyncio.create_task(drive_sync_service.sync_company_drive(
                company_id=current_user.company_id, user_id=current_user.id,
            ))
            _sync_tasks.add(task)
            task.add_done_callback(_sync_tasks.discard)
        return ResponseEnvelope.ok(SyncStatusData(**{**current_status, "status": "syncing"}))
    
    result = await drive_sync_service.sync_company_drive(
        company_id=current_user.company_id,
        user_id=current_user.id,
        db=db,
    )
    
    return ResponseEnvelope.ok(
        data=SyncStatusData(**result),
        meta={"company_id": str(current_user.company_id)},
    )


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[SyncStatusData],
    summary="Текущий статус синхронизации Google Диска",
)
async def get_drive_sync_status(
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[SyncStatusData]:
    """
    Returns time of last synchronization, number of processed/skipped files,
    and operational state (idle, syncing, error).
    """
    status_info = drive_sync_service.get_status(current_user.company_id)
    return ResponseEnvelope.ok(
        data=SyncStatusData(**status_info.to_dict()),
        meta={"company_id": str(current_user.company_id)},
    )
