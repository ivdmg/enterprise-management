import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.enums import UserRole


class TokenPayload(BaseModel):
    """Internal decoded JWT payload."""
    sub: str
    company_id: str
    role: str
    exp: int
    type: str


class TokensBlock(BaseModel):
    """Pair of access and refresh tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class CompanyBrief(BaseModel):
    """Brief company info for responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    inn: Optional[str] = None
    timezone: Optional[str] = None


class UserBrief(BaseModel):
    """Brief user info for auth responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    company_id: Optional[uuid.UUID] = None


class UserRegisterRequest(BaseModel):
    """Company registration request payload."""
    company_name: str = Field(..., min_length=2, max_length=255)
    inn: Optional[str] = Field(default=None, max_length=12)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=255)


class RegisterResponseData(BaseModel):
    """Response payload for successful registration."""
    user: UserBrief
    company: CompanyBrief
    tokens: TokensBlock


class UserLoginRequest(BaseModel):
    """User login credentials payload."""
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginResponseData(BaseModel):
    """Response payload for successful login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserBrief


class RefreshTokenRequest(BaseModel):
    """Refresh token request payload."""
    refresh_token: str = Field(..., min_length=10)


class RefreshTokenResponseData(BaseModel):
    """Response payload for token refresh."""
    access_token: str
    refresh_token: str
    expires_in: int = 3600


class UserProfileData(BaseModel):
    """Current authenticated user profile."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    telegram_connected: bool
    company: CompanyBrief


class TelegramLinkResponseData(BaseModel):
    """Telegram link code response payload."""
    link_code: str
    bot_url: str
    expires_in_seconds: int = 600


class CompanyUserItem(BaseModel):
    """Employee record in company users list."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    telegram_chat_id: Optional[int] = None
    created_at: datetime


class InviteUserRequest(BaseModel):
    """Payload to invite/create a new employee."""
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    role: UserRole = UserRole.VIEWER
    initial_password: str = Field(..., min_length=8)


class InviteUserResponseData(BaseModel):
    """Response payload for invited employee."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    created_at: datetime
