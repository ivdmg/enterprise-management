import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alert import IntegrationSetting, SystemAlert
from app.models.company import Company
from app.models.enums import AlertSeverity, DomainCategory, ProjectRisk, TaskPriority, TaskStatus, UserRole
from app.models.finance import CashflowOperation
from app.models.procurement import ProcurementItem
from app.models.project import TenderProject
from app.models.task import OperationalTask
from app.models.user import User
from app.services.alerts_engine import AlertsEngine


@pytest.fixture
def test_user():
    company_id = uuid.uuid4()
    company = Company(id=company_id, name="АО Мосинжстрой", is_active=True)
    user = User(
        id=uuid.uuid4(),
        company_id=company_id,
        email="chief@mosinzh.ru",
        password_hash="hash",
        full_name="Смирнов А.В.",
        role=UserRole.ADMIN,
        is_active=True,
    )
    user.company = company
    return user


@pytest.mark.asyncio
async def test_44fz_statutory_penalty_calculation():
    """
    Validates Russian 44-FZ statutory penalty formula (BE-4.2):
    Penalty = Unfulfilled_Sum * Days_Overdue * (1/300 * KeyRate).
    """
    company_id = uuid.uuid4()
    today = datetime.now(timezone.utc).date()
    deadline = today - timedelta(days=4)

    # 10,000,000 contract with 0 completed, 4 days overdue
    project = TenderProject(
        id=uuid.uuid4(),
        company_id=company_id,
        project_name="Кислородный цех №101",
        contract_sum=Decimal("10000000.00"),
        completed_sum=Decimal("0.00"),
        deadline_date=deadline,
        status="in_progress",
    )

    db_mock = AsyncMock()
    db_mock.add = MagicMock()
    # Mock settings query (no custom setting)
    setting_res_mock = MagicMock()
    setting_res_mock.scalar_one_or_none.return_value = None

    # Mock project query
    proj_res_mock = MagicMock()
    proj_res_mock.scalars.return_value.all.return_value = [project]

    # Mock alert query (no existing alert)
    alert_res_mock = MagicMock()
    alert_res_mock.scalar_one_or_none.return_value = None

    db_mock.execute.side_effect = [proj_res_mock, setting_res_mock, alert_res_mock]

    alerts = await AlertsEngine.evaluate_tender_penalties(company_id, db_mock)

    # Key rate = 0.19 -> rate per day = 0.19 / 300 = 0.0006333333...
    # Expected penalty = 10,000,000 * 4 * (0.19 / 300) = 25,333.33
    expected_penalty = (Decimal("10000000.00") * 4 * (Decimal("0.19") / Decimal("300"))).quantize(
        Decimal("0.01")
    )
    assert project.penalty_amount_calculated == expected_penalty
    assert len(alerts) == 1
    assert alerts[0].alert_type == "DEADLINE_BREACH"
    assert alerts[0].calculated_financial_impact == expected_penalty
    assert alerts[0].severity == AlertSeverity.CRITICAL


