import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import Field, model_validator
from sqlalchemy import text

from app.api.deps import get_current_user
from app.api.v1.platform_auth import Payload, db_dependency, platform_db_dependency
from app.core.database import set_tenant_context
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import ResponseEnvelope
from app.services import company_config as config
from app.services import platform_auth as auth
from app.services.platform_operations import record_platform_audit

router = APIRouter()
user_dependency = Annotated[User, Depends(get_current_user)]
idempotency_key = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
PATH = "/platform/companies/{company_id}/config"


class Module(Payload):
    id: str
    label: str | None = Field(default=None, min_length=1, max_length=80)
    order: int = Field(ge=0, le=100)
    enabled: bool
    settings: dict[str, str] = Field(default_factory=dict)


class Draft(Payload):
    base_revision: int = Field(ge=0)
    modules: list[Module] = Field(min_length=1, max_length=len(config.CATALOG))

    @model_validator(mode="after")
    def unique_catalog(self):
        ids = {item.id for item in self.modules}
        if len(ids) != len(self.modules) or not ids <= config.CATALOG.keys():
            raise ValueError("Invalid module catalog")
        # Integration adapters own their settings schema. UI module configs accept no free-form keys.
        if any(item.settings for item in self.modules):
            raise ValueError("Unsupported module settings")
        if not config.effective_modules([item.model_dump() for item in self.modules]):
            raise ValueError("Enable at least one available module")
        return self


class Transition(Payload):
    expected_active_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)


@router.get("/company/modules")
async def modules(user: user_dependency, db: db_dependency):
    revision = await config.current_revision(db, user.company_id)
    items = []
    for module in sorted(config.effective_modules(revision["modules"]), key=lambda item: (item["order"], item["id"])):
        item_id = module["id"]
        permissions = [f"{item_id}.read"]
        if user.role in (UserRole.ADMIN, UserRole.MANAGER) and (item_id != "settings" or user.role == UserRole.ADMIN):
            permissions.append(f"{item_id}.write")
        items.append({"id": item_id, "label": module["label"], "order": module["order"], "permissions": permissions})
    return ResponseEnvelope.ok({"revision": revision["revision"], "modules": items})


async def _platform_actor(request, db, company_id, *, owner=False, lock=False):
    actor = await auth.authenticate(request, db, platform=True)
    if owner and actor["role"] != "owner":
        raise auth.auth_error(403, "FORBIDDEN", "Изменение доступно владельцу платформы")
    if not await db.scalar(text("SELECT public.platform_company_exists(:company)"), {"company": company_id}):
        raise auth.auth_error(404, "NOT_FOUND", "Компания недоступна")
    await set_tenant_context(db, company_id)
    if lock:
        company = (await db.execute(text("SELECT state FROM public.platform_company_lock(:company)"),
                                    {"company": company_id})).scalar_one_or_none()
        if company == "closed":
            raise auth.auth_error(409, "CONFLICT", "Закрытая компания недоступна для изменений")
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                         {"scope": f"company-config:{company_id}"})
    return actor["id"]


async def _next_revision(db, company):
    return await db.scalar(text("""
        SELECT COALESCE(MAX(revision),0)+1 FROM company_config_revisions WHERE company_id=:company
    """), {"company": company})


async def _revision(db, company, number):
    query = await db.execute(text("""
        SELECT revision,base_revision,state,modules FROM company_config_revisions WHERE company_id=:company AND revision=:revision
    """), {"company": company, "revision": number})
    row = query.mappings().one_or_none()
    if not row:
        raise auth.auth_error(404, "NOT_FOUND", "Версия конфигурации недоступна")
    return dict(row) | {"version": number}


async def _idempotency(db, company, actor, action, key, payload):
    scope = {"company": company, "actor": actor, "action": action, "key": auth.token_hash(key)}
    digest = auth.token_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    row = (await db.execute(text("""
        SELECT request_hash,response FROM company_config_requests
        WHERE company_id=:company AND actor_id=:actor AND action=:action AND key_hash=:key
    """), scope)).mappings().one_or_none()
    if row and row["request_hash"] != digest:
        raise auth.auth_error(409, "CONFLICT", "Ключ запроса уже использован для другого действия")
    return scope | {"digest": digest}, row["response"] if row else None


async def _save(db, scope, result):
    await db.execute(text("""
        INSERT INTO company_config_requests (company_id,actor_id,action,key_hash,request_hash,response)
        VALUES (:company,:actor,:action,:key,:digest,CAST(:response AS jsonb))
    """), scope | {"response": json.dumps(result, ensure_ascii=False)})
    return ResponseEnvelope.ok(result)


