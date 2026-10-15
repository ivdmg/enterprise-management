import uuid
from typing import Annotated
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import decode_token
from app.models.enums import UserRole
from app.models.user import User

# HTTP Bearer scheme with automatic parsing of "Authorization: Bearer <token>"
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Core multi-tenancy dependency.
    Extracts the authenticated user strictly from validated JWT claims.
    Tenant isolation guarantee: company_id is bound directly to the database query
    preventing any cross-tenant data leaks.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Отсутствует заголовок авторизации Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия токена доступа истек",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен авторизации",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token type
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Предоставлен неверный тип токена (ожидался access-токен)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    company_id_str = payload.get("company_id")
    if not user_id_str or not company_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректная структура payload в токене",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
        company_uuid = uuid.UUID(company_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный формат UUID в токене",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Tenant-isolated database query
    query = (
        select(User)
        .options(joinedload(User.company))
        .where(
            User.id == user_uuid,
            User.company_id == company_uuid,
            User.is_active.is_(True),
        )
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или учетная запись отключена",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.company or not user.company.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ заблокирован: компания деактивирована",
        )

    return user


async def get_current_active_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency enforcing Administrator role within the tenant.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Операция доступна только администратору организации",
        )
    return current_user


async def get_current_active_manager(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency enforcing Manager or Administrator role within the tenant.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Операция доступна только менеджеру или администратору организации",
        )
    return current_user
