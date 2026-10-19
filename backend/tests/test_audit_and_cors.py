import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.company import Company
from app.models.user import User
from app.models.task import OperationalTask
from app.models.project import TenderProject
from app.models.procurement import ProcurementItem
from app.models.audit import AuditLog
from app.models.enums import TaskStatus, TaskPriority, UserRole


@pytest.mark.asyncio
async def test_audit_trail_logging_on_status_change():
    """
    Validates BE-5.1:
    - Status change in tasks (/tasks/{id}/status) writes an entry into audit_logs
    - Stage change in projects (/dashboard/projects/{id}/stage) writes an entry into audit_logs
    - Status change in procurement (/procurement/items/{id}/status) writes an entry into audit_logs
    - Verifies entity_type, entity_id, old_status, new_status, ip_address, user_id, timestamp.
    """
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()
    rand_suffix = uuid.uuid4().hex[:8]

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.core.config import settings

    test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_session_factory() as db:
        company = Company(
            id=company_id,
            name=f"ООO ТестАудит_{rand_suffix}",
            inn=f"77{uuid.uuid4().int % 100000000:08d}",
            is_active=True,
        )
        user = User(
            id=user_id,
            company_id=company_id,
            email=f"auditor_{rand_suffix}@test.ru",
            password_hash="hash",
            full_name="Иванов Аудитор",
            role=UserRole.ADMIN,
            is_active=True,
        )
        task = OperationalTask(
            company_id=company_id,
            task_title="Тестовая задача аудита",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
        )
        project = TenderProject(
            company_id=company_id,
            project_name="Тестовый проект аудита",
            status="in_progress",
            custom_attributes={"tender_stage": "preparation"},
        )
        proc = ProcurementItem(
            company_id=company_id,
            project_name="Тестовый проект аудита",
            item_name="Тестовые трубы",
            status="Счет на оплате",
        )
        db.add_all([company, user, task, project, proc])
        await db.commit()

        task_id = task.id
        project_id = project.id
        proc_id = proc.id

    token = create_access_token(
        subject=str(user_id),
        company_id=str(company_id),
        role="admin",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "PytestAuditClient/1.0",
        "X-Forwarded-For": "192.168.1.55",
    }

    from app.core.database import get_db

    async def override_get_db():
        async with test_session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Update Task Status
            resp_task = await client.patch(
                f"/api/v1/tasks/{task_id}/status",
                json={"status": "in_progress"},
                headers=headers,
            )
            assert resp_task.status_code == 200

            # 2. Update Project Stage
            resp_proj = await client.patch(
                f"/api/v1/dashboard/projects/{project_id}/stage",
                json={"tender_stage": "bidding"},
                headers=headers,
            )
            assert resp_proj.status_code == 200

            # 3. Update Procurement Status
            resp_proc = await client.patch(
                f"/api/v1/procurement/items/{proc_id}/status",
                json={"status": "Оплачено"},
                headers=headers,
            )
            assert resp_proc.status_code == 200

        # Verify audit_logs in DB
        async with test_session_factory() as db:
            logs_q = (
                select(AuditLog)
                .where(AuditLog.company_id == company_id)
                .order_by(AuditLog.timestamp.asc())
            )
            logs = (await db.execute(logs_q)).scalars().all()
            assert len(logs) == 3, f"Expected 3 audit logs, found {len(logs)}"

            # Task log
            task_log = next(l for l in logs if l.entity_type == "task")
            assert task_log.entity_id == task_id
            assert task_log.old_status == "pending"
            assert task_log.new_status == "in_progress"
            assert task_log.user_id == user_id
            assert task_log.ip_address == "192.168.1.55"
            assert task_log.user_agent == "PytestAuditClient/1.0"
            assert task_log.timestamp is not None

            # Project log
            proj_log = next(l for l in logs if l.entity_type == "project")
            assert proj_log.entity_id == project_id
            assert proj_log.old_status == "preparation"
            assert proj_log.new_status == "bidding"
            assert proj_log.user_id == user_id

            # Procurement log
            proc_log = next(l for l in logs if l.entity_type == "procurement")
            assert proc_log.entity_id == proc_id
            assert proc_log.old_status == "Счет на оплате"
            assert proc_log.new_status == "Оплачено"
    finally:
        app.dependency_overrides.clear()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_cors_local_network_and_mobile_access():
    """
    Validates BE-5.2:
    - CORS preflight/requests succeed for localhost:5173
    - CORS preflight/requests succeed for LAN IP addresses (192.168.x.x, 10.x.x.x) on mobile devices
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Localhost
        resp_local = await client.options(
            "/api/v1/dashboard/summary",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_local.status_code == 200
        assert resp_local.headers.get("access-control-allow-origin") == "http://localhost:5173"

        # 2. LAN WiFi Mobile device (e.g. 192.168.1.120:5173)
        resp_lan = await client.options(
            "/api/v1/dashboard/summary",
            headers={
                "Origin": "http://192.168.1.120:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_lan.status_code == 200
        assert resp_lan.headers.get("access-control-allow-origin") == "http://192.168.1.120:5173"

        # 3. LAN 10.0.0.50
        resp_corp = await client.options(
            "/api/v1/dashboard/summary",
            headers={
                "Origin": "http://10.0.0.50:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_corp.status_code == 200
        assert resp_corp.headers.get("access-control-allow-origin") == "http://10.0.0.50:3000"
