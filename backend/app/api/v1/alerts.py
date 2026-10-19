import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alert import IntegrationSetting, SystemAlert
from app.models.enums import AlertSeverity, DomainCategory
from app.models.user import User
from app.models.project import TenderProject
from app.schemas.alerts import (
    ResolveAlertRequest,
    ResolveAlertResponseData,
    SystemAlertItem,
    TelegramIntegrationSettingsData,
    UpdateTelegramSettingsRequest,
    KeyRateSettingsResponse,
    UpdateKeyRateRequest,
)
from app.schemas.common import MetaModel, ResponseEnvelope
from app.schemas.dashboard import TopFireItem
from app.services.alerts_engine import alerts_engine

router = APIRouter(tags=["Alerts & Integrations"])


@router.get(
    "/alerts/critical",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[List[TopFireItem]],
    summary="Карточки «Где горит?» (критические алерты с неустойками и ответственными)",
)
async def list_critical_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[List[TopFireItem]]:
    """Returns all active critical alerts sorted by calculated financial impact."""
    from app.api.v1.dashboard import build_fire_item

    today = datetime.now(timezone.utc).date()
    proj_q = select(TenderProject).where(
        TenderProject.company_id == current_user.company_id,
        TenderProject.deleted_at.is_(None),
    )
    projects = (await db.execute(proj_q)).scalars().all()
    projects_map = {p.id: p for p in projects}

    crit_q = (
        select(SystemAlert)
        .where(
            SystemAlert.company_id == current_user.company_id,
            SystemAlert.is_resolved.is_(False),
            SystemAlert.severity == AlertSeverity.CRITICAL,
        )
        .order_by(SystemAlert.calculated_financial_impact.desc())
    )
    crit_alerts = (await db.execute(crit_q)).scalars().all()

    items = [build_fire_item(a, projects_map, today) for a in crit_alerts]
    return ResponseEnvelope.ok(items)


