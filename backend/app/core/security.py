import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
import jwt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against the stored bcrypt hash.
    Direct bcrypt implementation avoids legacy passlib bugs with bcrypt>=4.1.
    """
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Hashes a plain password using bcrypt with cost factor 12 (OWASP compliant).
    """
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(
    subject: str,
    company_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates a signed JWT access token containing subject, company_id, and role.
    Strictly valid for at most settings.ACCESS_TOKEN_EXPIRE_MINUTES (default: 60 mins).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "company_id": str(company_id),
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    encoded_jwt = jwt.encode(
        payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    subject: str,
    company_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates a signed JWT refresh token valid for settings.REFRESH_TOKEN_EXPIRE_DAYS (default: 14 days).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "company_id": str(company_id),
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh",
    }
    encoded_jwt = jwt.encode(
        payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token. Raises jwt.PyJWTError if invalid or expired.
    """
    return jwt.decode(
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )
