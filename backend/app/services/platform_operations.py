"""Persist sanitized integration outcomes and platform administrative audit."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.integration_jobs import ERRORS

SUCCESS_CODE = "IMPORT_SUCCEEDED"
INCIDENT_TRANSITIONS = {
    "new": {"in_progress"},
    "in_progress": {"escalated", "verifying"},
    "escalated": {"verifying"},
    "verifying": {"closed"},
    "closed": {"in_progress"},
}
ERROR_CATALOG = ERRORS | {
    "SOURCE_STALE": ("Источник давно не обновлялся", "Проверьте расписание и последние запуски"),
    "WORKER_OFFLINE": ("Обработчик давно не отвечал", "Передайте инцидент разработчику"),
    SUCCESS_CODE: ("Импорт завершён", "Проверьте актуальность данных"),
}
WARNING_CODES = {"SOURCE_TIMEOUT", "SOURCE_RATE_LIMITED", "SOURCE_UNAVAILABLE", "SOURCE_STALE"}


def describe(code: str) -> tuple[str, str]:
    return ERROR_CATALOG.get(code, ERROR_CATALOG["IMPORT_FAILED"])


async def record_integration_outcome(
    db: AsyncSession, *, company_id: UUID, integration_id: UUID, run_id: UUID,
    code: str | None, succeeded: bool,
) -> None:
    if succeeded:
        safe_code, severity = SUCCESS_CODE, "info"
    else:
        safe_code = code if code in ERROR_CATALOG and code != SUCCESS_CODE else "IMPORT_FAILED"
        severity = "warning" if safe_code in WARNING_CODES else "error"
    params = {"company": company_id, "integration": integration_id, "run": run_id,
              "code": safe_code, "severity": severity}
    event = await db.scalar(text("""
        INSERT INTO public.platform_integration_events (company_id, integration_id, run_id, code, severity)
        VALUES (:company, :integration, :run, :code, :severity)
        ON CONFLICT (company_id, integration_id, run_id, code) DO NOTHING
        RETURNING id
    """), params)
    if not event:
        return

    if succeeded:
        await db.execute(text("""
            UPDATE public.platform_incidents
            SET state = 'verifying', updated_at = clock_timestamp(), version = version + 1
            WHERE company_id = :company AND integration_id = :integration
              AND state IN ('new', 'in_progress', 'escalated')
        """), params)
        return

    await db.execute(text("""
        INSERT INTO public.platform_incidents (company_id, integration_id, run_id, code, severity)
        VALUES (:company, :integration, :run, :code, :severity)
        ON CONFLICT (company_id, integration_id, code) WHERE state <> 'closed'
        DO UPDATE SET run_id = EXCLUDED.run_id,
                      state = CASE WHEN platform_incidents.state = 'verifying' THEN 'in_progress'
                                   ELSE platform_incidents.state END,
                      updated_at = clock_timestamp(), version = platform_incidents.version + 1
    """), params)


async def record_platform_audit(
    db: AsyncSession, *, actor_id: UUID, company_id: UUID | None, action: str,
    entity_id: UUID | None = None, correlation_id: str | None = None,
    result: str = "success",
) -> None:
    await db.execute(text("""
        INSERT INTO public.platform_operation_audit
            (actor_id, company_id, action, entity_id, correlation_id, result)
        VALUES (:actor, :company, :action, :entity, :correlation, :result)
    """), {"actor": actor_id, "company": company_id, "action": action, "entity": entity_id,
           "correlation": correlation_id, "result": result})
