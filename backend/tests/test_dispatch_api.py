from datetime import date
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.dispatch import FleetDispatchRecord
from app.models.user import User
from app.models.enums import UserRole

@pytest.mark.asyncio
async def test_dispatch_normalizes_spreadsheet_statuses_and_filters():
    user = User(id=uuid.uuid4(),company_id=uuid.uuid4(),email='test@example.com',role=UserRole.ADMIN)
    rows = [FleetDispatchRecord(id=uuid.uuid4(),company_id=user.company_id,shift_date=date(2026,10,24),
        target_object='Объект',resource_type='Спецтехника',unit_name='Экскаватор',status='В_Ремонте'),
        FleetDispatchRecord(id=uuid.uuid4(),company_id=user.company_id,shift_date=date(2026,10,24),
        target_object='Объект',resource_type='Бригада_Рабочих',unit_name='Бригада',status='На_Объекте')]
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value=rows
    db.execute.return_value=result
    async def override_db(): yield db
    app.dependency_overrides[get_current_user]=lambda:user
    app.dependency_overrides[get_db]=override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            r=await client.get('/api/v1/dispatch/records?status=repair&resource_type=machinery')
            assert r.status_code==200
            assert len(r.json()['data'])==1
            assert r.json()['data'][0]['status']=='repair'
            assert r.json()['data'][0]['resource_type']=='machinery'
            query = str(db.execute.call_args.args[0])
            assert 'company_id' in query and 'deleted_at IS NULL' in query
    finally:
        app.dependency_overrides.clear()
