from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_manager
from app.core.config import settings
from app.core.database import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.common import ResponseEnvelope

router = APIRouter(prefix="/engineer-documents", tags=["Engineer Documents"])


@router.get("")
async def get_engineer_documents(
    response: Response,
    user: User = Depends(get_current_active_manager),
    db: AsyncSession = Depends(get_db),
):
    if settings.GOOGLE_DRIVE_MOCK or user.company_id != settings.GOOGLE_DRIVE_COMPANY_ID:
        raise HTTPException(404, "Реестр не подключён к этой организации")
    register = await db.scalar(
        select(Company.engineer_documents).where(Company.id == user.company_id)
    )
    response.headers["Cache-Control"] = "private, no-store"
    return ResponseEnvelope.ok({"register": register})
