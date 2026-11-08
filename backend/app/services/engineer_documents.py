"""Read the customer engineer matrix and resolve its private Drive attachments."""

import re
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath

from openpyxl import load_workbook

from app.services.google_drive import DriveFileInfo, GoogleDriveClient

SOURCE_NAME = "Документы инженеров"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"


def is_engineer_source(name: str, mime_type: str) -> bool:
    return name.strip().casefold() == SOURCE_NAME.casefold() and mime_type == GOOGLE_SHEET


FILE_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
KEYWORDS = (
    r"\bтоми\b", r"\bвысот\w*", r"\bэлектробез\w*", r"\bпожар\w*|\bпмт\b",
    r"\bохран[аы] труда\b", r"\bмедосмотр\w*", r"\bпривив\w*",
    r"\bрадиац\w*",
)
DRIVE_ID = re.compile(r"^https://drive\.google\.com/(?:file/d/|open\?id=)([\w-]+)(?:[/?&#]|$)")


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", text.casefold().replace("ё", "е")))


TWO_DIGIT_DATE = re.compile(r"(d{1,2})\.(m{1,2})\.yy", re.IGNORECASE)


def source_date(value: date, number_format: str) -> dict[str, str]:
    match = TWO_DIGIT_DATE.fullmatch(number_format)
    if not match:
        return {"value": value.isoformat()[:10]}

    # This operational register uses two-digit years in the 2000s.
    year = value.year % 100
    normalized = value.replace(year=2000 + year)
    day = str(value.day).zfill(len(match[1]))
    month = str(value.month).zfill(len(match[2]))
    return {"value": normalized.isoformat()[:10], "display": f"{day}.{month}.{year:02d}"}


def parse_engineer_documents(data: bytes, files: list[DriveFileInfo]) -> list[dict]:
    workbook = load_workbook(BytesIO(data), data_only=True)
    try:
        sheet = workbook.active
        if normalize(str(sheet["D1"].value)) != "фио сотрудника":
            raise ValueError("Изменился заголовок матрицы документов инженеров")
        columns = [(cell.column, cell.value.strip()) for cell in sheet[2][3:]
                   if isinstance(cell.value, str) and cell.value.strip()]
        if not columns:
            raise ValueError("В матрице документов инженеров нет заголовков сотрудников")

        blocks = []
        for row in sheet.iter_rows(min_row=3):
            number = row[0].value
            title = row[1].value
            if isinstance(number, (int, float)) and isinstance(title, str):
                # Group 9 is a shared reference block, outside the employee matrix.
                if number == 9:
                    break
                blocks.append((title.strip(), []))
            if blocks:
                blocks[-1][1].append(row)
        if [rows[0][0].value for _, rows in blocks] != list(range(1, len(KEYWORDS) + 1)):
            raise ValueError("Изменились группы документов в матрице инженеров")

        people = []
        identities = [normalize(name).split()[0] for _, name in columns]
        for (column, name), surname in zip(columns, identities):
            documents = []
            for (title, rows), keyword in zip(blocks, KEYWORDS):
                entries, explicit = [], set()
                for row in rows:
                    cell = row[column - 1]
                    if cell.hyperlink and cell.hyperlink.target:
                        if match := DRIVE_ID.match(cell.hyperlink.target):
                            explicit.add(match[1])
                    value = cell.value
                    if value is None:
                        continue
                    if isinstance(value, str) and (match := DRIVE_ID.match(value)):
                        explicit.add(match[1])
                        continue
                    label = row[2].value or (row[1].value if row is not rows[0] else None)
                    entries.append({
                        "label": str(label) if label else None,
                        "is_date": isinstance(value, date),
                        **(source_date(value, cell.number_format) if isinstance(value, date)
                           else {"value": str(value)}),
                    })

                attachments = []
                for file in files:
                    if file.mime_type not in FILE_TYPES or not re.fullmatch(r"[\w-]+", file.id):
                        continue
                    filename = normalize(PurePosixPath(file.name).stem)
                    inferred = (not explicit and identities.count(surname) == 1
                                and surname in filename.split() and re.search(keyword, filename))
                    if file.id in explicit or inferred:
                        attachments.append({
                            "name": file.name,
                            "url": f"https://drive.google.com/file/d/{file.id}/view",
                        })
                documents.append({
                    "title": title,
                    "entries": entries,
                    "attachments": sorted(attachments, key=lambda file: file["name"].casefold()),
                    "match": "sheet" if explicit else "filename",
                })
            people.append({"name": name, "column": column, "documents": documents})
        return people
    finally:
        workbook.close()


def read_engineer_documents(client: GoogleDriveClient, source: DriveFileInfo) -> dict:
    if not client.resolve_folder_id("удостоверения"):
        raise ValueError("Папка удостоверений недоступна")
    files = client.list_files_in_folder("удостоверения")
    people = parse_engineer_documents(client.download_file_bytes(source.id), files)
    return {
        "source_url": f"https://docs.google.com/spreadsheets/d/{source.id}/view",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "people": people,
    }
