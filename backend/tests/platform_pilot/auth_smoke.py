"""Centralized authentication smoke, invoked only by the disposable pilot runner."""

import asyncio
import base64
from datetime import datetime
from email import policy
from email.parser import BytesParser
from hashlib import sha1
import hmac
import os
from pathlib import Path
import re
import secrets
import shutil
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import psycopg2
from psycopg2 import sql
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def isolated_roles():
    url = os.environ["DATABASE_URL"]
    parts = urlsplit(url)
    assert os.environ["ENVIRONMENT"] == "platform-pilot-test" and parts.hostname == "127.0.0.1"
    assert parts.path == "/platform_pilot_test" and parts.username == "pilot_qa"
    with psycopg2.connect(url) as connection, connection.cursor() as cursor:
        for role, variable in (("auth_runtime_qa", "DATABASE_RUNTIME_URL"),
                               ("auth_platform_qa", "DATABASE_PLATFORM_URL"),
                               ("auth_worker_qa", "DATABASE_WORKER_URL")):
            password = secrets.token_hex(20)
            cursor.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s").format(sql.Identifier(role)), (password,))
            os.environ[variable] = urlunsplit(parts._replace(netloc=f"{role}:{password}@127.0.0.1:{parts.port}"))
        cursor.execute("""
            GRANT USAGE ON SCHEMA public TO auth_runtime_qa, auth_platform_qa, auth_worker_qa;
            GRANT SELECT, INSERT, UPDATE, DELETE ON auth_grants, auth_factors, auth_rate_limits, auth_recovery_codes
                TO auth_runtime_qa, auth_platform_qa;
            GRANT SELECT, INSERT, UPDATE, DELETE ON users, company_access_requests TO auth_runtime_qa;
            GRANT SELECT, UPDATE ON companies TO auth_runtime_qa;
            GRANT SELECT ON tender_projects, uploaded_files, company_config_revisions, procurement_items TO auth_runtime_qa;
            GRANT SELECT, UPDATE ON company_invitations TO auth_runtime_qa;
            GRANT INSERT, SELECT (timestamp) ON audit_logs TO auth_runtime_qa;
            GRANT EXECUTE ON FUNCTION auth_tenant_subject(text,text) TO auth_runtime_qa;
            GRANT SELECT, INSERT, UPDATE, DELETE ON platform_operators, company_config_revisions,
              company_config_requests, company_invitations, invitation_outbox TO auth_platform_qa;
            GRANT SELECT (id,company_id,provider,label,module_id,adapter_id,adapter_version,enabled,schedule_seconds,
                          stale_after_seconds,version,last_attempt_at,last_success_at,last_success_version,last_error_code),
                  INSERT (company_id,provider,label,module_id,adapter_id,adapter_version,source_ref,secret_ref,
                          schedule_seconds,stale_after_seconds,enabled),
                  UPDATE (label,adapter_version,source_ref,secret_ref,schedule_seconds,stale_after_seconds,
                          enabled,version,next_due_at) ON company_integrations TO auth_platform_qa;
            GRANT SELECT (id,company_id,integration_id,mode,state,attempt_count,adapter_version,release_version,
                          request_id,created_at,started_at,finished_at,rows_processed,warning_count,integration_version,
                          config_revision,available_at,error_code,idempotency_key,reason,approved_preview_id),
                  INSERT (company_id,integration_id,integration_version,config_revision,adapter_version,release_version,
                          request_id,mode,idempotency_key,reason,approved_preview_id),
                  UPDATE (state,lease_until,finished_at) ON integration_runs TO auth_platform_qa;
            GRANT SELECT, UPDATE ON company_access_requests TO auth_platform_qa;
            GRANT INSERT ON platform_operation_audit TO auth_platform_qa;
            GRANT EXECUTE ON FUNCTION platform_company_exists(uuid),
              platform_company_summary(uuid), platform_company_create(uuid,text,text), platform_company_lock(uuid),
              platform_company_transition(uuid,integer,text), platform_prepare_invitee(uuid,text,text,text),
              platform_transfer_director(uuid,integer,text,text),
              platform_pending_invitee(uuid,uuid), platform_pending_invitation_company(),
              platform_preview_is_approved(uuid,uuid,uuid,integer,integer),
              platform_approve_preview(uuid,uuid,integer,integer) TO auth_platform_qa;
            GRANT SELECT (id,is_active), UPDATE (engineer_documents) ON companies TO auth_worker_qa;
            GRANT SELECT, INSERT, UPDATE ON uploaded_files,tender_projects,operational_tasks TO auth_worker_qa;
            GRANT SELECT, UPDATE ON company_integrations,integration_runs TO auth_worker_qa;
            GRANT SELECT ON company_config_revisions TO auth_worker_qa;
            GRANT SELECT, INSERT, UPDATE ON platform_incidents TO auth_worker_qa;
            GRANT SELECT, INSERT ON platform_integration_events TO auth_worker_qa;
            GRANT EXECUTE ON FUNCTION schedule_integration_jobs(text), claim_integration_job(uuid) TO auth_worker_qa;
        """)


