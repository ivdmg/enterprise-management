from datetime import timedelta
from math import ceil
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import EmailStr, Field, model_validator
from sqlalchemy import text

from app.api.v1.company_config import _idempotency, _save, idempotency_key
from app.api.v1.platform_auth import Payload, platform_db_dependency
from app.api.v1.platform_companies import actor_for, company_lock, company_scope
from app.schemas.common import MetaModel, ResponseEnvelope
from app.services import platform_auth as auth
from app.services.platform_operations import record_platform_audit

router = APIRouter(prefix="/platform/companies/{company_id}")
INVITATION_COLUMNS = """
    id,email,role,CASE WHEN state='pending' AND expires_at<=now() THEN 'expired' ELSE state END AS state,
    created_at,expires_at,delivery_state,version
"""


class Invite(Payload):
    access_request_id: UUID | None = None
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: Literal["admin"] | None = None

    @model_validator(mode="after")
    def valid_source(self):
        director = (self.email, self.full_name, self.role)
        if (self.access_request_id is None and not all(director)) or (self.access_request_id and any(director)):
            raise ValueError("Provide either an access request or director details")
        return self


class Decision(Payload):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


def _page(page, limit, total):
    return MetaModel(page=page, limit=limit, total_items=total, total_pages=ceil(total / limit))


async def _invitation(db, company, invitation):
    row = (await db.execute(text("SELECT " + INVITATION_COLUMNS + """
        FROM company_invitations WHERE company_id=:company AND id=:id
    """), {"company": company, "id": invitation})).mappings().one_or_none()
    if not row:
        raise auth.auth_error(404, "NOT_FOUND", "Приглашение не найдено")
    return dict(row)


