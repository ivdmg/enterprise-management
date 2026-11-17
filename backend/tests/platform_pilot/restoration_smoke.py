"""Verify a disposable PostgreSQL dump and tenant-only extract of legacy fixture data."""

import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit
from zipfile import ZipFile

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def snapshot():
    root = Path.cwd().parent.resolve()
    parsed = urlsplit(os.environ["DATABASE_URL"])
    if (os.environ["ENVIRONMENT"] != "platform-pilot-test" or parsed.hostname != "127.0.0.1"
            or parsed.path != "/platform_pilot_test" or not root.name.startswith("enterprise-platform-pilot-")
            or (Path.cwd() / ".env").exists()):
        raise RuntimeError("Run only through the disposable pilot runner.")
    restored_url = parsed._replace(scheme="postgresql+asyncpg", path="/platform_pilot_restore").geturl()
    storage = (root / "restore-file-backup").resolve()
    engine = create_async_engine(restored_url)
    started = monotonic()
    try:
        async with engine.connect() as db:
            assert Path(await db.scalar(text("SHOW data_directory"))).resolve() == root / "postgres"
            assert await db.scalar(text("SELECT current_database()")) == "platform_pilot_restore"
            company = await db.scalar(text("SELECT id FROM companies WHERE name = 'Строй-Пилот'"))
            neighbor = await db.scalar(text("SELECT id FROM companies WHERE name = 'Клиника-Операции'"))
            assert company and neighbor and company != neighbor
            tenders = (await db.execute(text("""
                SELECT id, company_id, project_code FROM tender_projects WHERE company_id = :company
            """), {"company": company})).mappings().all()
            files = (await db.execute(text("""
                SELECT id, company_id, storage_path, sha256_hash FROM uploaded_files WHERE company_id = :company
            """), {"company": company})).mappings().all()
            foreign_files = (await db.execute(text("""
                SELECT storage_path FROM uploaded_files WHERE company_id = :company
            """), {"company": neighbor})).scalars().all()
            assert len(tenders) == len(files) == len(foreign_files) == 1
            assert str(tenders[0]["project_code"]) == "2501"

        archive = root / "single-company-recovery.zip"
        with ZipFile(archive, "w") as output:
            output.writestr("manifest.json", json.dumps({
                "company_id": str(company), "tenders": [dict(row) for row in tenders],
                "files": [dict(row) for row in files],
            }, default=str))
            for item in files:
                key = Path(item["storage_path"])
                prefix = storage / "tenants" / str(company)
                source = (storage / key).resolve()
                assert source.is_relative_to(prefix)
                assert sha256(source.read_bytes()).hexdigest() == item["sha256_hash"]
                output.write(source, arcname=key.as_posix())

        with ZipFile(archive) as result:
            names = result.namelist()
            assert names == ["manifest.json", Path(files[0]["storage_path"]).as_posix()]
            assert not set(names).intersection(Path(key).as_posix() for key in foreign_files)
            assert str(neighbor) not in result.read("manifest.json").decode()
        print(f"Restore rehearsal passed: one tenant's tender and XLSX, neighboring file excluded; extract {monotonic() - started:.2f}s.")

        # Rehearse scoped deletion after export only inside the restored database.
        async with engine.begin() as db:
            assert await db.scalar(text("SELECT current_database()")) == "platform_pilot_restore"
            assert Path(await db.scalar(text("SHOW data_directory"))).resolve() == root / "postgres"
            await db.execute(text("""
                UPDATE companies SET platform_state = 'closed', is_active = false WHERE id = :company
            """), {"company": company})
            deleted = await db.scalar(text("""
                DELETE FROM companies AS c WHERE c.id = :company AND c.platform_state = 'closed'
                AND NOT EXISTS (SELECT FROM company_integrations AS i WHERE i.company_id = c.id AND i.enabled)
                AND NOT EXISTS (SELECT FROM integration_runs AS r WHERE r.company_id = c.id
                                AND r.state IN ('queued', 'running', 'retry_wait'))
                RETURNING c.id
            """), {"company": company})
            assert deleted == company
            assert await db.scalar(text("SELECT count(*) FROM uploaded_files WHERE company_id = :id"), {"id": company}) == 0
            assert await db.scalar(text("SELECT count(*) FROM tender_projects WHERE company_id = :id"), {"id": company}) == 0
            assert await db.scalar(text("SELECT count(*) FROM uploaded_files WHERE company_id = :id"), {"id": neighbor}) == 1

        for item in files:
            source = (storage / item["storage_path"]).resolve()
            assert source.is_relative_to(storage / "tenants" / str(company))
            source.unlink()
        assert all((storage / key).is_file() for key in foreign_files)
        assert archive.is_file()
        print("Offboarding rehearsal passed: closed tenant removed from restored DB and copied files; neighbor unchanged.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(snapshot())
