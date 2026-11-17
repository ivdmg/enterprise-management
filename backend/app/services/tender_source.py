from sqlalchemy import func, or_, select, true

from app.core.config import settings
from app.models.file import UploadedFile
from app.models.project import TenderProject

TENDER_WORKBOOK_NAME = "тендерщицы.xlsx"


def tender_source_files(company_id):
    new_workbook = func.lower(UploadedFile.original_name) == TENDER_WORKBOOK_NAME
    return select(UploadedFile.id).where(
        UploadedFile.company_id == company_id,
        UploadedFile.google_drive_id.is_not(None),
        UploadedFile.deleted_at.is_(None),
        or_(UploadedFile.google_drive_id == settings.GOOGLE_DRIVE_SOURCE_FILE_ID, new_workbook),
        select(TenderProject.id).where(
            TenderProject.file_id == UploadedFile.id,
            TenderProject.company_id == company_id,
            TenderProject.custom_attributes["customer_tenders"].as_boolean().is_(True),
        ).correlate(UploadedFile).exists(),
    ).correlate(None).order_by(new_workbook.desc(), UploadedFile.created_at.desc(), UploadedFile.id).limit(1)


def active_tender_source(company_id):
    """Keep saved source snapshots independent while selecting the configured one."""
    if settings.GOOGLE_DRIVE_MOCK or company_id != settings.GOOGLE_DRIVE_COMPANY_ID:
        return true()
    return or_(
        TenderProject.custom_attributes["customer_tenders"].as_boolean().is_not(True),
        TenderProject.file_id.in_(tender_source_files(company_id)),
    )