@pytest.mark.asyncio
async def test_5_day_rule_and_bank_guarantee_expiry():
    """
    Validates BE-4.1:
    - 5-day rule for approaching СМР deadline
    - 5-day rule for expiring / expired bank guarantee
    """
    company_id = uuid.uuid4()
    today = datetime.now(timezone.utc).date()

    # Project with deadline in 3 days (approaching) and BG expiring in 2 days
    project = TenderProject(
        id=uuid.uuid4(),
        company_id=company_id,
        project_name="Реконструкция ВНС №4",
        curator_name="Петров В.С.",
        contract_sum=Decimal("5000000.00"),
        completed_sum=Decimal("1000000.00"),  # unclosed = 4,000,000
        deadline_date=today + timedelta(days=3),
        bank_guarantee_expiry=today + timedelta(days=2),
        application_guarantee_sum=Decimal("250000.00"),
        status="in_progress",
    )

    db_mock = AsyncMock()
    db_mock.add = MagicMock()

    proj_res = MagicMock()
    proj_res.scalars.return_value.all.return_value = [project]

    setting_res = MagicMock()
    setting_res.scalar_one_or_none.return_value = None

    alert_res1 = MagicMock()
    alert_res1.scalar_one_or_none.return_value = None

    alert_res2 = MagicMock()
    alert_res2.scalar_one_or_none.return_value = None

    db_mock.execute.side_effect = [proj_res, setting_res, alert_res1, alert_res2]

    alerts = await AlertsEngine.evaluate_tender_penalties(company_id, db_mock)
    assert len(alerts) == 2

    # Check KS2 alert
    ks2_alert = next(a for a in alerts if a.alert_type == "KS2_DEADLINE_APPROACHING")
    assert ks2_alert.severity == AlertSeverity.WARNING
    assert ks2_alert.calculated_financial_impact == Decimal("4000000.00")
    assert "Петров В.С." in ks2_alert.description

    # Check BG alert (2 days left -> CRITICAL)
    bg_alert = next(a for a in alerts if a.alert_type == "BANK_GUARANTEE_EXPIRING")
    assert bg_alert.severity == AlertSeverity.CRITICAL
    assert bg_alert.calculated_financial_impact == Decimal("250000.00")


@pytest.mark.asyncio
async def test_procurement_materials_delay_evaluation():
    """
    Validates BE-4.1 (3): Procurement materials delivery delay & approaching deadline.
    """
    company_id = uuid.uuid4()
    today = datetime.now(timezone.utc).date()

    item_overdue = ProcurementItem(
        id=uuid.uuid4(),
        company_id=company_id,
        project_name="Объект А",
        item_name="Трубы стальные 159мм",
        supplier="ООО ТрубПром",
        invoice_amount=Decimal("450000.00"),
        delivery_deadline=today - timedelta(days=2),
        status="В пути",
    )

    db_mock = AsyncMock()
    db_mock.add = MagicMock()

    items_res = MagicMock()
    items_res.scalars.return_value.all.return_value = [item_overdue]

    alert_res = MagicMock()
    alert_res.scalar_one_or_none.return_value = None

    db_mock.execute.side_effect = [items_res, alert_res]

    alerts = await AlertsEngine.evaluate_procurement_risks(company_id, db_mock)
    assert len(alerts) == 1
    assert alerts[0].alert_type == "PROCUREMENT_DELAY"
    assert alerts[0].severity == AlertSeverity.CRITICAL
    assert alerts[0].calculated_financial_impact == Decimal("450000.00")


@pytest.mark.asyncio
async def test_operational_tasks_critical_penalty_evaluation():
    """
    Validates BE-4.1 (4): Operational tasks with URGENT priority or disagreement protocol risks.
    """
    company_id = uuid.uuid4()
    today = datetime.now(timezone.utc).date()

    urgent_task = OperationalTask(
        id=uuid.uuid4(),
        company_id=company_id,
        task_title="Подача протокола разногласий по объекту ВНС",
        related_contract="К-2026/01",
        responsible_role="lawyer",
        responsible_person="Ковалев И.А.",
        priority=TaskPriority.URGENT,
        penalty_risk_desc="Критический штраф по ГК РФ",
        estimated_penalty_amount=Decimal("300000.00"),
        due_date=today + timedelta(days=1),
        status=TaskStatus.PENDING,
    )

    db_mock = AsyncMock()
    db_mock.add = MagicMock()

    tasks_res = MagicMock()
    tasks_res.scalars.return_value.all.return_value = [urgent_task]

    alert_res = MagicMock()
    alert_res.scalar_one_or_none.return_value = None

    db_mock.execute.side_effect = [tasks_res, alert_res]

    alerts = await AlertsEngine.evaluate_operational_tasks_risks(company_id, db_mock)
    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.CRITICAL
    assert alerts[0].calculated_financial_impact == Decimal("300000.00")
    assert "Ковалев И.А." in alerts[0].description


