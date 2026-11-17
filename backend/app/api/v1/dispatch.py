import asyncio
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.dispatch import FleetDispatchRecord
from app.models.user import User
from app.schemas.common import ResponseEnvelope
from app.services.audit import record_audit_log
from app.services.google_drive import get_google_drive_client
from app.services.monthly_dispatch import load_monthly_dispatch

router = APIRouter(prefix="/dispatch", tags=["Dispatch"])
Status = Literal["on_site", "repair", "downtime"]


@router.get("/monthly")
async def monthly(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    if settings.GOOGLE_DRIVE_MOCK or user.company_id != settings.GOOGLE_DRIVE_COMPANY_ID:
        return ResponseEnvelope.ok(None)
    try:
        client = get_google_drive_client().for_company(user.company_id)
        return ResponseEnvelope.ok(await asyncio.to_thread(load_monthly_dispatch, client))
    except Exception as exc:
        raise HTTPException(502, "Не удалось прочитать помесячный график Google Диска") from exc

def present(row):
    status = row.status.lower().replace("_", " ")
    status = "repair" if "ремонт" in status or status == "repair" else "downtime" if "простой" in status or status == "downtime" else "on_site"
    return dict(id=str(row.id), shift_date=row.shift_date, target_object=row.target_object,
        resource_type="machinery" if row.resource_type in ("Спецтехника", "machinery") else "crew",
        unit_name=row.unit_name, responsible_person=row.responsible_person,
        status=status, incident_notes=row.incident_notes,
        downtime_hours=row.downtime_hours, downtime_reason=row.downtime_reason)

class StatusUpdate(BaseModel):
    status: Status

class Incident(BaseModel):
    status: Status = "repair"
    downtime_reason: str = Field(min_length=1, max_length=2000)
    downtime_hours: float = Field(ge=0, le=100000)
    incident_notes: str | None = Field(default=None, max_length=4000)

async def find_record(record_id, user, db):
    row = (await db.execute(select(FleetDispatchRecord).where(
        FleetDispatchRecord.id == record_id, FleetDispatchRecord.company_id == user.company_id,
        FleetDispatchRecord.deleted_at.is_(None)))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Запись диспетчерской не найдена")
    return row

@router.get("/records")
async def records(status: Status | None = None, resource_type: Literal["machinery", "crew"] | None = None,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db, scope="function")):
    rows = (await db.execute(select(FleetDispatchRecord).where(
        FleetDispatchRecord.company_id == user.company_id, FleetDispatchRecord.deleted_at.is_(None)
    ).order_by(FleetDispatchRecord.shift_date.desc()))).scalars().all()
    items = [present(row) for row in rows]
    return ResponseEnvelope.ok([item for item in items if
        (not status or item['status'] == status) and (not resource_type or item['resource_type'] == resource_type)])

@router.patch("/records/{record_id}/status")
async def update_status(record_id: uuid.UUID, payload: StatusUpdate, request: Request,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db, scope="function")):
    row = await find_record(record_id, user, db)
    old = row.status
    row.status = payload.status
    if payload.status == "on_site":
        row.downtime_hours = None
        row.downtime_reason = None
    await record_audit_log(db=db, company_id=user.company_id, entity_type="dispatch", entity_id=row.id,
        old_status=old, new_status=row.status, user_id=user.id, request=request)
    await db.commit()
    return ResponseEnvelope.ok(dict(id=str(row.id), status=row.status))

@router.post("/records/{record_id}/incident")
async def log_incident(record_id: uuid.UUID, payload: Incident, request: Request,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db, scope="function")):
    row = await find_record(record_id, user, db)
    old = row.status
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await record_audit_log(db=db, company_id=user.company_id, entity_type="dispatch", entity_id=row.id,
        old_status=old, new_status=row.status, user_id=user.id, request=request)
    await db.commit()
    return ResponseEnvelope.ok(present(row))
