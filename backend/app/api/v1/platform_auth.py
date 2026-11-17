from datetime import timedelta
import secrets
from typing import Annotated
from urllib.parse import quote, urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.platform_database import get_platform_db
from app.core.security import get_password_hash, verify_password
from app.schemas.common import ResponseEnvelope
from app.services import platform_auth as service
from app.services.auth_mail import send_reset_link
from app.models.enums import UserRole

router = APIRouter()
db_dependency = Annotated[AsyncSession, Depends(get_db, scope="function")]
platform_db_dependency = Annotated[AsyncSession, Depends(get_platform_db, scope="function")]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Address(Payload):
    email: EmailStr
    company_code: str = Field(min_length=1, max_length=63)


class Login(Payload):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=255, strip_whitespace=False)]


class ClientLogin(Login):
    company_code: str = Field(min_length=1, max_length=63)


class Challenge(Payload):
    challenge_id: str = Field(min_length=1, max_length=128)


class ChallengeCode(Challenge):
    code: str = Field(pattern=r"^(?:[0-9]{6}|[0-9a-f]{16})$")


class Link(Payload):
    token: str = Field(min_length=1, max_length=128)


class PasswordLink(Link):
    password: Annotated[str, StringConstraints(min_length=12, max_length=72, strip_whitespace=False)]


class Invitation(PasswordLink):
    full_name: str = Field(min_length=1, max_length=255)


async def _lookup(db: AsyncSession, code: str, email: str):
    result = await db.execute(text("SELECT * FROM public.auth_tenant_subject(:code,:email)"),
                              dict(code=code.lower(), email=email.lower()))
    return result.mappings().one_or_none()


async def _session(db: AsyncSession, response: Response, principal, platform: bool, family=None):
    from uuid import uuid4
    subject, company = (principal["id"], None) if platform else (principal.id, principal.company_id)
    if not platform:
        principal.last_login_at = service.now()
    days = timedelta(days=14)
    token, _ = await service.issue(db, service.domain("session", platform), subject, company, days,
                                   family=family or uuid4(),
                                   payload={"access_exp": (service.now() + timedelta(hours=1)).timestamp()})
    service.set_cookie(response, "session", platform, token, int(days.total_seconds()))
    return service.profile(principal, platform)


async def _credentials(db, request, response, payload, platform):
    service.validate_csrf(request, platform, anonymous=True)
    identity = payload.email.lower() if platform else f"{payload.company_code.lower()}:{payload.email.lower()}"
    await service.rate_limit(request, service.domain("login", platform), identity=identity)
    if platform:
        query = await db.execute(text("SELECT * FROM platform_operators WHERE email=:email FOR UPDATE"),
                                 {"email": payload.email.lower()})
        principal = query.mappings().one_or_none()
        pwd = principal["password_hash"] if principal else service.DUMMY_HASH
    else:
        subject = await _lookup(db, payload.company_code, payload.email)
        principal = await service.get_principal(db, subject["user_id"], subject["company_id"], lock=True) if subject else None
        pwd = principal.password_hash if principal else service.DUMMY_HASH
    ok = await run_in_threadpool(verify_password, payload.password, pwd)
    if not ok or len(payload.password.encode()) > 72 or principal is None or not (principal["is_active"] if platform else principal.is_active):
        raise service.auth_error(401, "INVALID_CREDENTIALS", "Неверные данные для входа")
    service.check_principal(principal, platform)
    if not platform and principal.role != UserRole.ADMIN:
        return ResponseEnvelope.ok({"step": "authenticated", "profile": await _session(db, response, principal, False)})
    subject, company = (principal["id"], None) if platform else (principal.id, principal.company_id)
    factor = await db.scalar(text("SELECT 1 FROM auth_factors WHERE subject_id=:id"), {"id": subject})
    token, expires = await service.issue(
        db, service.domain("mfa", platform), subject, company, timedelta(minutes=5),
        payload={"binding": service.challenge_binding(request, platform)},
    )
    response.headers["Cache-Control"] = "no-store"
    return ResponseEnvelope.ok({"step": "mfa_required" if factor else "mfa_enrollment_required",
                                "challenge_id": token, "expires_at": expires})


@router.post("/auth/login")
async def login(payload: ClientLogin, request: Request, response: Response, db: db_dependency):
    return await _credentials(db, request, response, payload, False)


@router.post("/platform/auth/login")
async def platform_login(payload: Login, request: Request, response: Response, db: platform_db_dependency):
    return await _credentials(db, request, response, payload, True)


def _unavailable():
    return service.auth_error(410, "LINK_UNAVAILABLE", "Ссылка недоступна или срок её действия истёк")


