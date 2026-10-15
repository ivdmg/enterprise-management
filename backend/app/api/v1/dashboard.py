import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alert import SystemAlert
from app.models.enums import AlertSeverity, ProjectRisk
from app.models.finance import CashflowOperation
from app.models.payroll import PayrollRecord
from app.models.procurement import ProcurementItem
from app.models.project import TenderProject
from app.models.user import User
from app.schemas.common import MetaModel, ResponseEnvelope
from app.schemas.dashboard import (
    AlertsOverview,
    CashflowDynamicsItem,
    CreditorItem,
    DashboardFinanceData,
    DashboardPayrollData,
    DashboardSummaryData,
    DebtorItem,
    FinancialHealth,
    PayrollDepartmentItem,
    ProductionHealth,
    ProjectDashboardItem,
    TopFireItem,
)
from app.services.alerts_engine import alerts_engine

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Executive Analytics"])


def build_fire_item(
    a: SystemAlert,
    projects_map: dict[uuid.UUID, TenderProject],
    today: date,
) -> TopFireItem:
    """Helper to convert SystemAlert into rich TopFireItem with 44-FZ risk indicators."""
    proj = projects_map.get(a.entity_id) if a.entity_id and a.entity_type == "tender_projects" else None
    project_id = proj.id if proj else (a.entity_id if a.entity_type == "tender_projects" else None)
    project_name = proj.project_name if proj else None

    responsible = proj.curator_name if proj else None
    if not responsible:
        if "Ответственный: " in a.description:
            part = a.description.split("Ответственный: ")[1].split(".")[0].strip()
            if part != "Не назначен":
                responsible = part
        elif "Куратор: " in a.description:
            part = a.description.split("Куратор: ")[1].split(".")[0].strip()
            if part != "Не назначен":
                responsible = part

    cat: str = "ks2_delay"
    if "KS2" in a.alert_type or "DEADLINE_BREACH" in a.alert_type:
        cat = "ks2_delay"
    elif "BANK_GUARANTEE" in a.alert_type:
        cat = "bank_guarantee"
    elif "PROCUREMENT" in a.alert_type:
        cat = "procurement"
    elif "TASK" in a.alert_type:
        cat = "disagreement_protocol"
    elif "CASH_GAP" in a.alert_type:
        cat = "receivable_debt"

    days_overdue: Optional[int] = None
    days_remaining: Optional[int] = None
    if a.trigger_date:
        diff = (a.trigger_date - today).days
        if diff < 0:
            days_overdue = abs(diff)
            days_remaining = 0
        else:
            days_overdue = 0
            days_remaining = diff

    return TopFireItem(
        id=a.id,
        severity=a.severity.value,
        title=a.title,
        description=a.description,
        financial_impact=a.calculated_financial_impact,
        due_date=a.trigger_date,
        responsible=responsible,
        project_id=project_id,
        project_name=project_name,
        penalty_amount=a.calculated_financial_impact,
        days_overdue=days_overdue,
        days_remaining=days_remaining,
        category=cat,
    )


