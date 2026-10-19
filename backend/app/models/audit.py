import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """
    Task BE-5.1: Immutable audit trail logging status transitions and system changes.
    Tracks:
    - entity_type: 'project', 'procurement', 'task', etc.
    - entity_id: UUID of the target entity
    - old_status -> new_status
    - timestamp: timezone-aware UTC datetime
    - user_id: UUID of acting user (if authenticated)
    - ip_address: client IP address
    - user_agent: client User-Agent string
    """
    __tablename__ = "audit_logs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    new_status: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company")
    user: Mapped["User | None"] = relationship("User")

    __table_args__ = (
        Index("idx_audit_logs_company_entity", "company_id", "entity_type", "entity_id"),
        Index("idx_audit_logs_timestamp", "company_id", "timestamp"),
    )
