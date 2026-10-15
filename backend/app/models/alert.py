import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, TYPE_CHECKING
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from app.models.enums import (
    DomainCategory,
    AlertSeverity,
    NotificationChannel,
    NotificationStatus,
)

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class SystemAlert(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Incident and risk registry across all operational and financial domains.
    """
    __tablename__ = "system_alerts"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain_category: Mapped[DomainCategory] = mapped_column(
        Enum(DomainCategory, name="domain_category_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    calculated_financial_impact: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    trigger_date: Mapped[date] = mapped_column(
        Date, server_default=func.current_date(), nullable=False
    )
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="system_alerts")
    resolver: Mapped["User | None"] = relationship("User", back_populates="resolved_alerts")
    notification_logs: Mapped[List["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="alert", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_alerts_company_unresolved", "company_id", "is_resolved", "severity"),
        Index("idx_alerts_date", "company_id", trigger_date.desc()),
    )


class NotificationLog(Base, UUIDPrimaryKeyMixin):
    """
    Log of sent notifications across Telegram, Email, and In-App channels.
    """
    __tablename__ = "notification_logs"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("system_alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    recipient_target: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=NotificationStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    alert: Mapped["SystemAlert"] = relationship("SystemAlert", back_populates="notification_logs")

    __table_args__ = (
        Index("idx_notification_logs_alert", "alert_id"),
    )


class IntegrationSetting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Company-level configuration for external integrations and notification schedules.
    """
    __tablename__ = "integration_settings"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    telegram_bot_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telegram_bot_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    daily_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    daily_digest_time: Mapped[str] = mapped_column(String(5), default="08:30", nullable=False)
    alert_rules: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=lambda: {
            "deadline_warning_days": 5,
            "cash_gap_forecast_days": 14,
            "notify_on_critical_instant": True,
        },
        nullable=False,
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="integration_settings")
