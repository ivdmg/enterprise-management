"""Tenant-scoped enqueue, publication and operational projections for integration runs."""

import asyncio
from datetime import date, datetime, timedelta
import hashlib
from io import BytesIO
import json
import logging
from pathlib import Path
import re
from uuid import UUID, uuid4
from zipfile import ZipFile

import openpyxl
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory, set_tenant_context
from app.models.enums import FileStatus
from app.models.file import UploadedFile
from app.models.task import OperationalTask
from app.services.company_config import current_revision, effective_modules
from app.services.customer_tenders import (
    WorkbookShapeError,
    contract_amount,
    persist_customer_workbook,
    read_customer_workbook,
)
from app.services.google_drive import DriveFileTooLarge, GoogleDriveClient, google_drive_client
from app.services.storage import build_tenant_storage_key, storage_service


logger = logging.getLogger(__name__)
ADAPTERS = {"customer_tenders": ("v1", "projects"), "equipment_registry": ("v1", "tasks")}
ACTIVE_STATES = {"queued", "running", "retry_wait"}
SAFE_INTEGRATION_COLUMNS = (
    "id", "company_id", "provider", "label", "module_id", "adapter_id", "adapter_version",
    "enabled", "schedule_seconds", "stale_after_seconds", "version", "last_attempt_at",
    "last_success_at", "last_success_version", "last_error_code",
)
RUN_SUMMARY_COLUMNS = (
    "id", "integration_id", "mode", "state", "attempt_count", "adapter_version", "release_version",
    "request_id", "created_at", "started_at", "finished_at", "rows_processed", "warning_count",
)
SAFE_RUN_COLUMNS = RUN_SUMMARY_COLUMNS + (
    "company_id", "integration_version", "config_revision", "available_at", "error_code",
    "idempotency_key", "reason", "approved_preview_id",
)
ERRORS = {
    "SOURCE_ACCESS_REVOKED": ("Доступ к источнику недоступен", "Проверьте права на файл"),
    "SOURCE_RATE_LIMITED": ("Источник временно ограничил запросы", "Дождитесь повтора"),
    "SOURCE_TIMEOUT": ("Источник не ответил вовремя", "Дождитесь повтора"),
    "SOURCE_UNAVAILABLE": ("Источник временно недоступен", "Дождитесь повтора"),
    "SOURCE_TOO_LARGE": ("Файл превышает лимит импорта", "Уменьшите размер файла"),
    "SCHEMA_MISMATCH": ("Структура таблицы не соответствует адаптеру", "Сверьте листы и заголовки"),
    "PREVIEW_STALE": ("Источник изменился после проверки", "Выполните новый предварительный импорт"),
    "WORKER_LEASE_EXPIRED": ("Обработка прервалась", "Проверьте состояние обработчика"),
    "IMPORT_FAILED": ("Не удалось опубликовать данные", "Передайте идентификатор запуска разработчику"),
}
RETRYABLE = {"SOURCE_RATE_LIMITED", "SOURCE_TIMEOUT", "SOURCE_UNAVAILABLE"}


class JobError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class StaleLease(Exception):
    pass


def error_summary(code: str | None, request_id: str | None = None) -> dict | None:
    if not code:
        return None
    message, next_step = ERRORS.get(code, ERRORS["IMPORT_FAILED"])
    return {"code": code, "message": message, "next_step": next_step, "request_id": request_id}


def integration_status(integration, *, now: datetime, latest_run=None) -> dict:
    last_success = integration["last_success_at"]
    code = integration["last_error_code"]
    if latest_run and latest_run["state"] == "failed":
        code = latest_run["error_code"]
    if not integration["enabled"]:
        status = "paused"
    elif latest_run and latest_run["state"] in ACTIVE_STATES:
        status = "running"
    elif code:
        status = "needs_attention"
    elif last_success is None:
        status = "unchecked"
    elif last_success < now - timedelta(seconds=integration["stale_after_seconds"]):
        status = "stale"
    else:
        status = "current"
    return {
        "id": integration["id"], "label": integration["label"], "type": integration["provider"],
        "module_id": integration["module_id"], "adapter_id": integration["adapter_id"],
        "adapter_version": integration["adapter_version"], "status": status,
        "last_success_at": last_success, "last_attempt_at": integration["last_attempt_at"],
        "next_attempt_at": latest_run["available_at"] if latest_run and latest_run["state"] == "retry_wait" else None,
        "stale_after_seconds": integration["stale_after_seconds"], "version": integration["version"],
        "error": error_summary(code, latest_run["request_id"] if latest_run else None),
    }


