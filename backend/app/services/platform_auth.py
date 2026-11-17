import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha1, sha256
import hmac
import json
import secrets
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.database import set_tenant_context
from app.models.user import User

DUMMY_HASH = "$2b$12$5hnRX.8mIHXC32dm.PqIaOm2/VnXI5UyFcEz02VxtxkfZH6mls4uC"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def auth_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message})


def now() -> datetime:
    return datetime.now(timezone.utc)


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def domain(purpose: str, platform: bool) -> str:
    return f"platform_{purpose}" if platform else f"client_{purpose}"


def cookie_name(purpose: str, platform: bool) -> str:
    return "__Host-seh-" + domain(purpose, platform)


def set_cookie(response: Response, purpose: str, platform: bool, value: str, max_age: int) -> None:
    response.set_cookie(cookie_name(purpose, platform), value, secure=True, httponly=True,
                        samesite="strict", path="/", max_age=max_age)
    response.headers["Cache-Control"] = "no-store"


def clear_cookie(response: Response, purpose: str, platform: bool) -> None:
    response.delete_cookie(cookie_name(purpose, platform), path="/", secure=True, httponly=True, samesite="strict")


def origin(request: Request, platform: bool) -> str:
    expected = settings.PLATFORM_AUTH_ORIGIN if platform else settings.CLIENT_AUTH_ORIGIN
    if str(request.base_url).rstrip("/") != expected:
        raise auth_error(403, "FORBIDDEN", "Этот кабинет недоступен по текущему адресу")
    return expected


def csrf_value(platform: bool, binding: str) -> str:
    return hmac.new(settings.JWT_SECRET.encode(), domain(binding, platform).encode(), sha256).hexdigest()


def validate_csrf(request: Request, platform: bool, anonymous: bool = False) -> None:
    expected_origin = origin(request, platform)
    session = request.cookies.get(cookie_name("session", platform))
    binding = session or (request.cookies.get(cookie_name("csrf", platform)) if anonymous else None)
    supplied = request.headers.get("X-CSRF-Token", "")
    if (request.headers.get("Origin") != expected_origin or not binding or not supplied.isascii()
            or not hmac.compare_digest(csrf_value(platform, binding), supplied)):
        raise auth_error(403, "CSRF_FAILED", "Запрос не прошёл проверку безопасности")


def challenge_binding(request: Request, platform: bool) -> str:
    cookie = request.cookies.get(cookie_name("session", platform)) or request.cookies[cookie_name("csrf", platform)]
    return csrf_value(platform, cookie)


async def rate_limit(request: Request, purpose: str, limit: int = 12, *, identity: str | None = None) -> None:
    # Commit in a separate transaction before credential verification so failures count too.
    from app.core.database import AsyncSessionLocal
    from app.core.platform_database import PlatformSessionLocal

    address = request.client.host if request.client else "unknown"
    platform = purpose.startswith("platform_")
    buckets = [(csrf_value(platform, f"{purpose}:ip:{address}"), max(120, limit) if identity else limit)]
    if identity is not None:
        buckets.append((csrf_value(platform, f"{purpose}:account:{identity}"), limit))
    factory = PlatformSessionLocal if platform else AsyncSessionLocal
    denied = False
    async with factory.begin() as session:
        for bucket, ceiling in buckets:
            count = await session.scalar(text("""
                INSERT INTO auth_rate_limits (bucket, expires_at, count)
                VALUES (:bucket, now() + interval '5 minutes', 1)
                ON CONFLICT (bucket) DO UPDATE
                SET count = CASE WHEN auth_rate_limits.expires_at <= now() THEN 1 ELSE auth_rate_limits.count + 1 END,
                    expires_at = CASE WHEN auth_rate_limits.expires_at <= now() THEN excluded.expires_at ELSE auth_rate_limits.expires_at END
                RETURNING count
            """), {"bucket": bucket})
            denied |= count > ceiling
    if denied:
        raise HTTPException(429, {"code": "RATE_LIMITED", "message": "Повторите запрос позже"},
                            headers={"Retry-After": "300"})


async def issue(db: AsyncSession, purpose: str, subject: UUID, company: UUID | None, ttl: timedelta,
                *, family: UUID | None = None, payload: dict | None = None) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expiry = now() + ttl
    await db.execute(text("""
        INSERT INTO auth_grants (token_hash, purpose, company_id, subject_id, expires_at, payload, family)
        VALUES (:hash, :purpose, :company, :subject, :expiry, CAST(:payload AS jsonb), :family)
    """), dict(hash=token_hash(token), purpose=purpose, company=company, subject=subject, expiry=expiry,
               payload=json.dumps(payload or {}), family=family))
    return token, expiry


