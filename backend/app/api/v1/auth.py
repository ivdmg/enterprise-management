import secrets
from datetime import datetime, timezone
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.alert import IntegrationSetting
from app.models.company import Company
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import (
    CompanyBrief,
    LoginResponseData,
    RefreshTokenRequest,
    RefreshTokenResponseData,
    RegisterResponseData,
    TelegramLinkResponseData,
    TokensBlock,
    UserBrief,
    UserLoginRequest,
    UserProfileData,
    UserRegisterRequest,
)
from app.schemas.common import ResponseEnvelope

router = APIRouter(prefix="/auth", tags=["Authentication & Multi-tenancy"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseEnvelope[RegisterResponseData],
    summary="Регистрация новой компании и учетной записи первого администратора",
)
async def register_company_and_admin(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[RegisterResponseData]:
    """
    Registers a new tenant organization along with its initial root Administrator.
    Automatically provisions company entity, admin user, and integration settings.
    """
    # 1. Check if user email is already registered
    existing_user_query = select(User).where(User.email == payload.email)
    existing_user_res = await db.execute(existing_user_query)
    if existing_user_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с указанным e-mail адресом уже существует",
        )

    # 2. Create Company entity
    company = Company(
        name=payload.company_name.strip(),
        inn=payload.inn.strip() if payload.inn else None,
        timezone="Europe/Moscow",
        is_active=True,
    )
    db.add(company)
    await db.flush()  # Populates company.id

    # 3. Create Administrator User
    admin_user = User(
        company_id=company.id,
        email=payload.email.lower().strip(),
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name.strip(),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin_user)

    # 4. Create default integration settings
    integration = IntegrationSetting(
        company_id=company.id,
        telegram_bot_enabled=False,
        daily_digest_enabled=True,
        daily_digest_time="08:30",
    )
    db.add(integration)

    await db.commit()
    await db.refresh(admin_user)
    await db.refresh(company)

    # 5. Generate JWT tokens
    access_token = create_access_token(
        subject=str(admin_user.id),
        company_id=str(company.id),
        role=admin_user.role.value,
    )
    refresh_token = create_refresh_token(
        subject=str(admin_user.id),
        company_id=str(company.id),
        role=admin_user.role.value,
    )

    response_data = RegisterResponseData(
        user=UserBrief(
            id=admin_user.id,
            email=admin_user.email,
            full_name=admin_user.full_name,
            role=admin_user.role,
        ),
        company=CompanyBrief(
            id=company.id,
            name=company.name,
            inn=company.inn,
            timezone=company.timezone,
        ),
        tokens=TokensBlock(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )
    return ResponseEnvelope.ok(response_data)


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[LoginResponseData],
    summary="Аутентификация пользователя по e-mail и паролю",
)
async def login_user(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[LoginResponseData]:
    """
    Authenticates a user by email and password, verifies tenant active status,
    updates last_login_at timestamp, and issues signed JWT tokens.
    """
    query = (
        select(User)
        .options(joinedload(User.company))
        .where(User.email == payload.email.lower().strip())
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный e-mail или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Учетная запись пользователя деактивирована",
        )

    if not user.company or not user.company.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ организации временно заблокирован",
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )

    response_data = LoginResponseData(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserBrief(
            id=user.id,
            company_id=user.company_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
        ),
    )
    return ResponseEnvelope.ok(response_data)


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[RefreshTokenResponseData],
    summary="Ротация access-токена по валидному refresh-токену",
)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[RefreshTokenResponseData]:
    """
    Validates the refresh token cryptographic signature and expiration,
    verifies user existence and status, and issues a freshly signed token pair.
    """
    try:
        decoded = decode_token(payload.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия refresh-токена истек, требуется повторный вход",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный refresh-токен",
        )

    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Предоставлен неверный тип токена (ожидался refresh-токен)",
        )

    user_id_str = decoded.get("sub")
    company_id_str = decoded.get("company_id")
    if not user_id_str or not company_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректная структура payload в токене",
        )

    query = select(User).where(
        User.id == user_id_str,
        User.company_id == company_id_str,
        User.is_active.is_(True),
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или учетная запись отключена",
        )

    new_access_token = create_access_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )
    new_refresh_token = create_refresh_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )

    return ResponseEnvelope.ok(
        RefreshTokenResponseData(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    )


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[UserProfileData],
    summary="Получение профиля текущего авторизованного пользователя",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[UserProfileData]:
    """
    Returns profile details for the authenticated user and their organization.
    Protected strictly by JWT Authorization header.
    """
    response_data = UserProfileData(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        telegram_connected=bool(current_user.telegram_chat_id),
        company=CompanyBrief(
            id=current_user.company.id,
            name=current_user.company.name,
            inn=current_user.company.inn,
            timezone=current_user.company.timezone,
        ),
    )
    return ResponseEnvelope.ok(response_data)


@router.post(
    "/telegram-link",
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[TelegramLinkResponseData],
    summary="Генерация одноразового кода для подключения Telegram-бота",
)
async def generate_telegram_link(
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[TelegramLinkResponseData]:
    """
    Generates a secure short-lived linkage code and deep link for the Telegram bot.
    """
    code_suffix = secrets.randbelow(900000) + 100000  # 6-digit number
    link_code = f"TG-LINK-{code_suffix}"
    bot_username = "SmartEnterpriseHubBot"
    bot_url = f"https://t.me/{bot_username}?start=link_{code_suffix}"

    return ResponseEnvelope.ok(
        TelegramLinkResponseData(
            link_code=link_code,
            bot_url=bot_url,
            expires_in_seconds=600,
        )
    )
