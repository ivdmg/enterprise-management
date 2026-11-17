"""Open-loop HTTP load with authenticated tenant reads and concurrent durable imports."""

import argparse
import asyncio
from contextlib import AsyncExitStack
import ctypes
from datetime import timedelta
import json
import logging
import math
import os
from pathlib import Path
import secrets
import sys
from time import perf_counter, process_time
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tenant_rls import check_data_directory, pilot_owner_url


BASE = "/api/v1"
READS = ("/dashboard/summary", "/tasks/operational?limit=20", "/company/modules", "/company/integrations")
EMAIL = "employee-{index}@example.com"
PASSWORD = "Synthetic-load-password-26"


def memory_mib():
    if sys.platform == "win32":
        class Counters(ctypes.Structure):
            _fields_ = [("size", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in (
                    "peak_working_set", "working_set", "peak_paged_pool", "paged_pool",
                    "peak_nonpaged_pool", "nonpaged_pool", "pagefile", "peak_pagefile",
                )
            ]

        data = Counters()
        data.size = ctypes.sizeof(data)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.c_void_p(kernel.GetCurrentProcess()), ctypes.byref(data), data.size
        )
        return data.working_set / (1024 * 1024) if ok else None
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024 if sys.platform == "darwin" else 1024)


def make_books(sources, companies, revision, rows):
    for index, company_id in enumerate(companies):
        company_dir = sources / str(company_id)
        company_dir.mkdir(parents=True, exist_ok=True)
        for source in (0, 1):
            book = Workbook(write_only=True)
            sheet = book.create_sheet("Оборудование")
            sheet.append(["Оборудование", "Срок обслуживания"])
            for row in range(rows):
                sheet.append([f"Company {index} / source {source} / item {row} / v{revision}", "2026-12-01"])
            book.save(company_dir / f"source-{source}.xlsx")


def p95(values):
    return sorted(values)[max(0, math.ceil(0.95 * len(values)) - 1)] if values else None


async def roles(owner, owner_url):
    grants = {
        "runtime": (
            "SELECT, INSERT, UPDATE, DELETE ON auth_grants, auth_factors, auth_rate_limits, auth_recovery_codes",
            "SELECT, UPDATE ON users",
            "UPDATE (updated_at) ON companies",
            "SELECT ON companies, company_config_revisions, company_integrations, integration_runs, "
            "tender_projects, operational_tasks, procurement_items, cashflow_operations, payroll_records, "
            "fleet_dispatch_records, system_alerts, integration_settings, uploaded_files, audit_logs",
            "EXECUTE ON FUNCTION public.auth_tenant_subject(text,text)",
        ),
        "worker": (
            "SELECT (id, is_active), UPDATE (engineer_documents) ON companies",
            "SELECT, INSERT, UPDATE ON uploaded_files, tender_projects, operational_tasks",
            "SELECT, UPDATE ON company_integrations, integration_runs",
            "SELECT ON company_config_revisions",
            "SELECT, INSERT, UPDATE ON platform_incidents",
            "SELECT, INSERT ON platform_integration_events",
            "EXECUTE ON FUNCTION public.schedule_integration_jobs(text), public.claim_integration_job(uuid)",
        ),
        "platform": (),
    }
    async with owner.begin() as db:
        await check_data_directory(db)
        for kind, access in grants.items():
            role = f"load_test_{kind}"
            password = secrets.token_hex(24)
            await db.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD '{password}'"))
            await db.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            for grant in access:
                await db.execute(text(f"GRANT {grant} TO {role}"))
            os.environ[f"DATABASE_{kind.upper()}_URL"] = owner_url._replace(
                netloc=f"{role}:{password}@127.0.0.1:{owner_url.port}"
            ).geturl()


