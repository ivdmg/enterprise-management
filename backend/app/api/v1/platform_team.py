from datetime import timedelta
from math import ceil
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import EmailStr, Field, StringConstraints
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_active_admin
from app.api.v1.platform_auth import Link, Payload, db_dependency, _unavailable
from app.core.security import verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import MetaModel, ResponseEnvelope
from app.services import platform_auth as service
from app.services.audit import record_audit_log
from app.services.auth_mail import notify_email_change, send_link

router = APIRouter()
director = Annotated[User, Depends(get_current_active_admin)]


class ChangeUser(Payload):
    version: int = Field(ge=1)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: Literal["manager", "viewer"] | None = None
    is_active: bool | None = None


class ChangeEmail(Payload):
    version: int = Field(ge=1)
    new_email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=255, strip_whitespace=False)]


class AccessRequest(Payload):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: Literal["manager", "viewer"]
    reason: str | None = Field(default=None, max_length=1000)


def _item(user):
    return {key: getattr(user, key) for key in ("id", "full_name", "email", "role", "is_active", "version")}


def _meta(page: int, limit: int, count: int):
    return MetaModel(page=page, limit=limit, total_items=count, total_pages=ceil(count / limit))


@router.get("/company/users")
async def list_users(actor: director, db: db_dependency, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    predicate = User.company_id == actor.company_id
    total = await db.scalar(select(func.count()).select_from(User).where(predicate))
    users = await db.scalars(select(User).where(predicate).order_by(User.created_at, User.id)
                            .limit(limit).offset((page - 1) * limit))
    return ResponseEnvelope.ok([_item(user) for user in users], _meta(page, limit, total))


async def _target(actor, db, user_id, version):
    user = await service.get_principal(db, user_id, actor.company_id, lock=True)
    if not user:
        raise service.auth_error(404, "NOT_FOUND", "Сотрудник не найден")
    if user.role == UserRole.ADMIN:
        raise service.auth_error(409, "LAST_DIRECTOR", "Полномочия директора изменяются через владельца платформы")
    if user.version != version:
        raise service.auth_error(409, "STALE_REVISION", "Данные сотрудника уже изменились")
    return user


@router.patch("/company/users/{user_id}")
async def change_user(user_id: UUID, payload: ChangeUser, actor: director, db: db_dependency):
    user = await _target(actor, db, user_id, payload.version)
    if user.password_hash == "!invited":
        raise service.auth_error(409, "CONFLICT", "Приглашение ещё не принято")
    revoke = False
    before = f"{'active' if user.is_active else 'disabled'}:{user.role.value}"
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None and payload.role != user.role.value:
        user.role = UserRole(payload.role)
        revoke = True
    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        revoke = True
    user.version += 1
    if revoke:
        await service.revoke_subject(db, user.id, user.company_id)
    after = f"{'active' if user.is_active else 'disabled'}:{user.role.value}"
    await record_audit_log(db, actor.company_id, "team_user", user.id, before,
                           after if before != after else "profile_updated", actor.id)
    return ResponseEnvelope.ok(_item(user))


@router.post("/company/users/{user_id}/email-change", status_code=202)
async def change_email(user_id: UUID, payload: ChangeEmail, actor: director, db: db_dependency, request: Request):
    await service.rate_limit(request, "email_change", 6, identity=str(actor.id))
    if not await run_in_threadpool(verify_password, payload.password, actor.password_hash):
        raise service.auth_error(401, "INVALID_CREDENTIALS", "Неверный пароль")
    user = await _target(actor, db, user_id, payload.version)
    email = payload.new_email.lower()
    if not user.is_active or await db.scalar(select(User.id).where(User.company_id == actor.company_id, User.email == email)):
        raise service.auth_error(409, "CONFLICT", "Смена адреса недоступна")
    user.version += 1
    token, _ = await service.issue(db, "client_email", user.id, user.company_id, timedelta(hours=24),
                                   payload={"email": email, "version": user.version})
    await record_audit_log(db, actor.company_id, "team_user", user.id, None, "email_change_requested", actor.id)
    await db.commit()
    try:
        await notify_email_change(user.email)
        await send_link(email, user.company.code, "email-change", token)
    except Exception:
        row = await service.grant(db, "client_email", token, lock=True)
        await service.consume(db, row)
        await db.commit()
        raise service.auth_error(503, "SERVICE_UNAVAILABLE", "Не удалось отправить подтверждение") from None
    return ResponseEnvelope.ok({"state": "accepted"})


@router.post("/auth/email-change/confirm")
async def confirm_email(payload: Link, request: Request, db: db_dependency):
    service.validate_csrf(request, False, anonymous=True)
    await service.rate_limit(request, "client_link", identity=payload.token)
    row = await service.grant(db, "client_email", payload.token)
    if not service.active(row):
        raise _unavailable()
    user = await service.get_principal(db, row["subject_id"], row["company_id"], lock=True)
    row = await service.grant(db, "client_email", payload.token, lock=True)
    if (not service.active(row) or not user or not user.is_active or not user.company.is_active
            or user.version != row["payload"].get("version")):
        raise _unavailable()
    user.email = row["payload"]["email"]
    user.version += 1
    try:
        await db.flush()
    except IntegrityError:
        raise _unavailable() from None
    await service.consume(db, row)
    await service.revoke_subject(db, user.id, user.company_id)
    await record_audit_log(db, user.company_id, "team_user", user.id, None, "email_change_confirmed", user.id)
    return ResponseEnvelope.ok({"state": "accepted"})


@router.get("/company/access-requests")
async def access_requests(actor: director, db: db_dependency, state: Literal["pending", "invited", "fulfilled", "declined"] | None = None,
                          page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    where = "WHERE company_id=:company"
    params = {"company": actor.company_id, "limit": limit, "offset": (page - 1) * limit}
    if state:
        where += " AND state=:state"
        params["state"] = state
    count = await db.scalar(text("SELECT count(*) FROM company_access_requests " + where), params)
    rows = await db.execute(text("SELECT id,email,role,state,created_at,version FROM company_access_requests "
                                 + where + " ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset"), params)
    return ResponseEnvelope.ok([dict(row) for row in rows.mappings()], _meta(page, limit, count))


@router.post("/company/access-requests", status_code=201)
async def new_access_request(payload: AccessRequest, actor: director, db: db_dependency):
    query = await db.execute(text("""
        INSERT INTO company_access_requests (id,company_id,email,full_name,role,reason)
        VALUES (:id,:company,:email,:full_name,:role,:reason)
        RETURNING id,email,role,state,created_at,version
    """), payload.model_dump() | {"id": uuid4(), "company": actor.company_id, "email": payload.email.lower()})
    row = dict(query.mappings().one())
    await record_audit_log(db, actor.company_id, "access_request", row["id"], None, "pending", actor.id)
    return ResponseEnvelope.ok(row)
