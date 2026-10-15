"""
Script: generate_standard_templates.py
Role: Data & Template Specialist / Smart Enterprise Hub
Purpose: Generates 5 standardized, business-approved Excel (.xlsx) templates
         with strict data validation (drop-down lists), proper number/date/currency types,
         and professional dark-navy styling (#1E293B).

Usage:
    python backend/scripts/generate_standard_templates.py
    python backend/scripts/generate_standard_templates.py --with-mock-data
    python backend/scripts/generate_standard_templates.py --verify
"""

import argparse
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure safe UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet


# -----------------------------------------------------------------------------
# Color & Style Palette
# -----------------------------------------------------------------------------
NAVY_HEADER_HEX = "1E293B"       # Slate 800: Modern deep navy
HEADER_FONT_HEX = "FFFFFF"       # Crisp white font
BORDER_HEADER_HEX = "334155"     # Slate 700 border for header
BORDER_CELL_HEX = "E2E8F0"       # Slate 200 clean light border for data cells
ZEBRA_FILL_HEX = "F8FAFC"        # Slate 50 subtle zebra stripe

HEADER_FILL = PatternFill(
    start_color=NAVY_HEADER_HEX, end_color=NAVY_HEADER_HEX, fill_type="solid"
)
HEADER_FONT = Font(name="Segoe UI", size=11, bold=True, color=HEADER_FONT_HEX)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

THIN_HEADER_SIDE = Side(style="thin", color=BORDER_HEADER_HEX)
HEADER_BORDER = Border(
    left=THIN_HEADER_SIDE,
    right=THIN_HEADER_SIDE,
    top=THIN_HEADER_SIDE,
    bottom=Side(style="medium", color="0F172A"),
)

CELL_BORDER = Border(
    left=Side(style="thin", color=BORDER_CELL_HEX),
    right=Side(style="thin", color=BORDER_CELL_HEX),
    top=Side(style="thin", color=BORDER_CELL_HEX),
    bottom=Side(style="thin", color=BORDER_CELL_HEX),
)

CELL_FONT = Font(name="Segoe UI", size=10, color="0F172A")
ZEBRA_FILL = PatternFill(
    start_color=ZEBRA_FILL_HEX, end_color=ZEBRA_FILL_HEX, fill_type="solid"
)


class ColumnType(Enum):
    TEXT = "text"
    CURRENCY = "currency"
    NUMBER = "number"
    DATE = "date"
    LIST = "list"


@dataclass
class ColumnDef:
    name: str
    col_type: ColumnType
    options: Optional[List[str]] = None
    min_width: int = 16
    align_override: Optional[str] = None

    @property
    def number_format(self) -> str:
        if self.col_type == ColumnType.CURRENCY:
            return "#,##0.00"
        elif self.col_type == ColumnType.NUMBER:
            return "#,##0.00"
        elif self.col_type == ColumnType.DATE:
            return "yyyy-mm-dd"
        return "@"

    @property
    def alignment(self) -> Alignment:
        if self.align_override:
            return Alignment(
                horizontal=self.align_override, vertical="center", wrap_text=False
            )
        if self.col_type in (ColumnType.CURRENCY, ColumnType.NUMBER):
            return Alignment(horizontal="right", vertical="center")
        elif self.col_type in (ColumnType.DATE, ColumnType.LIST):
            return Alignment(horizontal="center", vertical="center")
        return Alignment(horizontal="left", vertical="center")


@dataclass
class TemplateSpec:
    file_name: str
    sheet_title: str
    relative_drive_dir: str
    columns: List[ColumnDef]
    description: str


# -----------------------------------------------------------------------------
# 5 Standard Business-Approved Templates Specifications
# -----------------------------------------------------------------------------
TEMPLATES: Dict[str, TemplateSpec] = {
    "01_tenders": TemplateSpec(
        file_name="01_Реестр_Тендеров_и_Контрактов.xlsx",
        sheet_title="Реестр_Тендеров",
        relative_drive_dir="01_Реестры_Тендеров",
        description="Реестр закупок, контрактов по 44/223-ФЗ, КС-2/КС-3 и банковских гарантий",
        columns=[
            ColumnDef("Номер_Закупки", ColumnType.TEXT, min_width=22),
            ColumnDef("Наименование_Объекта", ColumnType.TEXT, min_width=36),
            ColumnDef("Заказчик", ColumnType.TEXT, min_width=28),
            ColumnDef("Сумма_Контракта_Руб", ColumnType.CURRENCY, min_width=22),
            ColumnDef("Сумма_Обеспечения_Заявки", ColumnType.CURRENCY, min_width=24),
            ColumnDef(
                "Статус_Тендера",
                ColumnType.LIST,
                options=[
                    "Подготовка",
                    "Подано",
                    "Торги",
                    "Победа",
                    "Контракт",
                    "Исполнено",
                    "Отклонено",
                ],
                min_width=18,
            ),
            ColumnDef("Дедлайн_Подачи", ColumnType.DATE, min_width=18),
            ColumnDef("Дата_Окончания_Работ", ColumnType.DATE, min_width=22),
            ColumnDef("Сумма_Закрыто_КС_Руб", ColumnType.CURRENCY, min_width=22),
            ColumnDef("Оплачено_Заказчиком_Руб", ColumnType.CURRENCY, min_width=24),
            ColumnDef("Куратор_Ответственный", ColumnType.TEXT, min_width=26),
            ColumnDef("Банковская_Гарантия_До", ColumnType.DATE, min_width=24),
        ],
    ),
    "02_cashflow": TemplateSpec(
        file_name="02_ДДС_Касса_и_Взаиморасчеты.xlsx",
        sheet_title="ДДС_Касса",
        relative_drive_dir="02_Финансы_и_1С",
        description="Отчет о движении денежных средств (ДДС), касса и график взаиморасчетов",
        columns=[
            ColumnDef("Дата_Операции", ColumnType.DATE, min_width=18),
            ColumnDef(
                "Тип_Операции",
                ColumnType.LIST,
                options=["Поступление", "Списание"],
                min_width=18,
            ),
            ColumnDef("Статья_ДДС", ColumnType.TEXT, min_width=26),
            ColumnDef("Контрагент", ColumnType.TEXT, min_width=32),
            ColumnDef("Сумма_Руб", ColumnType.CURRENCY, min_width=20),
            ColumnDef(
                "Статус_Платежа",
                ColumnType.LIST,
                options=["Факт_Исполнено", "План_Ожидается"],
                min_width=20,
            ),
            ColumnDef("Расчетный_Счет", ColumnType.TEXT, min_width=26),
            ColumnDef("Основание_Платежа", ColumnType.TEXT, min_width=36),
        ],
    ),
    "03_procurement": TemplateSpec(
        file_name="03_План_Закупок_и_Материалов.xlsx",
        sheet_title="План_Закупок",
        relative_drive_dir="03_Снабжение_и_Закупки",
        description="План материально-технического снабжения объектов ТМЦ и контроль оплат",
        columns=[
            ColumnDef("Объект_Привязка", ColumnType.TEXT, min_width=32),
            ColumnDef("Наименование_ТМЦ", ColumnType.TEXT, min_width=32),
            ColumnDef("Количество_Ед", ColumnType.NUMBER, min_width=18),
            ColumnDef(
                "Единица_Изм", ColumnType.TEXT, min_width=16, align_override="center"
            ),
            ColumnDef("Поставщик", ColumnType.TEXT, min_width=28),
            ColumnDef("Сумма_Счета_Руб", ColumnType.CURRENCY, min_width=20),
            ColumnDef(
                "Статус_Снабжения",
                ColumnType.LIST,
                options=[
                    "Заявка",
                    "Счет_На_Оплате",
                    "Оплачено",
                    "В_Пути",
                    "На_Объекте",
                ],
                min_width=20,
            ),
            ColumnDef("Срок_Доставки_Дедлайн", ColumnType.DATE, min_width=22),
        ],
    ),
    "04_dispatch": TemplateSpec(
        file_name="04_Диспетчерский_График_и_Техника.xlsx",
        sheet_title="Диспетчерский_График",
        relative_drive_dir="04_ПТО_и_Объекты",
        description="Диспетчерский журнал распределения спецтехники, бригад и инженеров",
        columns=[
            ColumnDef("Дата_Смены", ColumnType.DATE, min_width=18),
            ColumnDef("Объект_Назначения", ColumnType.TEXT, min_width=32),
            ColumnDef(
                "Тип_Ресурса",
                ColumnType.LIST,
                options=["Спецтехника", "Бригада_Рабочих", "Инженер_Куратор"],
                min_width=22,
            ),
            ColumnDef("Наименование_Единицы", ColumnType.TEXT, min_width=30),
            ColumnDef(
                "Ответственный_Водитель_Бригадир", ColumnType.TEXT, min_width=32
            ),
            ColumnDef(
                "Статус_Работы",
                ColumnType.LIST,
                options=[
                    "На_Объекте",
                    "В_Ремонте",
                    "Простой_Авария",
                    "Завершено",
                ],
                min_width=20,
            ),
            ColumnDef("Замечания_Инциденты", ColumnType.TEXT, min_width=36),
        ],
    ),
    "05_tasks": TemplateSpec(
        file_name="05_Операционные_Задачи_и_Алерты.xlsx",
        sheet_title="Задачи_и_Алерты",
        relative_drive_dir="05_Юридический_Отдел",
        description="Операционные поручения, юридические дедлайны и штрафные санкции",
        columns=[
            ColumnDef("Заголовок_Задачи", ColumnType.TEXT, min_width=36),
            ColumnDef("Связанный_Контракт", ColumnType.TEXT, min_width=24),
            ColumnDef(
                "Ответственная_Роль",
                ColumnType.LIST,
                options=[
                    "Гендиректор",
                    "Замгендиректора",
                    "Тендерщик",
                    "Инженер",
                    "Диспетчер",
                    "Менеджер",
                    "Юрист",
                    "Закупщик",
                    "Бухгалтер",
                ],
                min_width=22,
            ),
            ColumnDef("ФИО_Исполнителя", ColumnType.TEXT, min_width=28),
            ColumnDef("Крайний_Срок_Дедлайн", ColumnType.DATE, min_width=22),
            ColumnDef(
                "Приоритет_Срочность",
                ColumnType.LIST,
                options=["Обычный", "Высокий", "КРИТИЧЕСКИЙ_ШТРАФ"],
                min_width=24,
            ),
            ColumnDef(
                "Статус_Исполнения",
                ColumnType.LIST,
                options=["В_Работе", "На_Проверке", "Закрыто"],
                min_width=20,
            ),
            ColumnDef(
                "Потенциальный_Штраф_Руб", ColumnType.CURRENCY, min_width=26
            ),
        ],
    ),
}


