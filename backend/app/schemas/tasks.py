import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
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


class CreateTaskRequest(BaseModel):
    task_title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    related_contract: Optional[str] = Field(None, max_length=255)
    responsible_person: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    responsible_role: Optional[str] = Field(None, max_length=100)
    due_date: date
    estimated_penalty_amount: Decimal = Field(Decimal("0.00"), ge=0, max_digits=15, decimal_places=2)


class UpdateTaskStatusResponse(BaseModel):
    id: str
    status: str
    message: Optional[str] = None
