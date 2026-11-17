from math import ceil
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import EmailStr, Field
from sqlalchemy import text

from app.api.v1.company_config import _idempotency, _save, idempotency_key
from app.api.v1.platform_auth import Payload, platform_db_dependency
from app.core.database import set_tenant_context
from app.schemas.common import MetaModel, ResponseEnvelope
from app.services import company_config
from app.services import platform_auth as auth
from app.services.platform_operations import record_platform_audit

router = APIRouter(prefix="/platform/companies")


class Create(Payload):
    code: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    name: str = Field(min_length=1, max_length=255)


class Transition(Payload):
    version: int = Field(ge=1)
    to: Literal["active", "paused", "closed"]
    reason: str = Field(min_length=1, max_length=500)


class DirectorTransfer(Payload):
    version: int = Field(ge=1)
    current_email: EmailStr
    successor_email: EmailStr
    reason: str = Field(min_length=1, max_length=500)


async def actor_for(request, db, *, owner=False):
    actor = await auth.authenticate(request, db, platform=True)
    if owner and actor["role"] != "owner":
        raise auth.auth_error(403, "FORBIDDEN", "Действие доступно владельцу платформы")
    return actor


async def company_lock(db, company_id):
    row = (await db.execute(text("SELECT * FROM public.platform_company_lock(:company)"),
                            {"company": company_id})).mappings().one_or_none()
    if not row:
        raise auth.auth_error(404, "NOT_FOUND", "Компания не найдена")
    await set_tenant_context(db, company_id)
    return row


async def company_scope(db, company_id):
    if not await db.scalar(text("SELECT public.platform_company_exists(:company)"), {"company": company_id}):
        raise auth.auth_error(404, "NOT_FOUND", "Компания не найдена")
    await set_tenant_context(db, company_id)


def _summary(row):
    modules = row["modules"]
    if modules is None:
        modules = company_config.DEFAULT_MODULES if row["state"] != "draft" else []
    safe = [{"id": item["id"], "label": item["label"]} for item in company_config.effective_modules(modules)]
    return dict(row) | {"modules": safe, "assignee_id": None}


async def _detail(db, company_id):
    row = (await db.execute(text("SELECT * FROM public.platform_company_summary(:id)"),
                            {"id": company_id})).mappings().one_or_none()
    if not row:
        raise auth.auth_error(404, "NOT_FOUND", "Компания не найдена")
    return _summary(row)


@router.get("")
async def list_companies(request: Request, db: platform_db_dependency,
                         state: Literal["draft", "active", "paused", "closed"] | None = None,
                         health: Literal["healthy", "degraded", "unknown"] | None = None,
                         search: str | None = Query(None, max_length=100),
                         page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    await actor_for(request, db)
    query = """
        FROM public.platform_company_summary(NULL) AS c
        WHERE (:state IS NULL OR c.state=:state) AND (:health IS NULL OR c.health=:health)
          AND (:search IS NULL OR strpos(lower(c.name),lower(:search))>0 OR strpos(c.code,lower(:search))>0)
    """
    params = {"state": state, "health": health, "search": search, "limit": limit, "offset": (page - 1) * limit}
    # Explicit casts ensure asyncpg infers types for optional filter arguments.
    for key in ("state", "health", "search"):
        query = query.replace(f":{key} IS NULL", f"CAST(:{key} AS text) IS NULL")
    total = await db.scalar(text("SELECT count(*) " + query), params)
    rows = await db.execute(text("SELECT c.* " + query + " ORDER BY c.name,c.id LIMIT :limit OFFSET :offset"), params)
    return ResponseEnvelope.ok([_summary(row) for row in rows.mappings()],
                               MetaModel(page=page, limit=limit, total_items=total, total_pages=ceil(total / limit)))


@router.post("", status_code=201)
async def create_company(payload: Create, request: Request, db: platform_db_dependency, key: idempotency_key):
    actor = await actor_for(request, db, owner=True)
    # Stable generated company ID also provides idempotency across retries before the tenant exists.
    company_id = uuid5(NAMESPACE_URL, f"seh:{actor['id']}:company:{auth.token_hash(key)}")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"), {"scope": str(company_id)})
    existing = await db.scalar(text("SELECT public.platform_company_exists(:company)"), {"company": company_id})
    if not existing:
        created = await db.scalar(text("SELECT public.platform_company_create(:id,:code,:name)"),
                                  payload.model_dump() | {"id": company_id})
        if not created:
            raise auth.auth_error(409, "CONFLICT", "Код компании уже используется")
    await set_tenant_context(db, company_id)
    scope, prior = await _idempotency(db, company_id, actor["id"], "company.create", key, payload.model_dump())
    if prior is not None:
        return ResponseEnvelope.ok(prior)
    result = await _detail(db, company_id)
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action="company.create", entity_id=company_id)
    return await _save(db, scope, jsonable_encoder(result))


@router.get("/{company_id}")
async def get_company(company_id: UUID, request: Request, db: platform_db_dependency):
    actor = await actor_for(request, db)
    result = await _detail(db, company_id)
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action="company.open", entity_id=company_id)
    return ResponseEnvelope.ok(result)


@router.post("/{company_id}/transitions")
async def transition_company(company_id: UUID, payload: Transition, request: Request, db: platform_db_dependency,
                             key: idempotency_key):
    actor = await actor_for(request, db, owner=True)
    await company_lock(db, company_id)
    scope, prior = await _idempotency(db, company_id, actor["id"], "company.transition", key, payload.model_dump())
    if prior is not None:
        return ResponseEnvelope.ok(prior)
    code = await db.scalar(text("SELECT public.platform_company_transition(:company,:version,:state)"),
                           {"company": company_id, "version": payload.version, "state": payload.to})
    if code != "OK":
        message = "Сначала опубликуйте конфигурацию, подтвердите источники и пригласите директора" if code == "COMPANY_NOT_READY" else "Переход недоступен"
        raise auth.auth_error(409, code, message)
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action=f"company.{payload.to}",
                                entity_id=company_id)
    return await _save(db, scope, jsonable_encoder(await _detail(db, company_id)))


@router.post("/{company_id}/director-transfer")
async def transfer_director(company_id: UUID, payload: DirectorTransfer, request: Request, db: platform_db_dependency,
                            key: idempotency_key):
    actor = await actor_for(request, db, owner=True)
    await company_lock(db, company_id)
    scope, prior = await _idempotency(db, company_id, actor["id"], "company.director_transfer", key, payload.model_dump())
    if prior:
        return ResponseEnvelope.ok(prior)
    code = await db.scalar(text("SELECT public.platform_transfer_director(:company,:version,:old,:new)"),
                           {"company": company_id, "version": payload.version, "old": payload.current_email.lower(),
                            "new": payload.successor_email.lower()})
    if code != "OK":
        raise auth.auth_error(409, code, "Передача требует двух действующих учётных записей директора")
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action="company.director_transfer",
                                entity_id=company_id)
    return await _save(db, scope, jsonable_encoder(await _detail(db, company_id)))
