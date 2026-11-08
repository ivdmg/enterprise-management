from datetime import date
from io import BytesIO
from types import SimpleNamespace

from openpyxl import Workbook

from app.services.engineer_documents import parse_engineer_documents


def test_engineer_matrix_keeps_source_dates_and_matches_exact_surname():
    book = Workbook()
    sheet = book.active
    sheet["D1"] = "ФИО сотрудника"
    sheet["D2"] = "Иванов"
    sheet["E2"] = "Иванова"
    for number in range(1, 10):
        row = 2 * number + 1
        sheet.cell(row, 1, number)
        sheet.cell(row, 2, f"Документ {number}")
    sheet["D4"] = "да"
    sheet["E4"] = "нет"
    sheet["D14"] = date(2026, 10, 24)
    sheet["D8"] = date(1930, 10, 4)
    sheet["D8"].number_format = "d.m.yy"
    sheet["E8"] = date(1931, 11, 5)
    sheet["E8"].number_format = "dd.mm.yyyy"
    sheet["E20"] = "бессрочно"
    data = BytesIO()
    book.save(data)
    files = [
        SimpleNamespace(id="doc-a", name="ТОМИ Иванов.pdf", mime_type="application/pdf"),
        SimpleNamespace(id="doc-b", name="ТОМИ Иванова.pdf", mime_type="application/pdf"),
    ]

    first, second = parse_engineer_documents(data.getvalue(), files)

    assert len(first["documents"]) == len(second["documents"]) == 8
    assert first["documents"][0]["attachments"] == [
        {"name": "ТОМИ Иванов.pdf", "url": "https://drive.google.com/file/d/doc-a/view"}
    ]
    assert second["documents"][0]["attachments"] == [
        {"name": "ТОМИ Иванова.pdf", "url": "https://drive.google.com/file/d/doc-b/view"}
    ]
    assert first["documents"][5]["entries"] == [
        {"label": None, "value": "2026-10-24", "is_date": True}
    ]
    assert second["documents"][5]["entries"] == []


    assert first["documents"][2]["entries"] == [
        {"label": None, "value": "2030-10-04", "display": "4.10.30", "is_date": True}
    ]
    assert second["documents"][2]["entries"] == [
        {"label": None, "value": "1931-11-05", "is_date": True}
    ]