async def _mfa(db, request, response, payload, platform, setup):
    service.validate_csrf(request, platform, anonymous=True)
    await service.rate_limit(request, service.domain("mfa", platform), identity=payload.challenge_id)
    purpose = service.domain("mfa", platform)
    challenge = await service.grant(db, purpose, payload.challenge_id)
    if not service.active(challenge):
        raise _unavailable()
    subject, company = challenge["subject_id"], challenge["company_id"]
    principal = service.check_principal(await service.get_principal(db, subject, company, lock=True), platform)
    challenge = await service.grant(db, purpose, payload.challenge_id, lock=True)
    if not service.active(challenge) or challenge["payload"]["binding"] != service.challenge_binding(request, platform):
        raise _unavailable()
    factor = (await db.execute(text("SELECT * FROM auth_factors WHERE subject_id=:id FOR UPDATE"),
                               {"id": subject})).mappings().one_or_none()
    pending = challenge["payload"].get("secret")
    cipher = service.fernet()
    if setup:
        if factor:
            raise service.auth_error(409, "CONFLICT", "Фактор уже настроен")
        if pending:
            secret = cipher.decrypt(pending.encode()).decode()
        else:
            secret = service.new_factor()
            await db.execute(text("""
                UPDATE auth_grants SET payload=payload || jsonb_build_object('secret', CAST(:secret AS text))
                WHERE token_hash=:hash
            """), dict(secret=cipher.encrypt(secret.encode()).decode(), hash=challenge["token_hash"]))
        account = principal["email"] if platform else principal.email
        parameters = urlencode({"secret": secret, "issuer": "Smart Enterprise Hub"})
        response.headers["Cache-Control"] = "no-store"
        return ResponseEnvelope.ok({"secret": secret,
                                    "otpauth_uri": f"otpauth://totp/Smart%20Enterprise%20Hub:{quote(account, safe='')}?{parameters}"})
    encrypted = factor["secret_ciphertext"] if factor else pending
    if not encrypted:
        raise service.auth_error(409, "CONFLICT", "Сначала настройте фактор")
    counter = service.verify_totp(cipher.decrypt(encrypted.encode()).decode(), payload.code,
                                  factor["last_counter"] if factor else -1)
    recovered = None
    if factor and counter is None and len(payload.code) == 16:
        recovered = await db.scalar(text("""
            DELETE FROM auth_recovery_codes WHERE subject_id=:id AND code_hash=:code RETURNING subject_id
        """), {"id": subject, "code": service.token_hash(payload.code)})
    if counter is None and recovered is None:
        raise service.auth_error(401, "INVALID_CREDENTIALS", "Неверный код подтверждения")
    if counter is not None:
        await db.execute(text("""
            INSERT INTO auth_factors (subject_id, secret_ciphertext, last_counter)
            VALUES (:id, :secret, :counter)
            ON CONFLICT (subject_id) DO UPDATE SET last_counter=excluded.last_counter
        """), dict(id=subject, secret=encrypted, counter=counter))
    await service.consume(db, challenge)
    result = {"step": "authenticated", "profile": await _session(db, response, principal, platform)}
    if not factor:
        codes = [secrets.token_hex(8) for _ in range(8)]
        await db.execute(text("""
            INSERT INTO auth_recovery_codes (subject_id,code_hash) VALUES (:id,:code)
        """), [{"id": subject, "code": service.token_hash(code)} for code in codes])
        result["recovery_codes"] = codes
    return ResponseEnvelope.ok(result)


