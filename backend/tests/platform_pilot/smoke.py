"""Synthetic pilot scenario, executed only by the isolated runner."""

import asyncio
from email.message import EmailMessage
import os
from pathlib import Path
import secrets
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from openpyxl import Workbook, load_workbook
from sqlalchemy import text


def make_sources(root: Path):
    build = root / "construction-drive"
    clinic = root / "clinic-drive"
    build_file = build / "01_Сметы_и_Тендеры" / "Реестр.xlsx"
    clinic_file = clinic / "02_Счета_Снабжения" / "Реестр.xlsx"
    for path in (build_file, clinic_file):
        path.parent.mkdir(parents=True)

    book = Workbook()
    registry = book.active
    registry.title = "Реест Ольга"
    registry.append(["вн.№", "Заказчик"] + [None] * 20)
    registry.append([None] * 12 + ["НМЦК", "Процент падения", "Сумма падения", "Сумма контракта (выиграли)"])
    registry.append([None] * 22)
    registry.append([2501, "Тестовый заказчик строительства"] + [None] * 14 + ["На проверке"])
    monitor = book.create_sheet("Ежедневный мониторинг")
    monitor.append(["вн.№", "Заказчик", "Юрлицо", "Город"] + ["Дата", "Документ", "Ссылка", "ЕИС", "Подписано", "Оплата", "Полностью"] * 3)
    monitor.append([None] * 25)
    monitor.append([None] * 4 + ["окт.26"] + [None] * 6 + ["ноя.26"] + [None] * 6 + ["дек.26"])
    monitor.append(["2501", "Тестовый заказчик строительства", None, None, "2026-10-26"])
    book.save(build_file)

    book = Workbook()
    book.active.title = "Снабжение"
    book.active.append(["Проект", "Наименование_ТМЦ", "Количество", "Сумма_счета", "Срок"])
    book.active.append(["2501", "Тестовый фильтр оборудования", 2, 1800, "2026-11-20"])
    book.save(clinic_file)
    return (build, build_file), (clinic, clinic_file)


def capture_mail(root: Path, recipient: str, subject: str, body: str) -> None:
    """Capture mail locally without resolving DNS or opening an SMTP connection."""
    mail = EmailMessage()
    mail["From"] = "pilot-qa@example.com"
    mail["To"] = recipient
    mail["Subject"] = subject
    mail.set_content(body)
    outbox = root / "mail-outbox"
    outbox.mkdir(exist_ok=True)
    (outbox / f"{secrets.token_hex(8)}.eml").write_bytes(mail.as_bytes())


