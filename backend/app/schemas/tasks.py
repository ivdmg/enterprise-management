import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import TaskPriority, TaskStatus


class TaskItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_title: str
    description: Optional[str] = None
    related_contract: Optional[str] = None
    project_id: Optional[str] = None
    responsible_role: str = "manager"
    responsible_person: str = "Не назначен"
    due_date: Optional[str] = None
    days_remaining: Optional[int] = None
    days_overdue: Optional[int] = None
    is_urgent: bool = False
    source: Optional[str] = "manual"
    source_label: Optional[str] = "Операционный реестр"
    status: str
    priority: str
    estimated_penalty_amount: Optional[Decimal] = Decimal("0.00")
    penalty_amount: Optional[Decimal] = Decimal("0.00")
    risk_amount: Optional[Decimal] = Decimal("0.00")
    document_name: Optional[str] = None
    google_drive_link: Optional[str] = None
    file_id: Optional[str] = None
    created_at: Optional[datetime] = None


class UpdateTaskStatusRequest(BaseModel):
    status: str = Field(..., description="Новый статус задачи: pending, in_progress, completed, approved_closed")


class UpdateTaskStatusResponse(BaseModel):
    id: str
    status: str
    message: Optional[str] = None