def run_summary(run) -> dict:
    return {key: run[key] for key in RUN_SUMMARY_COLUMNS} | {
        "error": error_summary(run["error_code"], run["request_id"])
    }


async def get_integration(db, company_id: UUID, integration_id: UUID, *, for_update=False, platform_scope=False):
    columns = ", ".join(SAFE_INTEGRATION_COLUMNS) if platform_scope else "*"
    query = f"SELECT {columns} FROM company_integrations WHERE company_id = :company AND id = :id"
    if for_update:
        query += " FOR UPDATE"
    return (await db.execute(text(query), {"company": company_id, "id": integration_id})).mappings().one_or_none()


async def get_run(db, company_id: UUID, run_id: UUID, *, for_update=False, platform_scope=False):
    columns = ", ".join(SAFE_RUN_COLUMNS) if platform_scope else "*"
    query = f"SELECT {columns} FROM integration_runs WHERE company_id = :company AND id = :id"
    if for_update:
        query += " FOR UPDATE"
    return (await db.execute(text(query), {"company": company_id, "id": run_id})).mappings().one_or_none()


async def _configuration(db, company_id: UUID, module_id: str):
    config = await current_revision(db, company_id)
    enabled = {module["id"] for module in effective_modules(config["modules"])}
    return config["revision"], {"sources", module_id} <= enabled


async def list_integrations(db, company_id: UUID, *, platform_scope=False) -> list[dict]:
    columns = ", ".join(f"i.{column}" for column in SAFE_INTEGRATION_COLUMNS) if platform_scope else "i.*"
    entries = (await db.execute(text(f"""
        SELECT {columns}, to_jsonb(latest) AS latest_run, clock_timestamp() AS now
        FROM company_integrations AS i
        LEFT JOIN LATERAL (
          SELECT state, request_id, error_code, available_at
          FROM integration_runs AS r
          WHERE r.company_id = i.company_id AND r.integration_id = i.id
          ORDER BY r.created_at DESC, r.id DESC LIMIT 1
        ) AS latest ON true
        WHERE i.company_id = :company ORDER BY i.label, i.id
    """), {"company": company_id})).mappings().all()
    output = []
    for entry in entries:
        latest = entry["latest_run"]
        if latest and latest["available_at"]:
            latest["available_at"] = datetime.fromisoformat(latest["available_at"])
        output.append(integration_status(entry, now=entry["now"], latest_run=latest))
    return output


async def enqueue_run(
    db: AsyncSession, *, company_id: UUID, integration_id: UUID, mode: str,
    expected_integration_version: int, reason: str, idempotency_key: str,
    request_id: str | None = None, approved_preview_id: UUID | None = None,
    company_active: bool | None = None, platform_scope=False,
) -> dict:
    if mode not in {"preview", "import"} or not idempotency_key or len(idempotency_key) > 128:
        raise JobError("VALIDATION_ERROR")
    parameters = {
        "company": company_id, "integration": integration_id, "mode": mode,
        "key": idempotency_key, "reason": reason[:256], "approval": approved_preview_id,
        "version": expected_integration_version, "request_id": (request_id or str(uuid4()))[:64],
        "release": settings.RELEASE_VERSION[:64],
    }
    integration = await get_integration(db, company_id, integration_id, for_update=True, platform_scope=platform_scope)
    if not integration:
        raise JobError("NOT_FOUND")
    columns = ", ".join(SAFE_RUN_COLUMNS) if platform_scope else "*"
    existing = (await db.execute(text(f"""
        SELECT {columns} FROM integration_runs WHERE company_id = :company AND integration_id = :integration
          AND idempotency_key = :key
    """), parameters)).mappings().one_or_none()
    if existing:
        if (existing["mode"], existing["integration_version"], existing["reason"], existing["approved_preview_id"]) != (
            mode, expected_integration_version, reason[:256], approved_preview_id
        ):
            raise JobError("CONFLICT")
        return run_summary(existing)
    if integration["version"] != expected_integration_version:
        raise JobError("STALE_REVISION")
    if not integration["enabled"]:
        raise JobError("CONFLICT")
    config_revision, module_enabled = await _configuration(db, company_id, integration["module_id"])
    if not module_enabled:
        raise JobError("MODULE_DISABLED")
    parameters["config_revision"] = config_revision
    if mode == "import":
        if company_active is None:
            company_active = await db.scalar(text("SELECT is_active FROM companies WHERE id = :company"), parameters)
        if not company_active:
            raise JobError("CONFLICT")
        if approved_preview_id is not None or integration["last_success_version"] != integration["version"]:
            if platform_scope:
                approved = await db.scalar(text("""
                    SELECT public.platform_preview_is_approved(:company,:integration,:approval,:version,:config_revision)
                """), parameters)
            else:
                approved = bool(await _approved_fingerprint(db, parameters, integration["version"]))
            if not approved:
                raise JobError("PREVIEW_STALE")
    parameters["adapter"] = integration["adapter_version"]
    run = (await db.execute(text(f"""
        INSERT INTO integration_runs
            (company_id,integration_id,integration_version,config_revision,adapter_version,release_version,request_id,
             mode,idempotency_key,reason,approved_preview_id)
        VALUES (:company,:integration,:version,:config_revision,:adapter,:release,:request_id,:mode,:key,:reason,:approval)
        ON CONFLICT DO NOTHING RETURNING {columns}
    """), parameters)).mappings().one_or_none()
    if not run:
        raise JobError("RUN_ALREADY_ACTIVE")
    return run_summary(run)


