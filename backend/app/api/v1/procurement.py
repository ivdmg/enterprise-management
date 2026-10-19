import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.procurement import ProcurementItem
from app.models.user import User
from app.schemas.common import MetaModel, ResponseEnvelope
from app.schemas.procurement import (
    ProcurementItemResponse,
    UpdateProcurementStatusRequest,
    UpdateProcurementStatusResponse,
)
from app.services.audit import record_audit_log

router = APIRouter(prefix="/procurement", tags=["Procurement & Materials Supply"])


@router.get(
    "/items",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[List[ProcurementItemResponse]],
    summary="Реестр позиций снабжения и счетов ТМЦ (FE-5.2)",
)
async def list_procurement_items(
    project_name: Optional[str] = Query(None, description="Фильтрация по наименованию объекта"),
    status_filter: Optional[str] = Query(None, alias="status", description="Фильтрация по статусу поставки"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[List[ProcurementItemResponse]]:
    """
    Returns procurement items for tenant company with optional filters by project and status.
    """
    base_q = select(ProcurementItem).where(
        ProcurementItem.company_id == current_user.company_id,
        ProcurementItem.deleted_at.is_(None),
    )

    if project_name and project_name != "all":
        base_q = base_q.where(func.lower(ProcurementItem.project_name) == project_name.lower().strip())

    if status_filter:
        s_norm = status_filter.lower().strip()
        # Handle English frontend statuses and Russian database statuses
        status_map = {
            "invoice_pending": ["счет на оплате", "заявка", "согласование", "invoice_pending"],
            "paid": ["оплачено", "paid"],
            "in_transit": ["в пути", "in_transit"],
            "delivered": ["на объекте", "на складе", "доставлено", "delivered"],
        }
        allowed = status_map.get(s_norm, [s_norm])
        base_q = base_q.where(func.lower(ProcurementItem.status).in_(allowed))

    # Count
    total_q = select(func.count()).select_from(base_q.subquery())
    total_items = (await db.execute(total_q)).scalar_one()

    # Query items
    query = (
        base_q.order_by(
            ProcurementItem.delivery_deadline.asc().nulls_last(),
            ProcurementItem.created_at.desc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
    )
    res = await db.execute(query)
    items = res.scalars().all()

    response_items = [
        ProcurementItemResponse(
            id=item.id,
            project_name=item.project_name,
            item_name=item.item_name,
            quantity=item.quantity,
            unit=item.unit,
            supplier=item.supplier,
            invoice_amount=item.invoice_amount,
            status=item.status,
            delivery_deadline=item.delivery_deadline,
            invoice_number=getattr(item, "invoice_number", None),
            created_at=item.created_at,
        )
        for item in items
    ]

    total_pages = (total_items + limit - 1) // limit if limit else 1
    meta = MetaModel(page=page, limit=limit, total_items=total_items, total_pages=total_pages)
    return ResponseEnvelope.ok(response_items, meta=meta)


@router.patch(
    "/items/{item_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[UpdateProcurementStatusResponse],
    summary="Обновление статуса позиции снабжения в 1 клик",
)
async def update_procurement_status(
    item_id: uuid.UUID,
    payload: UpdateProcurementStatusRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[UpdateProcurementStatusResponse]:
    """
    Updates the delivery/procurement status of a supply item.
    BE-5.1: Logs transition in audit_logs.
    """
    q = select(ProcurementItem).where(
        ProcurementItem.id == item_id,
        ProcurementItem.company_id == current_user.company_id,
        ProcurementItem.deleted_at.is_(None),
    )
    res = await db.execute(q)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позиция снабжения не найдена",
        )

    old_status = item.status
    item.status = payload.status

    # Record Audit Log (BE-5.1)
    await record_audit_log(
        db=db,
        company_id=current_user.company_id,
        entity_type="procurement",
        entity_id=item.id,
        old_status=old_status,
        new_status=payload.status,
        user_id=current_user.id,
        request=request,
    )

    await db.commit()

    return ResponseEnvelope.ok(
        UpdateProcurementStatusResponse(
            id=item.id,
            status=item.status,
            message="Статус позиции снабжения успешно обновлен",
        )
    )
