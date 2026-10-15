from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.file import UploadedFile, FileTemplate
    from app.models.project import TenderProject
    from app.models.finance import CashflowOperation
    from app.models.payroll import PayrollRecord
    from app.models.task import OperationalTask
    from app.models.procurement import ProcurementItem
    from app.models.dispatch import FleetDispatchRecord
    from app.models.alert import SystemAlert, IntegrationSetting


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Anchor multi-tenant company entity isolating all client data.
    """
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(9), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships with CASCADE delete
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="company", cascade="all, delete-orphan"
    )
    uploaded_files: Mapped[List["UploadedFile"]] = relationship(
        "UploadedFile", back_populates="company", cascade="all, delete-orphan"
    )
    file_templates: Mapped[List["FileTemplate"]] = relationship(
        "FileTemplate", back_populates="company", cascade="all, delete-orphan"
    )
    tender_projects: Mapped[List["TenderProject"]] = relationship(
        "TenderProject", back_populates="company", cascade="all, delete-orphan"
    )
    cashflow_operations: Mapped[List["CashflowOperation"]] = relationship(
        "CashflowOperation", back_populates="company", cascade="all, delete-orphan"
    )
    payroll_records: Mapped[List["PayrollRecord"]] = relationship(
        "PayrollRecord", back_populates="company", cascade="all, delete-orphan"
    )
    procurement_items: Mapped[List["ProcurementItem"]] = relationship(
        "ProcurementItem", back_populates="company", cascade="all, delete-orphan"
    )
    fleet_dispatch_records: Mapped[List["FleetDispatchRecord"]] = relationship(
        "FleetDispatchRecord", back_populates="company", cascade="all, delete-orphan"
    )
    operational_tasks: Mapped[List["OperationalTask"]] = relationship(
        "OperationalTask", back_populates="company", cascade="all, delete-orphan"
    )
    system_alerts: Mapped[List["SystemAlert"]] = relationship(
        "SystemAlert", back_populates="company", cascade="all, delete-orphan"
    )
    integration_settings: Mapped["IntegrationSetting | None"] = relationship(
        "IntegrationSetting", back_populates="company", uselist=False, cascade="all, delete-orphan"
    )