async def _approved_fingerprint(db, parameters, version: int) -> str | None:
    return await db.scalar(text("""
        SELECT fingerprint FROM integration_runs
        WHERE company_id = :company AND integration_id = :integration AND id = :approval
          AND mode = 'preview' AND state = 'succeeded' AND approved_until > clock_timestamp()
          AND integration_version = :version AND config_revision = :config_revision
    """), parameters | {"version": version})


async def approve_preview(
    db: AsyncSession, *, company_id: UUID, run_id: UUID, expected_integration_version: int, platform_scope=False,
) -> dict:
    run = await get_run(db, company_id, run_id, platform_scope=platform_scope)
    if not run:
        raise JobError("NOT_FOUND")
    integration = await get_integration(
        db, company_id, run["integration_id"], for_update=True, platform_scope=platform_scope,
    )
    config_revision, module_enabled = await _configuration(db, company_id, integration["module_id"])
    if (integration["version"] != expected_integration_version or run["integration_version"] != integration["version"]
            or run["config_revision"] != config_revision or not module_enabled):
        raise JobError("STALE_REVISION")
    params = {"company": company_id, "id": run_id, "version": expected_integration_version,
              "config_revision": config_revision}
    if platform_scope:
        expires = await db.scalar(text("""
            SELECT public.platform_approve_preview(:company,:id,:version,:config_revision)
        """), params)
    else:
        expires = await db.scalar(text("""
            UPDATE integration_runs SET approved_until = clock_timestamp() + interval '24 hours'
            WHERE company_id = :company AND id = :id AND mode = 'preview'
              AND state = 'succeeded' AND fingerprint IS NOT NULL
            RETURNING approved_until
        """), params)
    if expires is None:
        raise JobError("CONFLICT")
    return {"approved_preview_id": run_id, "expires_at": expires}


async def request_retry(db, *, company_id: UUID, integration_id: UUID, user_id: UUID, reason: str):
    if not await get_integration(db, company_id, integration_id):
        raise JobError("NOT_FOUND")
    params = {"company": company_id, "integration": integration_id, "user_id": user_id, "reason": reason}
    request = (await db.execute(text("""
        INSERT INTO integration_retry_requests (company_id,integration_id,requested_by,reason)
        VALUES (:company,:integration,:user_id,:reason)
        ON CONFLICT DO NOTHING RETURNING id,state,created_at
    """), params)).mappings().one_or_none()
    if request is None:
        request = (await db.execute(text("""
            SELECT id,state,created_at FROM integration_retry_requests
            WHERE company_id = :company AND integration_id = :integration AND state = 'pending'
        """), params)).mappings().one()
    return dict(request)



class Source:
    def __init__(self, content: bytes, reference: str, name: str, link: str | None = None):
        self.content = content
        self.reference = reference
        self.name = name
        self.link = link
        self.fingerprint = hashlib.sha256(content).hexdigest()


