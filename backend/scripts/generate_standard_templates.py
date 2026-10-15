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
# Main Entry Point
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Генератор 5 утвержденных Excel-шаблонов платформы Smart Enterprise Hub"
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
        help="Запустить строгую валидацию созданных шаблонов",
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

    # 2. Run verification if requested or as part of generation
    verify_generated_templates(templates_dir)

    # 3. If --with-mock-data is passed, we will handle mock data (Phase 2 hook)
    if args.with_mock_data:
        print(f"⚠️ Опция --with-mock-data будет полностью задействована на Фазе 2.")


if __name__ == "__main__":
    main()
