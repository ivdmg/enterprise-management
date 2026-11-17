from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session
from app.core.config import settings

_TENANT_SETTING = text("SELECT set_config('app.company_id', :company_id, true)")


class TenantSession(Session):
    pass


@event.listens_for(TenantSession, "after_begin")
def _restore_tenant_context(session, transaction, connection) -> None:
    company_id = session.info.get("company_id")
    if company_id is not None and not transaction.nested:
        connection.execute(_TENANT_SETTING, {"company_id": str(company_id)})


async def set_tenant_context(session: AsyncSession, company_id: UUID) -> None:
    """Bind a session to an authenticated company for all of its transactions."""
    if not isinstance(company_id, UUID):
        raise ValueError("A verified company UUID is required")
    current = session.info.get("company_id")
    if current == company_id:
        return
    if current is not None:
        raise ValueError("A database session cannot change companies")
    if session.in_nested_transaction():
        raise ValueError("Set the company before starting a savepoint")
    session.info["company_id"] = company_id
    if session.in_transaction():
        await session.execute(_TENANT_SETTING, {"company_id": str(company_id)})


def _make_engine(url: str, *, require_rls: bool) -> AsyncEngine:
    result = create_async_engine(
        url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    if require_rls:
        @event.listens_for(result.sync_engine, "connect")
        def _check_runtime_role(connection, record) -> None:
            cursor = connection.cursor()
            try:
                cursor.execute("""
                    SELECT NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb)
                           AND row_security_active('public.companies')
                           AND row_security_active('public.tender_projects')
                           AND NOT EXISTS (
                               SELECT FROM pg_class AS relation
                               WHERE relation.oid IN ('public.companies'::regclass, 'public.tender_projects'::regclass)
                                 AND pg_has_role(relation.relowner, 'MEMBER')
                           )
                    FROM pg_roles WHERE rolname = current_user
                """)
                if not cursor.fetchone()[0]:
                    raise RuntimeError("The runtime database role must be subject to tenant RLS")
            finally:
                cursor.close()
                connection.rollback()
    return result


engine = _make_engine(settings.async_runtime_database_url, require_rls=bool(settings.DATABASE_RUNTIME_URL))
worker_engine = (
    _make_engine(settings.async_worker_database_url, require_rls=True)
    if settings.DATABASE_WORKER_URL else engine
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    sync_session_class=TenantSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
async_session_factory = async_sessionmaker(
    bind=worker_engine,
    sync_session_class=TenantSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an active SQLAlchemy asynchronous session
    and automatically handles closure/rollback upon exceptions.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
