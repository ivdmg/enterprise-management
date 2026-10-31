from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.project import TenderProject
from app.models.file import UploadedFile
from app.models.user import User
from app.schemas.common import ResponseEnvelope

router=APIRouter(prefix='/customer-tenders',tags=['Customer tenders'])
@router.get('')
async def register(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    rows=(await db.execute(select(TenderProject,UploadedFile.google_drive_link).join(UploadedFile,TenderProject.file_id==UploadedFile.id).where(TenderProject.company_id==user.company_id,TenderProject.deleted_at.is_(None),UploadedFile.deleted_at.is_(None)))).all()
    records=[{'id':str(p.id),'number':p.project_code,'amount':float(p.contract_sum) if p.custom_attributes.get('contract_amount_known') else None,'link':link,**p.custom_attributes} for p,link in rows if p.custom_attributes.get('customer_tenders')]
    records.sort(key=lambda r: (r.get('registry') or r.get('monitoring'))['source_row'])
    return ResponseEnvelope.ok(records)
