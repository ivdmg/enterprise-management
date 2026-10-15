import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import SystemAlert
from app.models.enums import AlertSeverity, DomainCategory, ProjectRisk
from app.models.finance import CashflowOperation
from app.models.payroll import PayrollRecord
from app.models.project import TenderProject


class AlertsEngine:
    """
    Financial Impact & Risk Calculation Engine.
    Implements Russian 44-FZ statutory penalty calculations (1/300 Central Bank key rate/day),
    multi-day cash gap forecasting, and systemic alert generation.
    """

    # Central Bank of Russia baseline key rate (19% annualized)
    KEY_RATE: Decimal = Decimal("0.19")
    DAILY_PENALTY_RATE: Decimal = Decimal("0.19") / Decimal("300")

    @classmethod
    async def evaluate_tender_penalties(
        cls, company_id: uuid.UUID, db: AsyncSession
    ) -> List[SystemAlert]:
        """
        Calculates 44-FZ statutory penalties for overdue projects:
        Penalty = Unfulfilled_Sum * Days_Overdue * (1/300 * KeyRate).
        Generates or updates DEADLINE_BREACH alerts in system_alerts table.
        """
        today = datetime.now(timezone.utc).date()
        query = select(TenderProject).where(
            TenderProject.company_id == company_id,
            TenderProject.deleted_at.is_(None),
            TenderProject.status != "completed",
        )
        res = await db.execute(query)
        projects = res.scalars().all()

        generated_alerts: List[SystemAlert] = []

        for p in projects:
            if p.deadline_date and p.deadline_date < today:
                days_overdue = (today - p.deadline_date).days
                unfulfilled_sum = max(Decimal("0.00"), p.contract_sum - p.completed_sum)
                if unfulfilled_sum == Decimal("0.00"):
                    unfulfilled_sum = p.contract_sum

                penalty = (unfulfilled_sum * Decimal(days_overdue) * cls.DAILY_PENALTY_RATE).quantize(
                    Decimal("0.01")
                )
                p.penalty_amount_calculated = penalty

                if days_overdue >= 3 or penalty >= Decimal("50000.00"):
                    p.risk_level = ProjectRisk.CRITICAL
                    severity = AlertSeverity.CRITICAL
                else:
                    p.risk_level = ProjectRisk.WARNING
                    severity = AlertSeverity.WARNING

                # Check if active alert already exists for this project
                alert_q = select(SystemAlert).where(
                    SystemAlert.company_id == company_id,
                    SystemAlert.alert_type == "DEADLINE_BREACH",
                    SystemAlert.entity_id == p.id,
                    SystemAlert.is_resolved.is_(False),
                )
                alert_res = await db.execute(alert_q)
                existing_alert = alert_res.scalar_one_or_none()

                desc = (
                    f"Отставание {days_overdue} дня(ей). Расчетная неустойка по контракту 44-ФЗ: "
                    f"{penalty:,.2f} ₽."
                )

                if existing_alert:
                    existing_alert.severity = severity
                    existing_alert.calculated_financial_impact = penalty
                    existing_alert.description = desc
                    existing_alert.trigger_date = p.deadline_date
                    generated_alerts.append(existing_alert)
                else:
                    new_alert = SystemAlert(
                        company_id=company_id,
                        domain_category=DomainCategory.PRODUCTION_TENDERS,
                        severity=severity,
                        alert_type="DEADLINE_BREACH",
                        entity_type="tender_projects",
                        entity_id=p.id,
                        title=f"Срыв срока: {p.project_name}",
                        description=desc,
                        calculated_financial_impact=penalty,
                        trigger_date=p.deadline_date,
                        is_resolved=False,
                    )
                    db.add(new_alert)
                    generated_alerts.append(new_alert)

        return generated_alerts

    @classmethod
    async def evaluate_cash_gap(
        cls, company_id: uuid.UUID, db: AsyncSession
    ) -> Tuple[Decimal, Decimal, Decimal, bool, Decimal, Optional[date]]:
        """
        Computes current balance and models daily cash positions across 14-day horizon.
        Returns:
            (current_balance, forecast_inflow, forecast_outflow, is_gap_predicted, gap_deficit, gap_date)
        """
        today = datetime.now(timezone.utc).date()
        horizon_end = today + timedelta(days=14)

        # 1. Calculate actual current cash balance from recorded operations
        inflow_q = select(func.coalesce(func.sum(CashflowOperation.actual_amount), Decimal("0.00"))).where(
            CashflowOperation.company_id == company_id,
            CashflowOperation.deleted_at.is_(None),
            CashflowOperation.direction == "incoming",
        )
        outflow_q = select(func.coalesce(func.sum(CashflowOperation.actual_amount), Decimal("0.00"))).where(
            CashflowOperation.company_id == company_id,
            CashflowOperation.deleted_at.is_(None),
            CashflowOperation.direction == "outgoing",
        )
        total_in = (await db.execute(inflow_q)).scalar_one()
        total_out = (await db.execute(outflow_q)).scalar_one()
        current_balance = total_in - total_out

        # 2. Forecast next 14 days planned cashflows
        plan_in_q = select(func.coalesce(func.sum(CashflowOperation.planned_amount), Decimal("0.00"))).where(
            CashflowOperation.company_id == company_id,
            CashflowOperation.deleted_at.is_(None),
            CashflowOperation.direction == "incoming",
            CashflowOperation.payment_due_date >= today,
            CashflowOperation.payment_due_date <= horizon_end,
            CashflowOperation.is_paid.is_(False),
        )
        plan_out_q = select(func.coalesce(func.sum(CashflowOperation.planned_amount), Decimal("0.00"))).where(
            CashflowOperation.company_id == company_id,
            CashflowOperation.deleted_at.is_(None),
            CashflowOperation.direction == "outgoing",
            CashflowOperation.payment_due_date >= today,
            CashflowOperation.payment_due_date <= horizon_end,
            CashflowOperation.is_paid.is_(False),
        )
        forecast_inflow = (await db.execute(plan_in_q)).scalar_one()
        forecast_outflow = (await db.execute(plan_out_q)).scalar_one()

        # 3. Model daily cash trajectory
        ops_q = select(CashflowOperation).where(
            CashflowOperation.company_id == company_id,
            CashflowOperation.deleted_at.is_(None),
            CashflowOperation.is_paid.is_(False),
            CashflowOperation.payment_due_date >= today,
            CashflowOperation.payment_due_date <= horizon_end,
        ).order_by(CashflowOperation.payment_due_date.asc())
        ops_res = await db.execute(ops_q)
        unpaid_ops = ops_res.scalars().all()

        daily_delta: Dict[date, Decimal] = {}
        for op in unpaid_ops:
            if op.payment_due_date:
                amount = op.planned_amount if op.planned_amount > Decimal("0.00") else op.actual_amount
                delta = amount if op.direction == "incoming" else -amount
                daily_delta[op.payment_due_date] = daily_delta.get(op.payment_due_date, Decimal("0.00")) + delta

        sim_balance = current_balance
        min_balance = current_balance
        gap_date = None

        for day_offset in range(15):
            sim_day = today + timedelta(days=day_offset)
            sim_balance += daily_delta.get(sim_day, Decimal("0.00"))
            if sim_balance < min_balance:
                min_balance = sim_balance
                if min_balance < Decimal("0.00") and gap_date is None:
                    gap_date = sim_day

        is_gap_predicted = min_balance < Decimal("0.00")
        gap_deficit = abs(min_balance) if is_gap_predicted else Decimal("0.00")

        # 4. Create or update CASH_GAP alert if needed
        alert_q = select(SystemAlert).where(
            SystemAlert.company_id == company_id,
            SystemAlert.alert_type == "CASH_GAP",
            SystemAlert.is_resolved.is_(False),
        )
        existing_gap_alert = (await db.execute(alert_q)).scalar_one_or_none()

        if is_gap_predicted:
            desc = (
                f"Прогнозируется кассовый разрыв {gap_deficit:,.2f} ₽ на дату {gap_date}. "
                f"Плановые списания превышают доступный баланс."
            )
            if existing_gap_alert:
                existing_gap_alert.calculated_financial_impact = gap_deficit
                existing_gap_alert.description = desc
                existing_gap_alert.trigger_date = gap_date or today
            else:
                new_gap_alert = SystemAlert(
                    company_id=company_id,
                    domain_category=DomainCategory.CASHFLOW_DEBT,
                    severity=AlertSeverity.CRITICAL,
                    alert_type="CASH_GAP",
                    entity_type="cashflow_operations",
                    title="Прогнозируется кассовый разрыв",
                    description=desc,
                    calculated_financial_impact=gap_deficit,
                    trigger_date=gap_date or today,
                    is_resolved=False,
                )
                db.add(new_gap_alert)

        return (
            current_balance,
            forecast_inflow,
            forecast_outflow,
            is_gap_predicted,
            gap_deficit,
            gap_date,
        )

    @classmethod
    async def run_full_evaluation(cls, company_id: uuid.UUID, db: AsyncSession) -> None:
        """Runs complete analytical risk evaluation across all domains and commits results."""
        await cls.evaluate_tender_penalties(company_id, db)
        await cls.evaluate_cash_gap(company_id, db)
        await db.commit()


alerts_engine = AlertsEngine()
