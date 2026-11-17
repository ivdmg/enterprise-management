"""Exercise the durable worker using synthetic sources in a disposable cluster."""

import asyncio
import os
from pathlib import Path
import secrets
import shutil
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from openpyxl import Workbook, load_workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from smoke import make_sources
from tenant_rls import check_data_directory, pilot_owner_url


def equipment(path: Path, *, title: str = "Фильтр тестовой установки"):
    book = Workbook()
    book.active.title = "Оборудование"
    book.active.append(["Оборудование", "Срок обслуживания"])
    book.active.append([title, "2026-12-01"])
    book.save(path)


async def smoke():
    owner_url = pilot_owner_url()
    owner = create_async_engine(owner_url._replace(scheme="postgresql+asyncpg").geturl())
    company_a, company_b, integration_a, integration_b, worker = [uuid4() for _ in range(5)]
    root = Path.cwd().parent / "integration-fixtures"
    sources = root / "sources"
    _, tender_file = make_sources(root)[0]
    source_a = sources / str(company_a) / "registry.xlsx"
    source_b = sources / str(company_b) / "registry.xlsx"
    for source in (source_a, source_b):
        source.parent.mkdir(parents=True)
    shutil.copy2(tender_file, source_a)
    equipment(source_b)
    try:
        async with owner.begin() as db:
            await check_data_directory(db)
            password = secrets.token_hex(24)
            await db.execute(text(f"CREATE ROLE integration_test_worker LOGIN PASSWORD '{password}'"))
            for grant in (
                "USAGE ON SCHEMA public",
                "SELECT (id, is_active), UPDATE (engineer_documents) ON companies",
                "SELECT, INSERT, UPDATE ON uploaded_files, tender_projects, operational_tasks",
                "SELECT, UPDATE ON company_integrations, integration_runs",
                "SELECT ON company_config_revisions",
                "SELECT, INSERT, UPDATE ON platform_incidents",
                "SELECT, INSERT ON platform_integration_events",
                "EXECUTE ON FUNCTION public.schedule_integration_jobs(text), public.claim_integration_job(uuid)",
            ):
                await db.execute(text(f"GRANT {grant} TO integration_test_worker"))
            os.environ["DATABASE_WORKER_URL"] = owner_url._replace(
                netloc=f"integration_test_worker:{password}@127.0.0.1:{owner_url.port}"
            ).geturl()
            os.environ["INTEGRATION_TEST_WORKBOOK_DIR"] = str(sources)
            os.environ["INTEGRATIONS_ENABLED"] = "true"
            await db.execute(text("INSERT INTO companies (id,name) VALUES (:a,'Worker A'),(:b,'Worker B')"),
                             {"a": company_a, "b": company_b})
            await db.execute(text("""
                INSERT INTO company_integrations
                    (id,company_id,provider,label,module_id,adapter_id,adapter_version,source_ref,schedule_seconds,stale_after_seconds)
                VALUES
                    (:ia,:a,'test_workbook','Стройка','projects','customer_tenders','v1','registry',60,120),
                    (:ib,:b,'test_workbook','Клиника','tasks','equipment_registry','v1','registry',60,120)
            """), {"a": company_a, "b": company_b, "ia": integration_a, "ib": integration_b})

        from app.core.database import AsyncSessionLocal, engine, set_tenant_context, worker_engine
        from app.services import integration_jobs as jobs

        async def enqueue(company, integration, mode, key=None, approval=None, *, version=1):
            async with AsyncSessionLocal.begin() as session:
                await set_tenant_context(session, company)
                return await jobs.enqueue_run(
                    session, company_id=company, integration_id=integration,
                    mode=mode, expected_integration_version=version, reason="pilot",
                    idempotency_key=key or str(uuid4()), approved_preview_id=approval,
                )

        async def approve(company, run, *, version=1):
            async with AsyncSessionLocal.begin() as session:
                await set_tenant_context(session, company)
                await jobs.approve_preview(session, company_id=company, run_id=run,
                                           expected_integration_version=version)

        async def process(run):
            claim = await jobs.claim_run(worker)
            assert claim and claim["run_id"] == run
            await jobs.process_claim(**claim)

        async def lookup(run_id):
            async with owner.connect() as connection:
                return (await connection.execute(text("SELECT * FROM integration_runs WHERE id=:run"),
                                                 {"run": run_id})).mappings().one()

        try:
            preview_a = await enqueue(company_a, integration_a, "preview", "same-key")
            preview_b = await enqueue(company_b, integration_b, "preview", "same-key")
            assert (await enqueue(company_a, integration_a, "preview", "same-key"))["id"] == preview_a["id"]
            claims = [await jobs.claim_run(worker), await jobs.claim_run(worker)]
            assert {claim["run_id"] for claim in claims} == {preview_a["id"], preview_b["id"]}
            assert await jobs.claim_run(worker) is None
            await asyncio.gather(*(jobs.process_claim(**claim) for claim in claims))
            assert (await lookup(preview_a["id"]))["state"] == "succeeded"
            assert (await lookup(preview_b["id"]))["state"] == "succeeded"
            async with owner.connect() as db:
                assert await db.scalar(text("SELECT count(*) FROM uploaded_files WHERE company_id IN (:a,:b)"),
                                       {"a": company_a, "b": company_b}) == 0
            await approve(company_a, preview_a["id"])
            await approve(company_b, preview_b["id"])

            workbook = load_workbook(source_a)
            workbook["Реест Ольга"].cell(row=4, column=17, value="Сверено")
            workbook.save(source_a)
            run_a = await enqueue(company_a, integration_a, "import", approval=preview_a["id"])
            await process(run_a["id"])
            assert (await lookup(run_a["id"]))["error_code"] == "PREVIEW_STALE"
            run_b = await enqueue(company_b, integration_b, "import", approval=preview_b["id"])
            await process(run_b["id"])
            assert (await lookup(run_b["id"]))["state"] == "succeeded"

            good_preview = await enqueue(company_a, integration_a, "preview")
            await process(good_preview["id"])
            await approve(company_a, good_preview["id"])
            good_import = await enqueue(company_a, integration_a, "import", approval=good_preview["id"])
            await process(good_import["id"])
            assert (await lookup(good_import["id"]))["state"] == "succeeded"

            async with owner.begin() as db:
                await db.execute(text("""
                    UPDATE tender_projects SET custom_attributes=custom_attributes || '{"tender_stage":"manual"}'
                    WHERE company_id=:company
                """), {"company": company_a})
                assert await db.scalar(text("""
                    SELECT task_title FROM operational_tasks WHERE company_id=:company AND deleted_at IS NULL
                """), {"company": company_b}) == "Фильтр тестовой установки"
            source_a.write_bytes(b"broken workbook")
            bad = await enqueue(company_a, integration_a, "import")
            await process(bad["id"])
            assert (await lookup(bad["id"]))["error_code"] == "SCHEMA_MISMATCH"
            async with owner.connect() as db:
                assert await db.scalar(text("""
                    SELECT custom_attributes->>'tender_stage' FROM tender_projects
                    WHERE company_id=:company AND deleted_at IS NULL
                """), {"company": company_a}) == "manual"
                assert await db.scalar(text("""
                    SELECT count(*) FROM platform_incidents WHERE company_id=:company AND code='SCHEMA_MISMATCH'
                """), {"company": company_a}) == 1
            workbook["Реест Ольга"].cell(row=4, column=17, value="Повтор")
            workbook.save(source_a)
            recovered = await enqueue(company_a, integration_a, "import")
            await process(recovered["id"])
            assert (await lookup(recovered["id"]))["state"] == "succeeded"
            async with owner.connect() as db:
                assert await db.scalar(text("""
                    SELECT custom_attributes->>'tender_stage' FROM tender_projects
                    WHERE company_id=:company AND deleted_at IS NULL
                """), {"company": company_a}) == "manual"

            new_source = source_a.with_name("registry-new.xlsx")
            shutil.copy2(source_a, new_source)
            async with owner.begin() as db:
                published_id = await db.scalar(text("""
                    UPDATE company_integrations SET version=2, source_ref='registry-new'
                    WHERE id=:integration RETURNING published_file_id
                """), {"integration": integration_a})
            original_read_source = jobs._read_source

            def read_replacement(integration):
                source = original_read_source(integration)
                return jobs.Source(source.content, "replacement-drive-file", source.name)

            with patch.object(jobs, "_read_source", read_replacement):
                replacement = await enqueue(company_a, integration_a, "preview", version=2)
                await process(replacement["id"])
                await approve(company_a, replacement["id"], version=2)
                replacement_import = await enqueue(company_a, integration_a, "import",
                                                   approval=replacement["id"], version=2)
                await process(replacement_import["id"])
            assert (await lookup(replacement_import["id"]))["state"] == "succeeded"
            async with owner.connect() as db:
                assert (await db.execute(text("""
                    SELECT id, google_drive_id FROM uploaded_files
                    WHERE company_id=:company AND deleted_at IS NULL
                """), {"company": company_a})).one() == (published_id, "replacement-drive-file")

            with patch.object(jobs, "_read_source", side_effect=jobs.JobError("SOURCE_TIMEOUT")):
                retry = await enqueue(company_b, integration_b, "import")
                await process(retry["id"])
            assert (await lookup(retry["id"]))["state"] == "retry_wait"
            async with owner.begin() as db:
                await db.execute(text("UPDATE integration_runs SET available_at=clock_timestamp() WHERE id=:run"),
                                 {"run": retry["id"]})
            old_claim = await jobs.claim_run(worker)
            assert old_claim["run_id"] == retry["id"]
            entered, release = Event(), Event()

            def read_blocked(integration):
                entered.set()
                if not release.wait(10):
                    raise TimeoutError()
                return original_read_source(integration)

            with patch.object(jobs, "_read_source", read_blocked):
                old_process = asyncio.create_task(jobs.process_claim(**old_claim))
                try:
                    assert await asyncio.to_thread(entered.wait, 10)
                    async with owner.begin() as db:
                        await db.execute(text("UPDATE integration_runs SET lease_until=clock_timestamp() WHERE id=:run"),
                                         {"run": retry["id"]})
                    new_claim = await jobs.claim_run(worker)
                finally:
                    release.set()
                    await old_process
            assert new_claim["generation"] == old_claim["generation"] + 1
            assert (await lookup(retry["id"]))["state"] == "running"
            await jobs.process_claim(**new_claim)
            assert (await lookup(retry["id"]))["state"] == "succeeded"

            equipment(source_b, title="Не должно попасть в приостановленную компанию")
            paused = await enqueue(company_b, integration_b, "import")
            claim = await jobs.claim_run(worker)
            entered.clear()
            release.clear()
            with patch.object(jobs, "_read_source", read_blocked):
                paused_process = asyncio.create_task(jobs.process_claim(**claim))
                try:
                    assert await asyncio.to_thread(entered.wait, 10)
                    async with owner.begin() as db:
                        await db.execute(text("UPDATE companies SET is_active=false WHERE id=:id"), {"id": company_b})
                finally:
                    release.set()
                    await paused_process
            assert (await lookup(paused["id"]))["state"] == "canceled"

            async with owner.begin() as db:
                await db.execute(text("UPDATE companies SET is_active=true WHERE id=:id"), {"id": company_b})
                await db.execute(text("""
                    UPDATE company_integrations SET next_due_at=clock_timestamp() WHERE id IN (:a,:b)
                """), {"a": integration_a, "b": integration_b})
            async with owner.begin() as db:
                await db.execute(text("UPDATE companies SET is_active=false WHERE id=:id"), {"id": company_b})
                racing_scheduler = asyncio.create_task(jobs.schedule_due())
                try:
                    async with asyncio.timeout(5):
                        while not await db.scalar(text("""
                            SELECT EXISTS(
                              SELECT FROM pg_stat_activity
                              WHERE usename='integration_test_worker' AND state='active'
                                AND wait_event_type='Lock' AND query LIKE '%schedule_integration_jobs%'
                            )
                        """)):
                            assert not racing_scheduler.done(), "Schedule finished before the company lock was released"
                            await asyncio.sleep(0.02)
                except BaseException:
                    racing_scheduler.cancel()
                    await asyncio.gather(racing_scheduler, return_exceptions=True)
                    raise
            await racing_scheduler
            await jobs.schedule_due()
            async with owner.connect() as db:
                assert await db.scalar(text("""
                    SELECT count(*) FROM integration_runs WHERE integration_id=:id AND state='queued'
                """), {"id": integration_a}) == 1
                assert await db.scalar(text("""
                    SELECT count(*) FROM integration_runs WHERE integration_id=:id AND state='queued'
                """), {"id": integration_b}) == 0
                assert await db.scalar(text("SELECT count(*) FROM integration_worker_heartbeats")) == 1
        finally:
            await engine.dispose()
            await worker_engine.dispose()
    finally:
        await owner.dispose()


if __name__ == "__main__":
    asyncio.run(smoke())
    print("Durable integrations: preview, publish, snapshot, incidents, retry, fencing, pause and schedule passed")