@pytest.mark.asyncio
async def test_cash_gap_prediction_simulation():
    """
    Validates 14-day cash gap simulation (BE-4.3):
    Detects when planned outflows exceed current balance + planned inflows.
    """
    company_id = uuid.uuid4()
    today = datetime.now(timezone.utc).date()

    db_mock = AsyncMock()
    db_mock.add = MagicMock()

    # Total in = 1,000,000; Total out = 200,000 -> Current Balance = 800,000
    mock_tot_in = MagicMock()
    mock_tot_in.scalar_one.return_value = Decimal("1000000.00")
    mock_tot_out = MagicMock()
    mock_tot_out.scalar_one.return_value = Decimal("200000.00")

    # Forecast in = 0; Forecast out = 2,000,000 (planned deficit of 1,200,000)
    mock_plan_in = MagicMock()
    mock_plan_in.scalar_one.return_value = Decimal("0.00")
    mock_plan_out = MagicMock()
    mock_plan_out.scalar_one.return_value = Decimal("2000000.00")

    # Unpaid planned operations: one big outflow of 2,000,000 due in 5 days
    due_date = today + timedelta(days=5)
    unpaid_op = CashflowOperation(
        company_id=company_id,
        direction="outgoing",
        planned_amount=Decimal("2000000.00"),
        payment_due_date=due_date,
        is_paid=False,
    )
    mock_ops_res = MagicMock()
    mock_ops_res.scalars.return_value.all.return_value = [unpaid_op]

    # No existing gap alert
    mock_alert_res = MagicMock()
    mock_alert_res.scalar_one_or_none.return_value = None

    db_mock.execute.side_effect = [
        mock_tot_in,
        mock_tot_out,
        mock_plan_in,
        mock_plan_out,
        mock_ops_res,
        mock_alert_res,
    ]

    (
        cur_bal,
        f_in,
        f_out,
        is_gap,
        deficit,
        gap_day,
    ) = await AlertsEngine.evaluate_cash_gap(company_id, db_mock)

    assert cur_bal == Decimal("800000.00")
    assert f_out == Decimal("2000000.00")
    assert is_gap is True
    assert deficit == Decimal("1200000.00")
    assert gap_day == due_date


