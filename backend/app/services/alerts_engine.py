import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.alert import IntegrationSetting, SystemAlert
from app.models.enums import AlertSeverity, DomainCategory, ProjectRisk, TaskPriority, TaskStatus
from app.models.finance import CashflowOperation
from app.models.procurement import ProcurementItem
from app.models.project import TenderProject
from app.models.task import OperationalTask


class AlertsEngine:
    """
    Financial Impact & Risk Calculation Engine («Где горит?»).
    Implements:
    - 5-day rule for approaching and overdue deadlines across all operational domains.
    - Russian 44-FZ statutory penalty calculations (1/300 Central Bank key rate/day on unfulfilled KS-2 volume).
    - Bank guarantee expiration monitoring with RNP risk control (<=5 days: critical, 6-15 days: warning).
    - Material supply procurement delay monitoring.
    - Critical operational tasks / disagreement protocol penalty monitoring.
    - 14-day cash gap forecasting with daily trajectory simulation.
    """

    # Central Bank of Russia default baseline key rate (19% annualized)
    KEY_RATE: Decimal = Decimal(str(settings.KEY_RATE_PERCENT)) / Decimal("100")
    DAILY_PENALTY_RATE: Decimal = (Decimal(str(settings.KEY_RATE_PERCENT)) / Decimal("100")) / Decimal("300")

    @classmethod
    async def get_effective_key_rate(cls, company_id: Optional[uuid.UUID], db: Optional[AsyncSession]) -> Decimal:
        """
        Retrieves company-specific key rate from IntegrationSetting or falls back to global Settings.
        """
        if company_id and db:
            try:
                q = select(IntegrationSetting).where(IntegrationSetting.company_id == company_id)
                res = await db.execute(q)
                setting_rec = res.scalar_one_or_none()
                if setting_rec and setting_rec.alert_rules and "key_rate_percent" in setting_rec.alert_rules:
                    val = Decimal(str(setting_rec.alert_rules["key_rate_percent"]))
                    return val / Decimal("100")
            except Exception:
                pass
        return Decimal(str(settings.KEY_RATE_PERCENT)) / Decimal("100")

    @classmethod
    def calculate_44fz_penalty(
        cls,
        contract_sum: Decimal,
        completed_sum: Decimal,
        days_overdue: int,
        key_rate: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Calculates Russian 44-FZ statutory penalty:
        Penalty = (Contract_Sum - Completed_Sum) * Days_Overdue * (1/300 * KeyRate).
        """
        if days_overdue <= 0:
            return Decimal("0.00")
        unfulfilled = max(Decimal("0.00"), contract_sum - completed_sum)
        if unfulfilled == Decimal("0.00") and completed_sum == Decimal("0.00"):
            unfulfilled = contract_sum
        rate = key_rate if key_rate is not None else cls.KEY_RATE
        daily_rate = rate / Decimal("300")
        penalty = (unfulfilled * Decimal(days_overdue) * daily_rate).quantize(Decimal("0.01"))
        return max(Decimal("0.00"), penalty)

    @classmethod
    def calculate_bg_risk_level(
        cls,
        bg_expiry: Optional[date],
        project_status: str,
        today: Optional[date] = None,
    ) -> str:
        """
        Computes Bank Guarantee risk level (BE-3.2):
        - If project is 'completed' -> 'ok'
        - If bg_expiry <= today + 5 days (remaining <= 5) -> 'critical' (Risk of RNP!)
        - If bg_expiry between 6 and 15 days remaining -> 'warning' (Renew BG or sign KS-2)
        - Otherwise -> 'ok'
        """
        if not bg_expiry or str(project_status).lower() == "completed":
            return "ok"
        current_date = today or datetime.now(timezone.utc).date()
        days_diff = (bg_expiry - current_date).days
        if days_diff <= 5:
            return "critical"
        elif 6 <= days_diff <= 15:
            return "warning"
        return "ok"

    @classmethod
    async def evaluate_tender_penalties(
        cls, company_id: uuid.UUID, db: AsyncSession
    ) -> List[SystemAlert]:
        """
        Evaluates tender projects:
        1. 44-FZ statutory penalties for overdue projects with unclosed KS-2 volumes:
           Penalty = Unfulfilled_Sum * Days_Overdue * (1/300 * KeyRate).
        2. 5-day rule for approaching completion deadlines.
        3. 5-day rule for expiring or expired bank guarantees.
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

        effective_key_rate = await cls.get_effective_key_rate(company_id, db)
        daily_penalty_rate = effective_key_rate / Decimal("300")

        for p in projects:
            unfulfilled_sum = max(Decimal("0.00"), p.contract_sum - p.completed_sum)
            if unfulfilled_sum == Decimal("0.00") and p.completed_sum == Decimal("0.00"):
                unfulfilled_sum = p.contract_sum

            # --- 1 & 2: Project completion deadline check ---
            if p.deadline_date:
                days_diff = (p.deadline_date - today).days
                if days_diff < 0:
                    # Overdue project
                    days_overdue = abs(days_diff)
                    penalty = (
                        unfulfilled_sum * Decimal(days_overdue) * daily_penalty_rate
                    ).quantize(Decimal("0.01"))
                    p.penalty_amount_calculated = penalty
                    p.risk_level = ProjectRisk.CRITICAL
                    severity = AlertSeverity.CRITICAL

                    alert_q = select(SystemAlert).where(
                        SystemAlert.company_id == company_id,
                        SystemAlert.alert_type == "DEADLINE_BREACH",
                        SystemAlert.entity_id == p.id,
                        SystemAlert.is_resolved.is_(False),
                    )
                    alert_res = await db.execute(alert_q)
                    existing_alert = alert_res.scalar_one_or_none()

                    desc = (
                        f"Отставание {days_overdue} дн. Незакрытый объем КС-2: {unfulfilled_sum:,.2f} ₽. "
                        f"Расчетная неустойка по контракту 44-ФЗ: {penalty:,.2f} ₽. "
                        f"Куратор: {p.curator_name or 'Не назначен'}."
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
                            title=f"Срыв срока СМР: {p.project_name}",
                            description=desc,
                            calculated_financial_impact=penalty,
                            trigger_date=p.deadline_date,
                            is_resolved=False,
                        )
                        db.add(new_alert)
                        generated_alerts.append(new_alert)

                elif days_diff <= 5:
                    # 5-day warning rule: approaching deadline
                    days_remaining = days_diff
                    severity = AlertSeverity.CRITICAL if days_remaining <= 2 else AlertSeverity.WARNING
                    p.risk_level = ProjectRisk.CRITICAL if days_remaining <= 2 else ProjectRisk.WARNING

                    approaching_daily_penalty = (unfulfilled_sum * daily_penalty_rate).quantize(
                        Decimal("0.01")
                    )

                    alert_q = select(SystemAlert).where(
                        SystemAlert.company_id == company_id,
                        SystemAlert.alert_type == "KS2_DEADLINE_APPROACHING",
                        SystemAlert.entity_id == p.id,
                        SystemAlert.is_resolved.is_(False),
                    )
                    alert_res = await db.execute(alert_q)
                    existing_alert = alert_res.scalar_one_or_none()

                    desc = (
                        f"До дедлайна сдачи СМР осталось {days_remaining} дн. ({p.deadline_date}). "
                        f"Незакрытый объем КС-2: {unfulfilled_sum:,.2f} ₽. "
                        f"Риск неустойки 44-ФЗ: {approaching_daily_penalty:,.2f} ₽/день. "
                        f"Куратор: {p.curator_name or 'Не назначен'}."
                    )

                    if existing_alert:
                        existing_alert.severity = severity
                        existing_alert.calculated_financial_impact = unfulfilled_sum
                        existing_alert.description = desc
                        existing_alert.trigger_date = p.deadline_date
                        generated_alerts.append(existing_alert)
                    else:
                        new_alert = SystemAlert(
                            company_id=company_id,
                            domain_category=DomainCategory.PRODUCTION_TENDERS,
                            severity=severity,
                            alert_type="KS2_DEADLINE_APPROACHING",
                            entity_type="tender_projects",
                            entity_id=p.id,
                            title=f"Дедлайн сдачи СМР через {days_remaining} дн.: {p.project_name}",
                            description=desc,
                            calculated_financial_impact=unfulfilled_sum,
                            trigger_date=p.deadline_date,
                            is_resolved=False,
                        )
                        db.add(new_alert)
                        generated_alerts.append(new_alert)

            # --- 3: Bank guarantee expiry check (BE-3.2) ---
            # If <= 5 days -> critical, "Срок банковской гарантии истекает через N дн. Риск включения в РНП!"
            # If 6..15 days -> warning, "Необходимо продлить БГ или подписать КС-2"
            bg_expiry = getattr(p, "bank_guarantee_expiry", getattr(p, "bank_guarantee_end_date", None))
            guarantee_sum = getattr(p, "application_guarantee_sum", getattr(p, "application_security_sum", Decimal("0.00"))) or Decimal("0.00")
            if bg_expiry and p.status != "completed":
                bg_days_diff = (bg_expiry - today).days
                if bg_days_diff <= 15:
                    if bg_days_diff < 0:
                        bg_overdue = abs(bg_days_diff)
                        bg_severity = AlertSeverity.CRITICAL
                        bg_alert_type = "BANK_GUARANTEE_EXPIRED"
                        bg_title = f"Истекла банковская гарантия: {p.project_name}"
                        bg_desc = (
                            f"Банковская гарантия истекла {bg_overdue} дн. назад ({bg_expiry}). "
                            f"Риск расторжения контракта заказчиком и занесения в РНП! "
                            f"Обеспечение: {guarantee_sum:,.2f} ₽. "
                            f"Куратор: {p.curator_name or 'Не назначен'}."
                        )
                    elif bg_days_diff <= 5:
                        bg_severity = AlertSeverity.CRITICAL
                        bg_alert_type = "BANK_GUARANTEE_EXPIRING"
                        bg_title = f"Срок банковской гарантии истекает через {bg_days_diff} дн. Риск включения в РНП! ({p.project_name})"
                        bg_desc = (
                            f"Срок действия БГ истекает {bg_expiry} (осталось {bg_days_diff} дн.). "
                            f"Срок банковской гарантии истекает через {bg_days_diff} дн. Риск включения в РНП! "
                            f"Обеспечение: {guarantee_sum:,.2f} ₽. "
                            f"Куратор: {p.curator_name or 'Не назначен'}."
                        )
                    else:
                        # 6 to 15 days
                        bg_severity = AlertSeverity.WARNING
                        bg_alert_type = "BANK_GUARANTEE_EXPIRING"
                        bg_title = f"Необходимо продлить БГ или подписать КС-2: {p.project_name}"
                        bg_desc = (
                            f"До окончания банковской гарантии осталось {bg_days_diff} дн. ({bg_expiry}). "
                            f"Необходимо продлить БГ или подписать КС-2. "
                            f"Обеспечение: {guarantee_sum:,.2f} ₽. "
                            f"Куратор: {p.curator_name or 'Не назначен'}."
                        )

                    alert_q = select(SystemAlert).where(
                        SystemAlert.company_id == company_id,
                        SystemAlert.alert_type.in_(["BANK_GUARANTEE_EXPIRING", "BANK_GUARANTEE_EXPIRED"]),
                        SystemAlert.entity_id == p.id,
                        SystemAlert.is_resolved.is_(False),
                    )
                    existing_bg_alert = (await db.execute(alert_q)).scalar_one_or_none()
                    if existing_bg_alert:
                        existing_bg_alert.severity = bg_severity
                        existing_bg_alert.alert_type = bg_alert_type
                        existing_bg_alert.title = bg_title
                        existing_bg_alert.description = bg_desc
                        existing_bg_alert.calculated_financial_impact = guarantee_sum
                        existing_bg_alert.trigger_date = bg_expiry
                        generated_alerts.append(existing_bg_alert)
                    else:
                        new_bg_alert = SystemAlert(
                            company_id=company_id,
                            domain_category=DomainCategory.PRODUCTION_TENDERS,
                            severity=bg_severity,
                            alert_type=bg_alert_type,
                            entity_type="tender_projects",
                            entity_id=p.id,
                            title=bg_title,
                            description=bg_desc,
                            calculated_financial_impact=guarantee_sum,
                            trigger_date=bg_expiry,
                            is_resolved=False,
                        )
                        db.add(new_bg_alert)
                        generated_alerts.append(new_bg_alert)

        return generated_alerts

    @classmethod
    async def evaluate_procurement_risks(
        cls, company_id: uuid.UUID, db: AsyncSession
    ) -> List[SystemAlert]:
        """
        Scans procurement orders for 5-day delivery deadlines or delays:
        - If delivery_deadline - today <= 5 and not completed -> WARNING / CRITICAL.
        """
        today = datetime.now(timezone.utc).date()
        query = select(ProcurementItem).where(
            ProcurementItem.company_id == company_id,
            ProcurementItem.deleted_at.is_(None),
            ProcurementItem.delivery_deadline.is_not(None),
        )
        res = await db.execute(query)
        items = res.scalars().all()

        completed_statuses = {"на складе", "доставлено", "delivered", "completed", "отменено", "оплачено"}
        generated_alerts: List[SystemAlert] = []

        for item in items:
            if str(item.status).strip().lower() in completed_statuses:
                continue

            days_diff = (item.delivery_deadline - today).days
            if days_diff <= 5:
                if days_diff < 0:
                    days_overdue = abs(days_diff)
                    severity = AlertSeverity.CRITICAL
                    alert_type = "PROCUREMENT_DELAY"
                    title = f"Срыв поставки ТМЦ: {item.item_name}"
                    desc = (
                        f"Просрочка поставки ТМЦ '{item.item_name}' на {days_overdue} дн. ({item.delivery_deadline}). "
                        f"Объект: {item.project_name}. Поставщик: {item.supplier or 'Не указан'}. "
                        f"Сумма счета: {item.invoice_amount:,.2f} ₽. Риск остановки СМР!"
                    )
                else:
                    severity = AlertSeverity.CRITICAL if days_diff <= 2 else AlertSeverity.WARNING
                    alert_type = "PROCUREMENT_DEADLINE_APPROACHING"
                    title = f"Дедлайн поставки ТМЦ ({days_diff} дн.): {item.item_name}"
                    desc = (
                        f"Поставка ТМЦ '{item.item_name}' ожидается через {days_diff} дн. ({item.delivery_deadline}). "
                        f"Объект: {item.project_name}. Поставщик: {item.supplier or 'Не указан'}. "
                        f"Сумма счета: {item.invoice_amount:,.2f} ₽."
                    )

                alert_q = select(SystemAlert).where(
                    SystemAlert.company_id == company_id,
                    SystemAlert.alert_type.in_(["PROCUREMENT_DELAY", "PROCUREMENT_DEADLINE_APPROACHING"]),
                    SystemAlert.entity_id == item.id,
                    SystemAlert.is_resolved.is_(False),
                )
                existing_alert = (await db.execute(alert_q)).scalar_one_or_none()
                if existing_alert:
                    existing_alert.severity = severity
                    existing_alert.alert_type = alert_type
                    existing_alert.title = title
                    existing_alert.description = desc
                    existing_alert.calculated_financial_impact = item.invoice_amount
                    existing_alert.trigger_date = item.delivery_deadline
                    generated_alerts.append(existing_alert)
                else:
                    new_alert = SystemAlert(
                        company_id=company_id,
                        domain_category=DomainCategory.PRODUCTION_TENDERS,
                        severity=severity,
                        alert_type=alert_type,
                        entity_type="procurement_items",
                        entity_id=item.id,
                        title=title,
                        description=desc,
                        calculated_financial_impact=item.invoice_amount,
                        trigger_date=item.delivery_deadline,
                        is_resolved=False,
                    )
                    db.add(new_alert)
                    generated_alerts.append(new_alert)

        return generated_alerts

    @classmethod
    async def evaluate_operational_tasks_risks(
        cls, company_id: uuid.UUID, db: AsyncSession
    ) -> List[SystemAlert]:
        """
        Scans operational tasks for critical penalties (disagreement protocols, urgent fines)
        and 5-day deadline proximity.
        """
        today = datetime.now(timezone.utc).date()
        query = select(OperationalTask).where(
            OperationalTask.company_id == company_id,
            OperationalTask.deleted_at.is_(None),
            OperationalTask.status != TaskStatus.COMPLETED,
        )
        res = await db.execute(query)
        tasks = res.scalars().all()

        generated_alerts: List[SystemAlert] = []

        for task in tasks:
            days_diff = (task.due_date - today).days if task.due_date else None
            p1 = getattr(task, "estimated_penalty_amount", None) or Decimal("0.00")
            p2 = getattr(task, "penalty_amount", None) or Decimal("0.00")
            impact = max(p1, p2)
            is_urgent_priority = task.priority == TaskPriority.URGENT or "критическ" in str(task.penalty_risk_desc or "").lower()

            if days_diff is not None and days_diff < 0:
                days_overdue = abs(days_diff)
                severity = AlertSeverity.CRITICAL
                alert_type = "TASK_OVERDUE"
                title = f"Просрочена задача: {task.task_title}"
                desc = (
                    f"Задача просрочена на {days_overdue} дн. (срок: {task.due_date}). "
                    f"Ответственный: {task.responsible_person or task.responsible_role or 'Не назначен'}. "
                    f"Контракт: {task.related_contract or '—'}. "
                    f"Риск штрафа: {task.penalty_risk_desc or ''} ({impact:,.2f} ₽)."
                )
            elif days_diff is not None and days_diff <= 5:
                severity = AlertSeverity.CRITICAL if (is_urgent_priority or days_diff <= 2) else AlertSeverity.WARNING
                alert_type = "TASK_DEADLINE_APPROACHING"
                title = f"Срочная задача ({days_diff} дн.): {task.task_title}"
                desc = (
                    f"Дедлайн по задаче через {days_diff} дн. ({task.due_date}). "
                    f"Ответственный: {task.responsible_person or task.responsible_role or 'Не назначен'}. "
                    f"Контракт: {task.related_contract or '—'}. "
                    f"Риск штрафа: {task.penalty_risk_desc or ''} ({impact:,.2f} ₽)."
                )
            elif is_urgent_priority:
                severity = AlertSeverity.CRITICAL
                alert_type = "TASK_CRITICAL_PENALTY"
                title = f"Критический риск штрафа: {task.task_title}"
                desc = (
                    f"Критическая задача с риском санкций! "
                    f"Ответственный: {task.responsible_person or task.responsible_role or 'Не назначен'}. "
                    f"Контракт: {task.related_contract or '—'}. "
                    f"Риск: {task.penalty_risk_desc or ''} ({impact:,.2f} ₽)."
                )
            else:
                continue

            alert_q = select(SystemAlert).where(
                SystemAlert.company_id == company_id,
                SystemAlert.alert_type.in_(["TASK_OVERDUE", "TASK_DEADLINE_APPROACHING", "TASK_CRITICAL_PENALTY"]),
                SystemAlert.entity_id == task.id,
                SystemAlert.is_resolved.is_(False),
            )
            existing_alert = (await db.execute(alert_q)).scalar_one_or_none()
            if existing_alert:
                existing_alert.severity = severity
                existing_alert.alert_type = alert_type
                existing_alert.title = title
                existing_alert.description = desc
                existing_alert.calculated_financial_impact = impact
                existing_alert.trigger_date = task.due_date or today
                generated_alerts.append(existing_alert)
            else:
                new_alert = SystemAlert(
                    company_id=company_id,
                    domain_category=DomainCategory.OPERATIONAL_TASKS,
                    severity=severity,
                    alert_type=alert_type,
                    entity_type="operational_tasks",
                    entity_id=task.id,
                    title=title,
                    description=desc,
                    calculated_financial_impact=impact,
                    trigger_date=task.due_date or today,
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
            gap_days = (gap_date - today).days if gap_date else 0
            title = f"Кассовый разрыв через {gap_days} дн. на сумму {gap_deficit:,.2f} ₽"
            desc = (
                f"Прогнозируется отрицательное сальдо кассы через {gap_days} дн. ({gap_date}). "
                f"Дефицит: {gap_deficit:,.2f} ₽. Плановые списания превышают доступный баланс."
            )
            if existing_gap_alert:
                existing_gap_alert.title = title
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
                    title=title,
                    description=desc,
                    calculated_financial_impact=gap_deficit,
                    trigger_date=gap_date or today,
                    is_resolved=False,
                )
                db.add(new_gap_alert)
        elif existing_gap_alert:
            existing_gap_alert.is_resolved = True
            existing_gap_alert.resolution_comment = "Кассовый разрыв устранен: положительное сальдо"

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
        await cls.evaluate_procurement_risks(company_id, db)
        await cls.evaluate_operational_tasks_risks(company_id, db)
        await cls.evaluate_cash_gap(company_id, db)
        await db.commit()


alerts_engine = AlertsEngine()