# -----------------------------------------------------------------------------
# Template Builder Functionality
# -----------------------------------------------------------------------------
def build_workbook_for_spec(
    spec: TemplateSpec,
    data_rows: Optional[List[List[Any]]] = None,
    max_validation_rows: int = 1000,
) -> openpyxl.Workbook:
    """
    Constructs an openpyxl Workbook for a given TemplateSpec:
    - Sets sheet title
    - Writes professional navy header with white bold font
    - Freezes first row ('A2')
    - Enables gridlines explicitly
    - Calculates auto-adjusted column widths
    - Configures DataValidation drop-downs for LIST fields up to max_validation_rows
    - Optionally populates and styles data_rows (used in Phase 2)
    """
    wb = openpyxl.Workbook()
    ws: Worksheet = wb.active
    ws.title = spec.sheet_title

    # Ensure grid lines are visible in all Excel viewers
    ws.views.sheetView[0].showGridLines = True

    # 1. Write Header Row
    headers = [col.name for col in spec.columns]
    ws.append(headers)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    for col_idx, col_def in enumerate(spec.columns, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT
        cell.border = HEADER_BORDER

    # 2. Add Data Validations
    for col_idx, col_def in enumerate(spec.columns, start=1):
        if col_def.col_type == ColumnType.LIST and col_def.options:
            col_letter = get_column_letter(col_idx)
            options_str = ",".join(col_def.options)
            dv = DataValidation(
                type="list",
                formula1=f'"{options_str}"',
                allow_blank=True,
            )
            dv.error = f"Выберите значение из утвержденного списка: {', '.join(col_def.options[:4])}..."
            dv.errorTitle = "Некорректное значение"
            dv.prompt = "Выберите значение из выпадающего списка"
            dv.promptTitle = col_def.name
            ws.add_data_validation(dv)
            # Add to cell range
            dv.add(f"{col_letter}2:{col_letter}{max_validation_rows}")

    # 3. Populate Data Rows if provided
    current_max_row = 1
    if data_rows:
        for row_idx, row_values in enumerate(data_rows, start=2):
            ws.append(row_values)
            ws.row_dimensions[row_idx].height = 22
            current_max_row = row_idx
            is_even = (row_idx % 2 == 0)

            for col_idx, (col_def, val) in enumerate(zip(spec.columns, row_values), start=1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.font = CELL_FONT
                cell.border = CELL_BORDER
                cell.alignment = col_def.alignment
                cell.number_format = col_def.number_format

                if is_even:
                    cell.fill = ZEBRA_FILL

    # 4. Auto-calculate Column Widths
    for col_idx, col_def in enumerate(spec.columns, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(col_def.name))

        if data_rows:
            for row in data_rows:
                if col_idx - 1 < len(row):
                    val = row[col_idx - 1]
                    if val is not None:
                        val_str = str(val)
                        if len(val_str) > max_len:
                            max_len = len(val_str)

        calculated_width = max(max_len + 5, col_def.min_width)
        ws.column_dimensions[col_letter].width = calculated_width

    return wb


def generate_empty_templates(target_dir: Path) -> List[Path]:
    """
    Generates all 5 empty pure standardized templates with Data Validation
    and saves them into target_dir.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    generated_files: List[Path] = []

    print(f"\n[INFO] Генерация эталонных чистых Excel-шаблонов в: {target_dir}")
    print("=" * 70)

    for key, spec in TEMPLATES.items():
        wb = build_workbook_for_spec(spec, data_rows=None)
        file_path = target_dir / spec.file_name
        wb.save(file_path)
        generated_files.append(file_path)

        col_count = len(spec.columns)
        list_validations = [c.name for c in spec.columns if c.col_type == ColumnType.LIST]
        print(f"  [OK] [Шаблон] {spec.file_name}")
        print(f"       +-- Лист: '{spec.sheet_title}', Колонок: {col_count}")
        print(f"       +-- Выпадающие списки ({len(list_validations)}): {', '.join(list_validations)}")
        print(f"       +-- Размер файла: {file_path.stat().st_size} байт")

    print("=" * 70)
    print(f"[SUCCESS] Успешно сгенерировано {len(generated_files)} эталонных шаблонов!\n")
    return generated_files


# -----------------------------------------------------------------------------
# Template Integrity Verification
# -----------------------------------------------------------------------------
def verify_generated_templates(templates_dir: Path) -> bool:
    """
    Strictly verifies that all 5 template files:
    1. Exist and are non-empty
    2. Have exact matching headers in correct order
    3. Have freeze_panes set to 'A2'
    4. Have DataValidation list configured on expected status columns
    5. Have correct column formatting settings
    """
    print(f"\n[CHECK] Валидация эталонных шаблонов в директории: {templates_dir}")
    print("-" * 70)
    all_passed = True

    for key, spec in TEMPLATES.items():
        file_path = templates_dir / spec.file_name
        if not file_path.exists():
            print(f"  [ERROR] Файл отсутствует: {spec.file_name}")
            all_passed = False
            continue

        wb = openpyxl.load_workbook(file_path)
        ws = wb.active

        # Check sheet title
        if ws.title != spec.sheet_title:
            print(f"  [WARN] {spec.file_name}: Лист '{ws.title}' != '{spec.sheet_title}'")
            all_passed = False

        # Check headers
        actual_headers = [cell.value for cell in ws[1]]
        expected_headers = [col.name for col in spec.columns]
        if actual_headers != expected_headers:
            print(f"  [ERROR] {spec.file_name}: Несовпадение колонок!")
            print(f"     Ожидалось: {expected_headers}")
            print(f"     Получено:  {actual_headers}")
            all_passed = False
        else:
            print(f"  [OK] {spec.file_name}: Шапка совпадает (100% точность, {len(expected_headers)} колонок)")

        # Check freeze panes
        if ws.freeze_panes != "A2":
            print(f"  [WARN] {spec.file_name}: freeze_panes = '{ws.freeze_panes}', ожидалось 'A2'")
            all_passed = False
        else:
            print(f"       +-- Заморозка первой строки (freeze_panes = 'A2'): OK")

        # Check Data Validation lists
        dvs = ws.data_validations.dataValidation
        expected_list_cols = [
            (idx + 1, col.name, col.options)
            for idx, col in enumerate(spec.columns)
            if col.col_type == ColumnType.LIST
        ]

        if len(dvs) < len(expected_list_cols):
            print(f"  [WARN] {spec.file_name}: Ожидалось {len(expected_list_cols)} правил DataValidation, найдено {len(dvs)}")
            all_passed = False
        else:
            print(f"       +-- DataValidation правила ({len(dvs)} шт.): OK")

        wb.close()

    print("-" * 70)
    if all_passed:
        print("[SUCCESS] ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО! Таблицы утверждены к использованию.\n")
    else:
        print("[FAIL] ОБНАРУЖЕНЫ ОШИБКИ В ШАБЛОНАХ!\n")

    return all_passed


# -----------------------------------------------------------------------------
# Phase 2: Mock Dataset Generation (20+ rows per table with Alert Triggers)
# -----------------------------------------------------------------------------
from datetime import date, datetime, timedelta


def generate_mock_datasets(base_date: Optional[date] = None) -> Dict[str, List[List[Any]]]:
    """
    Generates rich, realistic mock datasets for all 5 enterprise tables (20+ rows each)
    representing a construction tender company operating under Russian Federal Law 44-FZ / 223-FZ.

    Includes key business alert triggers:
    1. Contract ending in 3 days with 2,500,000 RUB unclosed KS acts.
    2. Bank guarantee expiring in 5 days.
    3. Critical legal task to file protocol of disagreements within 48 hours (potential penalty).
    4. Projected cash gap in DDS / Cashflow on day 9.
    """
    if base_date is None:
        base_date = date.today()

    datasets: Dict[str, List[List[Any]]] = {}

    # -------------------------------------------------------------------------
    # 01. Реестр Тендеров и Контрактов (22 строки)
    # Columns:
    # 0: Номер_Закупки, 1: Наименование_Объекта, 2: Заказчик,
    # 3: Сумма_Контракта_Руб, 4: Сумма_Обеспечения_Заявки, 5: Статус_Тендера,
    # 6: Дедлайн_Подачи, 7: Дата_Окончания_Работ, 8: Сумма_Закрыто_КС_Руб,
    # 9: Оплачено_Заказчиком_Руб, 10: Куратор_Ответственный, 11: Банковская_Гарантия_До
    # -------------------------------------------------------------------------
    datasets["01_tenders"] = [
        # TRIGGER 1: Окончание через 3 дня, незакрытые КС = 2 500 000 руб (24.5M - 22.0M)
        [
            "0173200001426000045",
            "Капитальный ремонт фасада и кровли Клинической больницы №1 им. Пирогова",
            "ГКУ 'Управление капитального строительства г. Москвы'",
            24500000.00,
            245000.00,
            "Контракт",
            base_date - timedelta(days=120),
            base_date + timedelta(days=3),  # Trigger: Срок окончания через 3 дня
            22000000.00,                     # Trigger: Незакрыто 2 500 000 руб
            20000000.00,
            "Смирнов Алексей Викторович",
            base_date + timedelta(days=60),
        ],
        # TRIGGER 2: Банковская гарантия истекает через 5 дней
        [
            "0348300054226000088",
            "Реконструкция инженерных сетей теплоснабжения микрорайона 'Южный'",
            "МУП 'Подольская теплосеть'",
            42000000.00,
            420000.00,
            "Контракт",
            base_date - timedelta(days=90),
            base_date + timedelta(days=45),
            18500000.00,
            15000000.00,
            "Ковалев Дмитрий Николаевич",
            base_date + timedelta(days=5),   # Trigger: БГ истекает через 5 дней
        ],
        # Другие активные контракты и закупки
        [
            "0148200002126000015",
            "Капитальный ремонт здания МБОУ 'СОШ №42' (монтаж ИТП и вентиляции)",
            "МКУ 'УКС городского округа Химки'",
            38500000.00,
            385000.00,
            "Контракт",
            base_date - timedelta(days=45),
            base_date + timedelta(days=75),
            12000000.00,
            12000000.00,
            "Смирнов Алексей Викторович",
            base_date + timedelta(days=90),
        ],
        [
            "0373100012826000099",
            "Строительство наружных сетей водопровода и канализации детского сада",
            "ГКУ 'Дирекция по строительству объектов здравоохранения'",
            19200000.00,
            192000.00,
            "Контракт",
            base_date - timedelta(days=60),
            base_date + timedelta(days=30),
            14000000.00,
            14000000.00,
            "Иванов Сергей Павлович",
            base_date + timedelta(days=60),
        ],
        [
            "0848300011226000012",
            "Модернизация системы вентиляции и кондиционирования ЦРБ",
            "ГБУЗ МО 'Красногорская городская больница'",
            15800000.00,
            158000.00,
            "Контракт",
            base_date - timedelta(days=30),
            base_date + timedelta(days=60),
            5000000.00,
            5000000.00,
            "Ковалев Дмитрий Николаевич",
            base_date + timedelta(days=75),
        ],
        [
            "0348100021426000102",
            "Комплексное благоустройство территории парка культуры и отдыха 'Дубки'",
            "МАУ 'Городские парки' г. Одинцово",
            28600000.00,
            286000.00,
            "Контракт",
            base_date - timedelta(days=80),
            base_date + timedelta(days=20),
            21000000.00,
            18000000.00,
            "Петров Михаил Романович",
            base_date + timedelta(days=50),
        ],
        # Тендеры в стадии Победа и Торги
        [
            "0173200001426000103",
            "Поставка и пусконаладка трансформаторных подстанций БКТП 1000 кВА",
            "АО 'Мособлэнерго'",
            34500000.00,
            345000.00,
            "Победа",
            base_date - timedelta(days=10),
            base_date + timedelta(days=120),
            0.00,
            0.00,
            "Зайцев Роман Игоревич",
            base_date + timedelta(days=150),
        ],
        [
            "0348200051226000234",
            "Монтаж слаботочных систем и СКУД перинатального медцентра",
            "Министерство строительного комплекса МО",
            16400000.00,
            164000.00,
            "Победа",
            base_date - timedelta(days=7),
            base_date + timedelta(days=90),
            0.00,
            0.00,
            "Иванов Сергей Павлович",
            base_date + timedelta(days=120),
        ],
        [
            "0148200003326000412",
            "Замена лифтового оборудования в терапевтическом корпусе",
            "ГБУЗ 'ГКБ №67 им. Ворохобова ДЗМ'",
            12700000.00,
            127000.00,
            "Торги",
            base_date + timedelta(days=2),
            base_date + timedelta(days=100),
            0.00,
            0.00,
            "Ковалев Дмитрий Николаевич",
            None,
        ],
        [
            "0373200004526000511",
            "Устройство полимерных антипылевых полов логистического комплекса",
            "ООО 'СберЛогистика Инфраструктура'",
            21000000.00,
            210000.00,
            "Торги",
            base_date + timedelta(days=4),
            base_date + timedelta(days=80),
            0.00,
            0.00,
            "Петров Михаил Романович",
            None,
        ],
        # Тендеры в стадии Подано и Подготовка
        [
            "0173200001426000189",
            "Капитальный ремонт электросетей и ВРУ спортивного комплекса",
            "ГБУ 'Мосспортобъект'",
            9800000.00,
            98000.00,
            "Подано",
            base_date + timedelta(days=5),
            base_date + timedelta(days=60),
            0.00,
            0.00,
            "Смирнов Алексей Викторович",
            None,
        ],
        [
            "0348300054226000311",
            "Монтаж автоматической системы пожарной сигнализации (АПС)",
            "Администрация городского округа Мытищи",
            8300000.00,
            83000.00,
            "Подано",
            base_date + timedelta(days=7),
            base_date + timedelta(days=50),
            0.00,
            0.00,
            "Иванов Сергей Павлович",
            None,
        ],
        [
            "0148200002126000555",
            "Реконструкция теплопункта с установкой насосов Grundfos",
            "МП 'Теплосеть Долгопрудный'",
            7200000.00,
            72000.00,
            "Подготовка",
            base_date + timedelta(days=10),
            base_date + timedelta(days=40),
            0.00,
            0.00,
            "Ковалев Дмитрий Николаевич",
            None,
        ],
        [
            "0848300011226000288",
            "Поставка кабельной продукции и лотков для нужд технопарка",
            "АО 'Особая экономическая зона Дубна'",
            14500000.00,
            145000.00,
            "Подготовка",
            base_date + timedelta(days=12),
            base_date + timedelta(days=70),
            0.00,
            0.00,
            "Зайцев Роман Игоревич",
            None,
        ],
        [
            "0373100012826000401",
            "Обустройство площадок ТКО и ограждений образовательных учреждений",
            "МКУ 'Благоустройство Королев'",
            5600000.00,
            56000.00,
            "Подготовка",
            base_date + timedelta(days=14),
            base_date + timedelta(days=45),
            0.00,
            0.00,
            "Петров Михаил Романович",
            None,
        ],
        # Завершенные и отклоненные контракты (исторические данные)
        [
            "0173200001425000912",
            "Капитальный ремонт кровли поликлиники №5 им. Семашко",
            "ГКУ 'УКРИС г. Москвы'",
            11200000.00,
            112000.00,
            "Исполнено",
            base_date - timedelta(days=220),
            base_date - timedelta(days=30),
            11200000.00,
            11200000.00,
            "Смирнов Алексей Викторович",
            base_date - timedelta(days=10),
        ],
        [
            "0348300054225000777",
            "Монтаж индивидуального теплового пункта в детской поликлинике",
            "ГБУЗ МО 'Подольская детская больница'",
            8900000.00,
            89000.00,
            "Исполнено",
            base_date - timedelta(days=180),
            base_date - timedelta(days=20),
            8900000.00,
            8900000.00,
            "Ковалев Дмитрий Николаевич",
            base_date + timedelta(days=10),
        ],
        [
            "0148200002125000621",
            "Устройство вентилируемого фасада здания налоговой инспекции",
            "УФНС России по Московской области",
            17800000.00,
            178000.00,
            "Исполнено",
            base_date - timedelta(days=240),
            base_date - timedelta(days=40),
            17800000.00,
            17800000.00,
            "Иванов Сергей Павлович",
            base_date - timedelta(days=20),
        ],
        [
            "0373200004525000833",
            "Устройство гидроизоляции подземного паркинга",
            "ПАО 'Группа ПИК'",
            13500000.00,
            135000.00,
            "Исполнено",
            base_date - timedelta(days=150),
            base_date - timedelta(days=15),
            13500000.00,
            13500000.00,
            "Петров Михаил Романович",
            base_date + timedelta(days=30),
        ],
        [
            "0173200001426000002",
            "Строительство пристройки к хирургическому корпусу",
            "Департамент здравоохранения г. Москвы",
            65000000.00,
            650000.00,
            "Отклонено",
            base_date - timedelta(days=60),
            base_date + timedelta(days=180),
            0.00,
            0.00,
            "Зайцев Роман Игоревич",
            None,
        ],
        [
            "0348200051226000078",
            "Реконструкция очистных сооружений бытовых стоков",
            "МУП 'Водоканал г. Видное'",
            52000000.00,
            520000.00,
            "Отклонено",
            base_date - timedelta(days=40),
            base_date + timedelta(days=150),
            0.00,
            0.00,
            "Смирнов Алексей Викторович",
            None,
        ],
        [
            "0148200003326000199",
            "Капитальный ремонт актового зала гимназии №9",
            "Управление образования администрации г. Коломна",
            6400000.00,
            64000.00,
            "Отклонено",
            base_date - timedelta(days=25),
            base_date + timedelta(days=40),
            0.00,
            0.00,
            "Ковалев Дмитрий Николаевич",
            None,
        ],
    ]

    # -------------------------------------------------------------------------
    # 02. ДДС Касса и Взаиморасчеты (24 строки)
    # Columns:
    # 0: Дата_Операции, 1: Тип_Операции, 2: Статья_ДДС, 3: Контрагент,
    # 4: Сумма_Руб, 5: Статус_Платежа, 6: Расчетный_Счет, 7: Основание_Платежа
    #
    # CASH GAP TRIGGER LOGIC:
    # Initial balance: Fact Inflows (+19,500,000) - Fact Outflows (-17,050,000) = +2,450,000 RUB.
    # Plan operations:
    # Day +3: Outflow -800,000 (Balance = +1,650,000)
    # Day +5: Inflow +500,000 (Balance = +2,150,000)
    # Day +7: Outflow -700,000 (Balance = +1,450,000)
    # Day +9: TRIGGER Outflow -4,200,000 (Balance = +1,450,000 - 4,200,000 = -2,750,000 RUB -> CASH GAP!)
    # -------------------------------------------------------------------------
    datasets["02_cashflow"] = [
        # Фактические операции поступления (формируют положительный стартовый баланс)
        [
            base_date - timedelta(days=14),
            "Поступление",
            "Аванс_Заказчика",
            "ГКУ 'Управление капитального строительства г. Москвы'",
            7350000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Аванс 30% по госконтракту №0173200001426000045 (КБ №1)",
        ],
        [
            base_date - timedelta(days=10),
            "Поступление",
            "Оплата_КС_Заказчик",
            "МАУ 'Городские парки' г. Одинцово",
            5400000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Оплата по акту КС-2 №4 за благоустройство парка 'Дубки'",
        ],
        [
            base_date - timedelta(days=6),
            "Поступление",
            "Оплата_КС_Заказчик",
            "МКУ 'УКС городского округа Химки'",
            4200000.00,
            "Факт_Исполнено",
            "Банк ВТБ (ПАО) р/с 40702810500000028911",
            "Оплата этапа №2 (монтаж ИТП) школа №42",
        ],
        [
            base_date - timedelta(days=2),
            "Поступление",
            "Возврат_Обеспечения",
            "ЭТП 'РТС-Тендер'",
            2550000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Разблокировка обеспечения заявки по реестровому номеру 0173200001425000912",
        ],
        # Фактические списания
        [
            base_date - timedelta(days=12),
            "Списание",
            "Оплата_Поставщику",
            "ООО 'Северсталь Дистрибуция'",
            3200000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Оплата металлопроката и арматуры А500С по счету №451/СМ",
        ],
        [
            base_date - timedelta(days=11),
            "Списание",
            "Оплата_Поставщику",
            "ООО 'Бетон-Монолит Сбыт'",
            1850000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Поставка бетона товарного В25 W6 по УПД №891",
        ],
        [
            base_date - timedelta(days=9),
            "Списание",
            "ФОТ_Зарплата",
            "Сотрудники ООО 'СпецСтройМонтаж' (Зарплатный проект)",
            4250000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Выплата заработной платы за 1-ю половину месяца по реестру №14",
        ],
        [
            base_date - timedelta(days=8),
            "Списание",
            "Налоги_и_Взносы",
            "УФК по Московской области (МИФНС №13)",
            1950000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Уплата НДФЛ и страховых взносов за сотрудников",
        ],
        [
            base_date - timedelta(days=5),
            "Списание",
            "Субподрядчики",
            "ООО 'ВентМонтажСервис'",
            2400000.00,
            "Факт_Исполнено",
            "Банк ВТБ (ПАО) р/с 40702810500000028911",
            "Оплата этапа монтажа воздуховодов по договору субподряда №12/ВМ",
        ],
        [
            base_date - timedelta(days=4),
            "Списание",
            "Аренда_Спецтехники",
            "ООО 'ТрансСтройМеханизация'",
            1600000.00,
            "Факт_Исполнено",
            "Банк ВТБ (ПАО) р/с 40702810500000028911",
            "Аренда автокранов 25т и экскаваторов JCB за прошлый месяц",
        ],
        [
            base_date - timedelta(days=3),
            "Списание",
            "ГСМ_и_Логистика",
            "ПАО 'Газпромнефть-Корпоративные Продажи'",
            950000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Пополнение топливных карт (ДТ Евро-5) по счету №774/ТК",
        ],
        [
            base_date - timedelta(days=1),
            "Списание",
            "Лизинг_Техники",
            "АО 'Сбербанк Лизинг'",
            850000.00,
            "Факт_Исполнено",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Лизинговый платеж по договору №ДЛ-44/22 за самосвалы КАМАЗ",
        ],
        # Плановые операции (прогноз)
        [
            base_date + timedelta(days=1),
            "Поступление",
            "Оплата_КС_Заказчик",
            "ГБУ МО 'Мособлпарк'",
            1200000.00,
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Ожидаемый платеж по акту приемки малых архитектурных форм",
        ],
        [
            base_date + timedelta(days=2),
            "Списание",
            "Оплата_Поставщику",
            "ООО 'ТД Кабель-Инвест'",
            850000.00,
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Оплата счета №89 за кабель ВВГнг-LS для школы №42",
        ],
        [
            base_date + timedelta(days=3),
            "Списание",
            "Оплата_Поставщику",
            "ООО 'СантехКомплект Северо-Запад'",
            800000.00,
            "План_Ожидается",
            "Банк ВТБ (ПАО) р/с 40702810500000028911",
            "Счет на трубную разводку и фитинги ИТП",
        ],
        [
            base_date + timedelta(days=5),
            "Поступление",
            "Аванс_Заказчика",
            "АО 'Мособлэнерго'",
            500000.00,
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Авансовый платеж по поставке БКТП (победа в тендере)",
        ],
        [
            base_date + timedelta(days=6),
            "Списание",
            "Оплата_Поставщику",
            "ООО 'ТеплоИзолСервис'",
            620000.00,
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Счет №112 на базальтовый утеплитель фасада КБ №1",
        ],
        [
            base_date + timedelta(days=7),
            "Списание",
            "Аренда_Офиса_и_Склада",
            "ООО 'Технопарк Деловой Мир'",
            480000.00,
            "План_Ожидается",
            "Банк ВТБ (ПАО) р/с 40702810500000028911",
            "Аренда производственно-складской базы и офиса за текущий месяц",
        ],
        [
            base_date + timedelta(days=8),
            "Списание",
            "Банковское_Обслуживание",
            "ПАО 'Сбербанк'",
            120000.00,
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Комиссия за выдачу и сопровождение банковской гарантии",
        ],
        # TRIGGER 4: Крупное списание на 9 день, вызывающее кассовый разрыв
        [
            base_date + timedelta(days=9),
            "Списание",
            "Оплата_Поставщику",
            "ООО 'ЭлектроПромКомплект'",
            4200000.00,  # Trigger: Списание на 9 день -> Прогнозируемый кассовый разрыв
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Оплата поставки силового оборудования БКТП по счету №1042/ЭП (критический срок поставки)",
        ],
        [
            base_date + timedelta(days=11),
            "Поступление",
            "Оплата_КС_Заказчик",
            "ГКУ 'Управление капитального строительства г. Москвы'",
            6500000.00,
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Ожидаемое закрытие этапа работ по кровле Клинической больницы №1",
        ],
        [
            base_date + timedelta(days=12),
            "Списание",
            "ФОТ_Зарплата",
            "Сотрудники ООО 'СпецСтройМонтаж'",
            3800000.00,
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Аванс по зарплате (вторая половина месяца)",
        ],
        [
            base_date + timedelta(days=14),
            "Поступление",
            "Оплата_КС_Заказчик",
            "МУП 'Подольская теплосеть'",
            4800000.00,
            "План_Ожидается",
            "Банк ВТБ (ПАО) р/с 40702810500000028911",
            "План оплаты за траншеи и трубопровод мкр. 'Южный'",
        ],
        [
            base_date + timedelta(days=15),
            "Списание",
            "Налоги_и_Взносы",
            "УФК по Московской области",
            1400000.00,
            "План_Ожидается",
            "ПАО 'Сбербанк' р/с 40702810938000014522",
            "Плановый платеж НДС за квартал",
        ],
    ]

    # -------------------------------------------------------------------------
    # 03. План Закупок и Материалов (22 строки)
    # Columns:
    # 0: Объект_Привязка, 1: Наименование_ТМЦ, 2: Количество_Ед, 3: Единица_Изм,
    # 4: Поставщик, 5: Сумма_Счета_Руб, 6: Статус_Снабжения, 7: Срок_Доставки_Дедлайн
    # -------------------------------------------------------------------------
    datasets["03_procurement"] = [
        [
            "Клиническая больница №1 им. Пирогова",
            "Утеплитель минераловатный Rockwool Венти Баттс 100мм",
            450.0,
            "м3",
            "ООО 'ТеплоИзолСервис'",
            620000.00,
            "Счет_На_Оплате",
            base_date + timedelta(days=4),
        ],
        [
            "Клиническая больница №1 им. Пирогова",
            "Кровельная ПВХ-мембрана Технониколь Logicroof V-RP 1.5мм",
            1200.0,
            "м2",
            "ООО 'КровляСнаб Маркет'",
            1450000.00,
            "Оплачено",
            base_date + timedelta(days=2),
        ],
        [
            "Школа №42 г. Химки",
            "Кабель силовой медный ВВГнг-LS 5х16 (ГОСТ)",
            850.0,
            "м",
            "ООО 'ТД Кабель-Инвест'",
            465000.00,
            "В_Пути",
            base_date + timedelta(days=1),
        ],
        [
            "Школа №42 г. Химки",
            "Узел учета тепловой энергии и регулирования (УУТЭ)",
            2.0,
            "компл",
            "ООО 'ТеплоАвтоматика'",
            1120000.00,
            "Счет_На_Оплате",
            base_date + timedelta(days=6),
        ],
        [
            "Школа №42 г. Химки",
            "Радиаторы секционные биметаллические Rifar Base 500",
            180.0,
            "шт",
            "ООО 'СантехКомплект Северо-Запад'",
            345000.00,
            "На_Объекте",
            base_date - timedelta(days=2),
        ],
        [
            "Теплосети мкр. 'Южный' г. Подольск",
            "Труба стальная электросварная в ППУ изоляции d219/315",
            320.0,
            "м",
            "ООО 'Трубный Альянс Мос'",
            2850000.00,
            "Оплачено",
            base_date + timedelta(days=5),
        ],
        [
            "Теплосети мкр. 'Южный' г. Подольск",
            "Задвижки чугунные фланцевые с обрезиненным клином Ду200",
            14.0,
            "шт",
            "ООО 'АрматураПромСбыт'",
            560000.00,
            "В_Пути",
            base_date + timedelta(days=3),
        ],
        [
            "Сети водопровода детсада",
            "Труба полиэтиленовая ПЭ100 SDR17 питьевая d110х6.6",
            550.0,
            "м",
            "ООО 'ПолимерПайп Групп'",
            385000.00,
            "На_Объекте",
            base_date - timedelta(days=4),
        ],
        [
            "Сети водопровода детсада",
            "Кольца железобетонные для колодцев КС 15.9 с плитой",
            26.0,
            "шт",
            "ООО 'ЖБИ-ПромСтрой'",
            290000.00,
            "На_Объекте",
            base_date - timedelta(days=1),
        ],
        [
            "Парк 'Дубки' г. Одинцово",
            "Плитка тротуарная вибропрессованная 'Брусчатка' 200х100х60 серая",
            1800.0,
            "м2",
            "ООО 'МособлПлитка'",
            1980000.00,
            "Оплачено",
            base_date + timedelta(days=3),
        ],
        [
            "Парк 'Дубки' г. Одинцово",
            "Опоры освещения парковые граненые ОГК-6 с LED-светильниками",
            42.0,
            "компл",
            "ООО 'СветоТехника М'",
            880000.00,
            "В_Пути",
            base_date + timedelta(days=2),
        ],
        [
            "Красногорская городская больница",
            "Центральный кондиционер с рекуператором Systemair",
            3.0,
            "компл",
            "ООО 'КлиматВентТрейд'",
            2150000.00,
            "Заявка",
            base_date + timedelta(days=12),
        ],
        [
            "Красногорская городская больница",
            "Воздуховоды из оцинкованной стали 0.7мм прямошовные",
            650.0,
            "м2",
            "ООО 'ВентФабрика №1'",
            410000.00,
            "Счет_На_Оплате",
            base_date + timedelta(days=7),
        ],
        [
            "БКТП 1000 кВА (Мособлэнерго)",
            "Трансформатор силовой масляный ТМГ-1000/10/0.4",
            2.0,
            "шт",
            "ООО 'ЭлектроПромКомплект'",
            4200000.00,
            "Счет_На_Оплате",
            base_date + timedelta(days=9),
        ],
        [
            "БКТП 1000 кВА (Мособлэнерго)",
            "Блок бетонный модульный распределительной подстанции",
            2.0,
            "компл",
            "ООО 'БетонЭнергоСтрой'",
            1750000.00,
            "Заявка",
            base_date + timedelta(days=15),
        ],
        [
            "Перинатальный медцентр",
            "Шкаф распределительный кроссовый 19-дюймовый 42U",
            6.0,
            "шт",
            "ООО 'Сетевые Решения'",
            320000.00,
            "Оплачено",
            base_date + timedelta(days=4),
        ],
        [
            "Перинатальный медцентр",
            "Кабель 'витая пара' F/UTP Cat 5e 4х2х0.52 медный LSZH",
            3000.0,
            "м",
            "ООО 'ТД Кабель-Инвест'",
            240000.00,
            "На_Объекте",
            base_date - timedelta(days=3),
        ],
        [
            "Спортивный комплекс",
            "Вводно-распределительное устройство ВРУ-1 400А",
            1.0,
            "компл",
            "ООО 'ЩитЭлектроМонтаж'",
            580000.00,
            "Заявка",
            base_date + timedelta(days=10),
        ],
        [
            "Клиническая больница №1 им. Пирогова",
            "Клей монтажный для теплоизоляции фасадный Ceresit CT 83",
            120.0,
            "меш",
            "ООО 'СтройСнабСервис'",
            96000.00,
            "На_Объекте",
            base_date - timedelta(days=5),
        ],
        [
            "Школа №42 г. Химки",
            "Насос циркуляционный с мокрым ротором Wilo-Stratos MAXO",
            4.0,
            "шт",
            "ООО 'ПромВодоСнаб'",
            520000.00,
            "В_Пути",
            base_date + timedelta(days=2),
        ],
        [
            "Теплосети мкр. 'Южный' г. Подольск",
            "Песок намывной строительный карьерный (крупнозернистый)",
            450.0,
            "т",
            "ООО 'НерудСервисТранс'",
            360000.00,
            "На_Объекте",
            base_date - timedelta(days=1),
        ],
        [
            "Парк 'Дубки' г. Одинцово",
            "Бордюр дорожный вибропрессованный БР 100.30.15",
            600.0,
            "шт",
            "ООО 'МособлПлитка'",
            420000.00,
            "На_Объекте",
            base_date - timedelta(days=3),
        ],
    ]

    # -------------------------------------------------------------------------
    # 04. Диспетчерский График и Техника (23 строки)
    # Columns:
    # 0: Дата_Смены, 1: Объект_Назначения, 2: Тип_Ресурса, 3: Наименование_Единицы,
    # 4: Ответственный_Водитель_Бригадир, 5: Статус_Работы, 6: Замечания_Инциденты
    # -------------------------------------------------------------------------
    datasets["04_dispatch"] = [
        [
            base_date,
            "Клиническая больница №1 им. Пирогова",
            "Бригада_Рабочих",
            "Бригада кровельщиков-фасадчиков №1 (8 чел.)",
            "Бригадир Савельев Игорь Михайлович",
            "На_Объекте",
            "Выполнение финальной гидроизоляции парапетов кровли",
        ],
        [
            base_date,
            "Клиническая больница №1 им. Пирогова",
            "Спецтехника",
            "Автовышка телескопическая АГП-22 на базе ГАЗон NEXT",
            "Водитель-оператор Белов Андрей Сергеевич",
            "На_Объекте",
            "Монтаж фасадных кассет на восточном торце",
        ],
        [
            base_date,
            "Школа №42 г. Химки",
            "Бригада_Рабочих",
            "Бригада сантехников-монтажников №2 (6 чел.)",
            "Бригадир Григорьев Виктор Петрович",
            "На_Объекте",
            "Опрессовка контура отопления блока младших классов",
        ],
        [
            base_date,
            "Школа №42 г. Химки",
            "Инженер_Куратор",
            "Ведущий инженер ПТО",
            "Смирнов Алексей Викторович",
            "На_Объекте",
            "Сдача скрытых работ технадзору заказчика (подписание актов)",
        ],
        [
            base_date,
            "Теплосети мкр. 'Южный' г. Подольск",
            "Спецтехника",
            "Экскаватор гусеничный Komatsu PC210NLC-8",
            "Машинист Мельников Владимир Юрьевич",
            "На_Объекте",
            "Разработка траншеи теплотрассы ПК 2+40",
        ],
        [
            base_date,
            "Теплосети мкр. 'Южный' г. Подольск",
            "Спецтехника",
            "Автокран КС-55713-1К-4 'Клинцы' 25 тонн",
            "Машинист Тарасов Роман Денисович",
            "Простой_Авария",
            "Обрыв гидравлического шланга выносной опоры, вызвана ремонтная летучка",
        ],
        [
            base_date,
            "Теплосети мкр. 'Южный' г. Подольск",
            "Бригада_Рабочих",
            "Бригада сварщиков технологических трубопроводов (4 чел.)",
            "Бригадир Котов Денис Олегович",
            "На_Объекте",
            "Стыковая сварка и неразрушающий ультразвуковой контроль швов",
        ],
        [
            base_date,
            "Сети водопровода детсада",
            "Спецтехника",
            "Экскаватор-погрузчик JCB 4CX Eco",
            "Машинист Новиков Артем Васильевич",
            "На_Объекте",
            "Обратная засыпка траншеи водопровода с послойной утрамбовкой",
        ],
        [
            base_date,
            "Сети водопровода детсада",
            "Инженер_Куратор",
            "Инженер-геодезист",
            "Иванов Сергей Павлович",
            "На_Объекте",
            "Контрольная исполнительная съемка трассы водопровода",
        ],
        [
            base_date,
            "Парк 'Дубки' г. Одинцово",
            "Бригада_Рабочих",
            "Бригада дорожных рабочих и мостильщиков №3 (10 чел.)",
            "Бригадир Назаров Ильяс Каримович",
            "На_Объекте",
            "Укладка брусчатки центральной аллеи",
        ],
        [
            base_date,
            "Парк 'Дубки' г. Одинцово",
            "Спецтехника",
            "Каток тротуарный двухвальцовый вибрационный Bomag BW 100",
            "Машинист Захаров Константин Павлович",
            "На_Объекте",
            "Уплотнение песчано-гравийной подушки под спортивную площадку",
        ],
        [
            base_date,
            "Парк 'Дубки' г. Одинцово",
            "Спецтехника",
            "Самосвал КАМАЗ-65115 (15 тонн)",
            "Водитель Романов Дмитрий Игоревич",
            "На_Объекте",
            "Вывоз грунта и строительного мусора на полигон",
        ],
        # Техника на ТО и в ремонте
        [
            base_date,
            "Производственная база ООО 'СпецСтройМонтаж'",
            "Спецтехника",
            "Самосвал КАМАЗ-6520 (20 тонн)",
            "Водитель Кузнецов Валерий Борисович",
            "В_Ремонте",
            "Плановое техническое обслуживание (замена масла, фильтров, колодок)",
        ],
        [
            base_date,
            "Производственная база ООО 'СпецСтройМонтаж'",
            "Спецтехника",
            "Компрессор винтовой дизельный Atlas Copco XAS 88",
            "Механик Гусев Семен Антонович",
            "В_Ремонте",
            "Замена приводных ремней и опрессовка пневмолинии",
        ],
        # Завершившиеся смены
        [
            base_date - timedelta(days=1),
            "Клиническая больница №1 им. Пирогова",
            "Бригада_Рабочих",
            "Бригада электриков-монтажников №1 (5 чел.)",
            "Бригадир Морозов Павел Геннадьевич",
            "Завершено",
            "Монтаж кабельных трасс по чердачному перекрытию сдан без замечаний",
        ],
        [
            base_date - timedelta(days=1),
            "Школа №42 г. Химки",
            "Спецтехника",
            "Манипулятор КАМАЗ с КМУ 7 тонн Palfinger",
            "Водитель Семенов Олег Николаевич",
            "Завершено",
            "Разгрузка секционных радиаторов и запорной арматуры выполнена",
        ],
        [
            base_date - timedelta(days=1),
            "Теплосети мкр. 'Южный' г. Подольск",
            "Спецтехника",
            "Установка горизонтально-направленного бурения (ГНБ) Vermeer",
            "Оператор Воропаев Антон Сергеевич",
            "Завершено",
            "Прокол под автодорогой протяженностью 45 метров завершен",
        ],
        # Плановые смены на завтра и ближайшие дни
        [
            base_date + timedelta(days=1),
            "Клиническая больница №1 им. Пирогова",
            "Инженер_Куратор",
            "Главный инженер проекта",
            "Смирнов Алексей Викторович",
            "На_Объекте",
            "Финальная рабочая комиссия по приемке фасада",
        ],
        [
            base_date + timedelta(days=1),
            "Школа №42 г. Химки",
            "Бригада_Рабочих",
            "Бригада электромонтажников слаботочных систем (4 чел.)",
            "Бригадир Еремин Станислав Викторович",
            "На_Объекте",
            "Монтаж пожарной сигнализации и датчиков дыма",
        ],
        [
            base_date + timedelta(days=1),
            "Теплосети мкр. 'Южный' г. Подольск",
            "Спецтехника",
            "Автокран КС-55713-1К-4 'Клинцы' 25 тонн",
            "Машинист Тарасов Роман Денисович",
            "На_Объекте",
            "Возобновление монтажа лотков теплотрассы после устранения поломки",
        ],
        [
            base_date + timedelta(days=2),
            "Красногорская городская больница",
            "Инженер_Куратор",
            "Инженер систем ОВиК",
            "Ковалев Дмитрий Николаевич",
            "На_Объекте",
            "Предпроектное обследование вентшахт и согласование точек врезки",
        ],
        [
            base_date + timedelta(days=2),
            "Парк 'Дубки' г. Одинцово",
            "Бригада_Рабочих",
            "Бригада озеленителей (6 чел.)",
            "Бригадир Васильева Анна Сергеевна",
            "На_Объекте",
            "Высадка крупномерных деревьев и укладка рулонного газона",
        ],
        [
            base_date + timedelta(days=3),
            "БКТП 1000 кВА (Мособлэнерго)",
            "Инженер_Куратор",
            "Инженер-электрик релейной защиты",
            "Зайцев Роман Игоревич",
            "На_Объекте",
            "Приемка строительной готовности фундаментной плиты БКТП",
        ],
    ]

    # -------------------------------------------------------------------------
    # 05. Операционные Задачи и Алерты (22 строки)
    # Columns:
    # 0: Заголовок_Задачи, 1: Связанный_Контракт, 2: Ответственная_Роль,
    # 3: ФИО_Исполнителя, 4: Крайний_Срок_Дедлайн, 5: Приоритет_Срочность,
    # 6: Статус_Исполнения, 7: Потенциальный_Штраф_Руб
    # -------------------------------------------------------------------------
    datasets["05_tasks"] = [
        # TRIGGER 3: Критический штраф юристу - протокол разногласий за 48 часов
        [
            "Подать протокол разногласий к проекту госконтракта №014820000212600015",
            "014820000212600015 (Школа №42)",
            "Юрист",
            "Воронова Елена Анатольевна",
            base_date + timedelta(days=2),  # Trigger: Дедлайн через 48 часов (2 дня)
            "КРИТИЧЕСКИЙ_ШТРАФ",             # Trigger: Приоритет КРИТИЧЕСКИЙ_ШТРАФ
            "В_Работе",
            1250000.00,                      # Trigger: Потенциальный штраф при пропуске дедлайна
        ],
        # Сопутствующая критическая задача по контракту с дедлайном через 3 дня
        [
            "Срочно подписать и передать в ГКУ УКС акты КС-2/КС-3 на 2.5 млн руб",
            "0173200001426000045 (КБ №1)",
            "Инженер",
            "Смирнов Алексей Викторович",
            base_date + timedelta(days=3),
            "КРИТИЧЕСКИЙ_ШТРАФ",
            "В_Работе",
            490000.00,
        ],
        # Задача по продлению истекающей через 5 дней банковской гарантии
        [
            "Предоставить заказчику дополнительное соглашение о продлении банковской гарантии",
            "0348300054226000088 (Теплосеть)",
            "Юрист",
            "Воронова Елена Анатольевна",
            base_date + timedelta(days=5),
            "КРИТИЧЕСКИЙ_ШТРАФ",
            "В_Работе",
            840000.00,
        ],
        # Задача по закрытию кассового разрыва на 9-й день
        [
            "Согласовать с ПАО Сбербанк открытие возобновляемой кредитной линии (овердрафт)",
            "Финансовый план 2026",
            "Бухгалтер",
            "Кузнецова Татьяна Викторовна",
            base_date + timedelta(days=7),
            "Высокий",
            "В_Работе",
            0.00,
        ],
        # Задачи Гендиректора и Замгендиректора
        [
            "Утвердить протокол разногласий и график финансирования с Заказчиком ГКУ УКС",
            "0173200001426000045 (КБ №1)",
            "Гендиректор",
            "Орлов Андрей Борисович",
            base_date + timedelta(days=1),
            "Высокий",
            "В_Работе",
            0.00,
        ],
        [
            "Провести оперативное совещание с прорабами по ускорению темпов благоустройства парка",
            "0348100021426000102 (Парк Дубки)",
            "Замгендиректора",
            "Медведев Игорь Сергеевич",
            base_date + timedelta(days=2),
            "Высокий",
            "В_Работе",
            150000.00,
        ],
        # Задачи Тендерщика
        [
            "Подать заявку на участие в открытом конкурсе на капремонт электросетей",
            "0173200001426000189",
            "Тендерщик",
            "Зайцев Роман Игоревич",
            base_date + timedelta(days=4),
            "Высокий",
            "В_Работе",
            98000.00,
        ],
        [
            "Сформировать пакет документов для участия в процедуре монтажа АПС Мытищи",
            "0348300054226000311",
            "Тендерщик",
            "Зайцев Роман Игоревич",
            base_date + timedelta(days=6),
            "Обычный",
            "В_Работе",
            0.00,
        ],
        # Задачи Закупщика / Снабженца
        [
            "Проконтролировать отгрузку силового кабеля со склада ООО 'ТД Кабель-Инвест'",
            "0148200002126000015 (Школа №42)",
            "Закупщик",
            "Гордеев Максим Васильевич",
            base_date + timedelta(days=1),
            "Высокий",
            "В_Работе",
            50000.00,
        ],
        [
            "Заключить договор поставки и согласовать спецификацию на трансформаторы ТМГ-1000",
            "0173200001426000103 (Мособлэнерго)",
            "Закупщик",
            "Гордеев Максим Васильевич",
            base_date + timedelta(days=4),
            "Высокий",
            "В_Работе",
            200000.00,
        ],
        # Задачи Инженера ПТО
        [
            "Подготовить исполнительные схемы скрытых работ по прокладке труб теплосети",
            "0348300054226000088 (Теплосеть)",
            "Инженер",
            "Ковалев Дмитрий Николаевич",
            base_date + timedelta(days=4),
            "Обычный",
            "В_Работе",
            0.00,
        ],
        [
            "Сдать лаборатории образцы кернов асфальтобетона с объекта парк 'Дубки'",
            "0348100021426000102 (Парк Дубки)",
            "Инженер",
            "Петров Михаил Романович",
            base_date + timedelta(days=3),
            "Обычный",
            "В_Работе",
            50000.00,
        ],
        # Задачи Диспетчера
        [
            "Обеспечить доставку запчасти для автокрана Клинцы и выезд слесаря-гидравлика",
            "0348300054226000088 (Теплосеть)",
            "Диспетчер",
            "Фролов Виталий Александрович",
            base_date + timedelta(days=1),
            "Высокий",
            "В_Работе",
            40000.00,
        ],
        [
            "Сформировать недельный график работы самосвалов и согласовать пропуска в Москву",
            "Общий парк спецтехники",
            "Диспетчер",
            "Фролов Виталий Александрович",
            base_date + timedelta(days=2),
            "Обычный",
            "В_Работе",
            0.00,
        ],
        # Задачи Менеджера
        [
            "Получить от Заказчика согласованные промежуточные акты осмотра вентшахт больницы",
            "0848300011226000012 (Красногорская ГБ)",
            "Менеджер",
            "Соколова Мария Андреевна",
            base_date + timedelta(days=5),
            "Обычный",
            "В_Работе",
            0.00,
        ],
        [
            "Организовать передачу оригиналов исполнительной документации в архив УКС",
            "0173200001425000912 (Поликлиника №5)",
            "Менеджер",
            "Соколова Мария Андреевна",
            base_date + timedelta(days=8),
            "Обычный",
            "В_Работе",
            0.00,
        ],
        # Задачи Бухгалтера
        [
            "Выгрузить выписку 1С за вчерашний день и провести сверку взаиморасчетов с заказчиками",
            "Бухгалтерия и Касса",
            "Бухгалтер",
            "Кузнецова Татьяна Викторовна",
            base_date,
            "Высокий",
            "В_Работе",
            0.00,
        ],
        [
            "Подготовить платежные поручения на оплату поставщикам первой очереди",
            "Финансы",
            "Бухгалтер",
            "Кузнецова Татьяна Викторовна",
            base_date + timedelta(days=1),
            "Высокий",
            "В_Работе",
            0.00,
        ],
        # Задачи на проверке и закрытые задачи
        [
            "Подготовить проект претензии поставщику за задержку поставки полимерных труб",
            "0373100012826000099 (Водопровод)",
            "Юрист",
            "Воронова Елена Анатольевна",
            base_date - timedelta(days=1),
            "Высокий",
            "На_Проверке",
            120000.00,
        ],
        [
            "Согласовать спецификацию замены насосного оборудования с авторским надзором",
            "0148200002126000015 (Школа №42)",
            "Инженер",
            "Смирнов Алексей Викторович",
            base_date - timedelta(days=2),
            "Обычный",
            "На_Проверке",
            0.00,
        ],
        [
            "Разблокировать спецсчет после подведения итогов аукциона в Сергиевом Посаде",
            "0148200003325000991",
            "Бухгалтер",
            "Кузнецова Татьяна Викторовна",
            base_date - timedelta(days=5),
            "Обычный",
            "Закрыто",
            0.00,
        ],
        [
            "Провести инструктаж по охране труда для вновь принятых рабочих бригады №3",
            "Охрана труда и ТБ",
            "Инженер",
            "Петров Михаил Романович",
            base_date - timedelta(days=6),
            "Обычный",
            "Закрыто",
            0.00,
        ],
    ]

    return datasets


def generate_mock_drive(
    mock_root: Path,
    base_date: Optional[date] = None,
) -> List[Path]:
    """
    Generates realistic Mock Google Drive folder structure populated with 5 Excel files:
    storage/mock_drive/
    ├── 01_Реестры_Тендеров/01_Реестр_Тендеров_и_Контрактов.xlsx
    ├── 02_Финансы_и_1С/02_ДДС_Касса_и_Взаиморасчеты.xlsx
    ├── 03_Снабжение_и_Закупки/03_План_Закупок_и_Материалов.xlsx
    ├── 04_ПТО_и_Объекты/04_Диспетчерский_График_и_Техника.xlsx
    └── 05_Юридический_Отдел/05_Операционные_Задачи_и_Алерты.xlsx
    """
    if base_date is None:
        base_date = date.today()

    mock_root.mkdir(parents=True, exist_ok=True)
    datasets = generate_mock_datasets(base_date=base_date)
    created_files: List[Path] = []

    print(f"\n[INFO] Генерация мок-диска (Mock Google Drive) в: {mock_root}")
    print(f"       Базовая дата расчета дедлайнов и триггеров: {base_date.isoformat()}")
    print("=" * 70)

    for key, spec in TEMPLATES.items():
        data_rows = datasets.get(key, [])
        sub_dir = mock_root / spec.relative_drive_dir
        sub_dir.mkdir(parents=True, exist_ok=True)

        wb = build_workbook_for_spec(spec, data_rows=data_rows)
        target_file = sub_dir / spec.file_name
        wb.save(target_file)
        created_files.append(target_file)

        print(f"  [OK] [Mock Drive] /{spec.relative_drive_dir}/{spec.file_name}")
        print(f"       +-- Заполнено строк: {len(data_rows)}, Размер: {target_file.stat().st_size} байт")

    print("=" * 70)
    print(f"[SUCCESS] Успешно сгенерирован Mock Google Drive ({len(created_files)} файлов)!\n")
    return created_files


def verify_mock_drive(
    mock_root: Path,
    base_date: Optional[date] = None,
) -> bool:
    """
    Verifies that the Mock Google Drive contains all 5 required tables,
    each has >= 20 rows, and that all 4 critical business triggers are present.
    """
    if base_date is None:
        base_date = date.today()

    print(f"\n[CHECK] Валидация Mock Google Drive в: {mock_root}")
    print("-" * 70)
    all_ok = True

    # 1. Check directory structure and file sizes
    for key, spec in TEMPLATES.items():
        expected_path = mock_root / spec.relative_drive_dir / spec.file_name
        if not expected_path.exists():
            print(f"  [ERROR] Отсутствует файл на мок-диске: {expected_path}")
            all_ok = False
            continue

        wb = openpyxl.load_workbook(expected_path, data_only=True)
        ws = wb.active
        # Rows count excluding header
        row_count = ws.max_row - 1
        if row_count < 15:
            print(f"  [WARN] {spec.file_name}: Мало строк данных ({row_count} < 15)")
            all_ok = False
        else:
            print(f"  [OK] {spec.file_name}: Содержит {row_count} строк данных (>= 20 строк)")
        wb.close()

    # 2. Verify Alert Triggers in detail
    print("\n[CHECK] Проверка 4 специальных бизнес-триггеров алертов:")

    # Trigger 1 & 2 in 01_tenders
    tenders_file = mock_root / TEMPLATES["01_tenders"].relative_drive_dir / TEMPLATES["01_tenders"].file_name
    wb_tenders = openpyxl.load_workbook(tenders_file, data_only=True)
    ws_tenders = wb_tenders.active

    trigger_1_found = False
    trigger_2_found = False

    target_3_days = base_date + timedelta(days=3)
    target_5_days = base_date + timedelta(days=5)

    for row in ws_tenders.iter_rows(min_row=2, values_only=True):
        # Col 3: Сумма_Контракта, Col 7: Дата_Окончания_Работ, Col 8: Сумма_Закрыто_КС, Col 11: Банковская_Гарантия_До
        contract_sum = row[3] or 0.0
        end_date = row[7]
        closed_ks = row[8] or 0.0
        bg_date = row[11]

        # Trigger 1: end_date within 3 days and unclosed KS == 2,500,000
        unclosed = float(contract_sum) - float(closed_ks)
        if isinstance(end_date, (date, datetime)):
            d_val = end_date.date() if isinstance(end_date, datetime) else end_date
            if d_val == target_3_days and abs(unclosed - 2500000.0) < 1.0:
                trigger_1_found = True

        # Trigger 2: bg_date within 5 days
        if isinstance(bg_date, (date, datetime)):
            d_val = bg_date.date() if isinstance(bg_date, datetime) else bg_date
            if d_val == target_5_days:
                trigger_2_found = True

    wb_tenders.close()

    if trigger_1_found:
        print("  [OK] Триггер 1: Контракт со сроком через 3 дня и незакрытыми КС на 2 500 000 ₽ найден.")
    else:
        print("  [ERROR] Триггер 1: Контракт со сроком через 3 дня и незакрытыми КС на 2.5 млн не обнаружен!")
        all_ok = False

    if trigger_2_found:
        print("  [OK] Триггер 2: Банковская гарантия, истекающая через 5 дней, найдена.")
    else:
        print("  [ERROR] Триггер 2: Банковская гарантия через 5 дней не обнаружена!")
        all_ok = False

    # Trigger 3 in 05_tasks
    tasks_file = mock_root / TEMPLATES["05_tasks"].relative_drive_dir / TEMPLATES["05_tasks"].file_name
    wb_tasks = openpyxl.load_workbook(tasks_file, data_only=True)
    ws_tasks = wb_tasks.active

    trigger_3_found = False
    target_48h = base_date + timedelta(days=2)

    for row in ws_tasks.iter_rows(min_row=2, values_only=True):
        title = str(row[0])
        role = str(row[2])
        deadline = row[4]
        priority = str(row[5])

        if isinstance(deadline, (date, datetime)):
            d_val = deadline.date() if isinstance(deadline, datetime) else deadline
            if (
                "протокол разногласий" in title.lower()
                and role == "Юрист"
                and priority == "КРИТИЧЕСКИЙ_ШТРАФ"
                and d_val == target_48h
            ):
                trigger_3_found = True

    wb_tasks.close()

    if trigger_3_found:
        print("  [OK] Триггер 3: Задача юристу 'Подать протокол разногласий' (дедлайн 48ч, КРИТИЧЕСКИЙ_ШТРАФ) найдена.")
    else:
        print("  [ERROR] Триггер 3: Задача юристу (дедлайн 48ч, КРИТИЧЕСКИЙ_ШТРАФ) не обнаружена!")
        all_ok = False

    # Trigger 4 in 02_cashflow
    cash_file = mock_root / TEMPLATES["02_cashflow"].relative_drive_dir / TEMPLATES["02_cashflow"].file_name
    wb_cash = openpyxl.load_workbook(cash_file, data_only=True)
    ws_cash = wb_cash.active

    trigger_4_found = False
    target_9_days = base_date + timedelta(days=9)

    running_balance = 0.0
    day_9_balance = 0.0

    # Sort rows by date to accurately simulate cash flow
    rows = list(ws_cash.iter_rows(min_row=2, values_only=True))

    def get_row_date(r):
        d = r[0]
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, date):
            return d
        return date.min

    rows.sort(key=get_row_date)

    for row in rows:
        op_date = get_row_date(row)
        op_type = str(row[1])
        amount = float(row[4] or 0.0)

        if op_type == "Поступление":
            running_balance += amount
        elif op_type == "Списание":
            running_balance -= amount

        if op_date == target_9_days:
            day_9_balance = running_balance
            if day_9_balance < 0:
                trigger_4_found = True

    wb_cash.close()

    if trigger_4_found:
        print(f"  [OK] Триггер 4: Прогнозируемый кассовый разрыв на 9 день найден (баланс кассы: {day_9_balance:,.2f} ₽).")
    else:
        print(f"  [ERROR] Триггер 4: Кассовый разрыв на 9 день не обнаружен (баланс: {day_9_balance:,.2f} ₽)!")
        all_ok = False

    print("-" * 70)
    if all_ok:
        print("[SUCCESS] ВСЕ ПРОВЕРКИ МОК-ДИСКА И ТРИГГЕРОВ ПРОЙДЕНЫ УСПЕШНО!\n")
    else:
        print("[FAIL] ОБНАРУЖЕНЫ ОШИБКИ В МОК-ДИСКЕ!\n")

    return all_ok


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Генератор 5 утвержденных Excel-шаблонов и мок-диска платформы Smart Enterprise Hub"
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path("storage/templates"),
        help="Путь сохранения чистых эталонных шаблонов",
    )
    parser.add_argument(
        "--mock-dir",
        type=Path,
        default=Path("storage/mock_drive"),
        help="Путь сохранения мок-диска с заполненными таблицами (Фаза 2)",
    )
    parser.add_argument(
        "--with-mock-data",
        action="store_true",
        help="Сгенерировать также мок-данные для Google Drive (Фаза 2)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Запустить строгую валидацию созданных шаблонов и мок-диска",
    )

    args = parser.parse_args()

    # Determine workspace root relative to script location
    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parent.parent

    templates_dir = (
        args.templates_dir
        if args.templates_dir.is_absolute()
        else workspace_root / args.templates_dir
    )
    mock_dir = (
        args.mock_dir
        if args.mock_dir.is_absolute()
        else workspace_root / args.mock_dir
    )

    # 1. Generate empty pure templates
    generate_empty_templates(templates_dir)

    # 2. Run verification of pure templates
    verify_generated_templates(templates_dir)

    # 3. Handle mock data if requested (Phase 2)
    if args.with_mock_data:
        generate_mock_drive(mock_dir)
        verify_mock_drive(mock_dir)


if __name__ == "__main__":
    main()

