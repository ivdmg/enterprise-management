"""Exercise tenant policies through separate, non-owner runtime and worker URLs."""

import asyncio
import argparse
import os
from pathlib import Path
import secrets
from uuid import uuid4
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine


def pilot_owner_url():
    if os.environ.get("ENVIRONMENT") != "platform-pilot-test" or Path(".env").exists():
        raise RuntimeError("Run tenant RLS checks through the disposable pilot runner.")
    owner_url = urlsplit(os.environ["DATABASE_URL"])
    if owner_url.hostname != "127.0.0.1" or owner_url.path != "/platform_pilot_test":
        raise RuntimeError("The pilot database must use a disposable loopback cluster.")
    return owner_url


async def check_data_directory(connection):
    data_directory = await connection.scalar(text("SHOW data_directory"))
    if Path(data_directory).resolve() != Path.cwd().parent / "postgres":
        raise RuntimeError("Refusing to write outside the disposable pilot cluster.")


async def prepare_legacy_rows() -> None:
    owner = create_async_engine(pilot_owner_url()._replace(scheme="postgresql+asyncpg").geturl())
    try:
        async with owner.begin() as connection:
            await check_data_directory(connection)
            await connection.execute(text("""
                WITH company AS (
                    INSERT INTO companies (name) VALUES ('Legacy migration check') RETURNING id
                ), file AS (
                    INSERT INTO uploaded_files
                        (company_id, original_name, storage_path, file_size_bytes, mime_type, sha256_hash)
                    SELECT id, 'legacy.xlsx', 'legacy', 1, 'test', 'legacy' FROM company
                    RETURNING id
                )
                INSERT INTO parsing_jobs (file_id) SELECT id FROM file
            """))
    finally:
        await owner.dispose()


async def check_rls(*, expect_legacy: bool) -> None:
    owner_url = pilot_owner_url()
    owner = create_async_engine(owner_url._replace(scheme="postgresql+asyncpg").geturl())
    company_a, company_b = uuid4(), uuid4()
    file_a, file_b = uuid4(), uuid4()
    task_id = uuid4()
    try:
        async with owner.begin() as connection:
            await check_data_directory(connection)
            if expect_legacy:
                assert await connection.scalar(text("""
                    SELECT count(*)
                    FROM parsing_jobs AS job JOIN uploaded_files AS file ON file.id = job.file_id
                    WHERE file.original_name = 'legacy.xlsx' AND job.company_id = file.company_id
                """)) == 1
            for kind, grants in (
                ("runtime", "GRANT SELECT, INSERT, UPDATE ON operational_tasks TO pilot_runtime"),
                ("worker", "GRANT SELECT ON operational_tasks TO pilot_worker"),
            ):
                role = f"pilot_{kind}"
                password = secrets.token_hex(24)
                await connection.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD '{password}'"))
                await connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
                await connection.execute(text(f"GRANT SELECT ON companies TO {role}"))
                await connection.execute(text(grants))
                os.environ[f"DATABASE_{kind.upper()}_URL"] = owner_url._replace(
                    netloc=f"{role}:{password}@127.0.0.1:{owner_url.port}"
                ).geturl()
            await connection.execute(
                text("INSERT INTO companies (id, name) VALUES (:a, 'RLS-A'), (:b, 'RLS-B')"),
                {"a": company_a, "b": company_b},
            )
            await connection.execute(
                text("""
                    INSERT INTO uploaded_files
                        (id, company_id, original_name, storage_path, file_size_bytes, mime_type, sha256_hash)
                    VALUES
                        (:file_a, :company_a, 'same.xlsx', 'a', 1, 'test', 'same'),
                        (:file_b, :company_b, 'same.xlsx', 'b', 1, 'test', 'same')
                """),
                {"file_a": file_a, "file_b": file_b, "company_a": company_a, "company_b": company_b},
            )
            await connection.execute(
                text("""
                    INSERT INTO operational_tasks (id, company_id, file_id, task_title)
                    VALUES (:task, :company_a, :file_a, 'Company A task')
                """),
                {"task": task_id, "company_a": company_a, "file_a": file_a},
            )

        from app.core.database import AsyncSessionLocal, async_session_factory, engine, set_tenant_context, worker_engine

        try:
            async with AsyncSessionLocal() as db:
                backend_pid = await db.scalar(text("SELECT pg_backend_pid()"))
                assert await db.scalar(text("SELECT count(*) FROM companies")) == 0
                await set_tenant_context(db, company_a)
                assert await db.scalar(text("SELECT name FROM companies")) == "RLS-A"
                await db.commit()
                assert await db.scalar(text("SELECT task_title FROM operational_tasks")) == "Company A task"
                await db.rollback()
                assert await db.scalar(text("SELECT name FROM companies")) == "RLS-A"
                try:
                    await set_tenant_context(db, company_b)
                except ValueError:
                    pass
                else:
                    raise AssertionError("A session switched to another company")
                try:
                    await db.execute(
                        text("UPDATE operational_tasks SET company_id = :company WHERE id = :id"),
                        {"company": company_b, "id": task_id},
                    )
                except DBAPIError as exc:
                    assert exc.orig.sqlstate == "42501"
                    await db.rollback()
                else:
                    raise AssertionError("A cross-company update passed RLS")
                await db.execute(
                    text("UPDATE operational_tasks SET file_id = :file WHERE id = :id"),
                    {"file": file_b, "id": task_id},
                )
                try:
                    await db.commit()
                except IntegrityError as exc:
                    assert exc.orig.sqlstate == "23503"
                    await db.rollback()
                else:
                    raise AssertionError("A cross-company file reference passed the FK")

            async with AsyncSessionLocal() as db:
                assert await db.scalar(text("SELECT pg_backend_pid()")) == backend_pid
                assert await db.scalar(text("SELECT count(*) FROM companies")) == 0
                await set_tenant_context(db, company_b)
                assert await db.scalar(text("SELECT name FROM companies")) == "RLS-B"
                assert await db.scalar(text("SELECT count(*) FROM operational_tasks")) == 0

            async with async_session_factory() as db:
                assert await db.scalar(text("SELECT current_user")) == "pilot_worker"
                await set_tenant_context(db, company_a)
                assert await db.scalar(text("SELECT task_title FROM operational_tasks")) == "Company A task"
        finally:
            await engine.dispose()
            await worker_engine.dispose()

        async with owner.begin() as connection:
            await connection.execute(text("DELETE FROM uploaded_files WHERE id = :file"), {"file": file_a})
            assert await connection.scalar(
                text("SELECT company_id FROM operational_tasks WHERE id = :id AND file_id IS NULL"),
                {"id": task_id},
            ) == company_a
    finally:
        await owner.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-legacy", action="store_true")
    parser.add_argument("--expect-legacy", action="store_true")
    args = parser.parse_args()
    if args.prepare_legacy:
        asyncio.run(prepare_legacy_rows())
    else:
        asyncio.run(check_rls(expect_legacy=args.expect_legacy))
        print("Tenant RLS: no-context deny, pooled scope, worker role and composite foreign key passed")
