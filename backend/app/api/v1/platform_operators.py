from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import EmailStr, Field
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.api.v1.platform_auth import Invitation, Payload, _unavailable, platform_db_dependency as db_dependency
from app.core.security import get_password_hash
from app.schemas.common import ResponseEnvelope
from app.services import platform_auth as service
from app.services.auth_mail import send_link
from app.services.platform_operations import record_platform_audit

router = APIRouter(prefix="/platform")


class Invite(Payload):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: Literal["support", "owner"]


class PatchOperator(Payload):
    is_active: bool


async def _owner(request, db):
    actor = await service.authenticate(request, db, platform=True)
    if actor["role"] != "owner":
        raise service.auth_error(403, "FORBIDDEN", "Действие доступно владельцу платформы")
    return actor


@router.get("/operators")
async def operators(request: Request, db: db_dependency):
    await _owner(request, db)
    rows = await db.execute(text("SELECT id,email,full_name,role,is_active FROM platform_operators ORDER BY email,id"))
    return ResponseEnvelope.ok([dict(row) for row in rows.mappings()])


@router.post("/operators", status_code=201)
async def invite_operator(payload: Invite, request: Request, db: db_dependency):
    actor = await _owner(request, db)
    user = (await db.execute(text("""
        INSERT INTO platform_operators (id,email,full_name,role,password_hash,is_active)
        VALUES (:id,:email,:full_name,:role,'!invited',false)
        ON CONFLICT (email) DO UPDATE SET full_name=excluded.full_name
        WHERE platform_operators.password_hash='!invited' AND NOT platform_operators.is_active
          AND platform_operators.role=excluded.role
        RETURNING id
    """), payload.model_dump() | {"id": uuid4(), "email": payload.email.lower()})).mappings().one_or_none()
    if not user:
        raise service.auth_error(409, "CONFLICT", "Учётная запись уже существует")
    await db.execute(text("""
        UPDATE auth_grants SET revoked_at=now()
        WHERE purpose='platform_invite' AND subject_id=:id AND revoked_at IS NULL
    """), {"id": user["id"]})
    token, expiry = await service.issue(db, "platform_invite", user["id"], None, timedelta(hours=48),
                                        payload={"actor_id": str(actor["id"])})
    await record_platform_audit(db, actor_id=actor["id"], company_id=None,
                                action="operator.invite", entity_id=user["id"])
    await db.commit()
    try:
        await send_link(payload.email, None, "invite", token)
    except Exception:
        await db.execute(text("DELETE FROM platform_operators WHERE id=:id AND password_hash='!invited'"),
                         {"id": user["id"]})
        await db.execute(text("UPDATE auth_grants SET revoked_at=now() WHERE token_hash=:hash"),
                         {"hash": service.token_hash(token)})
        await db.commit()
        raise service.auth_error(503, "SERVICE_UNAVAILABLE", "Не удалось отправить приглашение") from None
    return ResponseEnvelope.ok({"id": user["id"], "expires_at": expiry})


@router.post("/auth/invitation/accept")
async def activate_operator(payload: Invitation, request: Request, db: db_dependency):
    service.validate_csrf(request, True, anonymous=True)
    await service.rate_limit(request, "platform_invite_accept", identity=payload.token)
    row = await service.grant(db, "platform_invite", payload.token)
    if not service.active(row):
        raise _unavailable()
    operator = await service.get_principal(db, row["subject_id"], None, lock=True)
    row = await service.grant(db, "platform_invite", payload.token, lock=True)
    if not service.active(row) or not operator or operator["is_active"] or operator["password_hash"] != "!invited":
        raise _unavailable()
    if len(payload.password.encode()) > 72:
        raise service.auth_error(422, "VALIDATION_ERROR", "Пароль превышает допустимую длину")
    await db.execute(text("""
        UPDATE platform_operators SET full_name=:name, password_hash=:password, is_active=true WHERE id=:id
    """), {"name": payload.full_name, "password": await run_in_threadpool(get_password_hash, payload.password),
           "id": operator["id"]})
    await service.consume(db, row)
    return ResponseEnvelope.ok({"state": "accepted"})


@router.patch("/operators/{operator_id}")
async def update_operator(operator_id: UUID, payload: PatchOperator, request: Request, db: db_dependency):
    await _owner(request, db)
    # Serialize owner activation changes so two owners cannot both disable one another.
    await db.execute(text("SELECT pg_advisory_xact_lock(284619634731)"))
    actor = await _owner(request, db)
    target = await service.get_principal(db, operator_id, None, lock=True)
    if not target:
        raise service.auth_error(404, "NOT_FOUND", "Оператор не найден")
    if target["role"] == "owner" and target["id"] == actor["id"] and not payload.is_active:
        raise service.auth_error(409, "CONFLICT", "Попросите другого владельца изменить ваш доступ")
    if payload.is_active and target["password_hash"] == "!invited":
        raise service.auth_error(409, "CONFLICT", "Приглашение ещё не принято")
    await db.execute(text("UPDATE platform_operators SET is_active=:active WHERE id=:id"),
                     {"id": operator_id, "active": payload.is_active})
    if not payload.is_active:
        await db.execute(text("""
            UPDATE auth_grants SET revoked_at=now()
            WHERE company_id IS NULL AND subject_id=:id AND revoked_at IS NULL
        """), {"id": operator_id})
    await record_platform_audit(db, actor_id=actor["id"], company_id=None,
                                action="operator.enable" if payload.is_active else "operator.disable",
                                entity_id=operator_id)
    return ResponseEnvelope.ok({"id": operator_id, "is_active": payload.is_active})