async def smoke(root: Path) -> None:
    from app.core.config import settings
    from app.core.database import async_session_factory, engine
    from app.core.security import get_password_hash
    from app.main import app
    from app.models.company import Company
    from app.models.enums import UserRole
    from app.models.user import User
    from app.services.google_drive import GoogleDriveClient

    assert settings.ENVIRONMENT == "platform-pilot-test"
    assert settings.GOOGLE_DRIVE_MOCK
    assert not settings.GOOGLE_SERVICE_ACCOUNT_JSON
    assert settings.STORAGE_DIR.parent == root
    assert not (Path.cwd() / ".env").exists()
    initial_files = {path for path in settings.STORAGE_DIR.rglob("*") if path.is_file()}

    drives = make_sources(root)
    passwords = {}
    companies = (("construction", "Строй-Пилот"), ("clinic", "Клиника-Операции"))
    try:
        async with async_session_factory() as db:
            data_dir = await db.scalar(text("SHOW data_directory"))
            if Path(data_dir).resolve() != root / "postgres":
                raise RuntimeError("Refusing to populate a PostgreSQL cluster outside the test directory.")
            for code, name in companies:
                company = Company(name=name)
                db.add(company)
                await db.flush()
                for role in (UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER):
                    email = f"{code}-{role.value}@example.com"
                    passwords[email] = secrets.token_urlsafe(24)
                    db.add(User(
                        company_id=company.id, role=role, full_name=f"{name} / {role.value}",
                        email=email, password_hash=get_password_hash(passwords[email]),
                    ))
            await db.commit()

        # ASGI transport avoids starting an HTTP listener or the periodic scheduler.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://pilot.test/api/v1/") as client:
            async def request(method: str, path: str, **kwargs):
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()["data"]

            async def login(code: str, role: str):
                email = f"{code}-{role}@example.com"
                data = await request("POST", "auth/login", json={
                    "email": email, "password": passwords[email],
                })
                return {"Authorization": f"Bearer {data['access_token']}"}

            a = await login("construction", "admin")
            b = await login("clinic", "admin")
            reader = await login("construction", "viewer")
            assert len(await request("GET", "company/users", headers=a)) == 3
            assert len(await request("GET", "company/users", headers=b)) == 3
            assert (await client.post("sync/drive-now", headers=reader)).status_code == 403

            for headers, (drive, _) in zip((a, b), drives, strict=True):
                # The current application has one global Drive binding. Substitute
                # the local transport one call at a time, leaving import/API/DB real.
                transport = GoogleDriveClient(mock_mode=True, mock_dir=drive)
                with patch("app.services.drive_sync.google_drive_client", transport):
                    result = await request("POST", "sync/drive-now", headers=headers)
                    assert result["processed_files_count"] == 1, result
                    repeat = await request("POST", "sync/drive-now", headers=headers)
                    assert repeat["skipped_files_count"] == 1, repeat

            tenders = await request("GET", "customer-tenders", headers=a)
            assert len(tenders) == 1 and tenders[0]["number"] == "2501"
            assert tenders[0]["amount"] is None
            assert await request("GET", "customer-tenders", headers=b) == []
            supplies = await request("GET", "procurement/items", headers=b)
            assert len(supplies) == 1 and supplies[0]["item_name"] == "Тестовый фильтр оборудования"
            assert await request("GET", "procurement/items", headers=a) == []
            files_a = await request("GET", "files", headers=a)
            files_b = await request("GET", "files", headers=b)
            assert len(files_a) == len(files_b) == 1
            assert files_a[0]["original_name"] == files_b[0]["original_name"] == "Реестр.xlsx"
            assert files_a[0]["id"] != files_b[0]["id"]
            denied = await client.delete(f"files/{files_b[0]['id']}", headers=a)
            assert denied.status_code == 404
            assert await request("GET", "files", headers=b) == files_b
            current_files = {path for path in settings.STORAGE_DIR.rglob("*") if path.is_file()}
            assert initial_files <= current_files and len(current_files - initial_files) == 2

            build_drive, build_file = drives[0]
            book = load_workbook(build_file)
            book["Реест Ольга"].delete_cols(17)
            book.save(build_file)
            book.close()
            with patch("app.services.drive_sync.google_drive_client", GoogleDriveClient(mock_mode=True, mock_dir=build_drive)):
                failed = await request("POST", "sync/drive-now", headers=a)
                assert failed["status"] == "error", failed
                assert failed["last_error"]
                assert failed["details"][-1]["action"] == "error"
            assert await request("GET", "customer-tenders", headers=a) == tenders

            clinic_drive, clinic_file = drives[1]
            book = load_workbook(clinic_file)
            book.active["B2"] = "Тестовый фильтр оборудования, новая версия"
            book.save(clinic_file)
            book.close()
            with patch("app.services.drive_sync.google_drive_client", GoogleDriveClient(mock_mode=True, mock_dir=clinic_drive)):
                updated = await request("POST", "sync/drive-now", headers=b)
                assert updated["status"] == "idle" and updated["processed_files_count"] == 1, updated
            supplies = await request("GET", "procurement/items", headers=b)
            assert len(supplies) == 1 and supplies[0]["item_name"] == "Тестовый фильтр оборудования, новая версия"
            assert (await request("GET", "sync/status", headers=a))["status"] == "error"
            assert (await request("GET", "sync/status", headers=b))["status"] == "idle"

        capture_mail(root, "clinic-admin@example.com", "QA mail transport", "Synthetic delivery probe")
        assert len(list((root / "mail-outbox").glob("*.eml"))) == 1
    finally:
        await engine.dispose()
    print("Pilot smoke passed: separate companies, real API and imports, repeat and storage.")


if __name__ == "__main__":
    root = Path.cwd().parent.resolve()
    db_url = urlsplit(os.environ.get("DATABASE_URL", ""))
    if (
        os.environ.get("ENVIRONMENT") != "platform-pilot-test"
        or not root.name.startswith("enterprise-platform-pilot-")
        or not (root / "postgres" / "postmaster.pid").is_file()
        or db_url.hostname != "127.0.0.1"
        or db_url.path != "/platform_pilot_test"
        or db_url.username != "pilot_qa"
        or not db_url.port
    ):
        raise SystemExit("Run this scenario via run.py.")
    asyncio.run(smoke(root))
