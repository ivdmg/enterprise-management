"""Allowlisted operations projections for the support console and company director."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_admin
from app.core.config import settings
from app.core.database import get_db, set_tenant_context
from app.core.platform_database import get_platform_db
from app.models.audit import AuditAction, AuditLog
from app.models.user import User
from app.schemas.common import ResponseEnvelope
from app.services.platform_auth import authenticate
from app.services.platform_operations import INCIDENT_TRANSITIONS, describe, record_platform_audit

router = APIRouter(tags=["Operations"])
PlatformDB = Annotated[AsyncSession, Depends(get_platform_db, scope="function")]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
IncidentState = Literal["new", "in_progress", "escalated", "verifying", "closed"]

INCIDENT_SELECT = """
    SELECT id, integration_id, severity, state, code, run_id, assignee_id, version,
           opened_at, updated_at
    FROM public.platform_incidents
    WHERE company_id = :company
"""


class IncidentTransition(BaseModel):
    version: int = Field(ge=1)
    to: IncidentState
    reason: str = Field(min_length=1, max_length=256, pattern=r"\S")
    assignee_id: UUID | None = None


def summary(row) -> dict:
    message, next_step = describe(row["code"])
    return dict(row) | {
        "message": message,
        "next_step": next_step,
        "impact": "Данные источника могут быть устаревшими. Последняя подтверждённая версия сохраняется.",
    }


async def platform_actor(request: Request, db: AsyncSession, *, owner: bool = False):
    if not settings.PLATFORM_AUTH_ENABLED:
        raise HTTPException(404, "Раздел недоступен")
    actor = await authenticate(request, db, platform=True)
    if owner and actor["role"] != "owner":
        raise HTTPException(403, "Недостаточно прав")
    return actor


async def company_actor(request: Request, db: AsyncSession, company: UUID):
    actor = await platform_actor(request, db)
    if not await db.scalar(text("SELECT public.platform_company_exists(:company)"), {"company": company}):
        raise HTTPException(404, "Компания недоступна")
    await set_tenant_context(db, company)
    return actor


@router.get("/platform/status")
async def platform_status(request: Request, db: PlatformDB):
    await platform_actor(request, db)
    data = (await db.execute(text("SELECT * FROM public.platform_operation_status()"))).mappings().one()
    heartbeat = data["worker_heartbeat_at"]
    state = "healthy"
    if heartbeat is None or datetime.now(timezone.utc) - heartbeat > timedelta(minutes=2):
        state = "degraded"
    return ResponseEnvelope.ok(dict(data) | {"status": state})


@router.get("/platform/companies/{company}/incidents")
async def incidents(
    request: Request, db: PlatformDB, company: UUID, state: IncidentState | None = None,
    severity: Literal["warning", "error", "critical"] | None = None, integration_id: UUID | None = None,
    page: Page = 1, limit: Limit = 20,
):
    actor = await company_actor(request, db, company)
    query = INCIDENT_SELECT
    params = {"company": company, "limit": limit, "offset": (page - 1) * limit}
    for field, value in (("state", state), ("severity", severity), ("integration_id", integration_id)):
        if value is not None:
            query += f" AND {field} = :{field}"
            params[field] = value
    rows = (await db.execute(text(query + " ORDER BY updated_at DESC, id DESC LIMIT :limit OFFSET :offset"), params)).mappings()
    await record_platform_audit(db, actor_id=actor["id"], company_id=company, action="incident_list",
                                correlation_id=getattr(request.state, "request_id", None))
    return ResponseEnvelope.ok([summary(row) for row in rows])


@router.get("/platform/companies/{company}/incidents/{incident_id}")
async def incident(request: Request, db: PlatformDB, company: UUID, incident_id: UUID):
    actor = await company_actor(request, db, company)
    row = (await db.execute(text(INCIDENT_SELECT + " AND id = :id"), {"company": company, "id": incident_id})).mappings().first()
    if not row:
        raise HTTPException(404, "Инцидент недоступен")
    await record_platform_audit(db, actor_id=actor["id"], company_id=company, action="incident_read",
                                entity_id=incident_id, correlation_id=getattr(request.state, "request_id", None))
    return ResponseEnvelope.ok(summary(row))


@router.post("/platform/companies/{company}/incidents/{incident_id}/transitions")
async def transition(request: Request, db: PlatformDB, company: UUID, incident_id: UUID, payload: IncidentTransition):
    actor = await company_actor(request, db, company)
    params = {"company": company, "id": incident_id}
    row = (await db.execute(text(INCIDENT_SELECT + " AND id = :id FOR UPDATE"), params)).mappings().first()
    if not row:
        raise HTTPException(404, "Инцидент недоступен")
    if row["version"] != payload.version or payload.to not in INCIDENT_TRANSITIONS[row["state"]]:
        raise HTTPException(409, "Инцидент изменился или переход недоступен")
    assignee = payload.assignee_id
    if assignee is None and payload.to == "in_progress" and row["assignee_id"] is None:
        assignee = actor["id"]
    if assignee and not await db.scalar(text("SELECT EXISTS(SELECT FROM public.platform_operators WHERE id = :id AND is_active)"), {"id": assignee}):
        raise HTTPException(404, "Исполнитель недоступен")
    try:
        await db.execute(text("""
            UPDATE public.platform_incidents
            SET state = :state, assignee_id = COALESCE(:assignee, assignee_id),
                version = version + 1, updated_at = clock_timestamp()
            WHERE company_id = :company AND id = :id
        """), params | {"state": payload.to, "assignee": assignee})
    except IntegrityError:
        raise HTTPException(409, "По источнику уже открыт инцидент с этим кодом") from None
    updated = (await db.execute(text(INCIDENT_SELECT + " AND id = :id"), params)).mappings().one()
    await record_platform_audit(db, actor_id=actor["id"], company_id=company, action="incident_" + payload.to,
                                entity_id=incident_id, correlation_id=getattr(request.state, "request_id", None))
    return ResponseEnvelope.ok(summary(updated))


@router.get("/platform/companies/{company}/events")
async def events(
    request: Request, db: PlatformDB, company: UUID, integration_id: UUID | None = None,
    severity: Literal["info", "warning", "error", "critical"] | None = None,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    page: Page = 1, limit: Limit = 20,
):
    actor = await company_actor(request, db, company)
    query = """
        SELECT e.id, e.code, e.severity, e.integration_id, e.run_id, e.created_at, r.request_id
        FROM public.platform_integration_events AS e
        JOIN public.platform_run_correlation AS r USING (company_id, integration_id, run_id)
        WHERE e.company_id = :company
    """
    params = {"company": company, "limit": limit, "offset": (page - 1) * limit}
    for name, clause, value in (
        ("integration", "e.integration_id = :integration", integration_id),
        ("severity", "e.severity = :severity", severity),
        ("from_at", "e.created_at >= :from_at", from_at),
        ("to_at", "e.created_at <= :to_at", to_at),
    ):
        if value is not None:
            query += " AND " + clause
            params[name] = value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value
    rows = (await db.execute(text(query + " ORDER BY e.created_at DESC, e.id DESC LIMIT :limit OFFSET :offset"), params)).mappings()
    await record_platform_audit(db, actor_id=actor["id"], company_id=company, action="event_list",
                                correlation_id=getattr(request.state, "request_id", None))
    data = []
    for row in rows:
        message, next_step = describe(row["code"])
        data.append(dict(row) | {"message": message, "next_step": next_step})
    return ResponseEnvelope.ok(data)


@router.get("/platform/audit")
async def platform_audit(
    request: Request, db: PlatformDB, actor_id: UUID | None = None, company_id: UUID | None = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    page: Page = 1, limit: Limit = 20,
):
    await platform_actor(request, db, owner=True)
    query = "SELECT id, actor_id, company_id, action, entity_id, result, correlation_id, created_at FROM public.platform_operation_audit WHERE true"
    params = {"limit": limit, "offset": (page - 1) * limit}
    for name, clause, value in (
        ("actor", "actor_id = :actor", actor_id),
        ("company", "company_id = :company", company_id),
        ("action", "action = :action", action),
        ("from_at", "created_at >= :from_at", from_at),
        ("to_at", "created_at <= :to_at", to_at),
    ):
        if value is not None:
            query += " AND " + clause
            params[name] = value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value
    rows = (await db.execute(text(query + " ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset"), params)).mappings()
    return ResponseEnvelope.ok([dict(row) for row in rows])


@router.get("/company/audit")
async def company_audit(
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    user: Annotated[User, Depends(get_current_active_admin)],
    actor_id: UUID | None = None, action: AuditAction | None = None,
    entity_type: Annotated[str | None, Query(max_length=50)] = None,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    page: Page = 1, limit: Limit = 20,
):
    query = (
        select(AuditLog.id, AuditLog.user_id, User.full_name, AuditLog.entity_type, AuditLog.entity_id, AuditLog.action,
               AuditLog.old_status, AuditLog.new_status, AuditLog.timestamp)
        .outerjoin(User, (User.id == AuditLog.user_id) & (User.company_id == AuditLog.company_id))
        .where(AuditLog.company_id == user.company_id)
    )
    if actor_id:
        query = query.where(AuditLog.user_id == actor_id)
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if from_at:
        query = query.where(AuditLog.timestamp >= (from_at if from_at.tzinfo else from_at.replace(tzinfo=timezone.utc)))
    if to_at:
        query = query.where(AuditLog.timestamp <= (to_at if to_at.tzinfo else to_at.replace(tzinfo=timezone.utc)))
    rows = await db.execute(query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).offset((page - 1) * limit).limit(limit))
    return ResponseEnvelope.ok([
        {"id": row.id, "actor_id": row.user_id, "actor_name": row.full_name or "Система",
         "entity_type": row.entity_type, "entity_id": row.entity_id, "action": row.action,
         "result": "success", "created_at": row.timestamp,
         "changes": {"status": {"before": row.old_status, "after": row.new_status}}
         if row.action == "status_changed" else None}
        for row in rows
    ])
