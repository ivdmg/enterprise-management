from math import ceil
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_config import _idempotency, _save, idempotency_key
from app.api.v1.platform_auth import Payload, platform_db_dependency
from app.api.v1.platform_companies import actor_for, company_lock, company_scope
from app.core.config import settings
from app.schemas.common import MetaModel, ResponseEnvelope
from app.services import integration_jobs as jobs
from app.services import platform_auth as auth
from app.services.platform_operations import record_platform_audit

router = APIRouter(prefix="/platform/companies/{company_id}")
INTEGRATION_COLUMNS = ", ".join(jobs.SAFE_INTEGRATION_COLUMNS)
RUN_COLUMNS = ", ".join(jobs.SAFE_RUN_COLUMNS)


class IntegrationCreate(Payload):
    label: str = Field(min_length=1, max_length=160)
    adapter_version: str = Field(min_length=1, max_length=32)
    source_ref: str = Field(pattern=r"^[A-Za-z0-9_-]{1,255}$")
    secret_ref: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")
    schedule: int | None = Field(default=None, ge=60, le=86400)
    stale_after_seconds: int = Field(ge=60, le=604800)
    enabled: bool = True
    type: Literal["google_drive", "test_workbook"]
    adapter_id: str = Field(min_length=1, max_length=64)
    module_id: str = Field(min_length=1, max_length=64)


class IntegrationPatch(Payload):
    version: int = Field(ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=160)
    adapter_version: str | None = Field(default=None, min_length=1, max_length=32)
    source_ref: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,255}$")
    secret_ref: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")
    schedule: int | None = Field(default=None, ge=60, le=86400)
    stale_after_seconds: int | None = Field(default=None, ge=60, le=604800)
    enabled: bool | None = None

    @model_validator(mode="after")
    def non_nullable(self):
        for field in ("label", "adapter_version", "source_ref", "stale_after_seconds", "enabled"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError("Invalid null field")
        return self


class RunApproval(Payload):
    expected_integration_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=256)


class RunCreate(RunApproval):
    mode: Literal["preview", "import"]
    approved_preview_id: UUID | None = None


def _validate_profile(provider, adapter_id, adapter_version, module_id, secret_ref, *, check_secret=True):
    if jobs.ADAPTERS.get(adapter_id) != (adapter_version, module_id):
        raise auth.auth_error(422, "VALIDATION_ERROR", "Адаптер или версия отсутствуют в каталоге")
    if provider == "google_drive" and check_secret and not secret_ref:
        raise auth.auth_error(422, "VALIDATION_ERROR", "Укажите ссылку на ключ источника")
    if provider == "test_workbook" and (secret_ref or not settings.ENVIRONMENT.endswith("test")):
        raise auth.auth_error(422, "VALIDATION_ERROR", "Тестовый источник недоступен")


def _job_error(exc):
    status = {"NOT_FOUND": 404, "VALIDATION_ERROR": 422, "MODULE_DISABLED": 403}.get(exc.code, 409)
    return auth.auth_error(status, exc.code, "Действие с источником недоступно")


def _writes_enabled():
    if not settings.INTEGRATIONS_ENABLED:
        raise auth.auth_error(404, "NOT_FOUND", "Интеграции недоступны")


@router.get("/integrations")
async def integrations(company_id: UUID, request: Request, db: platform_db_dependency):
    await actor_for(request, db)
    await company_scope(db, company_id)
    return ResponseEnvelope.ok(await jobs.list_integrations(db, company_id, platform_scope=True))


@router.post("/integrations", status_code=201)
async def create_integration(company_id: UUID, payload: IntegrationCreate, request: Request,
                             db: platform_db_dependency, key: idempotency_key):
    _writes_enabled()
    actor = await actor_for(request, db)
    state = await company_lock(db, company_id)
    scope, prior = await _idempotency(db, company_id, actor["id"], "integration.create", key, payload.model_dump())
    if prior:
        return ResponseEnvelope.ok(prior)
    if state["state"] in {"closed", "paused"}:
        raise auth.auth_error(409, "CONFLICT", "Изменения источников недоступны")
    _validate_profile(payload.type, payload.adapter_id, payload.adapter_version, payload.module_id, payload.secret_ref)
    row = (await db.execute(text(f"""
        INSERT INTO company_integrations (company_id,provider,label,module_id,adapter_id,adapter_version,
                                          source_ref,secret_ref,schedule_seconds,stale_after_seconds,enabled)
        VALUES (:company,:type,:label,:module_id,:adapter_id,:adapter_version,:source_ref,:secret_ref,:schedule,
                :stale_after_seconds,:enabled)
        ON CONFLICT DO NOTHING RETURNING {INTEGRATION_COLUMNS}
    """), payload.model_dump() | {"company": company_id})).mappings().one_or_none()
    if not row:
        raise auth.auth_error(409, "CONFLICT", "Источник уже подключён")
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action="integration.create", entity_id=row["id"])
    return await _save(db, scope, jsonable_encoder(jobs.integration_status(row, now=auth.now())))


@router.get("/integrations/{integration_id}")
async def integration(company_id: UUID, integration_id: UUID, request: Request, db: platform_db_dependency):
    await actor_for(request, db)
    await company_scope(db, company_id)
    item = next((row for row in await jobs.list_integrations(db, company_id, platform_scope=True)
                 if row["id"] == integration_id), None)
    if not item:
        raise auth.auth_error(404, "NOT_FOUND", "Источник не найден")
    return ResponseEnvelope.ok(item)