def _read_source(integration) -> Source:
    company_id = integration["company_id"]
    source_ref = integration["source_ref"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", source_ref):
        raise JobError("SOURCE_ACCESS_REVOKED")
    try:
        if integration["provider"] == "test_workbook":
            root = settings.INTEGRATION_TEST_WORKBOOK_DIR
            if not root or not settings.ENVIRONMENT.endswith("test"):
                raise JobError("SOURCE_ACCESS_REVOKED")
            company_root = root.resolve() / str(company_id)
            path = (company_root / f"{source_ref}.xlsx").resolve()
            if not path.is_relative_to(company_root):
                raise JobError("SOURCE_ACCESS_REVOKED")
            with path.open("rb") as stream:
                content = stream.read(settings.MAX_FILE_SIZE_BYTES + 1)
            if len(content) > settings.MAX_FILE_SIZE_BYTES:
                raise JobError("SOURCE_TOO_LARGE")
            return Source(content, f"integration:{integration['id']}", path.name)

        secret_ref = integration["secret_ref"]
        if secret_ref == "legacy-drive":
            if (company_id != settings.GOOGLE_DRIVE_COMPANY_ID
                    or source_ref != settings.GOOGLE_DRIVE_SOURCE_FILE_ID or google_drive_client.is_mock):
                raise JobError("SOURCE_ACCESS_REVOKED")
            client = google_drive_client
        else:
            try:
                secrets_json = settings.INTEGRATION_CREDENTIALS_JSON
                credentials = json.loads(secrets_json.get_secret_value())[str(company_id)][secret_ref]
                if not isinstance(credentials, dict):
                    raise ValueError()
                client = GoogleDriveClient(mock_mode=False, credentials_info=credentials)
            except (AttributeError, TypeError, KeyError, ValueError, RuntimeError):
                raise JobError("SOURCE_ACCESS_REVOKED") from None
        content = client.download_file_bytes(
            source_ref, max_bytes=settings.MAX_FILE_SIZE_BYTES, deadline_seconds=60, max_retries=0,
        )
        return Source(content, source_ref, f"{integration['label']}.xlsx", client.get_web_view_link(source_ref))
    except JobError:
        raise
    except DriveFileTooLarge:
        raise JobError("SOURCE_TOO_LARGE") from None
    except (FileNotFoundError, PermissionError):
        raise JobError("SOURCE_ACCESS_REVOKED") from None
    except TimeoutError:
        raise JobError("SOURCE_TIMEOUT") from None
    except Exception as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status in {401, 403, 404}:
            code = "SOURCE_ACCESS_REVOKED"
        elif status == 429:
            code = "SOURCE_RATE_LIMITED"
        else:
            code = "SOURCE_UNAVAILABLE"
        raise JobError(code) from None


def _prepare(adapter: str, content: bytes):
    try:
        with ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 1000 or sum(member.file_size for member in members) > 100 * 1024 * 1024:
                raise JobError("SOURCE_TOO_LARGE")
        workbook = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            if any((sheet.max_row or 0) > 50_000 or (sheet.max_column or 0) > 200 for sheet in workbook):
                raise JobError("SOURCE_TOO_LARGE")
            if adapter == "equipment_registry":
                sheet = workbook["Оборудование"]
                sheet.reset_dimensions()
                rows = sheet.iter_rows(values_only=True)
                if tuple(next(rows)) != ("Оборудование", "Срок обслуживания"):
                    raise ValueError()
                records = []
                for row_number, row in enumerate(rows, start=2):
                    if row_number > 50_000:
                        raise JobError("SOURCE_TOO_LARGE")
                    if not row or all(value is None for value in row):
                        continue
                    if len(row) > 2:
                        raise ValueError()
                    name, due = row if len(row) == 2 else (row[0], None)
                    if not isinstance(name, str) or not 0 < len(name.strip()) <= 500:
                        raise ValueError()
                    if isinstance(due, datetime):
                        due = due.date()
                    elif isinstance(due, str):
                        due = date.fromisoformat(due)
                    if due is not None and not isinstance(due, date):
                        raise ValueError()
                    records.append((name.strip(), due))
                return records, len(records), 0
        finally:
            workbook.close()
        data = read_customer_workbook(content, max_rows=50_000, max_columns=200)
        if data is None:
            raise ValueError()
        for row in data["Реест Ольга"]["rows"]:
            contract_amount(row)
        ids = {record["key"] for sheet in data.values() for record in sheet["rows"]}
        return data, len(ids), sum(len(sheet["warnings"]) for sheet in data.values())
    except JobError:
        raise
    except WorkbookShapeError:
        raise JobError("SOURCE_TOO_LARGE") from None
    except Exception:
        raise JobError("SCHEMA_MISMATCH") from None


async def _lease_rows(db, *, run_id: UUID, company_id: UUID, generation: int):
    run = await get_run(db, company_id, run_id)
    if not run:
        raise StaleLease()
    active = await db.scalar(text("SELECT is_active FROM companies WHERE id = :id FOR UPDATE"), {"id": company_id})
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                     {"scope": f"company-config:{company_id}"})
    integration = await get_integration(db, company_id, run["integration_id"], for_update=True)
    run = await get_run(db, company_id, run_id, for_update=True)
    now = await db.scalar(text("SELECT clock_timestamp()"))
    if not run or run["state"] != "running" or run["lease_generation"] != generation or run["lease_until"] <= now:
        raise StaleLease()
    return run, integration, active


