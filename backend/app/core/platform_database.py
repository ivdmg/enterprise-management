"""Restricted database connection used by the platform console."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import AsyncSessionLocal, TenantSession


if settings.DATABASE_PLATFORM_URL:
    engine = create_async_engine(settings._as_async_url(settings.DATABASE_PLATFORM_URL), pool_pre_ping=True)

    @event.listens_for(engine.sync_engine, "connect")
    def verify_platform_role(connection, _record):
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb)
                       AND NOT EXISTS (
                          SELECT 1 FROM unnest(ARRAY['uploaded_files','file_templates','parsing_jobs','tender_projects',
                            'cashflow_operations','payroll_records','operational_tasks','procurement_items',
                            'fleet_dispatch_records','system_alerts','notification_logs','integration_settings',
                            'audit_logs','users','companies']) AS t(table_name)
                          WHERE has_table_privilege(current_user, 'public.' || t.table_name,
                                  'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')
                             OR has_any_column_privilege(current_user, 'public.' || t.table_name, 'SELECT,INSERT,UPDATE')
                       )
                FROM pg_roles WHERE rolname=current_user
            """)
            if not cursor.fetchone()[0]:
                raise RuntimeError("Platform role cannot access client business tables")
        finally:
            cursor.close()

    PlatformSessionLocal = async_sessionmaker(bind=engine, sync_session_class=TenantSession,
                                               expire_on_commit=False, autoflush=False)
else:
    PlatformSessionLocal = AsyncSessionLocal


async def get_platform_db():
    async with PlatformSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