@router.get(PATH)
async def get_config(company_id: UUID, request: Request, db: platform_db_dependency):
    await _platform_actor(request, db, company_id)
    result = await config.current_revision(db, company_id)
    drafts = await db.execute(text("""
        SELECT revision,state,modules FROM company_config_revisions
        WHERE company_id=:company AND state IN ('draft','archived') ORDER BY revision DESC LIMIT 30
    """), {"company": company_id})
    return ResponseEnvelope.ok(result | {"catalog": config.CATALOG,
        "revisions": [dict(row) | {"version": row["revision"]} for row in drafts.mappings()]})


@router.post(PATH + "/revisions", status_code=201)
async def draft_config(company_id: UUID, payload: Draft, request: Request, db: platform_db_dependency, key: idempotency_key):
    actor = await _platform_actor(request, db, company_id, lock=True)
    scope, prior = await _idempotency(db, company_id, actor, "draft", key, payload.model_dump())
    if prior:
        return ResponseEnvelope.ok(prior)
    if payload.base_revision != (await config.current_revision(db, company_id))["revision"]:
        raise auth.auth_error(409, "STALE_REVISION", "Активная конфигурация уже изменилась")
    revision = await _next_revision(db, company_id)
    items = [item.model_dump() | {"label": item.label or config.CATALOG[item.id]} for item in payload.modules]
    await db.execute(text("""
        INSERT INTO company_config_revisions (company_id,revision,base_revision,state,modules,actor_id)
        VALUES (:company,:revision,:base,'draft',CAST(:items AS jsonb),:actor)
    """), {"company": company_id, "revision": revision, "base": payload.base_revision,
           "items": json.dumps(items), "actor": actor})
    await record_platform_audit(db, actor_id=actor, company_id=company_id, action="config.draft")
    return await _save(db, scope, {"revision": revision, "version": revision, "state": "draft", "modules": items})


async def _activate(company_id, revision, payload, request, db, key, rollback):
    actor = await _platform_actor(request, db, company_id, owner=True, lock=True)
    action = "rollback" if rollback else "publish"
    scope, prior = await _idempotency(db, company_id, actor, action, key, payload.model_dump() | {"revision": revision})
    if prior:
        return ResponseEnvelope.ok(prior)
    current = await config.current_revision(db, company_id)
    if payload.expected_active_revision != current["revision"]:
        raise auth.auth_error(409, "STALE_REVISION", "Активная конфигурация уже изменилась")
    if rollback and revision == 0 and current["revision"] != 0:
        target = {"state": "archived", "modules": config.DEFAULT_MODULES}
    else:
        target = await _revision(db, company_id, revision)
    if target["state"] != ("archived" if rollback else "draft"):
        raise auth.auth_error(409, "CONFLICT", "Недопустимое состояние версии")
    if not rollback and target["base_revision"] != current["revision"]:
        raise auth.auth_error(409, "STALE_REVISION", "Черновик создан из прежней конфигурации")
    await db.execute(text("""
        UPDATE company_config_revisions SET state='archived' WHERE company_id=:company AND state='active'
    """), {"company": company_id})
    if rollback:
        revision = await _next_revision(db, company_id)
        await db.execute(text("""
            INSERT INTO company_config_revisions (company_id,revision,base_revision,state,modules,actor_id,reason)
            VALUES (:company,:revision,:base,'active',CAST(:items AS jsonb),:actor,:reason)
        """), {"company": company_id, "revision": revision, "items": json.dumps(target["modules"]),
               "base": current["revision"], "actor": actor, "reason": payload.reason})
    else:
        await db.execute(text("""
            UPDATE company_config_revisions SET state='active',actor_id=:actor,reason=:reason
            WHERE company_id=:company AND revision=:revision
        """), {"company": company_id, "revision": revision, "actor": actor, "reason": payload.reason})
    await record_platform_audit(db, actor_id=actor, company_id=company_id, action=f"config.{action}")
    return await _save(db, scope, {"revision": revision, "version": revision, "state": "active", "modules": target["modules"]})


@router.post(PATH + "/revisions/{revision}/publish")
async def publish(company_id: UUID, revision: int, payload: Transition, request: Request, db: platform_db_dependency, key: idempotency_key):
    return await _activate(company_id, revision, payload, request, db, key, False)


@router.post(PATH + "/revisions/{revision}/rollback")
async def rollback(company_id: UUID, revision: int, payload: Transition, request: Request, db: platform_db_dependency, key: idempotency_key):
    return await _activate(company_id, revision, payload, request, db, key, True)
