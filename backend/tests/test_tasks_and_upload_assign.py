import io
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.main import app
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.alert import SystemAlert
from app.models.company import Company
from app.models.enums import AlertSeverity, DomainCategory, TaskPriority, TaskStatus, UserRole
from app.models.file import UploadedFile
from app.models.task import OperationalTask
from app.models.user import User


@pytest.fixture
def test_company_and_user():
    company_id = uuid.uuid4()
    rand_suffix = uuid.uuid4().hex[:8]
    company = Company(
        id=company_id,
        name=f"ООO ГлавСтрой_{rand_suffix}",
        inn=f"77{uuid.uuid4().int % 100000000:08d}",
        is_active=True,
    )
    user = User(
        id=uuid.uuid4(),
        company_id=company_id,
        email=f"accountant_{rand_suffix}@glavstroy.ru",
        password_hash="hash",
        full_name="Смирнова Е.А.",
        role=UserRole.ADMIN,
        is_active=True,
    )
    user.company = company
    return company, user


@pytest.mark.asyncio
async def test_upload_and_assign_end_to_end_real_db(test_company_and_user):
    """
    Validates BE-5.1:
    - POST /api/v1/files/upload-and-assign
    - Uploads Excel to Google Drive (Mock Mode)
    - Automatically creates OperationalTask with google_drive_link and comment
    - Checks tenant isolation and proper status.
    """
    company, user = test_company_and_user

    test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_session_factory() as session:
        session.add(company)
        session.add(user)
        await session.commit()

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = override_get_db

    # Create dummy Excel file
    excel_content = b"PK\x03\x04" + b"\x00" * 200  # zip header mockup
    file_bytes = io.BytesIO(excel_content)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        form_data = {
            "target_folder": "/02_Финансы_1С/2026-10/",
            "comment": "Отчет по взаиморасчетам за 15 октября, просьба согласовать с заказчиком",
            "assignee_role": "manager",
            "contract_id_or_name": "ТЭП-101 / Кислородный цех №101",
        }
        files = {
            "file": ("1C_Report_15_10.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }

        resp = await client.post("/api/v1/files/upload-and-assign", data=form_data, files=files)
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        assert data["file_name"] == "1C_Report_15_10.xlsx"
        assert data["google_drive_folder"] == "/02_Финансы_1С/2026-10/"
        assert "drive.google.com" in data["google_drive_link"]
        assert data["assigned_to_role"] == "manager"
        assert data["status"] == "transferred_to_manager"

        task_id = uuid.UUID(data["task_id"])
        file_id = uuid.UUID(data["file_id"])

        # Verify task in DB
        async with test_session_factory() as session:
            task = (await session.execute(select(OperationalTask).where(OperationalTask.id == task_id))).scalar_one_or_none()
            assert task is not None
            assert task.company_id == company.id
            assert task.responsible_role == "manager"
            assert task.status == TaskStatus.PENDING
            assert task.google_drive_link == data["google_drive_link"]
            assert "Согласование документа" in task.task_title
            assert task.related_contract == "ТЭП-101 / Кислородный цех №101"

            up_file = (await session.execute(select(UploadedFile).where(UploadedFile.id == file_id))).scalar_one_or_none()
            assert up_file is not None
            assert up_file.company_id == company.id

    # Cleanup test company and tasks
    async with test_session_factory() as session:
        target_company = await session.get(Company, company.id)
        if target_company:
            await session.delete(target_company)
            await session.commit()
        await test_engine.dispose()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tasks_list_and_status_transition_api(test_company_and_user):
    """
    Validates BE-5.2 and BE-5.3:
    - GET /api/v1/tasks (with role, status, urgent filters)
    - PATCH /api/v1/tasks/{task_id}/status (1-click status update and alert resolution)
    """
    company, user = test_company_and_user
    today = datetime.now(timezone.utc).date()

    test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    task_manager = OperationalTask(
        id=uuid.uuid4(),
        company_id=company.id,
        task_title="Согласовать доп. соглашение №2",
        responsible_role="manager",
        responsible_person="Кузнецов С.П.",
        due_date=today + timedelta(days=2),  # Urgent <= 5 days
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        penalty_amount=Decimal("150000.00"),
        google_drive_link="https://drive.google.com/file/d/test1/view",
    )

    task_lawyer = OperationalTask(
        id=uuid.uuid4(),
        company_id=company.id,
        task_title="Подготовить претензию поставщику",
        responsible_role="lawyer",
        responsible_person="Лебедева М.В.",
        due_date=today + timedelta(days=15),
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.MEDIUM,
        penalty_amount=Decimal("0.00"),
    )

    alert_for_manager_task = SystemAlert(
        id=uuid.uuid4(),
        company_id=company.id,
        domain_category=DomainCategory.OPERATIONAL_TASKS,
        severity=AlertSeverity.CRITICAL,
        alert_type="TASK_CRITICAL_PENALTY",
        entity_type="operational_tasks",
        entity_id=task_manager.id,
        title="Штрафной риск по доп. соглашению",
        description="Срочное согласование!",
        calculated_financial_impact=Decimal("150000.00"),
        is_resolved=False,
    )

    async with test_session_factory() as session:
        session.add(company)
        session.add(user)
        session.add(task_manager)
        session.add(task_lawyer)
        session.add(alert_for_manager_task)
        await session.commit()

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /api/v1/tasks without filters -> returns both tasks
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 2

        # 2. Filter by role=manager
        resp_mgr = await client.get("/api/v1/tasks?role=manager")
        assert resp_mgr.status_code == 200
        data_mgr = resp_mgr.json()["data"]
        assert len(data_mgr) == 1
        assert data_mgr[0]["id"] == str(task_manager.id)
        assert data_mgr[0]["google_drive_link"] == "https://drive.google.com/file/d/test1/view"
        assert Decimal(str(data_mgr[0]["risk_amount"])) == Decimal("150000.00")

        # 3. Filter by urgent=true
        resp_urg = await client.get("/api/v1/tasks?urgent=true")
        assert resp_urg.status_code == 200
        data_urg = resp_urg.json()["data"]
        assert len(data_urg) == 1
        assert data_urg[0]["id"] == str(task_manager.id)

        # 4. PATCH /api/v1/tasks/{id}/status -> 1-click update to "completed"
        patch_resp = await client.patch(
            f"/api/v1/tasks/{task_manager.id}/status",
            json={"status": "completed"},
        )
        assert patch_resp.status_code == 200
        patch_data = patch_resp.json()["data"]
        assert patch_data["status"] == "completed"

        # Verify task is completed in DB and alert is resolved
        async with test_session_factory() as session:
            t = (await session.execute(select(OperationalTask).where(OperationalTask.id == task_manager.id))).scalar_one()
            assert t.status == TaskStatus.COMPLETED

            a = (await session.execute(select(SystemAlert).where(SystemAlert.id == alert_for_manager_task.id))).scalar_one()
            assert a.is_resolved is True
            assert a.resolved_by_user_id == user.id

    # Cleanup
    async with test_session_factory() as session:
        target_company = await session.get(Company, company.id)
        if target_company:
            await session.delete(target_company)
            await session.commit()
        await test_engine.dispose()

    app.dependency_overrides.clear()
