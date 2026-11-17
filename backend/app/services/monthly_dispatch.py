import re
import shutil
from datetime import date
from functools import lru_cache
from io import BytesIO
from zipfile import ZipFile

from openpyxl import load_workbook

from app.services.customer_tenders import cell, key

EMPTY_STYLED_CELL = re.compile(rb'<c r="[A-Z]+[0-9]+" s="[0-9]+"\s*/>')
DISPATCH_WORKBOOK_NAMES = {
    "менеджер выполнение помесячное.xlsx", "менеджер выполнения помесячное.xlsx",
}


def compact_dispatch_workbook(content: bytes) -> BytesIO:
    """Drop formatting-only cells before decoding the very wide monthly sheet."""
    result = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(result, "w") as target:
        for member in source.infolist():
            with source.open(member) as incoming, target.open(member.filename, "w") as outgoing:
                if not member.filename.startswith("xl/worksheets/sheet") or member.file_size < 10_000_000:
                    shutil.copyfileobj(incoming, outgoing)
                    continue
                remainder = b""
                while chunk := incoming.read(1024 * 1024):
                    chunk = remainder + chunk
                    boundary = chunk.rfind(b">") + 1
                    outgoing.write(EMPTY_STYLED_CELL.sub(b"", chunk[:boundary]))
                    remainder = chunk[boundary:]
                outgoing.write(remainder)
    result.seek(0)
    return result


def read_monthly_dispatch(content: bytes) -> list[dict]:
    workbook = load_workbook(compact_dispatch_workbook(content), data_only=True, read_only=True)
    try:
        sheet = workbook["Лист1"]
        rows = sheet.values
        header = next(rows, ())
        if len(header) < 9 or header[:2] != ("вн.№", "Заказчик") or header[3] != "Город":
            raise ValueError("Не найдены заголовки помесячного графика")
        dates = {index: cell(value) for index, value in enumerate(header[8:], 8) if isinstance(value, date)}
        if not dates:
            raise ValueError("В помесячном графике нет дат")
        records = []
        for number, row in enumerate(rows, 2):
            code = key(row[0]) if row else ""
            if len(row) < 2 or not code or code.startswith("#") or not row[1]:
                continue
            details = dict(zip(("customer", "work", "city", "frequency", "work_type", "status", "assignee"),
                               (cell(value) for value in row[1:8])))
            entries = {day: cell(row[index]) for index, day in dates.items()
                       if index < len(row) and row[index] not in (None, "")}
            records.append(dict(row=number, code=code, entries=entries, **details))
        return records
    finally:
        workbook.close()


@lru_cache(maxsize=1)
def read_drive_schedule(client, file_id, version):
    return read_monthly_dispatch(client.download_file_bytes(file_id))


def load_monthly_dispatch(client):
    sources = [file for file in client.list_files_in_folder("root")
               if file.name.casefold() in DISPATCH_WORKBOOK_NAMES]
    if not sources:
        return None
    if len(sources) != 1:
        raise ValueError("Найдено несколько помесячных графиков")
    source = sources[0]
    version = (source.modified_time, source.md5_checksum)
    return dict(link=source.web_view_link, records=read_drive_schedule(client, source.id, version))
