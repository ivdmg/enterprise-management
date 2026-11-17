"""Issue the first owner invitation through the configured restricted platform database."""

import argparse
import asyncio
from datetime import timedelta
from uuid import uuid4

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import text

from app.core.config import settings
from app.core.platform_database import PlatformSessionLocal
from app.services.auth_mail import send_link
from app.services.platform_auth import issue, token_hash


async def create_owner(email: str, full_name: str) -> None:
    if not settings.PLATFORM_AUTH_ENABLED:
        raise RuntimeError("Centralized authentication is disabled")
    owner = uuid4()
    async with PlatformSessionLocal() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(284619634731)"))
        pending = (await db.execute(text("""
            SELECT id,email,role,password_hash FROM platform_operators FOR UPDATE
        """))).mappings().all()
        if pending:
            row = pending[0]
            if len(pending) != 1 or row["email"] != email or row["role"] != "owner" or row["password_hash"] != "!invited":
                raise RuntimeError("The platform already has an owner or an invitation for another address")
            owner = row["id"]
            await db.execute(text("""
                UPDATE auth_grants SET revoked_at=now() WHERE purpose='platform_invite' AND subject_id=:id
                  AND revoked_at IS NULL
            """), {"id": owner})
        else:
            await db.execute(text("""
                INSERT INTO platform_operators (id,email,full_name,role,password_hash,is_active)
                VALUES (:id,:email,:name,'owner','!invited',false)
            """), {"id": owner, "email": email, "name": full_name})
        token, _ = await issue(db, "platform_invite", owner, None, timedelta(hours=48))
        await db.commit()
        try:
            await send_link(email, None, "invite", token)
        except Exception:
            await db.execute(text("UPDATE auth_grants SET revoked_at=now() WHERE token_hash=:hash"),
                             {"hash": token_hash(token)})
            await db.commit()
            raise RuntimeError("Invitation delivery failed; retry the command for the same address") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    try:
        email = TypeAdapter(EmailStr).validate_python(args.email).lower()
        name = args.name.strip()
        if not 1 <= len(name) <= 255:
            raise ValueError()
    except ValueError:
        parser.error("Enter a valid e-mail and name")
    try:
        asyncio.run(create_owner(email, name))
    except RuntimeError as exc:
        parser.exit(1, str(exc) + "\n")
    print("Owner invitation sent")


if __name__ == "__main__":
    main()