@router.get(
    "/summary",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[DashboardSummaryData],
    summary="Главный экран руководителя («Executive Fire-Panel»)",
)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[DashboardSummaryData]:
    """
    Returns high-level Executive Fire-Panel metrics:
    - free_cash: текущий свободный остаток ДДС
    - active_portfolio_sum: суммарный объем активных контрактов в работе
    - receivables_sum: нам должны (подписано КС, но не оплачено заказчиком)
    - payables_sum: мы должны (неоплаченные счета поставщиков ТМЦ и кредиторы)
    - critical_alerts_count: количество горящих событий
    - Financial health and 14-day cash gap predictions
    - Production portfolio health and penalty exposures
    - Critical alerts overview and Top-Fire actionable items
    """
    today = datetime.now(timezone.utc).date()

    # 1. Evaluate cash health & gap
    (
        current_balance,
        forecast_inflow,
        forecast_outflow,
        is_gap_predicted,
        gap_deficit,
        gap_date,
    ) = await alerts_engine.evaluate_cash_gap(current_user.company_id, db)

    financial_health = FinancialHealth(
        current_cash_balance=current_balance,
        forecast_14d_inflow=forecast_inflow,
        forecast_14d_outflow=forecast_outflow,
        is_cash_gap_predicted=is_gap_predicted,
        gap_deficit_amount=gap_deficit,
        gap_date=gap_date,
    )

    # 2. Production portfolio health & receivables
    proj_q = select(TenderProject).where(
        TenderProject.company_id == current_user.company_id,
        TenderProject.deleted_at.is_(None),
    )
    proj_res = await db.execute(proj_q)
    projects = proj_res.scalars().all()
    projects_map = {p.id: p for p in projects}

    active_projects = [p for p in projects if p.status != "completed"]
    total_active_projects = len(active_projects)
    active_portfolio_sum = sum((p.contract_sum for p in active_projects), Decimal("0.00"))
    total_penalties = sum((p.penalty_amount_calculated for p in projects), Decimal("0.00"))
    projects_at_risk_count = sum(1 for p in projects if p.risk_level != ProjectRisk.NORMAL)

    # receivables_sum: нам должны (подписано КС, но не оплачено заказчиком)
    receivables_sum = sum(
        (max(Decimal("0.00"), p.completed_sum - p.paid_sum) for p in projects),
        Decimal("0.00"),
    )

    # payables_sum: мы должны (неоплаченные счета поставщиков ТМЦ и плановые списания)
    payables_proc_q = select(func.coalesce(func.sum(ProcurementItem.invoice_amount), Decimal("0.00"))).where(
        ProcurementItem.company_id == current_user.company_id,
        ProcurementItem.deleted_at.is_(None),
        func.lower(ProcurementItem.status).not_in(["на складе", "доставлено", "отменено", "оплачено"]),
    )
    proc_payables = (await db.execute(payables_proc_q)).scalar_one()

    payables_cf_q = select(func.coalesce(func.sum(CashflowOperation.planned_amount), Decimal("0.00"))).where(
        CashflowOperation.company_id == current_user.company_id,
        CashflowOperation.deleted_at.is_(None),
        CashflowOperation.direction == "outgoing",
        CashflowOperation.is_paid.is_(False),
    )
    cf_payables = (await db.execute(payables_cf_q)).scalar_one()
    payables_sum = proc_payables if proc_payables > Decimal("0.00") else cf_payables

    if projects:
        comp_ratios = [
            float((p.completed_sum / p.contract_sum) * 100)
            for p in projects
            if p.contract_sum > Decimal("0.00")
        ]
        avg_completion = sum(comp_ratios) / len(comp_ratios) if comp_ratios else 0.0
    else:
        avg_completion = 0.0

    production_health = ProductionHealth(
        total_active_projects=total_active_projects,
        total_portfolio_sum=active_portfolio_sum,
        average_completion_percent=round(avg_completion, 1),
        projects_at_risk_count=projects_at_risk_count,
        total_calculated_penalties=total_penalties,
    )

    # 3. Alerts Overview
    crit_count_q = select(func.count(SystemAlert.id)).where(
        SystemAlert.company_id == current_user.company_id,
        SystemAlert.is_resolved.is_(False),
        SystemAlert.severity == AlertSeverity.CRITICAL,
    )
    warn_count_q = select(func.count(SystemAlert.id)).where(
        SystemAlert.company_id == current_user.company_id,
        SystemAlert.is_resolved.is_(False),
        SystemAlert.severity == AlertSeverity.WARNING,
    )
    info_count_q = select(func.count(SystemAlert.id)).where(
        SystemAlert.company_id == current_user.company_id,
        SystemAlert.is_resolved.is_(False),
        SystemAlert.severity == AlertSeverity.INFO,
    )
    crit_count = (await db.execute(crit_count_q)).scalar_one()
    warn_count = (await db.execute(warn_count_q)).scalar_one()
    info_count = (await db.execute(info_count_q)).scalar_one()

    alerts_overview = AlertsOverview(
        critical_count=crit_count,
        warning_count=warn_count,
        info_count=info_count,
    )

    # 4. Top Fire items (highest financial impact active alerts)
    fire_q = (
        select(SystemAlert)
        .where(
            SystemAlert.company_id == current_user.company_id,
            SystemAlert.is_resolved.is_(False),
        )
        .order_by(
            desc(SystemAlert.severity == AlertSeverity.CRITICAL),
            SystemAlert.calculated_financial_impact.desc(),
        )
        .limit(10)
    )
    fire_res = await db.execute(fire_q)
    fire_alerts = fire_res.scalars().all()

    top_fire_items = [
        build_fire_item(a, projects_map, today)
        for a in fire_alerts
    ]

    summary_data = DashboardSummaryData(
        free_cash=current_balance,
        active_portfolio_sum=active_portfolio_sum,
        receivables_sum=receivables_sum,
        payables_sum=payables_sum,
        critical_alerts_count=crit_count,
        financial_health=financial_health,
        production_health=production_health,
        alerts_overview=alerts_overview,
        top_fire_items=top_fire_items,
    )
    return ResponseEnvelope.ok(summary_data)


