import uuid
from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.file import UploadedFile
    from app.models.alert import SystemAlert


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    User entity belonging to a single tenant company.
    """
    __tablename__ = "users"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", values_callable=lambda x: [e.value for e in x]),
        default=UserRole.VIEWER,
        nullable=False,
    )
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="users")
    uploaded_files: Mapped[List["UploadedFile"]] = relationship(
        "UploadedFile", back_populates="uploader"
    )
    resolved_alerts: Mapped[List["SystemAlert"]] = relationship(
        "SystemAlert", back_populates="resolver"
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("idx_users_company", "company_id"),
        Index(
            "idx_users_telegram",
            "telegram_chat_id",
            postgresql_where=(telegram_chat_id != None),  # noqa: E711
        ),
    )
