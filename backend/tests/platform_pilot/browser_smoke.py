"""Headless Chrome smoke on the disposable cluster. Uses the installed Chrome and its CDP API."""

import argparse
import asyncio
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import uvicorn
from websockets.asyncio.client import connect


class Page:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0

    async def command(self, method, **params):
        self.sequence += 1
        current = self.sequence
        await self.socket.send(json.dumps({"id": current, "method": method, "params": params}))
        while True:
            reply = json.loads(await asyncio.wait_for(self.socket.recv(), timeout=20))
            if reply.get("id") == current:
                if reply.get("error"):
                    raise AssertionError(f"Chrome command failed: {method}: {reply['error']['message']}")
                return reply.get("result", {})

    async def value(self, expression):
        result = await self.command("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in result:
            raise AssertionError("Chrome page script failed: " + result["exceptionDetails"]["text"])
        return result["result"].get("value")

    async def wait(self, expression, description):
        for _ in range(120):
            try:
                value = await self.value(expression)
            except AssertionError:
                value = None
            if value:
                return value
            await asyncio.sleep(.1)
        raise AssertionError(f"Browser expectation not met: {description}")

    async def visit(self, url):
        await self.command("Page.navigate", url=url)
        await self.wait(f"location.href === {json.dumps(url)} && document.readyState === 'complete'", "page navigation")

    async def text(self, substring):
        return await self.wait(f"document.body.innerText.includes({json.dumps(substring)})", substring)

    async def fill(self, **fields):
        for name, value in fields.items():
            await self.wait(f"document.querySelector('input[name={name}]') !== null", name)
            await self.value(f"""(() => {{
                const field = document.querySelector('input[name={name}]');
                Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(field, {json.dumps(value)});
                field.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return true;
            }})()""")

    async def click(self, selector):
        selector = json.dumps(selector)
        await self.wait(f"!!document.querySelector({selector}) && !document.querySelector({selector}).disabled", selector)
        await self.value(f"document.querySelector({selector}).click()")

    async def status(self):
        return await self.value("performance.getEntriesByType('navigation')[0]?.responseStatus")


def certificate(root, hosts):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    identity = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hosts[0])])
    cert = (x509.CertificateBuilder()
            .subject_name(identity).issuer_name(identity).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host) for host in hosts]), critical=False)
            .sign(key, hashes.SHA256()))
    key_path, cert_path = root / "browser-key.pem", root / "browser-cert.pem"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                            serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    spki = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return key_path, cert_path, b64encode(sha256(spki).digest()).decode("ascii")


async def fixture(engine, company):
    from app.services.platform_operations import record_integration_outcome

    async with engine.begin() as db:
        assert Path(await db.scalar(text("SHOW data_directory"))).resolve() == Path.cwd().parent / "postgres"
        for sql in (
            "GRANT SELECT ON audit_logs TO auth_runtime_qa",
            "GRANT SELECT, INSERT, UPDATE ON platform_incidents TO auth_platform_qa",
            "GRANT SELECT ON platform_integration_events, platform_run_correlation TO auth_platform_qa",
            "GRANT SELECT ON platform_operation_audit TO auth_platform_qa",
            "GRANT EXECUTE ON FUNCTION platform_operation_status() TO auth_platform_qa",
        ):
            await db.execute(text(sql))
        await db.execute(text("""
            INSERT INTO company_config_revisions (company_id, revision, state, modules)
            VALUES (:company, 1, 'active', CAST(:modules AS jsonb))
        """), {"company": company, "modules": json.dumps([
            {"id": "projects", "label": "Проекты стенда", "order": 0, "enabled": True}
        ])})
        source = await db.scalar(text("""
            INSERT INTO company_integrations
                (company_id,provider,label,module_id,adapter_id,adapter_version,source_ref,stale_after_seconds)
            VALUES (:company,'test_workbook','Синтетический источник','projects','customer_tenders','v1','test',600)
            RETURNING id
        """), {"company": company})
        run_id = await db.scalar(text("""
            INSERT INTO integration_runs
                (company_id,integration_id,integration_version,adapter_version,release_version,request_id,mode,state,
                 idempotency_key,reason,error_code)
            VALUES (:company,:source,1,'v1','test','browser-smoke','import','failed','test','test','SCHEMA_MISMATCH')
            RETURNING id
        """), {"company": company, "source": source})
        await record_integration_outcome(db, company_id=company, integration_id=source, run_id=run_id,
                                         code="SCHEMA_MISMATCH", succeeded=False)
        director = await db.scalar(text("SELECT id FROM users WHERE company_id=:company AND role='admin'"),
                                   {"company": company})
        await db.execute(text("""
            INSERT INTO platform_operators (id,email,full_name,password_hash,role,is_active)
            SELECT gen_random_uuid(),'support@example.com','QA Support',password_hash,'support',true
            FROM users WHERE id=:director
        """), {"director": director})
        return director


