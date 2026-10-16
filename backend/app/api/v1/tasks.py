import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alert import SystemAlert
from app.models.enums import TaskPriority, TaskStatus
from app.models.file import UploadedFile
from app.models.task import OperationalTask
from app.models.user import User
from app.schemas.common import MetaModel, ResponseEnvelope
from app.schemas.tasks import (
    TaskItemResponse,
    UpdateTaskStatusRequest,
    UpdateTaskStatusResponse,
)

router = APIRouter(prefix="/tasks", tags=["Operational Tasks & Smart Register"])


def map_task_to_response(task: OperationalTask, today: datetime.date) -> TaskItemResponse:
    days_rem = None
    days_overdue = None
    is_urgent = task.priority in (TaskPriority.URGENT, TaskPriority.HIGH)

    if task.due_date:
        diff = (task.due_date - today).days
        if diff < 0:
            days_overdue = abs(diff)
            days_rem = 0
            is_urgent = True
        else:
            days_overdue = 0
            days_rem = diff
            if diff <= 5:
                is_urgent = True

    p1 = getattr(task, "estimated_penalty_amount", None) or Decimal("0.00")
    p2 = getattr(task, "penalty_amount", None) or Decimal("0.00")
    risk_amount = max(p1, p2)

    source = "accounting" if task.file_id else "manual"
    source_label = "Бухгалтерия (1С)" if task.file_id else "Операционный реестр"
    doc_name = task.file.original_name if getattr(task, "file", None) else None

    return TaskItemResponse(
        id=str(task.id),
        task_title=task.task_title,
        description=task.description,
        related_contract=task.related_contract,
        responsible_role=task.responsible_role or "manager",
        responsible_person=task.responsible_person or "Не назначен",
        due_date=task.due_date.isoformat() if task.due_date else None,
        days_remaining=days_rem,
        days_overdue=days_overdue,
        is_urgent=is_urgent,
        source=source,
        source_label=source_label,
        status=task.status.value,
        priority=task.priority.value,
        estimated_penalty_amount=p1,
        penalty_amount=p2,
        risk_amount=risk_amount,
        document_name=doc_name,
        google_drive_link=task.google_drive_link,
        file_id=str(task.file_id) if task.file_id else None,
        created_at=task.created_at,
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[List[TaskItemResponse]],
    summary="Реестр операционных задач с фильтрацией по ролям и срочности (BE-5.2)",
)
async def list_operational_tasks(
    role: Optional[str] = Query(None, description="Фильтрация по роли исполнителя"),
    status_filter: Optional[str] = Query(None, alias="status", description="Фильтрация по статусу исполнения"),
    urgent: Optional[bool] = Query(None, description="Фильтрация срочных задач (дедлайн <= 5 дней)"),
    urgent_only: Optional[bool] = Query(None, description="Алиас для urgent"),
    source: Optional[str] = Query(None, description="Источник: accounting | legal | pto | manual"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[List[TaskItemResponse]]:
    """
    BE-5.2: Returns filtered operational tasks for current company tenant:
    - Filters by role (manager, accountant, etc.)
    - Filters by status (pending, in_progress, completed, overdue)
    - Filters urgent tasks (due_date <= 5 days or urgent priority)
    - Includes risk penalty amount and google_drive_link.
    """
    today = datetime.now(timezone.utc).date()
    is_urgent_filter = urgent if urgent is not None else urgent_only

    base_q = (
        select(OperationalTask)
        .options(selectinload(OperationalTask.file))
        .where(
            OperationalTask.company_id == current_user.company_id,
            OperationalTask.deleted_at.is_(None),
        )
    )

    if role and role.lower() != "all":
        base_q = base_q.where(func.lower(OperationalTask.responsible_role) == role.lower().strip())

    if status_filter:
        s_norm = status_filter.lower().strip()
        if s_norm in ("completed", "approved_closed"):
            base_q = base_q.where(OperationalTask.status == TaskStatus.COMPLETED)
        elif s_norm in ("pending", "transferred_to_manager"):
            base_q = base_q.where(OperationalTask.status == TaskStatus.PENDING)
        elif s_norm == "in_progress":
            base_q = base_q.where(OperationalTask.status == TaskStatus.IN_PROGRESS)
        elif s_norm == "overdue":
            base_q = base_q.where(OperationalTask.status == TaskStatus.OVERDUE)

    if source:
        if source == "accounting":
            base_q = base_q.where(OperationalTask.file_id.is_not(None))
        elif source == "manual":
            base_q = base_q.where(OperationalTask.file_id.is_(None))

    if is_urgent_filter:
        # 5-day rule or URGENT priority
        base_q = base_q.where(
            or_(
                OperationalTask.priority.in_([TaskPriority.URGENT, TaskPriority.HIGH]),
                OperationalTask.due_date <= today + timedelta(days=5),
            )
        )

    # Count
    total_q = select(func.count()).select_from(base_q.subquery())
    total_items = (await db.execute(total_q)).scalar_one()

    # Query items ordered by due date ascending, then creation date descending
    query = (
        base_q.order_by(
            OperationalTask.due_date.asc().nulls_last(),
            OperationalTask.created_at.desc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
    )
    res = await db.execute(query)
    tasks = res.scalars().all()

    items = [map_task_to_response(t, today) for t in tasks]
    total_pages = (total_items + limit - 1) // limit if limit else 1
    meta = MetaModel(
        page=page,
        limit=limit,
        total_items=total_items,
        total_pages=total_pages,
    )
    return ResponseEnvelope.ok(items, meta=meta)


@router.patch(
    "/{task_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[UpdateTaskStatusResponse],
    summary="Быстрая смена статуса операционной задачи в 1 клик (BE-5.3)",
)
async def update_task_status(
    task_id: uuid.UUID,
    payload: UpdateTaskStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[UpdateTaskStatusResponse]:
    """
    BE-5.3: 1-click status update by project manager:
    Accepts: 'pending' | 'in_progress' | 'completed' | 'approved_closed' | 'transferred_to_manager'.
    If status transitions to completed/approved_closed, automatically resolves linked system alerts.
    """
    query = select(OperationalTask).where(
        OperationalTask.id == task_id,
        OperationalTask.company_id == current_user.company_id,
        OperationalTask.deleted_at.is_(None),
    )
    res = await db.execute(query)
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена в вашей организации",
        )

    norm_status = payload.status.lower().strip()
    if norm_status in ("completed", "approved_closed"):
        target_status = TaskStatus.COMPLETED
    elif norm_status in ("in_progress",):
        target_status = TaskStatus.IN_PROGRESS
    elif norm_status in ("pending", "transferred_to_manager"):
        target_status = TaskStatus.PENDING
    elif norm_status in ("overdue",):
        target_status = TaskStatus.OVERDUE
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый статус: '{payload.status}'. Допустимы: pending, in_progress, completed, approved_closed",
        )

    task.status = target_status

    # If completed, resolve any active alerts linked to this task
    if target_status == TaskStatus.COMPLETED:
        alert_q = select(SystemAlert).where(
            SystemAlert.company_id == current_user.company_id,
            SystemAlert.entity_id == task.id,
            SystemAlert.is_resolved.is_(False),
        )
        alerts = (await db.execute(alert_q)).scalars().all()
        now_dt = datetime.now(timezone.utc)
        for a in alerts:
            a.is_resolved = True
            a.resolved_at = now_dt
            a.resolved_by_user_id = current_user.id
            a.resolution_comment = f"Задача '{task.task_title}' согласована и закрыта пользователем {current_user.full_name}"

    await db.commit()

    return ResponseEnvelope.ok(
        UpdateTaskStatusResponse(
            id=str(task.id),
            status=task.status.value,
            message="Статус задачи успешно обновлен",
        )
    )