async def grant(db: AsyncSession, purpose: str, token: str, *, lock: bool = False):
    query = """
        SELECT token_hash, company_id, subject_id, expires_at, payload, family, consumed_at, revoked_at
        FROM auth_grants WHERE token_hash=:hash AND purpose=:purpose
    """
    result = await db.execute(text(query + (" FOR UPDATE" if lock else "")),
                              dict(hash=token_hash(token), purpose=purpose))
    return result.mappings().one_or_none()


def active(row) -> bool:
    return bool(row and row["expires_at"] > now() and row["revoked_at"] is None and row["consumed_at"] is None)


async def consume(db: AsyncSession, row) -> None:
    await db.execute(text("UPDATE auth_grants SET consumed_at=now() WHERE token_hash=:hash"), {"hash": row["token_hash"]})


async def revoke_subject(db: AsyncSession, subject: UUID, company: UUID) -> None:
    await db.execute(text("""
        UPDATE auth_grants SET revoked_at=now()
        WHERE company_id=:company AND subject_id=:subject AND revoked_at IS NULL
    """), dict(subject=subject, company=company))


async def get_principal(db: AsyncSession, subject: UUID, company: UUID | None, *, lock: bool = False):
    if company is None:
        query = "SELECT * FROM platform_operators WHERE id=:id"
        result = await db.execute(text(query + (" FOR UPDATE" if lock else "")), {"id": subject})
        return result.mappings().one_or_none()

    await set_tenant_context(db, company)
    if lock:
        from app.models.company import Company

        await db.scalar(select(Company.id).where(Company.id == company).with_for_update(read=True))
    query = select(User).options(joinedload(User.company)).where(User.id == subject, User.company_id == company)
    if lock:
        query = query.with_for_update(of=User)
    return await db.scalar(query)


def check_principal(principal, platform: bool):
    if principal is None or not (principal["is_active"] if platform else principal.is_active):
        raise auth_error(401, "SESSION_REQUIRED", "Войдите в свой кабинет")
    if not platform and (principal.company is None or not principal.company.is_active):
        raise auth_error(403, "COMPANY_PAUSED", "Доступ организации временно приостановлен")
    return principal


async def authenticate(request: Request, db: AsyncSession, platform: bool = False):
    origin(request, platform)
    token = request.cookies.get(cookie_name("session", platform), "")
    row = await grant(db, domain("session", platform), token)
    if not active(row) or row["payload"]["access_exp"] <= now().timestamp():
        raise auth_error(401, "SESSION_REQUIRED", "Войдите в свой кабинет")
    if request.method not in SAFE_METHODS:
        validate_csrf(request, platform)
    return check_principal(await get_principal(db, row["subject_id"], row["company_id"]), platform)


def profile(principal, platform: bool) -> dict:
    if platform:
        permissions = ["platform.companies.read", "platform.incidents.manage", "platform.invites.manage"]
        if principal["role"] == "owner":
            permissions += ["platform.operators.manage", "platform.companies.manage", "platform.audit.read"]
        return {key: principal[key] for key in ("id", "email", "full_name", "role")} | {"permissions": permissions}
    permissions = ["company.sources.read"]
    if principal.role.value == "admin":
        permissions += ["company.team.read", "company.team.write", "company.access.request",
                        "company.audit.read", "company.sources.retry_request"]
    return {"id": principal.id, "email": principal.email, "full_name": principal.full_name,
            "role": principal.role.value, "permissions": permissions,
            "company": {"id": principal.company_id, "code": principal.company.code, "name": principal.company.name}}


def fernet() -> Fernet:
    return Fernet(settings.AUTH_MFA_KEY.get_secret_value().encode())


def new_factor() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def verify_totp(secret: str, code: str, last_counter: int) -> int | None:
    key = base64.b32decode(secret)
    counter = int(now().timestamp()) // 30
    for slot in range(counter - 1, counter + 2):
        digest = hmac.new(key, slot.to_bytes(8, "big"), sha1).digest()
        index = digest[-1] & 0x0f
        value = (int.from_bytes(digest[index:index + 4], "big") & 0x7fffffff) % 1000000
        if slot > last_counter and hmac.compare_digest(f"{value:06d}", code):
            return slot
    return None