async def browser_flow(page, client, platform, company, director, engine, totp, email, password):
    async def enroll(user_email):
        await page.fill(email=user_email, password=password)
        await page.click("form .auth-submit")
        key = await page.wait("document.querySelector('.auth-access code')?.textContent", "MFA setup key")
        code = totp(key)
        if await page.value("!!document.querySelector('input[name=mfa_code]')"):
            await page.fill(mfa_code=code)
        else:
            await page.fill(code=code)
        await page.click("form .auth-submit")
        await page.text("Коды восстановления")
        await page.click(".auth-submit")

    await page.visit(client + "/c/smoke-a/m/projects")
    assert await page.status() == 200
    await page.text("Вход в кабинет")
    await enroll(email)
    await page.wait("!!document.querySelector('.workspace-topbar')", "company workspace")
    await page.text("Проекты стенда")
    await page.visit(client + "/c/smoke-a/m/finance")
    assert await page.status() == 200
    await page.text("Раздел недоступен")
    assert await page.value("fetch('/api/v1/dashboard/finance').then(response => response.status)") == 403
    await page.visit(client + "/c/smoke-a/team")
    assert await page.status() == 200
    await page.text("Команда компании")
    await page.text(email)
    await page.command("Page.reload", ignoreCache=True)
    await page.text("Команда компании")
    await page.visit(client + "/c/smoke-b/team")
    await page.text("Этот кабинет недоступен в текущей сессии")
    assert not await page.value("document.body.innerText.includes('Команда компании')")

    await page.visit(platform + "/platform")
    await page.text("Вход в панель платформы")
    await enroll("owner@example.com")
    await page.text("Smoke A")
    await page.click(f'a[href="/platform/companies/{company}"]')
    await page.text("Синтетический источник")
    await page.text("Структура таблицы не соответствует адаптеру")
    await page.visit(platform + f"/platform/companies/{company}")
    assert await page.status() == 200
    await page.text("Синтетический источник")
    assert await page.value("fetch('/api/v1/auth/me').then(response => response.status)") == 403
    await page.visit(platform + "/platform/operators")
    assert await page.status() == 200
    await page.text("owner@example.com")
    await page.click("header button")
    await page.text("Вход в панель платформы")
    await enroll("support@example.com")
    await page.text("QA Support")
    assert not await page.value("!!document.querySelector('a[href=\"/platform/operators\"]')")
    await page.visit(platform + "/platform/operators")
    await page.text("Раздел недоступен")
    assert await page.value("fetch('/api/v1/platform/operators').then(response => response.status)") == 403

    async with engine.begin() as db:
        await db.execute(text("""
            UPDATE auth_grants SET revoked_at = now() WHERE company_id=:company
            AND subject_id=:director AND purpose='client_session'
        """), {"company": company, "director": director})
    await page.visit(client + "/c/smoke-a/team")
    await page.text("Вход в кабинет")
    assert not await page.value("document.body.innerText.includes('Команда компании')")
    await page.visit(client + "/unknown-browser-smoke-path")
    assert await page.status() == 404
    await page.visit(client + "/api/v1/unknown-browser-smoke-path")
    assert await page.status() == 404


async def main(chrome):
    root = Path.cwd().parent.resolve()
    assert os.environ["ENVIRONMENT"] == "platform-pilot-test" and root.name.startswith("enterprise-platform-pilot-")
    assert not (Path.cwd() / ".env").exists()
    hosts = ("client.pilot.test", "platform.pilot.test")
    key, cert, fingerprint = certificate(root, hosts)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    client, platform = (f"https://{host}:{port}" for host in hosts)
    os.environ.update(CLIENT_AUTH_ORIGIN=client, PLATFORM_AUTH_ORIGIN=platform)
    from auth_smoke import EMAIL, PASSWORD, app, seed, settings, totp

    company, _, _ = await seed()
    engine = create_async_engine(settings.async_database_url)
    director = await fixture(engine, company)
    config = uvicorn.Config(app, lifespan="off", log_level="error", ssl_keyfile=str(key), ssl_certfile=str(cert))
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve(sockets=[listener]))
    process = None
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(.1)
        else:
            raise AssertionError("Temporary HTTPS server did not start")
        profile = root / "chrome-profile"
        with (root / "chrome.log").open("wb") as chrome_log:
            process = subprocess.Popen([
                str(chrome), "--headless=new", "--disable-gpu", "--no-first-run", "--disable-background-networking",
                "--no-proxy-server", "--host-resolver-rules=MAP *.pilot.test 127.0.0.1",
                f"--ignore-certificate-errors-spki-list={fingerprint}", "--remote-debugging-port=0",
                f"--user-data-dir={profile}", "about:blank",
            ], stdout=chrome_log, stderr=chrome_log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        endpoint = profile / "DevToolsActivePort"
        for _ in range(100):
            if endpoint.exists():
                break
            if process.poll() is not None:
                raise AssertionError("Headless Chrome exited before exposing CDP")
            await asyncio.sleep(.1)
        else:
            raise AssertionError("Chrome did not publish a local debugging port")
        cdp_port = int(endpoint.read_text().splitlines()[0])
        async with httpx.AsyncClient(trust_env=False) as debug:
            targets = (await debug.get(f"http://127.0.0.1:{cdp_port}/json/list")).json()
        page_target = next(target for target in targets if target["type"] == "page")
        async with connect(page_target["webSocketDebuggerUrl"], max_size=2**24) as ws:
            page = Page(ws)
            await browser_flow(page, client, platform, company, director, engine, totp, EMAIL, PASSWORD)
        print("Chrome smoke passed: secure client/operator login, MFA, route reload, module and tenant denial, source/incident, revocation and 404.")
    finally:
        if process and process.poll() is None:
            if (root / "chrome-profile" / "DevToolsActivePort").exists():
                try:
                    debug_info = (root / "chrome-profile" / "DevToolsActivePort").read_text().splitlines()
                    async with connect(f"ws://127.0.0.1:{debug_info[0]}{debug_info[1]}") as ws:
                        await ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
                except (OSError, ValueError):
                    process.terminate()
            else:
                process.terminate()
            try:
                await asyncio.to_thread(process.wait, 10)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait)
        server.should_exit = True
        await server_task
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chrome", type=Path)
    asyncio.run(main(parser.parse_args().chrome))
