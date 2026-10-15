import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class FileStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROFILING = "profiling"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PROCESSED = "processed"
    FAILED = "failed"


class DomainCategory(str, enum.Enum):
    PRODUCTION_TENDERS = "production_tenders"
    CASHFLOW_DEBT = "cashflow_debt"
    PAYROLL_HR = "payroll_hr"
    OPERATIONAL_TASKS = "operational_tasks"


class ProjectRisk(str, enum.Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class CashflowDirection(str, enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class PayrollStatus(str, enum.Enum):
    ACCRUED = "accrued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class AlertSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class NotificationChannel(str, enum.Enum):
    IN_APP = "IN_APP"
    TELEGRAM = "TELEGRAM"
    EMAIL = "EMAIL"


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