isolated_roles()
os.environ["INTEGRATIONS_ENABLED"] = "true"
os.environ["INTEGRATION_TEST_WORKBOOK_DIR"] = str(Path.cwd().parent / "platform-admin-sources")

from app.core.config import settings
from app.core.database import set_tenant_context
from app.core.security import create_access_token, get_password_hash
from app.core.platform_database import PlatformSessionLocal
from app.api.v1.platform_auth import db_dependency
from app.main import app
from app.models.company import Company
from app.models.enums import UserRole
from app.models.user import User
from app.services.invitation_outbox import deliver_one
from app.services import integration_jobs
from smoke import make_sources

ROOT = "/api/v1"
PASSWORD = "smoke-secret-password"
EMAIL = "director@example.com"


def totp(secret):
    counter = int(datetime.now().timestamp()) // 30
    digest = hmac.new(base64.b32decode(secret), counter.to_bytes(8, "big"), sha1).digest()
    offset = digest[-1] & 0x0f
    return f"{(int.from_bytes(digest[offset:offset + 4], 'big') & 0x7fffffff) % 1000000:06d}"


async def call(client, method, path, code, *, json=None, csrf=True, headers=None):
    headers = headers or {}
    prefix = "/platform/auth" if str(client.base_url).startswith(settings.PLATFORM_AUTH_ORIGIN) else "/auth"
    if method != "GET" and csrf:
        r = await client.get(ROOT + prefix + "/csrf")
        assert r.status_code == 200, r.text
        headers = headers | {"Origin": str(client.base_url).rstrip("/"), "X-CSRF-Token": r.json()["data"]["csrf_token"]}
    response = await client.request(method, ROOT + path, headers=headers, json=json)
    assert response.status_code == code, (method, path, code, response.status_code, response.text)
    return response.json().get("data")


async def enroll(client, prefix, login):
    data = await call(client, "POST", prefix + "/login", 200, json=login)
    assert data["step"] == "mfa_enrollment_required"
    await call(client, "GET", prefix + "/me", 401)
    challenge = {"challenge_id": data["challenge_id"]}
    factor = await call(client, "POST", prefix + "/mfa/setup", 200, json=challenge)
    result = await call(client, "POST", prefix + "/mfa/verify", 200, json=challenge | {"code": totp(factor["secret"])})
    assert result["step"] == "authenticated"
    assert len(result["recovery_codes"]) == 8
    return result["profile"]


async def seed():
    password_hash = await asyncio.to_thread(get_password_hash, PASSWORD)
    engine = create_async_engine(settings.async_database_url)
    async with async_sessionmaker(engine, expire_on_commit=False).begin() as db:
        a, b = Company(name="Smoke A", code="smoke-a"), Company(name="Smoke B", code="smoke-b")
        db.add_all([a, b])
        await db.flush()
        db.add_all([
            User(company_id=company.id, email=EMAIL, password_hash=password_hash, full_name="Director", role=UserRole.ADMIN)
            for company in (a, b)
        ])
        owner_id = uuid4()
        await db.execute(text("""
            INSERT INTO platform_operators (id,email,full_name,password_hash,role,is_active)
            VALUES (:id,'owner@example.com','Owner',:password,'owner',true)
        """), dict(id=owner_id, password=password_hash))
    await engine.dispose()
    return a.id, b.id, owner_id


