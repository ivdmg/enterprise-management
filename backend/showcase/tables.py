"""Tabular contract shared by the synthetic seed and the read-only importer."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .data import STAGES, SHIFT_STATUS, snapshot

SHEETS = {
    "team": ("Документы сотрудников",),
    "finance": ("Платежи",),
    "operations": ("Реестр контрактов", "Ежедневный мониторинг", "Задачи", "Сигналы", "Смены"),
    "stock": ("Поставки",),
}
TITLES = {"team": "Документы сотрудников", "finance": "Реестр платежей",
          "operations": "Контракты и операции", "stock": "Реестр закупок и поставок"}
FOLDERS = {"team": "Команда", "finance": "Финансы", "operations": "Операции", "stock": "Запасы"}
DOC_HEADER = ["Сотрудник", "Документ", "Действует до"]
DOC_FIELDS = ["Табельный №", "Подразделение", "Должность", "Номер документа", "Выдан",
              "Организация", "Ответственный", "Следующее действие"]
PERSONNEL = (
    ("Алина Ветрова", "Служба эксплуатации", "Специалист по эксплуатации"),
    ("Мирон Соснов", "Служба эксплуатации", "Специалист по оборудованию"),
    ("Кира Ясенева", "Производственный участок", "Мастер участка"),
    ("Роман Камышев", "Операционный отдел", "Старший специалист"),
    ("Дина Рябинова", "Производственный участок", "Специалист по охране труда"),
    ("Лев Вишневский", "Операционный отдел", "Координатор работ"),
    ("Зоя Ольхина", "Контроль качества", "Специалист по качеству"),
    ("Никита Лиственный", "Контроль качества", "Оператор участка"),
    ("Мария Туманова", "Служба эксплуатации", "Специалист по обслуживанию"),
    ("Илья Берестов", "Логистика", "Координатор смены"),
)
MONITOR_HEADER = ["вн.№", "Заказчик", "Начало", "Завершение"]


COLUMN_NAMES = {
    "id": "Код записи", "project_code": "Код контракта", "project_name": "Объект",
    "customer_name": "Заказчик", "curator_name": "Куратор", "contract_sum": "Сумма договора",
    "completed_sum": "Выполнено, ₽", "completion_percent": "Готовность, %", "start_date": "Начало работ",
    "deadline_date": "Срок по договору", "status": "Статус", "penalty_amount_calculated": "Расчёт пени",
    "tender_stage": "Этап закупки", "task_title": "Поручение", "project_id": "Код объекта",
    "related_contract": "Номер договора", "responsible_role": "Роль", "responsible_person": "Ответственный",
    "due_date": "Исполнить до", "days_remaining": "Осталось, дн.", "is_urgent": "Срочно",
    "source": "Происхождение", "priority": "Приоритет", "resource_type": "Тип ресурса", "work_type": "Работы",
    "alert_type": "Тип риска", "severity": "Критичность", "title": "Событие", "description": "Описание",
    "calculated_financial_impact": "Оценка потерь, ₽", "is_resolved": "Закрыт", "created_at": "Дата регистрации",
    "shift_date": "Дата смены", "target_object": "Объект", "unit_name": "Подразделение",
    "item_name": "Номенклатура", "quantity": "Количество", "unit": "Ед. изм.", "supplier": "Поставщик",
    "invoice_amount": "Сумма счёта, ₽", "delivery_deadline": "Поставка до", "invoice_number": "Номер счёта",
    "date": "Дата операции", "incoming": "Поступление, ₽", "outgoing": "Расход, ₽",
}


DISPLAY_VALUES = {
    ("Реестр контрактов", "tender_stage"): dict(zip(STAGES, (
        "Подготовка", "Заявка подана", "Отбор", "Согласовано",
        "Обеспечение", "Контракт", "Исполнение", "Приёмка",
    ), strict=True)),
    ("Задачи", "responsible_role"): {
        "ceo": "Генеральный директор", "coo": "Операционный директор",
        "tender": "Тендерный специалист", "engineer": "Специалист по операциям",
        "dispatcher": "Диспетчер", "manager": "Менеджер проектов",
        "lawyer": "Юрист", "procurement": "Закупщик", "accountant": "Бухгалтер",
    },
    ("Смены", "status"): SHIFT_STATUS,
}


def template_tables(today=None):
    """Return business-facing headers and labels for editable source books."""
    tables = seed_tables(today)
    result = {}
    for name, (header, *records) in tables.items():
        values = [DISPLAY_VALUES.get((name, column), {}) for column in header]
        result[name] = [
            [COLUMN_NAMES.get(column, column) for column in header],
            *([labels.get(cell, cell) for labels, cell in zip(values, row, strict=True)] for row in records),
        ]
    return result


def encode(rows):
    return [list(rows[0]), *(list(row.values()) for row in rows)]


def employee_rows(today):
    yield [*DOC_HEADER, *DOC_FIELDS]
    kinds = ("Удостоверение по охране труда", "Допуск к работам",
             "Проверка знаний по безопасности", "Обучение первой помощи")
    for index, (name, department, role) in enumerate(PERSONNEL, 1):
        for item, kind in enumerate(kinds):
            days = (180 - index * 6, 18 - index, index * 18 - 50, 90 + index * 2)[item]
            missing = (index + item) % 7 == 0 or (index == 2 and item == 1)
            if missing:
                expiry = number = issued = organisation = ""
                action = "Запросить копию и сверить допуск"
            else:
                expiry = (today + timedelta(days=days)).isoformat()
                issued = (today + timedelta(days=days - 365)).isoformat()
                number = f"УД-{index:02d}-{item + 1:02d}"
                organisation = ("Учебный центр «Вектор»", "Комиссия по допускам",
                                "Учебный центр «Полюс»", "Учебный центр «Вектор»")[item]
                action = "Повторное обучение" if days < 0 else "Включить в график аттестации" if days <= 30 else ""
            yield [name, kind, expiry, f"Т-{index:03d}", department, role, number, issued,
                   organisation, "Дина Рябинова", action]


def seed_tables(today=None):
    today, projects, registry, tasks, alerts, supplies, shifts = snapshot(today)
    derived = {"paid_sum", "debt_sum", "risk_level", "days_overdue"}
    project_rows = [
        {"вн.№": row["project_code"], **{key: value for key, value in row.items() if key not in derived}}
        for row in projects
    ]
    def offset(days):
        return (today + timedelta(days=days)).isoformat()

    payments = [
        {"date": offset(-2 * index - part), "incoming": project["paid_sum"] // 3
         + (project["paid_sum"] % 3 if part == 0 else 0),
         "outgoing": 12_000 + 2_500 * index + 1_000 * part,
         "project_code": project["project_code"], "Статья": ("Оплата по договору", "Закупка материалов", "Монтажные работы")[part],
         "Основание": f"ПП-{2000 + index * 3 + part}", "ЦФО": project["curator_name"],
         "Канал расчёта": "Банковский перевод", "Валюта": "RUB"}
        for index, project in enumerate(projects)
        for part in range(3)
    ]
    return {
        "Документы сотрудников": list(employee_rows(today)),
        "Реестр контрактов": encode(project_rows),
        "Ежедневный мониторинг": [[*MONITOR_HEADER, "Куратор", "Ближайший этап", "Ответ заказчика",
                                  "Готовность, %", "Решение по исполнению"], *(
            [row["number"], row["monitoring"]["values"][1],
             row["monitoring"]["values"][4], row["monitoring"]["values"][5] or "",
             project["curator_name"], "Закрытие договора" if project["status"] == "completed" else "Сверка плана работ",
             "Акт подписан" if project["status"] == "completed" else "Получить подтверждение",
             project["completion_percent"], "Архивировать" if project["status"] == "completed" else "Уточнить на планёрке"]
            for row, project in zip(registry, projects)
        )],
        "Задачи": encode(tasks),
        "Сигналы": encode(alerts),
        "Смены": encode(shifts),
        "Поставки": encode(supplies),
        "Платежи": encode(payments),
    }


DATE_FIELDS = {"Действует до", "Выдан", "Начало", "Завершение", "start_date", "deadline_date",
               "due_date", "shift_date", "delivery_deadline", "date"}


def read_rows(raw, template, optional=frozenset(), additional=frozenset(), mapping=None, line_numbers=None):
    if not raw or len(raw) >= 1000:
        raise ValueError("sheet size")
    accepted = {
        key: {str(label).strip().casefold() for label in ((mapping or {}).get(key, key), COLUMN_NAMES.get(key, key))}
        for key in template
    }
    if "tender_stage" in accepted:
        accepted["tender_stage"].add("стадия тендера")
    required = template.keys() - additional
    for index, raw_header in enumerate(raw[:8]):
        header = [str(value).strip().casefold() for value in raw_header]
        if all(accepted[key].intersection(header) for key in required):
            break
    else:
        raise ValueError("missing sheet header")
    columns = {}
    for key in template:
        matches = [column for column, label in enumerate(header) if label in accepted[key]]
        if len(matches) > 1:
            raise ValueError("duplicate mapped column")
        if matches:
            columns[key] = matches[0]
    if len(set(columns.values())) != len(columns):
        raise ValueError("ambiguous column mapping")
    rows = []
    for line_number, values in enumerate(raw[index + 1:], index + 2):
        if not any(value != "" for value in values):
            continue
        row = {}
        for key, sample in template.items():
            column = columns.get(key)
            value = values[column] if column is not None and column < len(values) else ""
            if (key in DATE_FIELDS and type(value) in (int, float)
                    and 1 <= value <= 100_000 and value == int(value)):
                value = (date(1899, 12, 30) + timedelta(days=int(value))).isoformat()
            if key in DATE_FIELDS and value != "":
                if not isinstance(value, str):
                    raise ValueError("invalid date type")
                iso_day(value)
            if key == "created_at" and type(value) in (int, float) and 1 <= value <= 100_000:
                epoch = datetime(1899, 12, 30, tzinfo=ZoneInfo("Europe/Samara"))
                value = (epoch + timedelta(days=value)).isoformat(timespec="seconds")
            if type(sample) is bool and value in ("TRUE", "FALSE"):
                value = value == "TRUE"
            if value == "" and (key in optional or key in additional):
                row[key] = None
            elif value == "" or not (type(value) is type(sample) or type(sample) is int and type(value) is float):
                raise ValueError("invalid cell type")
            else:
                row[key] = value
        if line_numbers is not None:
            line_numbers.append(line_number)
        rows.append(row)
    return rows


def iso_day(value):
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("expected ISO date")
    return value


def documents(raw, synced_at, mapping=None):
    rows = read_rows(raw, dict.fromkeys([*DOC_HEADER, *DOC_FIELDS], ""), {"Действует до"}, set(DOC_FIELDS), mapping)
    people = {}
    for row in rows:
        name, kind, expiry = (row[key] for key in DOC_HEADER)
        records = people.setdefault(name, {})
        if kind in records:
            raise ValueError("duplicate document")
        records[kind] = {
            "title": kind,
            "entries": [{"label": "Действует до", "value": iso_day(expiry) if expiry else "нет",
                         "is_date": expiry is not None},
                        *({"label": key, "value": row[key], "is_date": False}
                          for key in ("Должность", "Номер документа", "Следующее действие") if row[key])],
            "attachments": [],
        }
    return {"synced_at": synced_at, "people": [
        {"name": name, "column": index, "documents": list(records.values())}
        for index, (name, records) in enumerate(people.items(), 1)
    ]}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def parse_tables(tables, today, mapping=None, sources=None):
    seed = seed_tables(today)
    mapping = mapping or {}
    sources = sources or {}

    def read(name, optional=frozenset(), additional=frozenset(), line_numbers=None):
        header, example, *_ = seed[name]
        if name == "Платежи":
            header = header[:4]
        elif name == "Ежедневный мониторинг":
            header = MONITOR_HEADER
        template = {key: "" if key in DATE_FIELDS else value for key, value in zip(header, example)}
        legacy = "Реест Ольга" if name == "Реестр контрактов" and name not in tables else name
        rows = read_rows(tables[legacy], template, optional, additional,
                         mapping=mapping.get(name, mapping.get(legacy)), line_numbers=line_numbers)
        for field in template:
            if labels := DISPLAY_VALUES.get((name, field)):
                codes = {label.casefold(): code for code, label in labels.items()}
                for row in rows:
                    value = row[field]
                    if isinstance(value, str):
                        row[field] = codes.get(value.strip().casefold(), value)
        return rows

    contract_rows = []
    projects = read("Реестр контрактов", line_numbers=contract_rows)
    monitoring = read("Ежедневный мониторинг", {"Завершение"})
    by_code = {row["вн.№"]: row for row in monitoring}
    project_codes = {row["project_code"] for row in projects}
    codes_by_id = {row["id"]: row["project_code"] for row in projects}
    if (len(by_code) != len(monitoring) or len(project_codes) != len(projects)
            or len(codes_by_id) != len(projects) or project_codes != by_code.keys()):
        raise ValueError("invalid register join")
    registry = []
    for project, source_row in zip(projects, contract_rows, strict=True):
        if project["tender_stage"] not in STAGES:
            raise ValueError("unknown procurement stage")
        if source := sources.get("Реестр контрактов"):
            project["google_drive_link"] = f"{source}&range=A{source_row}"
        code = project.pop("вн.№")
        monitor = by_code[code]
        if code != project["project_code"] or project["customer_name"] != monitor["Заказчик"]:
            raise ValueError("inconsistent contract")
        days = (today - date.fromisoformat(iso_day(project["deadline_date"]))).days
        project["days_overdue"] = max(0, days) if project["status"] != "completed" else 0
        project["risk_level"] = "critical" if project["days_overdue"] else "normal"
        values = [None] * 22
        values[0], values[1], values[3], values[9] = code, project["customer_name"], "Самара", project["project_name"]
        values[15], values[18] = project["contract_sum"], project["deadline_date"]
        values[16] = "Завершен" if project["status"] == "completed" else "На исполнении"
        row = [None] * 25
        row[:2] = [code, monitor["Заказчик"]]
        row[4:6] = [iso_day(monitor["Начало"]), iso_day(monitor["Завершение"]) if monitor["Завершение"] else None]
        registry.append({
            "id": project["id"], "number": code, "amount": project["contract_sum"], "link": project.get("google_drive_link"),
            "curator": project["curator_name"], "registry": {"source_row": source_row, "values": values},
            "monitoring": {"source_row": monitoring.index(monitor) + 2, "values": row},
            "registry_columns": [], "monitoring_columns": [], "source_warnings": {},
        })
    tasks = read("Задачи")
    for task in tasks:
        if codes_by_id.get(task["project_id"]) != task["related_contract"]:
            raise ValueError("unknown task contract")
        if task["status"] == "completed":
            task["status"] = "approved_closed"
        if task["status"] not in {"pending", "in_progress", "overdue", "transferred_to_manager", "approved_closed"}:
            raise ValueError("unknown task status")
        task["days_remaining"] = (date.fromisoformat(iso_day(task["due_date"])) - today).days
        if task["status"] in {"pending", "in_progress", "overdue"}:
            if task["days_remaining"] < 0:
                task["status"] = "overdue"
            elif task["status"] == "overdue":
                task["status"] = "pending"
            task["is_urgent"] = task["days_remaining"] <= 5
    payments = read("Платежи")
    paid_by_code = dict.fromkeys(project_codes, 0)
    for point in payments:
        code = point["project_code"]
        if code not in project_codes:
            raise ValueError("unknown payment contract")
        paid_by_code[code] += point["incoming"]
    for project in projects:
        project["paid_sum"] = paid_by_code[project["project_code"]]
        project["debt_sum"] = project["completed_sum"] - project["paid_sum"]

    supplies = read("Поставки")
    shifts = read("Смены", additional={"work_type"})
    if any(shift["status"] not in SHIFT_STATUS for shift in shifts):
        raise ValueError("unknown shift status")
    project_names = {project["project_name"] for project in projects}
    if (any(item["project_name"] not in project_names for item in supplies)
            or any(shift["target_object"] not in project_names for shift in shifts)):
        raise ValueError("unknown project name")
    return {
        "customer-tenders": registry, "dashboard/projects": projects, "tasks": tasks,
        "alerts": read("Сигналы", additional={"project_id"}), "procurement/items": supplies,
        "dispatch/records": shifts, "payments": payments,
        "engineer-documents": documents(tables["Документы сотрудников"], timestamp(), mapping.get("Документы сотрудников")),
    }