@router.get(
    "/alerts/critical",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[list[TopFireItem]],
    summary="Список карточек «Где горит?» (критические алерты с неустойками и ответственными)",
)
async def get_dashboard_critical_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[list[TopFireItem]]:
    """
    Returns critical actionable alert cards for 'Where is it burning?' widget:
    Includes calculated 44-FZ penalty, responsible person, deadline date and days remaining/overdue.
    """
    today = datetime.now(timezone.utc).date()

    proj_q = select(TenderProject).where(
        TenderProject.company_id == current_user.company_id,
        TenderProject.deleted_at.is_(None),
    )
    projects = (await db.execute(proj_q)).scalars().all()
    projects_map = {p.id: p for p in projects}

    crit_q = (
        select(SystemAlert)
        .where(
            SystemAlert.company_id == current_user.company_id,
            SystemAlert.is_resolved.is_(False),
            SystemAlert.severity == AlertSeverity.CRITICAL,
        )
        .order_by(SystemAlert.calculated_financial_impact.desc())
    )
    crit_alerts = (await db.execute(crit_q)).scalars().all()

    items = [build_fire_item(a, projects_map, today) for a in crit_alerts]
    return ResponseEnvelope.ok(items)


@router.get(
    "/finance",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[DashboardFinanceData],
    summary="Аналитика движения денежных средств, кассы и задолженностей",
)
async def get_dashboard_finance(
    period: str = Query("month", pattern="^(month|quarter|year)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[DashboardFinanceData]:
    """
    Returns cashflow totals, daily inflow/outflow dynamics, and top debtors & creditors.
    """
    today = datetime.now(timezone.utc).date()
    if not start_date:
        if period == "month":
            start_date = today.replace(day=1)
        elif period == "quarter":
            start_date = today - timedelta(days=90)
        else:
            start_date = today.replace(month=1, day=1)
    if not end_date:
        end_date = today

    base_filter = [
        CashflowOperation.company_id == current_user.company_id,
        CashflowOperation.deleted_at.is_(None),
    ]

    # Inflow and Outflow totals
    in_q = select(func.coalesce(func.sum(CashflowOperation.actual_amount), Decimal("0.00"))).where(
        *base_filter,
        CashflowOperation.direction == "incoming",
        CashflowOperation.operation_date >= start_date,
        CashflowOperation.operation_date <= end_date,
    )
    out_q = select(func.coalesce(func.sum(CashflowOperation.actual_amount), Decimal("0.00"))).where(
        *base_filter,
        CashflowOperation.direction == "outgoing",
        CashflowOperation.operation_date >= start_date,
        CashflowOperation.operation_date <= end_date,
    )
    total_in = (await db.execute(in_q)).scalar_one()
    total_out = (await db.execute(out_q)).scalar_one()

    # Daily dynamics
    dyn_q = (
        select(
            CashflowOperation.operation_date,
            func.coalesce(
                func.sum(CashflowOperation.actual_amount).filter(CashflowOperation.direction == "incoming"),
                Decimal("0.00"),
            ).label("incoming"),
            func.coalesce(
                func.sum(CashflowOperation.actual_amount).filter(CashflowOperation.direction == "outgoing"),
                Decimal("0.00"),
            ).label("outgoing"),
        )
        .where(
            *base_filter,
            CashflowOperation.operation_date >= start_date,
            CashflowOperation.operation_date <= end_date,
        )
        .group_by(CashflowOperation.operation_date)
        .order_by(CashflowOperation.operation_date.asc())
    )
    dyn_res = await db.execute(dyn_q)
    dynamics = [
        CashflowDynamicsItem(
            date=row.operation_date.isoformat(),
            incoming=row.incoming,
            outgoing=row.outgoing,
        )
        for row in dyn_res.all()
    ]

    # Top Debtors (parties that owe us money)
    debtors_q = (
        select(
            CashflowOperation.counterparty,
            func.sum(CashflowOperation.actual_amount).label("debt_sum"),
        )
        .where(
            *base_filter,
            CashflowOperation.direction == "incoming",
            CashflowOperation.is_paid.is_(False),
            CashflowOperation.counterparty.isnot(None),
        )
        .group_by(CashflowOperation.counterparty)
        .order_by(desc("debt_sum"))
        .limit(5)
    )
    debtors_res = await db.execute(debtors_q)
    top_debtors = [
        DebtorItem(counterparty=row.counterparty, debt_sum=row.debt_sum, overdue_days=0)
        for row in debtors_res.all()
    ]

    # Top Creditors (parties we owe money to)
    creditors_q = (
        select(
            CashflowOperation.counterparty,
            func.sum(CashflowOperation.actual_amount).label("debt_sum"),
            func.min(CashflowOperation.payment_due_date).label("due_date"),
        )
        .where(
            *base_filter,
            CashflowOperation.direction == "outgoing",
            CashflowOperation.is_paid.is_(False),
            CashflowOperation.counterparty.isnot(None),
        )
        .group_by(CashflowOperation.counterparty)
        .order_by(desc("debt_sum"))
        .limit(5)
    )
    creditors_res = await db.execute(creditors_q)
    top_creditors = [
        CreditorItem(counterparty=row.counterparty, debt_sum=row.debt_sum, payment_due_date=row.due_date)
        for row in creditors_res.all()
    ]

    finance_data = DashboardFinanceData(
        total_incoming=total_in,
        total_outgoing=total_out,
        net_cash_flow=total_in - total_out,
        dynamics=dynamics,
        top_debtors=top_debtors,
        top_creditors=top_creditors,
    )
    return ResponseEnvelope.ok(finance_data)


@router.get(
    "/projects",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[List[ProjectDashboardItem]],
    summary="Реестр тендеров и производства с расчетом рисков и штрафов",
)
async def get_dashboard_projects(
    status_filter: Optional[str] = Query(None, alias="status"),
    risk_level: Optional[ProjectRisk] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[List[ProjectDashboardItem]]:
    """
    Returns tenant construction & tender projects with real-time risk evaluations.
    """
    today = datetime.now(timezone.utc).date()
    base_q = select(TenderProject).where(
        TenderProject.company_id == current_user.company_id,
        TenderProject.deleted_at.is_(None),
    )
    if status_filter and status_filter != "all":
        base_q = base_q.where(TenderProject.status == status_filter)
    if risk_level:
        base_q = base_q.where(TenderProject.risk_level == risk_level)

    # Count
    total_q = select(func.count()).select_from(base_q.subquery())
    total_items = (await db.execute(total_q)).scalar_one()

    # Query items
    query = (
        base_q.order_by(
            desc(TenderProject.risk_level == ProjectRisk.CRITICAL),
            TenderProject.deadline_date.asc().nullslast(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
    )
    res = await db.execute(query)
    projects = res.scalars().all()

    items: List[ProjectDashboardItem] = []
    for p in projects:
        comp_pct = (
            float((p.completed_sum / p.contract_sum) * 100)
            if p.contract_sum > Decimal("0.00")
            else 0.0
        )
        days_overdue = (today - p.deadline_date).days if (p.deadline_date and p.deadline_date < today) else 0

        items.append(
            ProjectDashboardItem(
                id=p.id,
                project_code=p.project_code,
                project_name=p.project_name,
                customer_name=p.customer_name,
                curator_name=p.curator_name,
                contract_sum=p.contract_sum,
                completed_sum=p.completed_sum,
                paid_sum=p.paid_sum,
                debt_sum=p.debt_sum,
                completion_percent=round(comp_pct, 1),
                start_date=p.start_date,
                deadline_date=p.deadline_date,
                days_overdue=max(0, days_overdue),
                risk_level=p.risk_level,
                penalty_amount_calculated=p.penalty_amount_calculated,
            )
        )

    total_pages = (total_items + limit - 1) // limit if limit else 1
    meta = MetaModel(page=page, limit=limit, total_items=total_items, total_pages=total_pages)
    return ResponseEnvelope.ok(items, meta=meta)


@router.get(
    "/payroll",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[DashboardPayrollData],
    summary="Аналитика фонда оплаты труда по отделам",
)
async def get_dashboard_payroll(
    period: Optional[str] = Query(None, description="Расчетный период YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[DashboardPayrollData]:
    """
    Aggregates wage accruals, payouts, and debts grouped by corporate department.
    """
    now = datetime.now(timezone.utc)
    target_period = period or now.strftime("%Y-%m")

    base_filter = [
        PayrollRecord.company_id == current_user.company_id,
        PayrollRecord.deleted_at.is_(None),
        PayrollRecord.payroll_period == target_period,
    ]

    totals_q = select(
        func.coalesce(func.sum(PayrollRecord.accrued_amount), Decimal("0.00")).label("total_accrued"),
        func.coalesce(func.sum(PayrollRecord.paid_amount), Decimal("0.00")).label("total_paid"),
        func.coalesce(func.sum(PayrollRecord.debt_amount), Decimal("0.00")).label("total_debt"),
        func.min(PayrollRecord.payment_due_date).label("next_due"),
    ).where(*base_filter)
    totals_res = (await db.execute(totals_q)).one()

    dept_q = (
        select(
            func.coalesce(PayrollRecord.department, "Основной отдел").label("department"),
            func.coalesce(func.sum(PayrollRecord.accrued_amount), Decimal("0.00")).label("accrued"),
            func.coalesce(func.sum(PayrollRecord.paid_amount), Decimal("0.00")).label("paid"),
            func.coalesce(func.sum(PayrollRecord.debt_amount), Decimal("0.00")).label("debt"),
        )
        .where(*base_filter)
        .group_by(PayrollRecord.department)
        .order_by(desc("accrued"))
    )
    dept_res = await db.execute(dept_q)
    dept_items = [
        PayrollDepartmentItem(
            department=row.department,
            accrued=row.accrued,
            paid=row.paid,
            debt=row.debt,
        )
        for row in dept_res.all()
    ]

    payroll_data = DashboardPayrollData(
        period=target_period,
        total_accrued=totals_res.total_accrued,
        total_paid=totals_res.total_paid,
        total_debt=totals_res.total_debt,
        next_payment_deadline=totals_res.next_due,
        by_department=dept_items,
    )
    return ResponseEnvelope.ok(payroll_data)
