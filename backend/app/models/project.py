import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, TYPE_CHECKING
from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import ProjectRisk

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.file import UploadedFile


class TenderProject(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Domain 1: Tenders, Construction & Contractual commitments.
    """
    __tablename__ = "tender_projects"

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
    project_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purchase_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    curator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_sum: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    application_guarantee_sum: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    completed_sum: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    paid_sum: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    debt_sum: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    submission_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    work_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    bank_guarantee_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="in_progress", nullable=False)
    risk_level: Mapped[ProjectRisk] = mapped_column(
        Enum(ProjectRisk, name="project_risk_enum", values_callable=lambda x: [e.value for e in x]),
        default=ProjectRisk.NORMAL,
        nullable=False,
    )
    penalty_amount_calculated: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    custom_attributes: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="tender_projects")
    file: Mapped["UploadedFile | None"] = relationship("UploadedFile", back_populates="tender_projects")

    __table_args__ = (
        Index(
            "idx_tender_company_status",
            "company_id",
            "status",
            "deadline_date",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_tender_risk",
            "company_id",
            "risk_level",
            postgresql_where=text("risk_level != 'normal'"),
        ),
        Index(
            "idx_tender_bg_expiry",
            "company_id",
            "bank_guarantee_expiry",
        ),
    )
