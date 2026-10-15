import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, TYPE_CHECKING
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import FileStatus, DomainCategory

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User
    from app.models.project import TenderProject
    from app.models.finance import CashflowOperation
    from app.models.payroll import PayrollRecord
    from app.models.task import OperationalTask


class UploadedFile(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Registry of uploaded Excel documents with SHA-256 deduplication and status tracking.
    """
    __tablename__ = "uploaded_files"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus, name="file_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=FileStatus.UPLOADED,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="uploaded_files")
    uploader: Mapped["User | None"] = relationship("User", back_populates="uploaded_files")
    parsing_jobs: Mapped[List["ParsingJob"]] = relationship(
        "ParsingJob", back_populates="file", cascade="all, delete-orphan"
    )
    tender_projects: Mapped[List["TenderProject"]] = relationship(
        "TenderProject", back_populates="file"
    )
    cashflow_operations: Mapped[List["CashflowOperation"]] = relationship(
        "CashflowOperation", back_populates="file"
    )
    payroll_records: Mapped[List["PayrollRecord"]] = relationship(
        "PayrollRecord", back_populates="file"
    )
    operational_tasks: Mapped[List["OperationalTask"]] = relationship(
        "OperationalTask", back_populates="file"
    )

    __table_args__ = (
        Index("idx_uploaded_files_company_hash", "company_id", "sha256_hash"),
        Index("idx_uploaded_files_status", "company_id", "status"),
    )


class FileTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Template column mapping cache (Fingerprint Cache) for 0-call instant parsing.
    """
    __tablename__ = "file_templates"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), default="Sheet1", nullable=False)
    headers_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_category: Mapped[DomainCategory] = mapped_column(
        Enum(DomainCategory, name="domain_category_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    column_mapping: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("1.00"), nullable=False
    )
    match_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="file_templates")

    __table_args__ = (
        UniqueConstraint("company_id", "headers_fingerprint", name="uq_company_fingerprint"),
        Index("idx_templates_lookup", "company_id", "headers_fingerprint"),
        Index("idx_templates_mapping_gin", "column_mapping", postgresql_using="gin"),
    )


class ParsingJob(Base, UUIDPrimaryKeyMixin):
    """
    Audit log of parsing pipeline executions.
    """
    __tablename__ = "parsing_jobs"

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="in_progress", nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    ai_model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extracted_rows_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detected_headers: Mapped[Dict[str, Any] | List[Any] | None] = mapped_column(JSONB, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    file: Mapped["UploadedFile"] = relationship("UploadedFile", back_populates="parsing_jobs")

    __table_args__ = (
        Index("idx_parsing_jobs_file", "file_id"),
    )