def latest_token(address: str) -> str:
    files = sorted(Path(settings.AUTH_MAIL_OUTBOX).glob("*.eml"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
    for path in files:
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        if message["To"] == address:
            return re.search(r"#token=([A-Za-z0-9_-]+)", message.get_content()).group(1)
    raise AssertionError("No matching synthetic outbox message")


async def main():
    assert settings.PLATFORM_AUTH_ENABLED and settings.ENVIRONMENT == "platform-pilot-test"
    a, b, owner = await seed()
    transport = ASGITransport(app=app)
    seed_engine = create_async_engine(settings.async_database_url)
    async with seed_engine.connect() as db:
        other_user = await db.scalar(text("SELECT id FROM users WHERE company_id=:company"), {"company": b})
    await seed_engine.dispose()

    @app.post(ROOT + "/_pilot_test/deferred-error")
    async def deferred_error(db: db_dependency):
        await set_tenant_context(db, a)
        # The legacy FK accepts an existing user. The tenant FK is deferred until commit.
        await db.execute(text("""
            INSERT INTO audit_logs (id,company_id,user_id,entity_type,entity_id,new_status)
            VALUES (:id,:company,:user,'test',:id,'pending')
        """), {"id": uuid4(), "company": a, "user": other_user})
        return {"would_have_been_success": True}

    async with (
        AsyncClient(transport=transport, base_url=settings.CLIENT_AUTH_ORIGIN) as director,
        AsyncClient(transport=transport, base_url=settings.CLIENT_AUTH_ORIGIN) as worker,
        AsyncClient(transport=transport, base_url=settings.PLATFORM_AUTH_ORIGIN) as operator,
    ):
        await call(director, "POST", "/_pilot_test/deferred-error", 500, csrf=False)
        await call(director, "POST", "/auth/register", 404, csrf=False)
        await call(director, "POST", "/auth/login", 403, json={"email": EMAIL, "password": PASSWORD,
                   "company_code": "smoke-a"}, csrf=False)
        throttle = {"email": "unknown-throttled@example.com", "company_code": "smoke-a"}
        for _ in range(6):
            await call(director, "POST", "/auth/password/forgot", 202, json=throttle)
        csrf = (await director.get(ROOT + "/auth/csrf")).json()["data"]["csrf_token"]
        limited = await director.post(ROOT + "/auth/password/forgot", json=throttle,
                                      headers={"Origin": settings.CLIENT_AUTH_ORIGIN, "X-CSRF-Token": csrf})
        assert limited.status_code == 429 and limited.headers["Retry-After"] == "300"
        assert limited.json()["error"]["code"] == "RATE_LIMITED"
        director_data = await enroll(director, "/auth", {"email": EMAIL, "password": PASSWORD, "company_code": "smoke-a"})
        assert director_data["company"]["id"] == str(a)
        bearer = create_access_token(director_data["id"], str(a), "admin")
        await call(worker, "GET", "/auth/me", 401, headers={"Authorization": f"Bearer {bearer}"})
        await call(director, "POST", "/auth/login", 401, json={"email": EMAIL, "password": PASSWORD,
                   "company_code": "unknown"})
        owner_data = await enroll(operator, "/platform/auth", {"email": "owner@example.com", "password": PASSWORD})
        assert owner_data["id"] == str(owner)
        async with PlatformSessionLocal() as db:
            for table in ("users", "companies", "tender_projects", "audit_logs"):
                assert not await db.scalar(text("SELECT has_table_privilege(:table, 'SELECT')"), {"table": table})
            for table, field in (("company_integrations", "source_ref"), ("company_integrations", "secret_ref"),
                                 ("integration_runs", "fingerprint")):
                assert not await db.scalar(text("SELECT has_column_privilege(:table, :field, 'SELECT')"),
                                           {"table": table, "field": field})
        await call(operator, "GET", "/auth/me", 403)
        await call(director, "GET", "/platform/auth/me", 403)
        access_request = await call(director, "POST", "/company/access-requests", 201,
                                    json={"email": "worker@example.com", "full_name": "Worker", "role": "manager"})
        assert access_request["state"] == "pending"
        invite = await call(operator, "POST", f"/platform/companies/{a}/invitations", 201,
                            json={"access_request_id": access_request["id"]},
                            headers={"Idempotency-Key": "smoke-invite-1"})
        assert invite["delivery_state"] == "pending" and "token" not in invite
        assert await deliver_one()
        token = latest_token("worker@example.com")
        accept = {"token": token, "password": PASSWORD, "full_name": "Worker"}
        await call(worker, "POST", "/auth/invitation/accept", 200, json=accept)
        await call(worker, "POST", "/auth/invitation/accept", 410, json=accept)
        credentials = {"email": "worker@example.com", "password": PASSWORD, "company_code": "smoke-a"}
        signed_in = await call(worker, "POST", "/auth/login", 200, json=credentials)
        worker_id = signed_in["profile"]["id"]
        await call(worker, "POST", "/auth/refresh", 200)
        team = await call(director, "GET", "/company/users", 200)
        assert len(team) == 2
        version = next(row["version"] for row in team if row["id"] == str(worker_id))
        await call(director, "PATCH", f"/company/users/{worker_id}", 200, json={"version": version, "is_active": False})
        await call(worker, "GET", "/auth/me", 401)
        await call(worker, "POST", "/auth/refresh", 401)
        await call(operator, "GET", "/platform/operators", 200)
        path = f"/platform/companies/{a}/config"
        configured = await call(operator, "GET", path, 200)
        assert configured["revision"] == 0
        draft_payload = {"base_revision": 0, "modules": [{"id": "projects", "label": "Сделки", "order": 0, "enabled": True}]}
        draft_key = {"Idempotency-Key": "smoke-draft-1"}
        draft = await call(operator, "POST", path + "/revisions", 201, json=draft_payload, headers=draft_key)
        assert draft == await call(operator, "POST", path + "/revisions", 201, json=draft_payload, headers=draft_key)
        await call(operator, "POST", path + "/revisions", 409, json=draft_payload | {"base_revision": 1}, headers=draft_key)
        await call(operator, "POST", path + f"/revisions/{draft['revision']}/publish", 200,
                   json={"expected_active_revision": 0, "reason": "Smoke"}, headers={"Idempotency-Key": "smoke-publish-1"})
        enabled = await call(director, "GET", "/company/modules", 200)
        assert [module["id"] for module in enabled["modules"]] == ["projects"]
        await call(director, "GET", "/procurement/items", 403)
        await call(director, "GET", "/customer-tenders", 200)
        assert (await call(operator, "GET", f"/platform/companies/{b}/config", 200))["revision"] == 0
        await call(operator, "POST", path + "/revisions/0/rollback", 200,
                   json={"expected_active_revision": draft["revision"], "reason": "Smoke rollback"},
                   headers={"Idempotency-Key": "smoke-rollback-1"})
        await call(director, "GET", "/procurement/items", 200)
        company_payload = {"code": "new-pilot", "name": "New Pilot"}
        create_key = {"Idempotency-Key": "smoke-company-1"}
        new_company = await call(operator, "POST", "/platform/companies", 201, json=company_payload, headers=create_key)
        assert new_company["state"] == "draft"
        assert new_company == await call(operator, "POST", "/platform/companies", 201, json=company_payload, headers=create_key)
        listed = await call(operator, "GET", "/platform/companies?state=draft&search=new", 200)
        assert [row["id"] for row in listed] == [new_company["id"]]
        company_path = "/platform/companies/" + new_company["id"]
        change = {"version": 1, "to": "active", "reason": "Approve pilot"}
        activation_key = {"Idempotency-Key": "smoke-activate-1"}
        await call(operator, "POST", company_path + "/transitions", 409, json=change, headers=activation_key)
        invite = await call(operator, "POST", company_path + "/invitations", 201,
                            json={"email": "new-director@example.com", "full_name": "New Director", "role": "admin"},
                            headers={"Idempotency-Key": "smoke-director-1"})
        assert invite["delivery_state"] == "pending" and not await deliver_one()
        new_modules = draft_payload["modules"] + [{"id": "sources", "order": 1, "enabled": True}]
        draft = await call(operator, "POST", company_path + "/config/revisions", 201,
                           json=draft_payload | {"modules": new_modules}, headers={"Idempotency-Key": "smoke-new-draft"})
        await call(operator, "POST", company_path + f"/config/revisions/{draft['revision']}/publish", 200,
                   json={"expected_active_revision": 0, "reason": "Approve module profile"},
                   headers={"Idempotency-Key": "smoke-new-publish"})
        source_dir = Path(settings.INTEGRATION_TEST_WORKBOOK_DIR) / new_company["id"]
        source_dir.mkdir(parents=True)
        _, workbook = make_sources(Path.cwd().parent / "platform-admin-fixtures")[0]
        shutil.copyfile(workbook, source_dir / "registry.xlsx")
        integration = await call(operator, "POST", company_path + "/integrations", 201,
                                 json={"type": "test_workbook", "label": "Pilot register", "module_id": "projects",
                                       "adapter_id": "customer_tenders", "adapter_version": "v1",
                                       "source_ref": "registry", "stale_after_seconds": 300},
                                 headers={"Idempotency-Key": "smoke-new-source"})
        assert {"source_ref", "secret_ref", "fingerprint"}.isdisjoint(integration)
        integration_path = company_path + "/integrations/" + integration["id"]
        integration = await call(operator, "PATCH", integration_path, 200,
                                 json={"version": integration["version"], "label": "Pilot register approved"})
        version = integration["version"]
        await call(operator, "POST", company_path + "/transitions", 409, json=change, headers=activation_key)
        run_input = {"mode": "preview", "reason": "Check pilot", "expected_integration_version": version}
        preview = await call(operator, "POST", integration_path + "/runs", 202, json=run_input,
                             headers={"Idempotency-Key": "smoke-new-preview"})

        async def process_run(expected_id):
            for _ in range(10):
                claimed = await integration_jobs.claim_run(uuid4())
                assert claimed
                await integration_jobs.process_claim(**claimed)
                if str(claimed["run_id"]) == expected_id:
                    return
            raise AssertionError("Target run did not reach the worker")

        await process_run(preview["id"])
        preview_path = company_path + "/runs/" + preview["id"]
        completed = await call(operator, "GET", preview_path, 200)
        assert completed["state"] == "succeeded" and completed["rows_processed"] > 0
        assert {"source_ref", "secret_ref", "fingerprint"}.isdisjoint(completed)
        await call(operator, "POST", preview_path + "/approve", 200,
                   json={"expected_integration_version": version, "reason": "Approve test evidence"},
                   headers={"Idempotency-Key": "smoke-new-approve"})
        active_company = await call(operator, "POST", company_path + "/transitions", 200, json=change, headers=activation_key)
        assert active_company["state"] == "active" and await deliver_one()
        new_login = {"email": "new-director@example.com", "password": PASSWORD, "company_code": "new-pilot"}
        await call(worker, "POST", "/auth/invitation/accept", 200,
                   json={"token": latest_token(new_login["email"]), "password": PASSWORD, "full_name": "New Director"})
        await enroll(worker, "/auth", new_login)
        import_run = await call(operator, "POST", integration_path + "/runs", 202,
                                json=run_input | {"mode": "import", "approved_preview_id": preview["id"]},
                                headers={"Idempotency-Key": "smoke-new-import"})
        await process_run(import_run["id"])
        assert (await call(operator, "GET", company_path + "/runs/" + import_run["id"], 200))["state"] == "succeeded"
        assert len(await call(worker, "GET", "/customer-tenders", 200)) == 1
        successor = {"email": "successor@example.com", "password": PASSWORD, "company_code": "new-pilot"}
        transfer = {"version": active_company["version"], "current_email": new_login["email"],
                    "successor_email": successor["email"], "reason": "Confirmed handover"}
        transfer_key = {"Idempotency-Key": "smoke-director-transfer"}
        await call(operator, "POST", company_path + "/director-transfer", 409, json=transfer, headers=transfer_key)
        await call(operator, "POST", company_path + "/invitations", 201,
                   json={"email": successor["email"], "full_name": "Successor", "role": "admin"},
                   headers={"Idempotency-Key": "smoke-successor-invite"})
        assert await deliver_one()
        async with AsyncClient(transport=transport, base_url=settings.CLIENT_AUTH_ORIGIN) as successor_client:
            await call(successor_client, "POST", "/auth/invitation/accept", 200,
                       json={"token": latest_token(successor["email"]), "password": PASSWORD, "full_name": "Successor"})
            await enroll(successor_client, "/auth", successor)
            active_company = await call(operator, "POST", company_path + "/director-transfer", 200,
                                        json=transfer, headers=transfer_key)
            await call(worker, "GET", "/auth/me", 401)
            await call(successor_client, "GET", "/auth/me", 200)
        pause = await call(operator, "POST", company_path + "/transitions", 200,
                           json={"version": active_company["version"], "to": "paused", "reason": "Pause pilot"},
                           headers={"Idempotency-Key": "smoke-pause-1"})
        assert pause["state"] == "paused"
        await call(worker, "GET", "/auth/me", 401)
        close = await call(operator, "POST", company_path + "/transitions", 200,
                           json={"version": pause["version"], "to": "closed", "reason": "Close pilot"},
                           headers={"Idempotency-Key": "smoke-close-1"})
        assert close["state"] == "closed"
        from operations_smoke import check_operations
        from access_edge_smoke import check_access_edges
        operations_engine = create_async_engine(settings.async_database_url)
        try:
            await check_operations(call, operations_engine, director, operator, a, b)
            await check_access_edges(call, transport, settings.CLIENT_AUTH_ORIGIN, director, operator, a,
                                     operations_engine, deliver_one, latest_token)
        finally:
            await operations_engine.dispose()
    print("Centralized auth smoke passed: invitation, MFA, cookies, CSRF, rotation and revocation.")


if __name__ == "__main__":
    asyncio.run(main())
