import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.alert import SystemAlert
from app.models.enums import AlertSeverity, DomainCategory, ProjectRisk
from app.models.finance import CashflowOperation
from app.models.project import TenderProject
from app.services.alerts_engine import AlertsEngine


@pytest.mark.asyncio
async def test_44fz_statutory_penalty_calculation():
    """
    Validates Russian 44-FZ statutory penalty formula:
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
    # Mock project query
    proj_res_mock = MagicMock()
    proj_res_mock.scalars.return_value.all.return_value = [project]

    # Mock alert query (no existing alert)
    alert_res_mock = MagicMock()
    alert_res_mock.scalar_one_or_none.return_value = None

    db_mock.execute.side_effect = [proj_res_mock, alert_res_mock]

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
    assert alerts[0].severity == AlertSeverity.CRITICAL  # 4 days overdue >= 3 days threshold


@pytest.mark.asyncio
async def test_cash_gap_prediction_simulation():
    """
    Validates 14-day cash gap simulation:
    Detects when planned outflows exceed current balance + planned inflows.
    """
    company_id = uuid.uuid4()
    today = datetime.now(timezone.utc).date()

    db_mock = AsyncMock()

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