async def _replace_snapshot(db, company_id: UUID, integration, source: Source, prepared) -> UUID:
    identity = (
        UploadedFile.id == integration["published_file_id"] if integration["published_file_id"] is not None
        else UploadedFile.google_drive_id == source.reference
    )
    file = await db.scalar(select(UploadedFile).where(
        UploadedFile.company_id == company_id, identity,
    ))
    if (file and file.deleted_at is None and file.sha256_hash == source.fingerprint
            and integration["last_success_version"] == integration["version"]):
        return file.id
    key = build_tenant_storage_key(company_id, source.fingerprint)
    await storage_service.save_tenant_file(source.content, key, company_id)
    if file is None:
        file = UploadedFile(company_id=company_id, google_drive_id=source.reference)
        db.add(file)
    file.original_name = source.name
    file.storage_path = key
    file.file_size_bytes = len(source.content)
    file.mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    file.sha256_hash = source.fingerprint
    file.google_drive_id = source.reference
    file.google_drive_link = source.link
    file.status = FileStatus.PROCESSED
    file.error_message = None
    file.deleted_at = None
    await db.flush()
    if integration["adapter_id"] == "customer_tenders":
        await persist_customer_workbook(source.content, company_id, file.id, db, prepared=prepared)
    else:
        await db.execute(update(OperationalTask).where(
            OperationalTask.company_id == company_id,
            OperationalTask.file_id == file.id,
            OperationalTask.deleted_at.is_(None),
        ).values(deleted_at=func.clock_timestamp()))
        db.add_all([
            OperationalTask(company_id=company_id, file_id=file.id, task_title=name, due_date=due)
            for name, due in prepared
        ])
    await db.flush()
    return file.id


async def _record_outcome(db, *, run, code, succeeded):
    if not settings.INTEGRATIONS_ENABLED:
        return
    # Imported here so projections can reuse integration status DTOs.
    from app.services.platform_operations import record_integration_outcome

    await record_integration_outcome(
        db, company_id=run["company_id"], integration_id=run["integration_id"],
        run_id=run["id"], code=code, succeeded=succeeded,
    )


def _fingerprint(prepared) -> str:
    digest = hashlib.sha256()
    for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, default=str).iterencode(prepared):
        digest.update(chunk.encode())
    return digest.hexdigest()