@router.get("/invitations")
async def invitations(company_id: UUID, request: Request, db: platform_db_dependency,
                      state: Literal["pending", "accepted", "revoked", "expired"] | None = None,
                      page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    await actor_for(request, db)
    await company_scope(db, company_id)
    table = f"FROM (SELECT {INVITATION_COLUMNS} FROM company_invitations WHERE company_id=:company) AS i"
    where = table + " WHERE CAST(:state AS text) IS NULL OR i.state=:state"
    params = {"company": company_id, "state": state, "limit": limit, "offset": (page - 1) * limit}
    count = await db.scalar(text("SELECT count(*) " + where), params)
    rows = await db.execute(text("SELECT * " + where + " ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset"), params)
    return ResponseEnvelope.ok([dict(row) for row in rows.mappings()], _page(page, limit, count))


@router.get("/access-requests")
async def access_requests(company_id: UUID, request: Request, db: platform_db_dependency,
                          state: Literal["pending", "invited", "fulfilled", "declined"] | None = None,
                          page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    await actor_for(request, db)
    await company_scope(db, company_id)
    where = "FROM company_access_requests WHERE company_id=:company AND (CAST(:state AS text) IS NULL OR state=:state)"
    params = {"company": company_id, "state": state, "limit": limit, "offset": (page - 1) * limit}
    count = await db.scalar(text("SELECT count(*) " + where), params)
    rows = await db.execute(text("SELECT id,email,full_name,role,state,created_at,version " +
                                 where + " ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset"), params)
    return ResponseEnvelope.ok([dict(row) for row in rows.mappings()], _page(page, limit, count))


async def _new_token(db, company_id, invitation, user, version, actor_id):
    token, _ = await auth.issue(db, "client_invite", user["user_id"], company_id, timedelta(hours=48),
                                payload={"version": user["user_version"], "invitation_id": str(invitation),
                                         "actor_id": str(actor_id)})
    await db.execute(text("""
        INSERT INTO invitation_outbox (invitation_id,company_id,invitation_version,token_ciphertext)
        VALUES (:invitation,:company,:version,:ciphertext)
        ON CONFLICT (invitation_id) DO UPDATE SET
          invitation_version=excluded.invitation_version,token_ciphertext=excluded.token_ciphertext,
          attempt_count=0,available_at=now()
    """), {"invitation": invitation, "company": company_id, "version": version,
           "ciphertext": auth.fernet().encrypt(token.encode()).decode()})


@router.post("/invitations", status_code=201)
async def invite(company_id: UUID, payload: Invite, request: Request, db: platform_db_dependency, key: idempotency_key):
    actor = await actor_for(request, db, owner=payload.access_request_id is None)
    company = await company_lock(db, company_id)
    scope, prior = await _idempotency(db, company_id, actor["id"], "invitation.create", key, payload.model_dump(mode="json"))
    if prior:
        return ResponseEnvelope.ok(prior)
    if company["state"] not in {"active", "draft"} or (payload.access_request_id and company["state"] != "active"):
        raise auth.auth_error(409, "CONFLICT", "Приглашение в текущем состоянии компании недоступно")
    request_id = payload.access_request_id
    if request_id:
        row = (await db.execute(text("""
            SELECT email,full_name,role,state FROM company_access_requests WHERE company_id=:company AND id=:id FOR UPDATE
        """), {"company": company_id, "id": request_id})).mappings().one_or_none()
        if not row:
            raise auth.auth_error(404, "NOT_FOUND", "Заявка не найдена")
        if row["state"] != "pending":
            raise auth.auth_error(409, "CONFLICT", "Заявка уже обработана")
        address, name, role = row["email"], row["full_name"], row["role"]
    else:
        address, name, role = payload.email.lower(), payload.full_name, payload.role
    user = (await db.execute(text("SELECT * FROM public.platform_prepare_invitee(:company,:email,:name,:role)"),
                             {"company": company_id, "email": address, "name": name, "role": role})).mappings().one_or_none()
    if not user:
        raise auth.auth_error(409, "CONFLICT", "Учётная запись уже существует")
    invite_id = await db.scalar(text("""
        INSERT INTO company_invitations (company_id,user_id,access_request_id,email,role,expires_at)
        VALUES (:company,:user,:request,:email,:role,now()+interval '48 hours')
        ON CONFLICT (company_id,user_id) WHERE state='pending' DO NOTHING RETURNING id
    """), {"company": company_id, "user": user["user_id"], "request": request_id, "email": address, "role": role})
    if not invite_id:
        raise auth.auth_error(409, "CONFLICT", "Приглашение уже существует. Перевыпустите его при необходимости")
    if request_id:
        await db.execute(text("""
            UPDATE company_access_requests SET state='invited',version=version+1 WHERE company_id=:company AND id=:id
        """), {"company": company_id, "id": request_id})
    await _new_token(db, company_id, invite_id, user, 1, actor["id"])
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action="invitation.create", entity_id=invite_id)
    return await _save(db, scope, jsonable_encoder(await _invitation(db, company_id, invite_id)))


async def _change(company_id, invitation_id, payload, request, db, *, reissue):
    actor = await actor_for(request, db)
    company = await company_lock(db, company_id)
    row = (await db.execute(text("""
        SELECT * FROM company_invitations WHERE company_id=:company AND id=:id FOR UPDATE
    """), {"company": company_id, "id": invitation_id})).mappings().one_or_none()
    if not row:
        raise auth.auth_error(404, "NOT_FOUND", "Приглашение не найдено")
    if row["role"] == "admin" and actor["role"] != "owner":
        raise auth.auth_error(403, "FORBIDDEN", "Действие доступно владельцу платформы")
    if row["version"] != payload.version:
        raise auth.auth_error(409, "STALE_REVISION", "Приглашение уже изменилось")
    if row["state"] != "pending" or (reissue and company["state"] not in {"active", "draft"}):
        raise auth.auth_error(409, "CONFLICT", "Действие с приглашением недоступно")
    user = (await db.execute(text("SELECT * FROM public.platform_pending_invitee(:company,:id)"),
                             {"company": company_id, "id": row["user_id"]})).mappings().one_or_none()
    if not user:
        raise auth.auth_error(409, "CONFLICT", "Приглашение уже недоступно")
    await auth.revoke_subject(db, user["user_id"], company_id)
    params = {"company": company_id, "id": invitation_id, "request": row["access_request_id"]}
    if reissue:
        await db.execute(text("""
            UPDATE company_invitations SET expires_at=now()+interval '48 hours',delivery_state='pending',version=version+1
            WHERE company_id=:company AND id=:id
        """), params)
        await _new_token(db, company_id, invitation_id, user, row["version"] + 1, actor["id"])
    else:
        await db.execute(text("""
            UPDATE company_invitations SET state='revoked',delivery_state='canceled',version=version+1
            WHERE company_id=:company AND id=:id
        """), params)
        await db.execute(text("DELETE FROM invitation_outbox WHERE company_id=:company AND invitation_id=:id"), params)
        if row["access_request_id"]:
            await db.execute(text("""
                UPDATE company_access_requests SET state='pending',version=version+1
                WHERE company_id=:company AND id=:request AND state='invited'
            """), params)
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id,
                                action="invitation.reissue" if reissue else "invitation.revoke", entity_id=invitation_id)
    return ResponseEnvelope.ok(await _invitation(db, company_id, invitation_id))


@router.post("/invitations/{invitation_id}/reissue")
async def reissue(company_id: UUID, invitation_id: UUID, payload: Decision, request: Request, db: platform_db_dependency):
    return await _change(company_id, invitation_id, payload, request, db, reissue=True)


@router.post("/invitations/{invitation_id}/revoke")
async def revoke(company_id: UUID, invitation_id: UUID, payload: Decision, request: Request, db: platform_db_dependency):
    return await _change(company_id, invitation_id, payload, request, db, reissue=False)


@router.post("/access-requests/{request_id}/decline")
async def decline(company_id: UUID, request_id: UUID, payload: Decision, request: Request, db: platform_db_dependency):
    actor = await actor_for(request, db)
    await company_lock(db, company_id)
    row = (await db.execute(text("""
        SELECT id,state,version FROM company_access_requests WHERE company_id=:company AND id=:id FOR UPDATE
    """), {"company": company_id, "id": request_id})).mappings().one_or_none()
    if not row:
        raise auth.auth_error(404, "NOT_FOUND", "Заявка не найдена")
    if row["version"] != payload.version or row["state"] != "pending":
        raise auth.auth_error(409, "STALE_REVISION", "Заявка уже изменена")
    result = (await db.execute(text("""
        UPDATE company_access_requests SET state='declined',version=version+1,decision_reason=:reason
        WHERE company_id=:company AND id=:id RETURNING id,email,full_name,role,state,version,created_at
    """), {"company": company_id, "id": request_id, "reason": payload.reason})).mappings().one()
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action="access_request.decline", entity_id=request_id)
    return ResponseEnvelope.ok(dict(result))
