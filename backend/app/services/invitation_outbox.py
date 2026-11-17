"""Deliver pending platform invitations without exposing plaintext tokens to the database."""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import text

from app.core.database import set_tenant_context
from app.core.platform_database import PlatformSessionLocal
from app.services import platform_auth as auth
from app.services.auth_mail import send_link

logger = logging.getLogger(__name__)


async def deliver_one() -> bool:
    async with PlatformSessionLocal.begin() as db:
        company_id = await db.scalar(text("SELECT public.platform_pending_invitation_company()"))
        if company_id is None:
            return False
        company = (await db.execute(text("SELECT * FROM public.platform_company_lock(:id)"),
                                    {"id": company_id})).mappings().one_or_none()
        if not company or company["state"] != "active":
            return False
        await set_tenant_context(db, company_id)
        job = (await db.execute(text("""
            SELECT o.invitation_id,o.invitation_version,o.token_ciphertext,o.attempt_count,
                   i.email,i.state,i.version,i.expires_at
            FROM invitation_outbox AS o JOIN company_invitations AS i ON i.id=o.invitation_id AND i.company_id=o.company_id
            WHERE o.company_id=:company AND o.available_at<=now()
            ORDER BY o.available_at,o.invitation_id LIMIT 1 FOR UPDATE OF o SKIP LOCKED
        """), {"company": company_id})).mappings().one_or_none()
        if not job:
            return False

        params = {"company": company_id, "id": job["invitation_id"]}
        if job["state"] == "pending" and job["version"] == job["invitation_version"] and job["expires_at"] > auth.now():
            try:
                token = auth.fernet().decrypt(job["token_ciphertext"].encode()).decode()
                await send_link(job["email"], company["code"], "invite", token)
            except Exception:
                attempt = job["attempt_count"] + 1
                if attempt < 5:
                    await db.execute(text("""
                        UPDATE invitation_outbox SET available_at=:retry,attempt_count=:attempt
                        WHERE company_id=:company AND invitation_id=:id
                    """), params | {"attempt": attempt, "retry": auth.now() + timedelta(seconds=2 ** attempt * 15)})
                    return True
                state = "failed"
            else:
                state = "sent"
            await db.execute(text("""
                UPDATE company_invitations SET delivery_state=:state WHERE company_id=:company AND id=:id
            """), params | {"state": state})
        elif job["state"] == "pending" and job["version"] == job["invitation_version"]:
            await db.execute(text("""
                UPDATE company_invitations SET delivery_state='canceled' WHERE company_id=:company AND id=:id
            """), params)
        await db.execute(text("DELETE FROM invitation_outbox WHERE company_id=:company AND invitation_id=:id"), params)
        return True


async def run_outbox() -> None:
    while True:
        try:
            processed = await deliver_one()
        except Exception:
            logger.error("Invitation delivery service unavailable")
            processed = False
        if not processed:
            await asyncio.sleep(3)