async def _finish(*, company_id, run_id, generation, source=None, prepared=None, fingerprint=None,
                  count=None, warnings=None, error=None):
    async with async_session_factory.begin() as db:
        await set_tenant_context(db, company_id)
        run, integration, active = await _lease_rows(db, run_id=run_id, company_id=company_id, generation=generation)
        config_revision, module_enabled = await _configuration(db, company_id, integration["module_id"])
        params = {
            "run": run_id, "company": company_id, "integration": run["integration_id"],
            "generation": generation, "approval": run["approved_preview_id"],
            "config_revision": config_revision,
        }
        if (not integration or not integration["enabled"] or run["integration_version"] != integration["version"]
                or not module_enabled or run["config_revision"] != config_revision
                or (run["mode"] == "import" and not active)):
            state, error = "canceled", None
        else:
            state = "succeeded" if error is None else "failed"
        if state == "succeeded" and run["mode"] == "import":
            if run["approved_preview_id"] is not None or integration["last_success_version"] != integration["version"]:
                approved = await _approved_fingerprint(db, params, integration["version"])
                if approved != fingerprint:
                    state, error = "failed", "PREVIEW_STALE"
            if state == "succeeded":
                params["published_file"] = await _replace_snapshot(db, company_id, integration, source, prepared)
        if state == "failed" and error in RETRYABLE and run["attempt_count"] < 3:
            state = "retry_wait"
        if state == "succeeded" and run["mode"] == "import":
            await db.execute(text("""
                UPDATE company_integrations
                SET last_attempt_at = clock_timestamp(), last_success_at = clock_timestamp(),
                    last_fingerprint = :fingerprint, last_success_version = version, published_file_id = :published_file,
                    last_error_code = NULL,
                    next_due_at = clock_timestamp() + make_interval(secs => coalesce(schedule_seconds, 0))
                WHERE company_id = :company AND id = :integration
            """), params | {"fingerprint": fingerprint})
        elif state in {"failed", "retry_wait"}:
            await db.execute(text("""
                UPDATE company_integrations SET last_attempt_at = clock_timestamp(), last_error_code = :error
                WHERE company_id = :company AND id = :integration
            """), params | {"error": error})
        backoff = 15 * 2 ** (run["attempt_count"] - 1)
        updated = await db.scalar(text("""
            UPDATE integration_runs
            SET state = CAST(:state AS varchar), lease_until = NULL, error_code = :error,
                finished_at = CASE WHEN CAST(:state AS varchar) = 'retry_wait' THEN NULL ELSE clock_timestamp() END,
                available_at = clock_timestamp() + make_interval(secs => :backoff),
                fingerprint = :fingerprint, rows_processed = :count, warning_count = :warnings
            WHERE company_id = :company AND id = :run AND state = 'running'
              AND lease_generation = :generation AND lease_until > clock_timestamp()
            RETURNING id
        """), params | {
            "state": state, "error": error, "backoff": backoff,
            "fingerprint": fingerprint if state == "succeeded" else None,
            "count": count if state == "succeeded" else None,
            "warnings": warnings if state == "succeeded" else None,
        })
        if updated is None:
            raise StaleLease()
        if state == "failed" or state == "succeeded" and run["mode"] == "import":
            await _record_outcome(db, run=run, code=error, succeeded=state == "succeeded")
        if await db.scalar(text("SELECT clock_timestamp()")) >= run["lease_until"]:
            raise StaleLease()


async def process_claim(*, run_id: UUID, company_id: UUID, generation: int) -> None:
    job = {"company_id": company_id, "run_id": run_id, "generation": generation}
    try:
        async with async_session_factory() as db:
            await set_tenant_context(db, company_id)
            run = await get_run(db, company_id, run_id)
            if not run or run["state"] != "running" or run["lease_generation"] != generation:
                return
            integration = await get_integration(db, company_id, run["integration_id"])
            active = await db.scalar(text("SELECT is_active FROM companies WHERE id = :id"), {"id": company_id})
        if (not integration or not integration["enabled"] or run["integration_version"] != integration["version"]
                or (run["mode"] == "import" and not active)):
            await _finish(**job, error="IMPORT_FAILED")
            return
        if ADAPTERS.get(integration["adapter_id"]) != (integration["adapter_version"], integration["module_id"]):
            raise JobError("SCHEMA_MISMATCH")
        source = await asyncio.wait_for(asyncio.to_thread(_read_source, integration), timeout=65)
        prepared, count, warnings = await asyncio.wait_for(
            asyncio.to_thread(_prepare, integration["adapter_id"], source.content), timeout=30,
        )
        fingerprint = await asyncio.to_thread(_fingerprint, prepared)
        await _finish(**job, source=source, prepared=prepared, fingerprint=fingerprint, count=count, warnings=warnings)
        return
    except StaleLease:
        return
    except JobError as exc:
        code = exc.code
    except TimeoutError:
        code = "SOURCE_TIMEOUT"
    except Exception:
        logger.warning("Integration publication failed for run %s", run_id)
        code = "IMPORT_FAILED"
    try:
        await _finish(**job, error=code)
    except StaleLease:
        return


async def claim_run(worker_id: UUID):
    async with async_session_factory.begin() as db:
        claimed = (await db.execute(text("SELECT * FROM public.claim_integration_job(:worker)"),
                                    {"worker": worker_id})).mappings().one_or_none()
    if claimed:
        return {"run_id": claimed["run_id"], "company_id": claimed["tenant_id"], "generation": claimed["generation"]}
    return None


async def schedule_due() -> None:
    async with async_session_factory.begin() as db:
        await db.execute(text("SELECT public.schedule_integration_jobs(:release)"), {"release": settings.RELEASE_VERSION})
