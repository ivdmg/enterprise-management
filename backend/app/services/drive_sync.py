import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.enums import FileStatus
from app.models.file import UploadedFile
from app.services.alerts_engine import alerts_engine
from app.services.google_drive import DriveFileInfo, google_drive_client
from app.services.storage import build_tenant_storage_key, storage_service
from app.services.template_parser import standard_template_parser

logger = logging.getLogger("enterprise_hub.drive_sync")


class SyncStatusInfo:
    """In-memory tracking of drive synchronization runs."""
    def __init__(self):
        self.status: str = "idle"  # "idle" | "syncing" | "error"
        self.last_sync_time: Optional[datetime] = None
        self.processed_files_count: int = 0
        self.skipped_files_count: int = 0
        self.last_error: Optional[str] = None
        self.details: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "processed_files_count": self.processed_files_count,
            "skipped_files_count": self.skipped_files_count,
            "last_error": self.last_error,
            "details": self.details[-10:],  # last 10 file events
        }


class GoogleDriveSyncService:
    """
    Orchestrator for automated bidirectional sync between Google Drive (or Mock Drive)
    and the Smart Enterprise Hub database.
    """

    TARGET_FOLDERS = [
        "01_Реестры_Тендеров",
        "02_Финансы_и_1С",
        "03_Снабжение_и_Закупки",
        "04_ПТО_и_Объекты",
        "05_Юридический_Отдел",
    ]

    def __init__(self):
        self._lock = asyncio.Lock()
        self._status_by_company: Dict[uuid.UUID, SyncStatusInfo] = {}

    def get_status(self, company_id: uuid.UUID) -> SyncStatusInfo:
        if company_id not in self._status_by_company:
            self._status_by_company[company_id] = SyncStatusInfo()
        return self._status_by_company[company_id]

    async def sync_company_drive(
        self,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Synchronizes all 5 target folders on Google Drive for the specified company.
        Performs 0-overhead hash skipping when files have not changed.
        """
        status_info = self.get_status(company_id)
        if status_info.status == "syncing":
            logger.warning("Sync already in progress for company %s", company_id)
            return status_info.to_dict()

        async with self._lock:
            status_info.status = "syncing"
            status_info.last_error = None
            status_info.details = []
            
            processed = 0
            skipped = 0

            # Session lifecycle: either use passed session or create a dedicated one
            owns_session = db is None
            session = db if db is not None else async_session_factory()

            try:
                # 1. Discover all files across the 5 target folders
                all_drive_files: List[DriveFileInfo] = []
                for folder in self.TARGET_FOLDERS:
                    try:
                        folder_files = google_drive_client.list_files_in_folder(folder)
                        all_drive_files.extend(folder_files)
                    except Exception as e:
                        logger.error("Error reading folder '%s' on Drive: %s", folder, e)

                logger.info(
                    "Drive sync started for company %s: found %d total files across folders",
                    company_id,
                    len(all_drive_files),
                )

                # 2. Process each file
                for file_info in all_drive_files:
                    try:
                        # Download raw file bytes to compute SHA-256
                        file_bytes = google_drive_client.download_file_bytes(file_info.id)
                        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

                        # Check if this exact file version was already ingested
                        query = select(UploadedFile).where(
                            UploadedFile.company_id == company_id,
                            UploadedFile.sha256_hash == sha256_hash,
                            UploadedFile.status == FileStatus.PROCESSED,
                            UploadedFile.deleted_at.is_(None),
                        )
                        existing_file = (await session.execute(query)).scalar_one_or_none()

                        if existing_file:
                            # 0 overhead: file content has not changed
                            skipped += 1
                            status_info.details.append({
                                "file": file_info.name,
                                "folder": file_info.parent_folder,
                                "action": "skipped",
                                "reason": "Hash unchanged",
                            })
                            continue

                        # File is new or updated: save to tenant storage
                        storage_key = build_tenant_storage_key(
                            company_id=company_id,
                            sha256_hash=sha256_hash,
                            extension=".xlsx",
                        )
                        await storage_service.save_file(file_bytes, storage_key)

                        # Create or update UploadedFile record
                        uploaded_file = UploadedFile(
                            company_id=company_id,
                            uploaded_by_user_id=user_id,
                            original_name=file_info.name,
                            storage_path=storage_key,
                            file_size_bytes=len(file_bytes),
                            mime_type=file_info.mime_type,
                            sha256_hash=sha256_hash,
                            status=FileStatus.PROCESSED,
                        )
                        session.add(uploaded_file)
                        await session.flush()

                        # Fast deterministic parsing into business models
                        tpl_type, count = await standard_template_parser.parse_and_persist(
                            file_source=file_bytes,
                            filename=file_info.name,
                            company_id=company_id,
                            file_id=uploaded_file.id,
                            db=session,
                        )

                        await session.commit()
                        processed += 1
                        status_info.details.append({
                            "file": file_info.name,
                            "folder": file_info.parent_folder,
                            "action": "imported",
                            "records_extracted": count,
                            "template_type": tpl_type,
                        })

                    except Exception as fe:
                        await session.rollback()
                        logger.error("Error processing Drive file '%s': %s", file_info.name, fe)
                        status_info.details.append({
                            "file": file_info.name,
                            "folder": file_info.parent_folder,
                            "action": "error",
                            "error": str(fe),
                        })

                # 3. Post-sync risk evaluation and alert updates
                try:
                    await alerts_engine.run_full_evaluation(company_id, session)
                except Exception as ae:
                    logger.error("Error running alert evaluation after sync: %s", ae)

                status_info.status = "idle"
                status_info.last_sync_time = datetime.now(timezone.utc)
                status_info.processed_files_count += processed
                status_info.skipped_files_count += skipped
                logger.info(
                    "Drive sync completed for company %s: %d processed, %d skipped",
                    company_id,
                    processed,
                    skipped,
                )

            except Exception as e:
                status_info.status = "error"
                status_info.last_error = str(e)
                logger.exception("Drive sync failed for company %s: %s", company_id, e)
            finally:
                if owns_session:
                    await session.close()

            return status_info.to_dict()


drive_sync_service = GoogleDriveSyncService()