@router.patch("/integrations/{integration_id}")
async def patch_integration(company_id: UUID, integration_id: UUID, payload: IntegrationPatch,
                            request: Request, db: platform_db_dependency):
    _writes_enabled()
    actor = await actor_for(request, db)
    state = await company_lock(db, company_id)
    if state["state"] in {"closed", "paused"}:
        raise auth.auth_error(409, "CONFLICT", "Изменения источников недоступны")
    row = await jobs.get_integration(db, company_id, integration_id, for_update=True, platform_scope=True)
    if not row:
        raise auth.auth_error(404, "NOT_FOUND", "Источник не найден")
    if row["version"] != payload.version:
        raise auth.auth_error(409, "STALE_REVISION", "Источник уже изменился")
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if not changes:
        raise auth.auth_error(422, "VALIDATION_ERROR", "Укажите, что изменить")
    if "schedule" in changes:
        changes["schedule_seconds"] = changes.pop("schedule")
    merged = dict(row) | changes
    _validate_profile(merged["provider"], merged["adapter_id"], merged["adapter_version"], merged["module_id"],
                      changes.get("secret_ref"), check_secret="secret_ref" in changes)
    # Keys come only from the closed IntegrationPatch schema.
    assignments = ", ".join(f"{field}=:{field}" for field in changes)
    params = changes | {"company": company_id, "id": integration_id}
    try:
        updated = (await db.execute(text(f"""
            UPDATE company_integrations SET {assignments},version=version+1,next_due_at=clock_timestamp()
            WHERE company_id=:company AND id=:id RETURNING {INTEGRATION_COLUMNS}
        """), params)).mappings().one()
    except IntegrityError:
        raise auth.auth_error(409, "CONFLICT", "Источник уже подключён") from None
    await db.execute(text("""
        UPDATE integration_runs SET state='canceled',lease_until=NULL,finished_at=clock_timestamp()
        WHERE company_id=:company AND integration_id=:id AND state IN ('queued','running','retry_wait')
    """), params)
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action="integration.update", entity_id=integration_id)
    return ResponseEnvelope.ok(jobs.integration_status(updated, now=auth.now()))


@router.post("/integrations/{integration_id}/runs", status_code=202)
async def enqueue(company_id: UUID, integration_id: UUID, payload: RunCreate, request: Request,
                  db: platform_db_dependency, key: idempotency_key):
    _writes_enabled()
    actor = await actor_for(request, db)
    state = await company_lock(db, company_id)
    scope, prior = await _idempotency(db, company_id, actor["id"], "integration.enqueue", key,
                                      payload.model_dump(mode="json") | {"integration_id": str(integration_id)})
    if prior:
        return ResponseEnvelope.ok(prior)
    if state["state"] not in {"active", "draft"} or (payload.mode == "import" and state["state"] != "active"):
        raise auth.auth_error(409, "CONFLICT", "Запуск в текущем состоянии компании недоступен")
    try:
        result = await jobs.enqueue_run(db, company_id=company_id, integration_id=integration_id,
                                        company_active=state["state"] == "active",
                                        platform_scope=True,
                                        request_id=getattr(request.state, "request_id", None),
                                        idempotency_key=auth.token_hash(f"{actor['id']}:{key}"), **payload.model_dump())
    except jobs.JobError as exc:
        raise _job_error(exc) from None
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action=f"integration.{payload.mode}",
                                entity_id=result["id"], correlation_id=result["request_id"])
    return await _save(db, scope, jsonable_encoder(result))


@router.post("/runs/{run_id}/approve")
async def approve(company_id: UUID, run_id: UUID, payload: RunApproval, request: Request,
                  db: platform_db_dependency, key: idempotency_key):
    _writes_enabled()
    actor = await actor_for(request, db, owner=True)
    state = await company_lock(db, company_id)
    scope, prior = await _idempotency(db, company_id, actor["id"], "integration.approve", key,
                                      payload.model_dump() | {"run_id": str(run_id)})
    if prior:
        return ResponseEnvelope.ok(prior)
    if state["state"] not in {"active", "draft"}:
        raise auth.auth_error(409, "CONFLICT", "Подтверждение недоступно")
    try:
        result = await jobs.approve_preview(db, company_id=company_id, run_id=run_id,
                                            expected_integration_version=payload.expected_integration_version, platform_scope=True)
    except jobs.JobError as exc:
        raise _job_error(exc) from None
    await record_platform_audit(db, actor_id=actor["id"], company_id=company_id, action="integration.approve", entity_id=run_id)
    return await _save(db, scope, jsonable_encoder(result))


@router.get("/runs")
async def runs(company_id: UUID, request: Request, db: platform_db_dependency,
               integration_id: UUID | None = None,
               state: Literal["queued", "running", "retry_wait", "succeeded", "failed", "canceled"] | None = None,
               page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    await actor_for(request, db)
    await company_scope(db, company_id)
    where = """
        FROM integration_runs WHERE company_id=:company
          AND (CAST(:integration AS uuid) IS NULL OR integration_id=:integration)
          AND (CAST(:state AS text) IS NULL OR state=:state)
    """
    params = {"company": company_id, "integration": integration_id, "state": state,
              "limit": limit, "offset": (page - 1) * limit}
    total = await db.scalar(text("SELECT count(*) " + where), params)
    rows = await db.execute(text(f"SELECT {RUN_COLUMNS} " + where + " ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset"), params)
    return ResponseEnvelope.ok([jobs.run_summary(row) for row in rows.mappings()],
                               MetaModel(page=page, limit=limit, total_items=total, total_pages=ceil(total / limit)))


@router.get("/runs/{run_id}")
async def run(company_id: UUID, run_id: UUID, request: Request, db: platform_db_dependency):
    await actor_for(request, db)
    await company_scope(db, company_id)
    row = await jobs.get_run(db, company_id, run_id, platform_scope=True)
    if not row:
        raise auth.auth_error(404, "NOT_FOUND", "Запуск не найден")
    return ResponseEnvelope.ok(jobs.run_summary(row))
