import uuid
from datetime import timedelta
import jwt
import pytest
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def test_password_hashing():
    """Validates that password hashing generates secure bcrypt salt and verifies correctly."""
    plain = "SuperSecurePassword123!"
    hashed = get_password_hash(plain)

    assert hashed != plain
    assert hashed.startswith("$2")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_access_token_creation_and_payload():
    """Validates JWT access token generation and claims payload."""
    user_id = str(uuid.uuid4())
    company_id = str(uuid.uuid4())
    role = "admin"

    token = create_access_token(
        subject=user_id,
        company_id=company_id,
        role=role,
    )
    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload["sub"] == user_id
    assert payload["company_id"] == company_id
    assert payload["role"] == role
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_refresh_token_creation():
    """Validates JWT refresh token structure."""
    user_id = str(uuid.uuid4())
    company_id = str(uuid.uuid4())
    role = "manager"

    token = create_refresh_token(
        subject=user_id,
        company_id=company_id,
        role=role,
    )
    payload = decode_token(token)
    assert payload["sub"] == user_id
    assert payload["company_id"] == company_id
    assert payload["role"] == role
    assert payload["type"] == "refresh"


def test_jwt_expired_token_raises_error():
    """Validates that an expired JWT token raises ExpiredSignatureError."""
    user_id = str(uuid.uuid4())
    company_id = str(uuid.uuid4())

    expired_token = create_access_token(
        subject=user_id,
        company_id=company_id,
        role="viewer",
        expires_delta=timedelta(seconds=-10),  # expired in the past
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)


def test_schema_sql_seed_password_match():
    """Verifies that the default demo admin seed password matches its valid bcrypt hash."""
    seed_hash = "$2b$12$qoXPodGKJwrVMGHkGaMueuDvg2urLfEEdmSRa8q9gX1bQCLFLh/lC"
    assert verify_password("Admin123!", seed_hash) is True
