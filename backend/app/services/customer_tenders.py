"""Import the customer's two-sheet register without inventing missing figures."""
import io
from datetime import date, datetime
from decimal import Decimal
import openpyxl
from sqlalchemy import select
from app.models.project import TenderProject
from app.models.enums import ProjectRisk

def cell(value):
    if isinstance(value, (date, datetime)): return value.isoformat()[:10]
    return value

def key(value):
    if isinstance(value, (int,float)): return str(int(value)) if value == int(value) else str(value)
    return str(value).strip() if value is not None else ''

def read_customer_workbook(content):
    wb=openpyxl.load_workbook(io.BytesIO(content),data_only=True)
    if not {'Реест Ольга','Ежедневный мониторинг'}.issubset(wb.sheetnames):
        wb.close()
        return None
    result={}
    for name in ('Реест Ольга','Ежедневный мониторинг'):
        ws=wb[name]
        rows=list(ws.values)
        columns=[]
        for i in range(ws.max_column):
            top=rows[0][i]
            sub=rows[1][i] if name=='Реест Ольга' else None
            label=str(top or '').strip()
            if sub: label=(label+' / '+str(sub).strip()).strip(' /')
            if not label and name=='Реест Ольга' and i==6: label='Обеспечение контракта / БГ'
            if name=='Ежедневный мониторинг' and i>=4:
                period=(i-4)//7+1
                marker=cell(rows[2][4+(period-1)*7])
                label=f'Период {period} ({marker or "не указан"}) / {label}'
            columns.append(label or f'Колонка {i+1}')
        records=[]
        warnings=[]
        seen=set()
        for number,row in enumerate(rows[3:],start=4):
            identifier=key(row[0])
            if not identifier or not any(v is not None and v!='' for v in row[1:]): continue
            if identifier.startswith('#'):
                warnings.append(f'Строка {number}: ошибка формулы в номере ({identifier})')
                continue
            if identifier in seen: raise ValueError(f'{name}, строка {number}: повтор внутреннего номера {identifier}')
            seen.add(identifier)
            records.append({'key':identifier,'source_row':number,'values':[cell(v) for v in row]})
        result[name]={'columns':columns,'rows':records,'warnings':warnings}
    wb.close()
    return result

async def persist_customer_workbook(content,company_id,file_id,db):
    data=read_customer_workbook(content)
    if data is None: raise ValueError('Не найдены оба листа реестра заказчика')
    existing=(await db.execute(select(TenderProject).where(TenderProject.company_id==company_id,TenderProject.deleted_at.is_(None)))).scalars().all()
    by_key={p.project_code:p for p in existing if (p.custom_attributes or {}).get('customer_tenders')}
    registry={r['key']:r for r in data['Реест Ольга']['rows']}
    monitoring={r['key']:r for r in data['Ежедневный мониторинг']['rows']}
    first_key=min(registry.keys() | monitoring.keys(),key=lambda k:(registry.get(k) or monitoring[k])['source_row']) if registry or monitoring else None
    for identifier in registry.keys() | monitoring.keys():
        r=registry.get(identifier)
        m=monitoring.get(identifier)
        values=r['values'] if r else m['values']
        project=by_key.get(identifier)
        if project is None:
            project=TenderProject(company_id=company_id,project_code=identifier,project_name=str(values[1] or identifier),risk_level=ProjectRisk.NORMAL)
            db.add(project)
        project.file_id=file_id
        project.customer_name=str(values[1]) if values[1] else None
        project.project_name=str(values[9] or values[1] or identifier) if r else str(values[1] or identifier)
        project.purchase_number=key(values[7]) or None if r else None
        amount=values[15] if r else None
        if amount == '': amount=None
        if amount is not None and not isinstance(amount,(int,float)):
            try: amount=Decimal(str(amount).replace(' ','').replace('\u00a0','').replace(',','.'))
            except Exception: raise ValueError(f'Реест Ольга, строка {r["source_row"]}: неверная сумма контракта')
        project.contract_sum=Decimal(str(amount)) if amount is not None else Decimal('0')
        project.status=str(values[16] or 'Не указан')[:50] if r else 'Не указан'
        project.deadline_date=None
        project.bank_guarantee_expiry=None
        project.custom_attributes={'customer_tenders':True,'registry':r,'monitoring':m,'registry_columns':data['Реест Ольга']['columns'],'monitoring_columns':data['Ежедневный мониторинг']['columns'],'contract_amount_known':amount is not None,'source_warnings':{name:sheet['warnings'] for name,sheet in data.items()} if identifier==first_key else {}}
    return 'customer_tenders',len(registry.keys() | monitoring.keys())
