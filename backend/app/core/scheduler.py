import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.company import Company
from app.services.drive_sync import drive_sync_service

logger = logging.getLogger("enterprise_hub.scheduler")

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def sync_google_drive_job() -> None:
    """
    Periodic background job: scans Google Drive (or Mock Drive) for all active tenant companies,
    syncs new/changed documents, updates business models, and evaluates risk alerts.
    """
    logger.info("Starting scheduled Google Drive sync job...")
    async with async_session_factory() as session:
        try:
            # Query all active tenant companies
            stmt = select(Company.id).where(Company.is_active == True)  # noqa: E712
            if settings.GOOGLE_DRIVE_COMPANY_ID:
                stmt = stmt.where(Company.id == settings.GOOGLE_DRIVE_COMPANY_ID)
            result = await session.execute(stmt)
            company_ids = result.scalars().all()

            logger.info("Found %d active companies for Drive synchronization", len(company_ids))
            for company_id in company_ids:
                try:
                    await drive_sync_service.sync_company_drive(
                        company_id=company_id,
                        user_id=None,
                        db=session,
                    )
                except Exception as comp_err:
                    logger.error("Error during scheduled sync for company %s: %s", company_id, comp_err)

            logger.info("Scheduled Google Drive sync job completed successfully")
        except Exception as e:
            logger.exception("Scheduled Google Drive sync job encountered a critical error: %s", e)


def start_scheduler() -> None:
    """Starts the AsyncIOScheduler and schedules recurring maintenance jobs."""
    if scheduler.running:
        logger.warning("Scheduler is already running")
        return

    interval_seconds = max(10, getattr(settings, "SYNC_INTERVAL_SECONDS", 120))
    scheduler.add_job(
        sync_google_drive_job,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id="sync_google_drive_job",
        name="Sync Google Drive Incoming Folders",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "AsyncIOScheduler started successfully. Drive sync job scheduled every %d seconds.",
        interval_seconds,
    )


def shutdown_scheduler() -> None:
    """Gracefully shuts down the background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("AsyncIOScheduler shut down.")
