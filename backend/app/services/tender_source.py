from sqlalchemy import or_, select, true

from app.core.config import settings
from app.models.file import UploadedFile
from app.models.project import TenderProject


def active_tender_source(company_id):
    """Keep saved source snapshots independent while selecting the configured one."""
    if settings.GOOGLE_DRIVE_MOCK or company_id != settings.GOOGLE_DRIVE_COMPANY_ID:
        return true()
    source_files = select(UploadedFile.id).where(
        UploadedFile.company_id == company_id,
        UploadedFile.google_drive_id == settings.GOOGLE_DRIVE_SOURCE_FILE_ID,
        UploadedFile.deleted_at.is_(None),
    )
    return or_(
        TenderProject.custom_attributes["customer_tenders"].as_boolean().is_not(True),
        TenderProject.file_id.in_(source_files),
    )
