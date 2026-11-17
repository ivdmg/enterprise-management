"""Operations checks for the disposable PostgreSQL pilot runner."""

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession






async def check_operations(call, owner_engine, director, operator, a, b, *, standalone=False):
    from app.core.database import set_tenant_context
    from app.core.platform_database import PlatformSessionLocal
    from app.services.platform_operations import record_integration_outcome

    a, b = UUID(str(a)), UUID(str(b))
    async with owner_engine.begin() as db:
        data_dir = await db.scalar(text("SHOW data_directory"))
        assert Path(data_dir).resolve() == Path.cwd().parent / "postgres"
        grants = """
            GRANT SELECT ON audit_logs TO auth_runtime_qa;
            GRANT SELECT, INSERT, UPDATE ON platform_incidents TO auth_platform_qa;
            GRANT SELECT ON platform_integration_events, platform_run_correlation TO auth_platform_qa;
            GRANT SELECT, INSERT ON platform_operation_audit TO auth_platform_qa;
            GRANT EXECUTE ON FUNCTION platform_operation_status() TO auth_platform_qa;
            CREATE ROLE ops_worker_qa NOLOGIN;
            GRANT USAGE ON SCHEMA public TO ops_worker_qa;
            GRANT SELECT, INSERT, UPDATE ON platform_incidents TO ops_worker_qa;
            GRANT SELECT, INSERT ON platform_integration_events TO ops_worker_qa;
        """
        for statement in grants.strip().split(";"):
            if statement.strip():
                await db.execute(text(statement))
    previous = await call(operator, "GET", "/platform/status", 200)
    async with owner_engine.begin() as db:
        integration = await db.scalar(text("""
            INSERT INTO company_integrations
                (company_id, provider, label, module_id, adapter_id, adapter_version, source_ref, stale_after_seconds)
            VALUES (:company, 'test_workbook', 'Synthetic source', 'projects', 'customer_tenders',
                    'v1', 'private-fixture.xlsx', 600)
            RETURNING id
        """), {"company": a})
        actor = await db.scalar(text("SELECT id FROM users WHERE company_id = :company AND role = 'admin'"), {"company": a})
        for company, actor_id in ((a, actor), (b, None)):
            await db.execute(text("""
                INSERT INTO audit_logs (id, company_id, user_id, entity_type, entity_id, old_status, new_status, ip_address)
                VALUES (gen_random_uuid(), :company, :actor, 'task', :entity, 'old', 'new', 'synthetic-ip')
            """), {"company": company, "actor": actor_id, "entity": uuid4()})
        await db.execute(text("""
            INSERT INTO audit_logs (id, company_id, user_id, entity_type, entity_id, action, new_status)
            VALUES (gen_random_uuid(), :company, :actor, 'file', :entity, 'downloaded', 'private-detail')
        """), {"company": a, "actor": actor, "entity": uuid4()})

        async def make_run(code):
            return await db.scalar(text("""
                INSERT INTO integration_runs (company_id, integration_id, adapter_version, integration_version,
                    release_version, request_id, mode, state, idempotency_key, reason)
                VALUES (:company, :integration, 'v1', 1, 'test', :request, 'import', :state, :request, 'private-reason')
                RETURNING id
            """), {"company": a, "integration": integration, "request": str(uuid4()),
                   "state": "failed" if code else "succeeded"})

        async with AsyncSession(bind=db) as worker:
            first, second, third = [await make_run(code) for code in ('failure', 'failure', None)]
            await worker.execute(text("SET LOCAL ROLE ops_worker_qa"))
            assert await worker.scalar(text("SELECT row_security_active('public.platform_incidents')"))
            await set_tenant_context(worker, a)
            for run_id in (first, first, second):
                await record_integration_outcome(worker, company_id=a, integration_id=integration,
                                                 run_id=run_id, code="synthetic private failure", succeeded=False)
            await worker.execute(text("RESET ROLE"))

    base = f"/platform/companies/{a}"
    incidents = await call(operator, "GET", base + "/incidents", 200)
    assert len(incidents) == 1 and incidents[0]["code"] == "IMPORT_FAILED"
    assert incidents[0]["run_id"] == str(second)
    incident = incidents[0]
    assert "synthetic private failure" not in str(incident)
    assert await call(operator, "GET", f"/platform/companies/{b}/incidents", 200) == []
    await call(operator, "GET", f"/platform/companies/{b}/incidents/{incident['id']}", 404)
    await call(director, "GET", base + "/incidents", 403)
    history = await call(operator, "GET", base + "/events", 200)
    assert len(history) == 2 and all(item["request_id"] for item in history)
    assert "private-fixture" not in str(history) and "private-reason" not in str(history)
    endpoint = f"{base}/incidents/{incident['id']}/transitions"
    changed = await call(operator, "POST", endpoint, 200,
                         json={"version": incident["version"], "to": "in_progress", "reason": "Test triage"})
    await call(operator, "POST", endpoint, 409,
               json={"version": incident["version"], "to": "escalated", "reason": "Stale test"})
    assert changed["assignee_id"] and changed["state"] == "in_progress"

    async with owner_engine.begin() as connection:
        async with AsyncSession(bind=connection) as worker:
            await worker.execute(text("SET LOCAL ROLE ops_worker_qa"))
            await set_tenant_context(worker, a)
            await record_integration_outcome(worker, company_id=a, integration_id=integration,
                                             run_id=third, code=None, succeeded=True)
            await worker.execute(text("RESET ROLE"))
    verifying = await call(operator, "GET", f"{base}/incidents/{incident['id']}", 200)
    assert verifying["state"] == "verifying"
    await call(operator, "POST", endpoint, 200,
               json={"version": verifying["version"], "to": "closed", "reason": "Confirmed"})
    platform = await call(operator, "GET", "/platform/status", 200)
    assert platform["active_incident_count"] == previous["active_incident_count"]
    if standalone:
        assert platform["status"] == "degraded"
    support_audit = await call(operator, "GET", "/platform/audit?action=incident_closed", 200)
    assert len(support_audit) == 1 and support_audit[0]["company_id"] == str(a)
    assert "Confirmed" not in str(support_audit)

    client_audit = await call(director, "GET", "/company/audit?entity_type=task", 200)
    assert len(client_audit) == 1 and client_audit[0]["actor_id"] == str(actor)
    assert client_audit[0]["changes"] == {"status": {"before": "old", "after": "new"}}
    assert "synthetic-ip" not in str(client_audit)
    downloads = await call(director, "GET", "/company/audit?action=downloaded", 200)
    assert len(downloads) == 1 and downloads[0]["action"] == "downloaded" and downloads[0]["changes"] is None
    assert "private-detail" not in str(downloads)
    async with PlatformSessionLocal() as db:
        if standalone:
            assert not await db.scalar(text("SELECT has_table_privilege('integration_runs', 'SELECT')"))
        assert not await db.scalar(text("SELECT has_table_privilege('audit_logs', 'SELECT')"))
        assert await db.scalar(text("SELECT count(*) FROM platform_incidents")) == 0
    print("Operations smoke passed: real RLS roles, cross-company checks, deduplication, recovery and safe audit.")


async def main():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import create_async_engine
    from auth_smoke import EMAIL, PASSWORD, app, call, enroll, seed, settings

    a, b, _ = await seed()
    engine = create_async_engine(settings.async_database_url)
    transport = ASGITransport(app=app)
    try:
        async with (
            AsyncClient(transport=transport, base_url=settings.CLIENT_AUTH_ORIGIN) as director,
            AsyncClient(transport=transport, base_url=settings.PLATFORM_AUTH_ORIGIN) as operator,
        ):
            await enroll(director, "/auth", {"email": EMAIL, "password": PASSWORD, "company_code": "smoke-a"})
            await enroll(operator, "/platform/auth", {"email": "owner@example.com", "password": PASSWORD})
            await check_operations(call, engine, director, operator, a, b, standalone=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
