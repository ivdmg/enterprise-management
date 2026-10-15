import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import CashflowDirection

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.file import UploadedFile


class CashflowOperation(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Domain 2: Financial operations, cashflow, debt and settlements.
    """
    __tablename__ = "cashflow_operations"

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
    operation_date: Mapped[date] = mapped_column(Date, nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    direction: Mapped[CashflowDirection] = mapped_column(
        Enum(CashflowDirection, name="cashflow_direction_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dds_article: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    planned_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    actual_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    payment_status: Mapped[str] = mapped_column(
        String(50), default="Факт_Исполнено", nullable=False
    )
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_purpose: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="cashflow_operations")
    file: Mapped["UploadedFile | None"] = relationship("UploadedFile", back_populates="cashflow_operations")

    __table_args__ = (
        Index(
            "idx_cashflow_company_date",
            "company_id",
            "operation_date",
            "direction",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_cashflow_due_unpaid",
            "company_id",
            "payment_due_date",
            postgresql_where=text("is_paid = false"),
        ),
        Index(
            "idx_cashflow_payment_status",
            "company_id",
            "payment_status",
        ),
    )
