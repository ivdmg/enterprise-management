import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ResponseEnvelope
from app.schemas.sync import SyncStatusData
from app.services.drive_sync import drive_sync_service

logger = logging.getLogger("enterprise_hub.api.sync")

router = APIRouter(prefix="/sync", tags=["Google Drive Synchronization"])


@router.post(
    "/drive-now",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[SyncStatusData],
    summary="Принудительный запуск синхронизации Google Диска для текущей компании",
)
async def trigger_drive_sync(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[SyncStatusData]:
    """
    Scans the 5 target folders on Google Drive (or Mock Drive), detects changed/new files,
    applies fast deterministic parsing, updates financial & operational models,
    and runs the analytical alert engine.
    """
    logger.info("Manual Drive sync initiated by user %s (company: %s)", current_user.email, current_user.company_id)
    
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
