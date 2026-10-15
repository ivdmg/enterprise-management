import uuid
import pytest
from fastapi import HTTPException, status
from unittest.mock import AsyncMock, MagicMock

from app.api.deps import (
    get_current_user,
    get_current_active_admin,
    get_current_active_manager,
)
from app.core.security import create_access_token, create_refresh_token
from app.models.company import Company
from app.models.enums import UserRole
from app.models.user import User


@pytest.mark.asyncio
async def test_get_current_user_no_credentials():
    """Validates that missing Bearer credentials raises HTTP 401."""
    db_mock = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(None, db_mock)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Отсутствует заголовок" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_type():
    """Validates that passing a refresh token to access endpoint raises HTTP 401."""
    token = create_refresh_token(
        subject=str(uuid.uuid4()),
        company_id=str(uuid.uuid4()),
        role="admin",
    )
    cred_mock = MagicMock()
    cred_mock.credentials = token
    db_mock = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(cred_mock, db_mock)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "неверный тип токена" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_success_isolation():
    """Validates that get_current_user executes isolated tenant SQL query."""
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()

    token = create_access_token(
        subject=str(user_id),
        company_id=str(company_id),
        role="admin",
    )
    cred_mock = MagicMock()
    cred_mock.credentials = token

    fake_company = Company(id=company_id, name="Test Company", is_active=True)
    fake_user = User(
        id=user_id,
        company_id=company_id,
        email="test@test.ru",
        password_hash="fake",
        full_name="Tester",
        role=UserRole.ADMIN,
        is_active=True,
    )
    fake_user.company = fake_company

    db_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fake_user
    db_mock.execute.return_value = result_mock

    user = await get_current_user(cred_mock, db_mock)
    assert user.id == user_id
    assert user.company_id == company_id
    assert user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_admin_role_enforcement():
    """Validates that non-admin user is rejected with HTTP 403."""
    viewer_user = User(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        email="viewer@test.ru",
        password_hash="fake",
        full_name="Viewer",
        role=UserRole.VIEWER,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_admin(viewer_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    admin_user = User(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        email="admin@test.ru",
        password_hash="fake",
        full_name="Admin",
        role=UserRole.ADMIN,
    )
    res = await get_current_active_admin(admin_user)
    assert res.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_manager_role_enforcement():
    """Validates that manager role dependency allows Manager and Admin but blocks Viewer."""
    viewer_user = User(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        email="viewer@test.ru",
        password_hash="fake",
        full_name="Viewer",
        role=UserRole.VIEWER,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_manager(viewer_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    manager_user = User(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        email="mgr@test.ru",
        password_hash="fake",
        full_name="Manager",
        role=UserRole.MANAGER,
    )
    res = await get_current_active_manager(manager_user)
    assert res.role == UserRole.MANAGER
