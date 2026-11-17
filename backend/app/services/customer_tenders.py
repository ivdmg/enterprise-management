"""Import the customer's two-sheet register without inventing missing figures."""
import io
from datetime import date, datetime, timezone
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

class WorkbookShapeError(ValueError):
    pass


def read_customer_workbook(content, *, max_rows=None, max_columns=None):
    wb=openpyxl.load_workbook(io.BytesIO(content),data_only=True)
    if not {'Реест Ольга','Ежедневный мониторинг'}.issubset(wb.sheetnames):
        wb.close()
        return None
    result={}
    for name in ('Реест Ольга','Ежедневный мониторинг'):
        ws=wb[name]
        if ((max_rows is not None and ws.max_row > max_rows)
                or (max_columns is not None and ws.max_column > max_columns)):
            wb.close()
            raise WorkbookShapeError()
        minimum_columns = 17 if name == "Реест Ольга" else 2
        if ws.max_row < 3 or ws.max_column < minimum_columns:
            wb.close()
            raise ValueError(f'Лист «{name}» не содержит обязательные заголовки или столбцы')
        rows=list(ws.values)
        # Keep the field positions consumed by the existing dashboard.
        if name == 'Реест Ольга' and str(rows[0][4]).startswith('Статус аукциона'):
            order = (0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 4, *range(17, ws.max_column))
            rows = [tuple(row[index] for index in order) for row in rows]
        elif name == 'Ежедневный мониторинг' and ws.max_column >= 8 and str(rows[0][7]).startswith('Дата выполнения'):
            rows = [row[:4] + row[7:] for row in rows]
        columns=[]
        for i in range(len(rows[0])):
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

def contract_amount(record):
    amount = record["values"][15] if record else None
    if amount in (None, ""):
        return None
    try:
        parsed = Decimal(str(amount).replace(" ", "").replace("\u00a0", "").replace(",", "."))
        if not parsed.is_finite():
            raise ValueError("Сумма не является конечным числом")
        return parsed
    except (ValueError, ArithmeticError) as exc:
        raise ValueError(f'Реест Ольга, строка {record["source_row"]}: неверная сумма контракта') from exc


async def persist_customer_workbook(content,company_id,file_id,db,*,prepared=None,replaces_file_id=None):
    data=prepared if prepared is not None else read_customer_workbook(content)
    if data is None: raise ValueError('Не найдены оба листа реестра заказчика')
    existing=(await db.execute(select(TenderProject).where(
        TenderProject.company_id == company_id,
        TenderProject.file_id.in_([file_id, replaces_file_id] if replaces_file_id else [file_id]),
        TenderProject.deleted_at.is_(None),
        TenderProject.custom_attributes['customer_tenders'].as_boolean().is_(True),
    ))).scalars().all()
    existing.sort(key=lambda project: project.file_id == file_id)
    by_key={p.project_code:p for p in existing if (p.custom_attributes or {}).get('customer_tenders')}
    registry={r['key']:r for r in data['Реест Ольга']['rows']}
    monitoring={r['key']:r for r in data['Ежедневный мониторинг']['rows']}
    identifiers = registry.keys() | monitoring.keys()
    for project in existing:
        if project.project_code not in identifiers or by_key[project.project_code] is not project:
            project.deleted_at = datetime.now(timezone.utc)
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
        amount = contract_amount(r)
        project.contract_sum=amount if amount is not None else Decimal('0')
        project.status=str(values[16] or 'Не указан')[:50] if r else 'Не указан'
        project.deadline_date=None
        project.bank_guarantee_expiry=None
        attributes = {'customer_tenders':True,'registry':r,'monitoring':m,'registry_columns':data['Реест Ольга']['columns'],'monitoring_columns':data['Ежедневный мониторинг']['columns'],'contract_amount_known':amount is not None,'source_warnings':{name:sheet['warnings'] for name,sheet in data.items()} if identifier==first_key else {}}
        stage = (project.custom_attributes or {}).get('tender_stage')
        if stage:
            attributes['tender_stage'] = stage
        project.custom_attributes = attributes
    return 'customer_tenders',len(registry.keys() | monitoring.keys())
