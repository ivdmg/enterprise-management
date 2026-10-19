import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProcurementItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_name: str
    item_name: str
    quantity: Decimal
    unit: str
    supplier: Optional[str] = None
    invoice_amount: Decimal
    status: str
    delivery_deadline: Optional[date] = None
    invoice_number: Optional[str] = None
    created_at: datetime


class UpdateProcurementStatusRequest(BaseModel):
    status: str = Field(..., description="Target status: 'invoice_pending', 'paid', 'in_transit', 'delivered', 'Счет на оплате', 'Оплачено', 'В пути', 'На объекте'")


class UpdateProcurementStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    message: str = "Статус позиции снабжения успешно обновлен"


class DispatchRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shift_date: date
    target_object: str
    resource_type: str
    unit_name: str
    responsible_person: Optional[str] = None
    status: str
    incident_notes: Optional[str] = None
    downtime_hours: Optional[float] = None
    downtime_reason: Optional[str] = None
    created_at: datetime
