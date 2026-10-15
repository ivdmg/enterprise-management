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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import PayrollStatus

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.file import UploadedFile


class PayrollRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Domain 3: Payroll, wage accruals and payments to employees.
    """
    __tablename__ = "payroll_records"

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
    payroll_period: Mapped[str] = mapped_column(String(20), nullable=False)  # Format: 'YYYY-MM'
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    role_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    accrued_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    debt_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    payment_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PayrollStatus] = mapped_column(
        Enum(PayrollStatus, name="payroll_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=PayrollStatus.ACCRUED,
        nullable=False,
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="payroll_records")
    file: Mapped["UploadedFile | None"] = relationship("UploadedFile", back_populates="payroll_records")

    __table_args__ = (
        Index(
            "idx_payroll_company_period",
            "company_id",
            "payroll_period",
            postgresql_where=(SoftDeleteMixin.deleted_at == None),  # noqa: E711
        ),
        Index(
            "idx_payroll_debt",
            "company_id",
            "status",
            postgresql_where=(status == "overdue"),
        ),
    )