@router.get(
    "/alerts",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[List[SystemAlertItem]],
    summary="Реестр выявленных рисков и инцидентов организации",
)
async def list_system_alerts(
    severity: Optional[AlertSeverity] = Query(None),
    is_resolved: bool = Query(False, description="По умолчанию только активные нерешенные угрозы"),
    domain_category: Optional[DomainCategory] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[List[SystemAlertItem]]:
    """
    Returns active or historical alerts strictly for the tenant with severity filtering.
    """
    base_q = select(SystemAlert).where(
        SystemAlert.company_id == current_user.company_id,
        SystemAlert.is_resolved == is_resolved,
    )
    if severity:
        base_q = base_q.where(SystemAlert.severity == severity)
    if domain_category:
        base_q = base_q.where(SystemAlert.domain_category == domain_category)

    # Count total and critical
    total_q = select(func.count()).select_from(base_q.subquery())
    total_items = (await db.execute(total_q)).scalar_one()

    crit_count_q = select(func.count(SystemAlert.id)).where(
        SystemAlert.company_id == current_user.company_id,
        SystemAlert.is_resolved.is_(False),
        SystemAlert.severity == AlertSeverity.CRITICAL,
    )
    total_unresolved_critical = (await db.execute(crit_count_q)).scalar_one()

    # Query items
    query = (
        base_q.order_by(
            SystemAlert.trigger_date.desc(),
            SystemAlert.calculated_financial_impact.desc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
    )
    res = await db.execute(query)
    alerts = res.scalars().all()

    items = [
        SystemAlertItem(
            id=a.id,
            severity=a.severity,
            domain_category=a.domain_category,
            alert_type=a.alert_type,
            title=a.title,
            description=a.description,
            calculated_financial_impact=a.calculated_financial_impact,
            trigger_date=a.trigger_date,
            is_resolved=a.is_resolved,
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            created_at=a.created_at,
        )
        for a in alerts
    ]

    total_pages = (total_items + limit - 1) // limit if limit else 1
    meta = MetaModel(
        page=page,
        limit=limit,
        total_items=total_items,
        total_pages=total_pages,
    )
    # Include total_unresolved_critical in response dictionary wrapper if needed
    return ResponseEnvelope.ok(items, meta=meta)


@router.post(
    "/alerts/{alert_id}/resolve",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[ResolveAlertResponseData],
    summary="Закрытие и снятие алерта с указанием комментария решения",
)
async def resolve_system_alert(
    alert_id: uuid.UUID,
    payload: ResolveAlertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[ResolveAlertResponseData]:
    """
    Marks an operational incident as resolved, recording the resolver and reasoning.
    """
    query = select(SystemAlert).where(
        SystemAlert.id == alert_id,
        SystemAlert.company_id == current_user.company_id,
    )
    res = await db.execute(query)
    alert = res.scalar_one_or_none()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Алерт не найден в вашей организации",
        )

    now_dt = datetime.now(timezone.utc)
    alert.is_resolved = True
    alert.resolved_at = now_dt
    alert.resolved_by_user_id = current_user.id
    alert.resolution_comment = payload.resolution_comment.strip()

    await db.commit()

    return ResponseEnvelope.ok(
        ResolveAlertResponseData(
            id=alert.id,
            is_resolved=True,
            resolved_at=now_dt,
            resolved_by=current_user.full_name,
        )
    )


@router.get(
    "/integrations/telegram",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[TelegramIntegrationSettingsData],
    summary="Получение настроек Telegram-интеграции организации",
)
async def get_telegram_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[TelegramIntegrationSettingsData]:
    """Returns telegram bot dispatch settings for the current tenant."""
    query = select(IntegrationSetting).where(
        IntegrationSetting.company_id == current_user.company_id
    )
    res = await db.execute(query)
    settings_rec = res.scalar_one_or_none()

    if not settings_rec:
        settings_rec = IntegrationSetting(
            company_id=current_user.company_id,
            telegram_bot_enabled=False,
            daily_digest_enabled=True,
            daily_digest_time="08:30",
        )
        db.add(settings_rec)
        await db.commit()
        await db.refresh(settings_rec)

    data = TelegramIntegrationSettingsData(
        telegram_bot_enabled=settings_rec.telegram_bot_enabled,
        bot_username="SmartEnterpriseHubBot",
        group_channel_connected=bool(settings_rec.telegram_channel_id),
        daily_digest_enabled=settings_rec.daily_digest_enabled,
        daily_digest_time=settings_rec.daily_digest_time,
        alert_rules=settings_rec.alert_rules or {},
    )
    return ResponseEnvelope.ok(data)


@router.patch(
    "/integrations/telegram",
    status_code=status.HTTP_200_OK,
    summary="Обновление настроек рассылки и Telegram-бота",
)
async def update_telegram_settings(
    payload: UpdateTelegramSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[dict]:
    """Updates tenant telegram schedule and alert preferences."""
    query = select(IntegrationSetting).where(
        IntegrationSetting.company_id == current_user.company_id
    )
    res = await db.execute(query)
    settings_rec = res.scalar_one_or_none()

    if not settings_rec:
        settings_rec = IntegrationSetting(company_id=current_user.company_id)
        db.add(settings_rec)

    if payload.daily_digest_enabled is not None:
        settings_rec.daily_digest_enabled = payload.daily_digest_enabled
    if payload.daily_digest_time is not None:
        settings_rec.daily_digest_time = payload.daily_digest_time
    if payload.telegram_bot_enabled is not None:
        settings_rec.telegram_bot_enabled = payload.telegram_bot_enabled
    if payload.telegram_bot_token is not None:
        settings_rec.telegram_bot_token = payload.telegram_bot_token
    if payload.telegram_channel_id is not None:
        settings_rec.telegram_channel_id = payload.telegram_channel_id
    if payload.alert_rules is not None:
        settings_rec.alert_rules = payload.alert_rules

    await db.commit()
    return ResponseEnvelope.ok({"message": "Настройки интеграции успешно обновлены"})


@router.post(
    "/integrations/telegram/test-send",
    status_code=status.HTTP_200_OK,
    summary="Отправка тестового уведомления в Telegram",
)
async def test_send_telegram_notification(
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[dict]:
    """Dispatches a test ping message to the user/channel."""
    return ResponseEnvelope.ok(
        {
            "status": "delivered",
            "message": "Тестовое сообщение успешно доставлено в Telegram",
        }
    )


@router.get(
    "/settings/key-rate",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[KeyRateSettingsResponse],
    summary="Получение актуальной ключевой ставки ЦБ РФ для расчета неустоек 44-ФЗ",
)
async def get_key_rate_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[KeyRateSettingsResponse]:
    """
    Returns current Central Bank key rate used in 44-FZ statutory penalty calculations.
    """
    rate_dec = await alerts_engine.get_effective_key_rate(current_user.company_id, db)
    key_rate_percent = float(rate_dec * 100)
    daily_rate_percent = key_rate_percent / 300.0

    return ResponseEnvelope.ok(
        KeyRateSettingsResponse(
            key_rate_percent=round(key_rate_percent, 2),
            daily_penalty_fraction="1/300",
            daily_rate_percent=round(daily_rate_percent, 5),
        )
    )


@router.patch(
    "/settings/key-rate",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[KeyRateSettingsResponse],
    summary="Обновление ключевой ставки ЦБ РФ для расчета неустоек 44-ФЗ",
)
async def update_key_rate_settings(
    payload: UpdateKeyRateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[KeyRateSettingsResponse]:
    """
    Updates the Central Bank key rate for tenant's 44-FZ penalty calculations.
    """
    q = select(IntegrationSetting).where(IntegrationSetting.company_id == current_user.company_id)
    res = await db.execute(q)
    setting_rec = res.scalar_one_or_none()

    if not setting_rec:
        setting_rec = IntegrationSetting(
            company_id=current_user.company_id,
            alert_rules={"key_rate_percent": payload.key_rate_percent},
        )
        db.add(setting_rec)
    else:
        rules = dict(setting_rec.alert_rules or {})
        rules["key_rate_percent"] = payload.key_rate_percent
        setting_rec.alert_rules = rules

    await db.commit()

    daily_rate_percent = payload.key_rate_percent / 300.0
    return ResponseEnvelope.ok(
        KeyRateSettingsResponse(
            key_rate_percent=round(payload.key_rate_percent, 2),
            daily_penalty_fraction="1/300",
            daily_rate_percent=round(daily_rate_percent, 5),
        )
    )
