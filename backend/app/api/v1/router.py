from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.company import router as company_router
from app.api.v1.files import router as files_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.sync import router as sync_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.procurement import router as procurement_router
from app.api.v1.dispatch import router as dispatch_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(company_router)
api_router.include_router(files_router)
api_router.include_router(dashboard_router)
api_router.include_router(alerts_router)
api_router.include_router(sync_router)
api_router.include_router(tasks_router)
api_router.include_router(procurement_router)
api_router.include_router(dispatch_router)

