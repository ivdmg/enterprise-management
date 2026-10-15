from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_admin
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import (
    CompanyUserItem,
    InviteUserRequest,
    InviteUserResponseData,
)
from app.schemas.common import ResponseEnvelope

router = APIRouter(prefix="/company", tags=["Company Management & Team"])


@router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[List[CompanyUserItem]],
    summary="Получение списка всех сотрудников текущей компании (только Admin)",
)
async def list_company_users(
    current_admin: User = Depends(get_current_active_admin),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[List[CompanyUserItem]]:
    """
    Returns the list of all active/inactive team members belonging strictly
    to the administrator's company. Enforces multi-tenant isolation.
    """
    query = (
        select(User)
        .where(User.company_id == current_admin.company_id)
        .order_by(User.created_at.asc())
    )
    result = await db.execute(query)
    users = result.scalars().all()

    items = [
        CompanyUserItem(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            telegram_chat_id=u.telegram_chat_id,
            created_at=u.created_at,
        )
        for u in users
    ]
    return ResponseEnvelope.ok(items)


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseEnvelope[InviteUserResponseData],
    summary="Добавление нового сотрудника в организацию (только Admin)",
)
async def invite_company_user(
    payload: InviteUserRequest,
    current_admin: User = Depends(get_current_active_admin),
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[InviteUserResponseData]:
    """
    Creates a new user account tied strictly to the administrator's company.
    """
    # Check if email is globally unique
    existing_query = select(User).where(User.email == payload.email.lower().strip())
    existing_res = await db.execute(existing_query)
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с указанным e-mail уже зарегистрирован в системе",
        )

    # Enforce safe role assignment (cannot create admins via this endpoint if desired, or allow)
    target_role = payload.role if payload.role in (UserRole.MANAGER, UserRole.VIEWER) else UserRole.VIEWER

    new_user = User(
        company_id=current_admin.company_id,
        email=payload.email.lower().strip(),
        password_hash=get_password_hash(payload.initial_password),
        full_name=payload.full_name.strip(),
        role=target_role,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    response_data = InviteUserResponseData(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        created_at=new_user.created_at,
    )
    return ResponseEnvelope.ok(response_data)
