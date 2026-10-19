import logging
import uuid
from typing import Optional
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog

logger = logging.getLogger("audit")


async def record_audit_log(
    db: AsyncSession,
    company_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    old_status: Optional[str],
    new_status: str,
    user_id: Optional[uuid.UUID] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """
    Task BE-5.1: Records an immutable audit log entry for status transitions.
    Extracts IP address and User-Agent from Request if provided.
    """
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    if request:
        client = getattr(request, "client", None)
        if client:
            ip_address = getattr(client, "host", None)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        user_agent = request.headers.get("user-agent")

    log_entry = AuditLog(
        company_id=company_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        old_status=str(old_status) if old_status is not None else None,
        new_status=str(new_status),
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(log_entry)
    logger.info(
        "AUDIT: [%s] %s status changed '%s' -> '%s' (user=%s, ip=%s)",
        entity_type,
        entity_id,
        old_status,
        new_status,
        user_id,
        ip_address,
    )
    return log_entry
