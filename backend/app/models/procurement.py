import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.file import UploadedFile


class ProcurementItem(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Domain: Procurement, materials supply, purchase orders and deliveries.
    Matches Template 3 (03_План_Закупок_и_Материалов.xlsx).
    """
    __tablename__ = "procurement_items"

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
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), default=Decimal("0.000"), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(50), default="шт", nullable=False)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default="Заявка", nullable=False
    )
    delivery_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="procurement_items")
    file: Mapped["UploadedFile | None"] = relationship("UploadedFile", back_populates="procurement_items")

    __table_args__ = (
        Index(
            "idx_procurement_company_status",
            "company_id",
            "status",
            "delivery_deadline",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_procurement_project",
            "company_id",
            "project_name",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
