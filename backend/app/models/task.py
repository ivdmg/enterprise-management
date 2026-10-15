import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import TaskStatus, TaskPriority

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.file import UploadedFile


class OperationalTask(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Domain 4: Operational tasks, orders, prescriptions & compliance.
    """
    __tablename__ = "operational_tasks"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsible_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority_enum", values_callable=lambda x: [e.value for e in x]),
        default=TaskPriority.MEDIUM,
        nullable=False,
    )
    penalty_risk_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_penalty_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="operational_tasks")
    file: Mapped["UploadedFile | None"] = relationship("UploadedFile", back_populates="operational_tasks")

    __table_args__ = (
        Index(
            "idx_tasks_company_due",
            "company_id",
            "due_date",
            "status",
            postgresql_where=(SoftDeleteMixin.deleted_at == None),  # noqa: E711
        ),
    )
