import uuid
from datetime import date
from typing import TYPE_CHECKING
from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.file import UploadedFile


class FleetDispatchRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Domain: Machinery, fleet dispatch, work shifts and field incidents.
    Matches Template 4 (04_Диспетчерский_График_и_Техника.xlsx).
    """
    __tablename__ = "fleet_dispatch_records"

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
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_object: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(255), nullable=False)
    responsible_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="На_Объекте", nullable=False
    )
    incident_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="fleet_dispatch_records")
    file: Mapped["UploadedFile | None"] = relationship("UploadedFile", back_populates="fleet_dispatch_records")

    __table_args__ = (
        Index(
            "idx_dispatch_company_shift",
            "company_id",
            "shift_date",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_dispatch_company_target",
            "company_id",
            "target_object",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
