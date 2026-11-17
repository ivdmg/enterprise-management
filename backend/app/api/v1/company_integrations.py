from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_admin, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ResponseEnvelope
from app.services import company_config
from app.services.integration_jobs import JobError, get_integration, list_integrations, request_retry

router = APIRouter(prefix="/company/integrations", tags=["Integrations"])
db_dependency = Annotated[AsyncSession, Depends(get_db, scope="function")]


class RetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="", max_length=256)


@router.get("")
async def integrations(user: Annotated[User, Depends(get_current_user)], db: db_dependency, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    if not settings.INTEGRATIONS_ENABLED:
        return ResponseEnvelope.ok([])
    await company_config.require_modules(db, user.company_id, {"sources"})
    revision = await company_config.current_revision(db, user.company_id)
    visible_modules = {module["id"] for module in company_config.effective_modules(revision["modules"])}
    entries = await list_integrations(db, user.company_id)
    return ResponseEnvelope.ok([entry for entry in entries if entry["module_id"] in visible_modules])


@router.post("/{integration_id}/retry-request", status_code=202)
async def create_retry_request(
    integration_id: UUID, payload: RetryRequest, user: Annotated[User, Depends(get_current_active_admin)],
    db: db_dependency,
):
    if not settings.INTEGRATIONS_ENABLED:
        raise HTTPException(404, "Источник не найден")
    integration = await get_integration(db, user.company_id, integration_id)
    if not integration:
        raise HTTPException(404, "Источник не найден")
    await company_config.require_modules(db, user.company_id, {"sources", integration["module_id"]})
    try:
        result = await request_retry(
            db, company_id=user.company_id, integration_id=integration_id,
            user_id=user.id, reason=payload.reason.strip(),
        )
    except JobError as exc:
        raise HTTPException(404, "Источник не найден") from exc
    return ResponseEnvelope.ok(result)
