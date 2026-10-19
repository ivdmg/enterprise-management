import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import AlertSeverity, DomainCategory


class SystemAlertItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    severity: AlertSeverity
    domain_category: DomainCategory
    alert_type: str
    title: str
    description: str
    calculated_financial_impact: Decimal
    trigger_date: date
    is_resolved: bool
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    created_at: datetime


class ResolveAlertRequest(BaseModel):
    resolution_comment: str = Field(..., min_length=2, max_length=1000)


class ResolveAlertResponseData(BaseModel):
    id: uuid.UUID
    is_resolved: bool
    resolved_at: datetime
    resolved_by: str


class TelegramIntegrationSettingsData(BaseModel):
    telegram_bot_enabled: bool
    bot_username: str = "SmartEnterpriseHubBot"
    group_channel_connected: bool
    daily_digest_enabled: bool
    daily_digest_time: str
    alert_rules: Dict[str, Any]


class UpdateTelegramSettingsRequest(BaseModel):
    daily_digest_enabled: Optional[bool] = None
    daily_digest_time: Optional[str] = None
    telegram_bot_enabled: Optional[bool] = None
    telegram_bot_token: Optional[str] = None
    telegram_channel_id: Optional[int] = None
    alert_rules: Optional[Dict[str, Any]] = None


class KeyRateSettingsResponse(BaseModel):
    key_rate_percent: float = Field(..., description="Annualized Central Bank key rate (in percent, e.g. 19.0)")
    daily_penalty_fraction: str = Field("1/300", description="Statutory daily fraction per 44-FZ")
    daily_rate_percent: float = Field(..., description="Daily penalty rate in percent")


class UpdateKeyRateRequest(BaseModel):
    key_rate_percent: float = Field(..., ge=0.0, le=100.0, description="New Central Bank key rate percent, e.g. 19.0 or 21.0")
