import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import ProjectRisk


class FinancialHealth(BaseModel):
    current_cash_balance: Decimal
    forecast_14d_inflow: Decimal
    forecast_14d_outflow: Decimal
    is_cash_gap_predicted: bool
    gap_deficit_amount: Decimal = Decimal("0.00")
    gap_date: Optional[date] = None


class ProductionHealth(BaseModel):
    total_active_projects: int
    total_portfolio_sum: Decimal
    average_completion_percent: float
    projects_at_risk_count: int
    total_calculated_penalties: Decimal


class AlertsOverview(BaseModel):
    critical_count: int
    warning_count: int
    info_count: int


class TopFireItem(BaseModel):
    id: uuid.UUID
    severity: str
    title: str
    description: str
    financial_impact: Decimal
    due_date: Optional[date] = None
    responsible: Optional[str] = None


class DashboardSummaryData(BaseModel):
    financial_health: FinancialHealth
    production_health: ProductionHealth
    alerts_overview: AlertsOverview
    top_fire_items: List[TopFireItem]


class CashflowDynamicsItem(BaseModel):
    date: str
    incoming: Decimal
    outgoing: Decimal


class DebtorItem(BaseModel):
    counterparty: str
    debt_sum: Decimal
    overdue_days: int = 0


class CreditorItem(BaseModel):
    counterparty: str
    debt_sum: Decimal
    payment_due_date: Optional[date] = None


class DashboardFinanceData(BaseModel):
    total_incoming: Decimal
    total_outgoing: Decimal
    net_cash_flow: Decimal
    dynamics: List[CashflowDynamicsItem]
    top_debtors: List[DebtorItem]
    top_creditors: List[CreditorItem]


class ProjectDashboardItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_code: Optional[str] = None
    project_name: str
    customer_name: Optional[str] = None
    curator_name: Optional[str] = None
    contract_sum: Decimal
    completed_sum: Decimal
    paid_sum: Decimal
    debt_sum: Decimal
    completion_percent: float
    start_date: Optional[date] = None
    deadline_date: Optional[date] = None
    days_overdue: int = 0
    risk_level: ProjectRisk
    penalty_amount_calculated: Decimal


class PayrollDepartmentItem(BaseModel):
    department: str
    accrued: Decimal
    paid: Decimal
    debt: Decimal


class DashboardPayrollData(BaseModel):
    period: str
    total_accrued: Decimal
    total_paid: Decimal
    total_debt: Decimal
    next_payment_deadline: Optional[date] = None
    by_department: List[PayrollDepartmentItem]