async def load(*, quick: bool, rows: int):
    owner_url = pilot_owner_url()
    owner = create_async_engine(owner_url._replace(scheme="postgresql+asyncpg").geturl())
    sources = Path.cwd().parent / "load-sources"
    os.environ["INTEGRATION_TEST_WORKBOOK_DIR"] = str(sources)
    os.environ["INTEGRATIONS_ENABLED"] = "true"
    await roles(owner, owner_url)

    from app.core.config import settings
    from app.core.database import engine, worker_engine
    from app.core.security import get_password_hash
    from app.main import app
    from app.services import integration_jobs as jobs
    from app.services import platform_auth as auth

    logging.getLogger("httpx").setLevel(logging.WARNING)
    owner_factory = async_sessionmaker(owner)
    company_ids = [uuid4() for _ in range(5)]
    await asyncio.to_thread(make_books, sources, company_ids, 0, rows)
    tokens = []
    active_workers = 0
    processed_jobs = 0
    worker_errors = 0

    async def worker(*, drain=False):
        nonlocal active_workers, processed_jobs, worker_errors
        worker_id = uuid4()
        while True:
            try:
                await jobs.schedule_due()
                claim = await jobs.claim_run(worker_id)
                if not claim:
                    if drain:
                        return
                    await asyncio.sleep(1)
                    continue
                active_workers += 1
                try:
                    await jobs.process_claim(**claim)
                    processed_jobs += 1
                finally:
                    active_workers -= 1
            except asyncio.CancelledError:
                raise
            except Exception:
                worker_errors += 1
                if drain:
                    raise
                await asyncio.sleep(1)

    async def force_schedule():
        async with owner.begin() as db:
            await db.execute(text("UPDATE company_integrations SET next_due_at=clock_timestamp()"))

    async def phase(name, rate, duration, revision, clients):
        await asyncio.to_thread(make_books, sources, company_ids, revision, rows)
        async with owner_factory() as db:
            phase_start = await db.scalar(text("SELECT clock_timestamp()"))
        await force_schedule()
        start_jobs, start_errors = processed_jobs, worker_errors
        latency, status_codes = [], {}
        overlapping = 0
        queue_peak = running_peak = 0
        peak_memory = memory_mib()
        total_cpu = process_time()
        started = perf_counter()

        async def monitor():
            nonlocal queue_peak, running_peak, peak_memory
            async with owner_factory() as db:
                while True:
                    queued, running = (await db.execute(text("""
                        SELECT count(*) FILTER (WHERE state IN ('queued','retry_wait')),
                               count(*) FILTER (WHERE state = 'running') FROM integration_runs
                    """))).one()
                    queue_peak, running_peak = max(queue_peak, queued), max(running_peak, running)
                    sample = memory_mib()
                    if sample is not None:
                        peak_memory = max(peak_memory or 0, sample)
                    await db.rollback()
                    await asyncio.sleep(0.25)

        async def request(index, scheduled):
            nonlocal overlapping
            client_index = index % len(clients)
            path = READS[index % len(READS)]
            if active_workers:
                overlapping += 1
            try:
                response = await asyncio.wait_for(clients[client_index].get(BASE + path), timeout=10)
                code = response.status_code
                if code == 200 and path.startswith("/tasks/"):
                    records = response.json()["data"]
                    if not isinstance(records, list) or not records or any(
                        not str(record.get("title", record.get("task_title", ""))).startswith(f"Company {client_index // 10} /")
                        for record in records
                    ):
                        raise AssertionError("Unexpected or cross-tenant task row")
            except AssertionError:
                raise
            except Exception:
                code = 599
            latency.append((perf_counter() - scheduled) * 1000)
            status_codes[code] = status_codes.get(code, 0) + 1

        async def dispatch():
            count = rate * duration
            async with asyncio.TaskGroup() as group:
                for index in range(count):
                    scheduled = started + index / rate
                    delay = scheduled - perf_counter()
                    if delay > 0:
                        await asyncio.sleep(delay)
                    group.create_task(request(index, scheduled))

        background = [asyncio.create_task(worker()) for _ in range(2)]
        observation = asyncio.create_task(monitor())
        try:
            await dispatch()
        finally:
            for task in [*background, observation]:
                task.cancel()
            await asyncio.gather(*background, observation, return_exceptions=True)
        elapsed = perf_counter() - started
        async with owner_factory() as db:
            failed_runs = await db.scalar(text("""
                SELECT count(*) FROM integration_runs WHERE state='failed'
            """))
            run_delays = (await db.scalars(text("""
                SELECT 1000 * extract(epoch FROM started_at-created_at)
                FROM integration_runs WHERE created_at >= :start AND state='succeeded'
            """), {"start": phase_start})).all()
            active_records = (await db.scalars(text("""
                SELECT count(*) FROM operational_tasks WHERE deleted_at IS NULL GROUP BY company_id
            """))).all()
        metric = {
            "profile": name, "seconds": round(elapsed, 2), "target_rps": rate, "requests": len(latency),
            "p95_ms": round(p95(latency), 1), "http_status": status_codes,
            "reads_with_worker_active": overlapping, "jobs_processed": processed_jobs - start_jobs,
            "jobs_failed_total": failed_runs, "worker_poll_errors": worker_errors - start_errors,
            "queue_peak": queue_peak, "running_peak": running_peak,
            "queue_delay_p95_ms": round(float(p95(run_delays)), 1) if run_delays else None,
            "python_peak_mib": round(peak_memory, 1) if peak_memory is not None else None,
            "python_cpu_seconds": round(process_time() - total_cpu, 2),
        }
        print(json.dumps(metric), flush=True)
        assert set(status_codes) == {200} and overlapping and worker_errors == start_errors and failed_runs == 0
        assert active_records == [rows * 2] * len(company_ids)
        assert p95(latency) <= (500 if name == "normal" else 1000)

    try:
        password_hash = await asyncio.to_thread(get_password_hash, PASSWORD)
        async with owner_factory.begin() as db:
            for index, company_id in enumerate(company_ids):
                await db.execute(text("INSERT INTO companies (id,name,code) VALUES (:id,:name,:code)"),
                                 {"id": company_id, "name": f"Load {index}", "code": f"load-{index}"})
                for source in (0, 1):
                    await db.execute(text("""
                        INSERT INTO company_integrations
                            (company_id,provider,label,module_id,adapter_id,adapter_version,source_ref,
                             schedule_seconds,stale_after_seconds,last_success_version)
                        VALUES (:id,'test_workbook',:source,'tasks','equipment_registry','v1',:source,900,1800,1)
                    """), {"id": company_id, "source": f"source-{source}"})
                for user_index in range(10):
                    email = EMAIL.format(index=user_index)
                    user_id = uuid4()
                    await db.execute(text("""
                        INSERT INTO users (id,company_id,email,password_hash,full_name,role)
                        VALUES (:id,:company,:email,:password,:email,'manager')
                    """), {"id": user_id, "company": company_id, "email": email, "password": password_hash})
                    token, _ = await auth.issue(
                        db, auth.domain("session", False), user_id, company_id, timedelta(hours=2),
                        family=uuid4(), payload={"access_exp": (auth.now() + timedelta(hours=2)).timestamp()},
                    )
                    tokens.append(token)
        await asyncio.gather(worker(drain=True), worker(drain=True))
        assert processed_jobs == 10 and worker_errors == 0

        async with AsyncExitStack() as stack:
            clients = []
            for index, token in enumerate(tokens):
                client = await stack.enter_async_context(AsyncClient(
                    transport=ASGITransport(app=app, client=(f"127.0.0.{index // 10 + 2}", 8000 + index)),
                    base_url=settings.CLIENT_AUTH_ORIGIN, timeout=15,
                ))
                client.cookies.set(auth.cookie_name("session", False), token)
                clients.append(client)
            print(json.dumps({"fixture": {"companies": 5, "accounts": 50, "sources": 10, "rows_per_source": rows,
                                          "shortened": quick}}), flush=True)
            await phase("normal", 6, 20 if quick else 1800, 1, clients)
            await phase("stress", 20, 12 if quick else 600, 2, clients)
            await phase("burst", 40, 5, 3, clients)

            async def login(index, client):
                client.cookies.clear()
                started = perf_counter()
                csrf = await client.get(BASE + "/auth/csrf")
                result = await client.post(BASE + "/auth/login", headers={
                    "Origin": settings.CLIENT_AUTH_ORIGIN, "X-CSRF-Token": csrf.json()["data"]["csrf_token"],
                }, json={"company_code": f"load-{index // 10}", "email": EMAIL.format(index=index % 10),
                         "password": PASSWORD})
                error = result.json().get("error")
                return result.status_code, (perf_counter() - started) * 1000, error["code"] if error else None

            logins = await asyncio.gather(*(login(index, client) for index, client in enumerate(clients)))
            failures = {str(code): sum(item[2] == code for item in logins)
                        for code in {item[2] for item in logins if item[2]}}
            print(json.dumps({"profile": "login_peak", "requests": len(logins),
                              "success": sum(code == 200 for code, _, _ in logins),
                              "errors": failures, "p95_ms": round(p95([ms for _, ms, _ in logins]), 1)}), flush=True)
            assert all(code == 200 for code, _, _ in logins)
    finally:
        await engine.dispose()
        await worker_engine.dispose()
        await owner.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--rows", default=300, type=int)
    args = parser.parse_args()
    asyncio.run(load(quick=args.quick, rows=args.rows))
