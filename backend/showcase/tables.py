"""Tabular contract shared by the synthetic seed and the read-only importer."""

from datetime import date, datetime, timedelta, timezone

from .data import snapshot

SHEETS = {
    "team": ("Документы сотрудников",),
    "finance": ("Платежи",),
    "operations": ("Реест Ольга", "Ежедневный мониторинг", "Задачи", "Сигналы", "Смены"),
    "stock": ("Поставки",),
}
TITLES = {"team": "Документы сотрудников", "finance": "Платежи демо",
          "operations": "Операционный реестр демо", "stock": "Поставки демо"}
FOLDERS = {"team": "Команда", "finance": "Финансы", "operations": "Операции", "stock": "Запасы"}
DOC_HEADER = ["Сотрудник", "Документ", "Действует до"]
MONITOR_HEADER = ["вн.№", "Заказчик", "Начало", "Завершение"]


def encode(rows):
    return [list(rows[0]), *(list(row.values()) for row in rows)]


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
         "project_code": project["project_code"]}
        for index, project in enumerate(projects)
        for part in range(3)
    ]
    return {
        "Документы сотрудников": [DOC_HEADER,
            ["Алина Ветрова", "Удостоверение по охране труда", offset(180)],
            ["Алина Ветрова", "Допуск к работам", offset(10)],
            ["Мирон Соснов", "Удостоверение по охране труда", offset(-7)],
            ["Мирон Соснов", "Допуск к работам", ""],
        ],
        "Реест Ольга": encode(project_rows),
        "Ежедневный мониторинг": [MONITOR_HEADER, *(
            [row["number"], row["monitoring"]["values"][1],
             row["monitoring"]["values"][4], row["monitoring"]["values"][5] or ""]
            for row in registry
        )],
        "Задачи": encode(tasks),
        "Сигналы": encode(alerts),
        "Смены": encode(shifts),
        "Поставки": encode(supplies),
        "Платежи": encode(payments),
    }


DATE_FIELDS = {"Действует до", "Начало", "Завершение", "start_date", "deadline_date",
               "due_date", "shift_date", "delivery_deadline", "date"}


def read_rows(raw, template, optional=frozenset()):
    if not raw or raw[0] != list(template) or len(raw) >= 1000:
        raise ValueError("sheet header or size")
    rows = []
    for values in raw[1:]:
        if len(values) > len(template):
            raise ValueError("too many columns")
        values = [*values, *[""] * (len(template) - len(values))]
        row = {}
        for (key, sample), value in zip(template.items(), values):
            if key in DATE_FIELDS and type(value) is int and 1 <= value <= 100_000:
                value = (date(1899, 12, 30) + timedelta(days=value)).isoformat()
            if key in DATE_FIELDS and value != "":
                if not isinstance(value, str):
                    raise ValueError("invalid date type")
                iso_day(value)
            if type(sample) is bool and value in ("TRUE", "FALSE"):
                value = value == "TRUE"
            if value == "" and key in optional:
                row[key] = None
            elif type(value) is not type(sample) or value == "":
                raise ValueError("invalid cell type")
            else:
                row[key] = value
        rows.append(row)
    return rows


def iso_day(value):
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("expected ISO date")
    return value


def documents(raw, synced_at):
    rows = read_rows(raw, dict.fromkeys(DOC_HEADER, ""), {"Действует до"})
    people = {}
    for name, kind, expiry in (row.values() for row in rows):
        records = people.setdefault(name, {})
        if kind in records:
            raise ValueError("duplicate document")
        records[kind] = {
            "title": kind,
            "entries": [{"label": "Действует до", "value": iso_day(expiry) if expiry else "нет",
                         "is_date": expiry is not None}],
            "attachments": [],
        }
    return {"synced_at": synced_at, "people": [
        {"name": name, "column": index, "documents": list(records.values())}
        for index, (name, records) in enumerate(people.items(), 1)
    ]}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def parse_tables(tables, today):
    seed = seed_tables(today)

    def read(name, optional=frozenset()):
        header, example, *_ = seed[name]
        template = {key: "" if key in DATE_FIELDS else value for key, value in zip(header, example)}
        return read_rows(tables[name], template, optional)

    projects = read("Реест Ольга")
    monitoring = read("Ежедневный мониторинг", {"Завершение"})
    by_code = {row["вн.№"]: row for row in monitoring}
    project_codes = {row["project_code"] for row in projects}
    codes_by_id = {row["id"]: row["project_code"] for row in projects}
    if (len(by_code) != len(monitoring) or len(project_codes) != len(projects)
            or len(codes_by_id) != len(projects) or project_codes != by_code.keys()):
        raise ValueError("invalid register join")
    registry = []
    for project in projects:
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
            "id": project["id"], "number": code, "amount": project["contract_sum"], "link": None,
            "curator": project["curator_name"], "registry": {"source_row": len(registry) + 2, "values": values},
            "monitoring": {"source_row": monitoring.index(monitor) + 2, "values": row},
            "registry_columns": [], "monitoring_columns": [], "source_warnings": {},
        })
    tasks = read("Задачи")
    for task in tasks:
        if codes_by_id.get(task["project_id"]) != task["related_contract"]:
            raise ValueError("unknown task contract")
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
    shifts = read("Смены")
    project_names = {project["project_name"] for project in projects}
    if (any(item["project_name"] not in project_names for item in supplies)
            or any(shift["target_object"] not in project_names for shift in shifts)):
        raise ValueError("unknown project name")
    return {
        "customer-tenders": registry, "dashboard/projects": projects, "tasks": tasks,
        "alerts": read("Сигналы"), "procurement/items": supplies,
        "dispatch/records": shifts, "payments": payments,
        "engineer-documents": documents(tables["Документы сотрудников"], timestamp()),
    }
