from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.project import TenderProject
from app.models.file import UploadedFile
from app.models.user import User
from app.schemas.common import ResponseEnvelope

router=APIRouter(prefix='/customer-tenders',tags=['Customer tenders'])
@router.get('')
async def register(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    query=select(TenderProject,UploadedFile.google_drive_link,UploadedFile.original_name).join(UploadedFile,TenderProject.file_id==UploadedFile.id).where(TenderProject.company_id==user.company_id,UploadedFile.company_id==user.company_id,TenderProject.deleted_at.is_(None),UploadedFile.deleted_at.is_(None))
    if not settings.GOOGLE_DRIVE_MOCK and user.company_id == settings.GOOGLE_DRIVE_COMPANY_ID:
        query = query.where(UploadedFile.google_drive_id == settings.GOOGLE_DRIVE_SOURCE_FILE_ID)
    rows = (await db.execute(query)).all()
    records=[{'id':str(p.id),'number':p.project_code,'amount':float(p.contract_sum) if p.custom_attributes.get('contract_amount_known') else None,'link':link,'source_name':name,'curator':p.curator_name,**p.custom_attributes} for p,link,name in rows if p.custom_attributes.get('customer_tenders')]
    records.sort(key=lambda r: (r.get('registry') or r.get('monitoring'))['source_row'])
    return ResponseEnvelope.ok(records)