def _add_session_routes(prefix: str, platform: bool):
    database = platform_db_dependency if platform else db_dependency
    @router.get(prefix + "/csrf")
    async def csrf(request: Request, response: Response):
        service.origin(request, platform)
        binding = request.cookies.get(service.cookie_name("csrf", platform))
        if not binding:
            binding = secrets.token_urlsafe(32)
            service.set_cookie(response, "csrf", platform, binding, 3600)
        response.headers["Cache-Control"] = "no-store"
        session = request.cookies.get(service.cookie_name("session", platform))
        return ResponseEnvelope.ok({"csrf_token": service.csrf_value(platform, session or binding)})

    @router.get(prefix + "/me")
    async def me(request: Request, response: Response, db: database):
        response.headers["Cache-Control"] = "no-store"
        return ResponseEnvelope.ok(service.profile(await service.authenticate(request, db, platform), platform))

    @router.post(prefix + "/mfa/setup")
    async def mfa_setup(payload: Challenge, request: Request, response: Response, db: database):
        return await _mfa(db, request, response, payload, platform, True)

    @router.post(prefix + "/mfa/verify")
    async def mfa_verify(payload: ChallengeCode, request: Request, response: Response, db: database):
        return await _mfa(db, request, response, payload, platform, False)

    @router.post(prefix + "/refresh")
    async def refresh(request: Request, response: Response, db: database):
        service.validate_csrf(request, platform)
        purpose = service.domain("session", platform)
        token = request.cookies[service.cookie_name("session", platform)]
        row = await service.grant(db, purpose, token)
        if not row:
            raise service.auth_error(401, "SESSION_REQUIRED", "Войдите в свой кабинет")
        principal = service.check_principal(await service.get_principal(db, row["subject_id"], row["company_id"], lock=True), platform)
        row = await service.grant(db, purpose, token, lock=True)
        if row and row["consumed_at"] is not None:
            await db.execute(text("UPDATE auth_grants SET revoked_at=now() WHERE family=:id"), {"id": row["family"]})
            await db.commit()
        if not service.active(row):
            raise service.auth_error(401, "SESSION_REQUIRED", "Войдите в свой кабинет")
        await service.consume(db, row)
        return ResponseEnvelope.ok(await _session(db, response, principal, platform, row["family"]))

    @router.post(prefix + "/logout")
    async def logout(request: Request, response: Response, db: database):
        if request.cookies.get(service.cookie_name("session", platform)):
            service.validate_csrf(request, platform)
            row = await service.grant(db, service.domain("session", platform),
                                      request.cookies[service.cookie_name("session", platform)], lock=True)
            if row:
                await db.execute(text("UPDATE auth_grants SET revoked_at=now() WHERE family=:id"), {"id": row["family"]})
        else:
            service.origin(request, platform)
        service.clear_cookie(response, "session", platform)
        response.headers["Cache-Control"] = "no-store"
        return ResponseEnvelope.ok(None)


_add_session_routes("/auth", False)
_add_session_routes("/platform/auth", True)


@router.post("/auth/password/forgot", status_code=202)
async def forgot(payload: Address, request: Request, db: db_dependency, background: BackgroundTasks):
    service.validate_csrf(request, False, anonymous=True)
    await service.rate_limit(request, "client_forgot", 6, identity=f"{payload.company_code.lower()}:{payload.email.lower()}")
    subject = await _lookup(db, payload.company_code, payload.email)
    if subject:
        user = await service.get_principal(db, subject["user_id"], subject["company_id"])
        if user and user.is_active and user.company.is_active:
            token, _ = await service.issue(db, "client_reset", user.id, user.company_id, timedelta(minutes=30),
                                           payload={"version": user.version})
            await db.commit()
            background.add_task(send_reset_link, user.email, user.company.code, token)
    return ResponseEnvelope.ok({"state": "accepted"})


async def _change_password(payload, request, db, invitation):
    service.validate_csrf(request, False, anonymous=True)
    await service.rate_limit(request, "client_link", identity=payload.token)
    purpose = "client_invite" if invitation else "client_reset"
    row = await service.grant(db, purpose, payload.token)
    if not service.active(row):
        raise _unavailable()
    user = await service.get_principal(db, row["subject_id"], row["company_id"], lock=True)
    row = await service.grant(db, purpose, payload.token, lock=True)
    if (not service.active(row) or not user or user.is_active == invitation or not user.company.is_active
            or row["payload"].get("version") != user.version):
        raise _unavailable()
    if len(payload.password.encode("utf-8")) > 72:
        raise service.auth_error(422, "VALIDATION_ERROR", "Пароль превышает допустимую длину")
    user.password_hash = await run_in_threadpool(get_password_hash, payload.password)
    user.version += 1
    if invitation:
        user.full_name = payload.full_name
        user.is_active = True
        invitation_id = row["payload"].get("invitation_id")
        if invitation_id:
            access_id = await db.scalar(text("""
                UPDATE company_invitations SET state='accepted',version=version+1
                WHERE company_id=:company AND id=CAST(:id AS uuid) AND state='pending'
                RETURNING access_request_id
            """), {"company": user.company_id, "id": invitation_id})
            if access_id:
                await db.execute(text("""
                    UPDATE company_access_requests SET state='fulfilled',version=version+1
                    WHERE company_id=:company AND id=:id AND state='invited'
                """), {"company": user.company_id, "id": access_id})
    await service.consume(db, row)
    await service.revoke_subject(db, user.id, user.company_id)
    return ResponseEnvelope.ok({"state": "accepted"})


@router.post("/auth/invitation/accept")
async def accept_invitation(payload: Invitation, request: Request, db: db_dependency):
    return await _change_password(payload, request, db, True)


@router.post("/auth/password/reset")
async def reset_password(payload: PasswordLink, request: Request, db: db_dependency):
    return await _change_password(payload, request, db, False)
