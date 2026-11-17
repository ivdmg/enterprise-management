import asyncio
import logging
from email.message import EmailMessage
from pathlib import Path
import smtplib
from urllib.parse import quote
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)


def _deliver(message: EmailMessage) -> None:
    if settings.AUTH_MAIL_OUTBOX:
        directory = Path(settings.AUTH_MAIL_OUTBOX)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{uuid4()}.eml").open("xb") as target:
            target.write(message.as_bytes())
    elif settings.AUTH_SMTP_HOST and settings.AUTH_SMTP_FROM:
        with smtplib.SMTP_SSL(settings.AUTH_SMTP_HOST, settings.AUTH_SMTP_PORT, timeout=10) as smtp:
            if settings.AUTH_SMTP_USER:
                password = settings.AUTH_SMTP_PASSWORD.get_secret_value() if settings.AUTH_SMTP_PASSWORD else ""
                smtp.login(settings.AUTH_SMTP_USER, password)
            smtp.send_message(message)
    else:
        raise RuntimeError("Authentication mail transport is unavailable")


async def send_link(email: str, company_code: str | None, purpose: str, token: str) -> None:
    message = EmailMessage()
    message["From"] = settings.AUTH_SMTP_FROM or "pilot@example.com"
    message["To"] = email
    message["Subject"] = "Smart Enterprise Hub"
    path = (f"{settings.CLIENT_AUTH_ORIGIN}/c/{quote(company_code, safe='')}/{purpose}"
            if company_code else f"{settings.PLATFORM_AUTH_ORIGIN}/platform/{purpose}")
    message.set_content(f"Откройте эту ссылку для подтверждения действия:\n{path}#token={quote(token, safe='')}")
    await asyncio.to_thread(_deliver, message)


async def notify_email_change(email: str) -> None:
    message = EmailMessage()
    message["From"] = settings.AUTH_SMTP_FROM or "pilot@example.com"
    message["To"] = email
    message["Subject"] = "Smart Enterprise Hub"
    message.set_content("Запрошена смена адреса вашей учётной записи. Обратитесь в поддержку, если запрос вам неизвестен.")
    await asyncio.to_thread(_deliver, message)


async def send_reset_link(email: str, company_code: str, token: str) -> None:
    try:
        await send_link(email, company_code, "reset", token)
    except Exception:
        logger.error("Password reset delivery failed")