@pytest.mark.asyncio
async def test_dashboard_summary_and_critical_alerts_api(test_user):
    """
    Validates BE-4.4:
    - GET /api/v1/dashboard/summary returning free_cash, active_portfolio_sum, receivables_sum,
      payables_sum, critical_alerts_count, and nested data structures.
    - GET /api/v1/alerts/critical returning actionable cards.
    """
    db_mock = AsyncMock()

    # Mock evaluate_cash_gap return
    today = datetime.now(timezone.utc).date()
    mock_project = TenderProject(
        id=uuid.uuid4(),
        company_id=test_user.company_id,
        project_name="Строительство школы на 1100 мест",
        curator_name="Иванов И.И.",
        contract_sum=Decimal("15000000.00"),
        completed_sum=Decimal("5000000.00"),
        paid_sum=Decimal("3000000.00"),  # receivable = 2,000,000
        deadline_date=today + timedelta(days=2),
        status="in_progress",
        risk_level=ProjectRisk.CRITICAL,
        penalty_amount_calculated=Decimal("50000.00"),
    )

    mock_alert = SystemAlert(
        id=uuid.uuid4(),
        company_id=test_user.company_id,
        domain_category=DomainCategory.PRODUCTION_TENDERS,
        severity=AlertSeverity.CRITICAL,
        alert_type="DEADLINE_BREACH",
        entity_type="tender_projects",
        entity_id=mock_project.id,
        title="Срыв срока СМР: Школа 1100 мест",
        description="Отставание 4 дн. Неустойка: 50,000.00 ₽. Куратор: Иванов И.И.",
        calculated_financial_impact=Decimal("50000.00"),
        trigger_date=today - timedelta(days=4),
        is_resolved=False,
    )

    async def override_get_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = override_get_db

    # Setup mocks for GET /api/v1/dashboard/summary
    # 1. cash gap (inflow, outflow, plan_in, plan_out, ops, alert)
    mock_tot_in = MagicMock()
    mock_tot_in.scalar_one.return_value = Decimal("5000000.00")
    mock_tot_out = MagicMock()
    mock_tot_out.scalar_one.return_value = Decimal("2000000.00")
    mock_plan_in = MagicMock()
    mock_plan_in.scalar_one.return_value = Decimal("1000000.00")
    mock_plan_out = MagicMock()
    mock_plan_out.scalar_one.return_value = Decimal("500000.00")
    mock_ops = MagicMock()
    mock_ops.scalars.return_value.all.return_value = []
    mock_gap_alert = MagicMock()
    mock_gap_alert.scalar_one_or_none.return_value = None

    # 2. projects query
    mock_proj_res = MagicMock()
    mock_proj_res.scalars.return_value.all.return_value = [mock_project]

    # 3. payables proc & payables cf
    mock_proc_pay = MagicMock()
    mock_proc_pay.scalar_one.return_value = Decimal("850000.00")
    mock_cf_pay = MagicMock()
    mock_cf_pay.scalar_one.return_value = Decimal("0.00")

    # 4. alert counts (crit, warn, info)
    mock_crit_c = MagicMock()
    mock_crit_c.scalar_one.return_value = 1
    mock_warn_c = MagicMock()
    mock_warn_c.scalar_one.return_value = 0
    mock_info_c = MagicMock()
    mock_info_c.scalar_one.return_value = 0

    # 5. top fire items
    mock_fire_res = MagicMock()
    mock_fire_res.scalars.return_value.all.return_value = [mock_alert]

    db_mock.execute.side_effect = [
        mock_tot_in,
        mock_tot_out,
        mock_plan_in,
        mock_plan_out,
        mock_ops,
        mock_gap_alert,
        mock_proj_res,
        mock_proc_pay,
        mock_cf_pay,
        mock_crit_c,
        mock_warn_c,
        mock_info_c,
        mock_fire_res,
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test /dashboard/summary
        resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        # BE-4.4 direct metrics validation
        assert Decimal(str(data["free_cash"])) == Decimal("3000000.00")  # 5,000,000 - 2,000,000
        assert Decimal(str(data["active_portfolio_sum"])) == Decimal("15000000.00")
        assert Decimal(str(data["receivables_sum"])) == Decimal("2000000.00")  # 5,000,000 - 3,000,000
        assert Decimal(str(data["payables_sum"])) == Decimal("850000.00")
        assert data["critical_alerts_count"] == 1
        assert len(data["top_fire_items"]) == 1
        assert data["top_fire_items"][0]["responsible"] == "Иванов И.И."
        assert data["top_fire_items"][0]["category"] == "ks2_delay"

        # Test /alerts/critical
        # Reset side_effect for second call
        mock_proj_res2 = MagicMock()
        mock_proj_res2.scalars.return_value.all.return_value = [mock_project]
        mock_crit_res2 = MagicMock()
        mock_crit_res2.scalars.return_value.all.return_value = [mock_alert]
        db_mock.execute.side_effect = [mock_proj_res2, mock_crit_res2]

        crit_resp = await client.get("/api/v1/alerts/critical")
        assert crit_resp.status_code == 200
        crit_body = crit_resp.json()
        assert crit_body["success"] is True
        crit_cards = crit_body["data"]
        assert len(crit_cards) == 1
        assert crit_cards[0]["severity"] == "CRITICAL"
        assert Decimal(str(crit_cards[0]["financial_impact"])) == Decimal("50000.00")
        assert crit_cards[0]["responsible"] == "Иванов И.И."

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_key_rate_settings_api(test_user):
    """
    Validates BE-3.1 key rate settings endpoints (GET / PATCH).
    """
    db_mock = AsyncMock()
    async def override_get_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET default
        mock_setting_res = MagicMock()
        mock_setting_res.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_setting_res

        resp = await client.get("/api/v1/settings/key-rate")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["key_rate_percent"] == 19.0
        assert data["daily_penalty_fraction"] == "1/300"
        assert round(data["daily_rate_percent"], 4) == round(19.0 / 300.0, 4)

        # PATCH update to 21.0%
        mock_setting_obj = IntegrationSetting(
            company_id=test_user.company_id,
            alert_rules={"key_rate_percent": 19.0},
        )
        mock_patch_res = MagicMock()
        mock_patch_res.scalar_one_or_none.return_value = mock_setting_obj
        db_mock.execute.return_value = mock_patch_res

        patch_resp = await client.patch(
            "/api/v1/settings/key-rate",
            json={"key_rate_percent": 21.0},
        )
        assert patch_resp.status_code == 200
        patch_data = patch_resp.json()["data"]
        assert patch_data["key_rate_percent"] == 21.0
        assert round(patch_data["daily_rate_percent"], 4) == round(21.0 / 300.0, 4)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_projects_bg_risk_level(test_user):
    """
    Validates BE-3.2: bg_risk_level ("critical" | "warning" | "ok") in GET /api/v1/dashboard/projects.
    """
    db_mock = AsyncMock()
    async def override_get_db():
        yield db_mock

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = override_get_db

    today = datetime.now(timezone.utc).date()

    # Project 1: critical BG (< 5 days)
    p_critical = TenderProject(
        id=uuid.uuid4(),
        company_id=test_user.company_id,
        project_name="ЖК Критический",
        contract_sum=Decimal("1000000.00"),
        completed_sum=Decimal("100000.00"),
        paid_sum=Decimal("0.00"),
        debt_sum=Decimal("0.00"),
        status="in_progress",
        risk_level=ProjectRisk.CRITICAL,
        penalty_amount_calculated=Decimal("0.00"),
        bank_guarantee_expiry=today + timedelta(days=3),
    )
    # Project 2: warning BG (10 days)
    p_warning = TenderProject(
        id=uuid.uuid4(),
        company_id=test_user.company_id,
        project_name="ЖК Предупреждение",
        contract_sum=Decimal("2000000.00"),
        completed_sum=Decimal("500000.00"),
        paid_sum=Decimal("0.00"),
        debt_sum=Decimal("0.00"),
        status="in_progress",
        risk_level=ProjectRisk.WARNING,
        penalty_amount_calculated=Decimal("0.00"),
        bank_guarantee_expiry=today + timedelta(days=10),
    )
    # Project 3: ok BG (30 days)
    p_ok = TenderProject(
        id=uuid.uuid4(),
        company_id=test_user.company_id,
        project_name="ЖК Спокойный",
        contract_sum=Decimal("3000000.00"),
        completed_sum=Decimal("2000000.00"),
        paid_sum=Decimal("0.00"),
        debt_sum=Decimal("0.00"),
        status="in_progress",
        risk_level=ProjectRisk.NORMAL,
        penalty_amount_calculated=Decimal("0.00"),
        bank_guarantee_expiry=today + timedelta(days=30),
    )

    mock_count = MagicMock()
    mock_count.scalar_one.return_value = 3
    mock_items = MagicMock()
    mock_items.scalars.return_value.all.return_value = [p_critical, p_warning, p_ok]

    db_mock.execute.side_effect = [mock_count, mock_items]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dashboard/projects")
        assert resp.status_code == 200
        items = resp.json()["data"]
        assert len(items) == 3
        assert items[0]["bg_risk_level"] == "critical"
        assert items[1]["bg_risk_level"] == "warning"
        assert items[2]["bg_risk_level"] == "ok"

    app.dependency_overrides.clear()

