"""Synthetic data for the public showcase, independent of customer sources."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


CUSTOMERS = (
    "АО «Волжский терминал»", "ООО «Альтаир Сервис»", "АО «Гранит Энерго»",
    "ООО «Северная логистика»", "АО «Контур Прибор»", "ООО «Новый причал»",
)
CURATORS = ("Алина Ветрова", "Мирон Соснов", "Кира Ясенева", "Роман Камышев")
PROJECTS = (
    ("Подготовка сервисной площадки", -4, 720_000, 70),
    ("Модернизация зоны приёмки", 5, 460_000, 40),
    ("Монтаж оборудования", 12, 980_000, 25),
    ("Обновление склада", -10, 310_000, 100),
    ("Переустройство зоны отгрузки", 22, 2_430_000, 55),
    ("Диагностика насосной станции", -2, 585_000, 80),
    ("Модернизация системы контроля доступа", 16, 1_280_000, 20),
    ("Поставка и пусконаладка резервного щита", 35, 3_150_000, 15),
    ("Ремонт вентиляции производственного корпуса", -14, 1_180_000, 100),
    ("Замена автоматики конвейера", 9, 1_560_000, 65),
    ("Поверка приборов узла учёта", 27, 392_000, 30),
    ("Организация резервного поста связи", 42, 825_000, 10),
)


STAGES = ("preparation", "submitted", "bidding", "won", "guarantee", "contract", "execution", "acceptance")
ROLE_TASKS = {
    "ceo": "Проверить ключевые показатели",
    "coo": "Сверить план операций",
    "tender": "Проверить условия предложения",
    "engineer": "Проверить готовность работ",
    "dispatcher": "Подтвердить график смены",
    "manager": "Согласовать график с заказчиком",
    "lawyer": "Проверить условия договора",
    "procurement": "Подтвердить поставку",
    "accountant": "Сверить взаиморасчёты",
}
SHIFT_STATUS = {"on_site": "На объекте", "repair": "В ремонте", "downtime": "Простой"}


def snapshot(today=None):
    today = today or datetime.now(ZoneInfo("Europe/Samara")).date()

    def day(offset):
        return (today + timedelta(days=offset)).isoformat()

    def shift_day(index):
        if index <= 4:
            return day(0)
        month_index = today.year * 12 + today.month - 1 - (index - 3) // 2
        year, month = divmod(month_index, 12)
        return date(year, month + 1, 12 + index).isoformat()

    projects = []
    registry = []
    for index, (name, offset, amount, completion) in enumerate(PROJECTS, start=1):
        project_id = f"project-{index}"
        code = f"К-{240 + index}"
        customer = CUSTOMERS[(index - 1) % len(CUSTOMERS)]
        curator = CURATORS[(index - 1) % len(CURATORS)]
        completed = amount * completion // 100
        paid = completed if completion == 100 else completed // 2
        projects.append({
            "id": project_id, "project_code": code, "project_name": name,
            "customer_name": customer, "curator_name": curator,
            "contract_sum": amount, "completed_sum": completed, "paid_sum": paid,
            "debt_sum": completed - paid, "completion_percent": completion,
            "start_date": day(-25), "deadline_date": day(offset),
            "status": "completed" if completion == 100 else "active",
            "days_overdue": max(0, -offset) if completion < 100 else 0,
            "risk_level": "critical" if offset < 0 and completion < 100 else "normal",
            "penalty_amount_calculated": amount // 100 if offset < 0 and completion < 100 else 0,
            "tender_stage": "acceptance" if completion == 100 else "execution" if offset < 0 else STAGES[(index - 1) % 7],
        })
        values = [None] * 22
        monitoring = [None] * 25
        values[0] = monitoring[0] = code
        values[1] = monitoring[1] = customer
        values[3] = monitoring[3] = "Самара"
        values[9], values[15], values[18] = name, amount, day(offset)
        values[16] = "Завершен" if completion == 100 else "На исполнении"
        monitoring[4] = day(-12)
        if completion == 100:
            monitoring[5] = day(offset)
        registry.append({
            "id": project_id, "number": code, "amount": amount, "link": None,
            "curator": curator,
            "registry": {"source_row": index + 3, "values": values},
            "monitoring": {"source_row": index + 3, "values": monitoring},
            "registry_columns": [], "monitoring_columns": [], "source_warnings": {},
        })

    tasks, alerts, procurement, dispatch = [], [], [], []
    materials = ("Комплект креплений", "Кабель силовой", "Датчик давления", "Шкаф управления",
                 "Рабочий комплект СИЗ", "Блок питания", "Оптический модуль", "Фильтр")
    suppliers = ("ВолгаКомплект", "Контакт-Поставка", "Приборная база", "Меридиан Снаб")
    for index, (project, (_, offset, amount, completion)) in enumerate(zip(projects, PROJECTS), 1):
        curator = project["curator_name"]
        for part, (role, title) in enumerate(ROLE_TASKS.items(), 1):
            if (index + part) % 2:
                continue
            due = offset - 2 if part == 1 else offset
            status = "completed" if completion == 100 or (part == 1 and completion >= 50) else "pending"
            if status != "completed" and due < 0:
                status = "overdue"
            tasks.append({
                "id": f"task-{index}-{part}", "task_title": f"{title} · {project['project_name']}",
                "project_id": project["id"], "related_contract": project["project_code"],
                "responsible_role": role, "responsible_person": curator, "due_date": day(due),
                "days_remaining": due, "is_urgent": due <= 5 and status != "completed",
                "source": "manual", "status": status, "priority": "high" if due <= 5 else "medium",
            })
        if offset < 0 and completion < 100:
            alerts.append({
                "id": f"alert-{index}", "project_id": project["id"], "alert_type": "DEADLINE_BREACH", "severity": "CRITICAL",
                "title": f"Нарушен срок исполнения · {project['project_name']}",
                "description": f"Прошло {abs(offset)} дн. с плановой даты. Требуется согласовать новый срок.",
                "calculated_financial_impact": amount // 100, "is_resolved": False,
                "created_at": f"{day(offset)}T08:00:00+04:00",
            })
        procurement.append({
            "id": f"supply-{index}", "project_name": project["project_name"],
            "item_name": materials[(index - 1) % len(materials)], "quantity": 3 + index * 2, "unit": "шт.",
            "supplier": suppliers[(index - 1) % len(suppliers)], "invoice_amount": 12_000 + index * 3500,
            "status": ("invoice_pending", "in_transit", "delivered")[(index - 1) % 3],
            "delivery_deadline": day(offset - 3), "invoice_number": f"СЧ-{620 + index}",
            "created_at": f"{day(-index)}T10:00:00+04:00",
        })
        if index <= 8:
            dispatch.append({
                "id": f"shift-{index}", "shift_date": shift_day(index),
                "target_object": project["project_name"], "resource_type": "crew",
                "unit_name": f"Рабочая группа №{(index - 1) % 4 + 1}",
                "responsible_person": curator, "status": tuple(SHIFT_STATUS)[(index - 1) % 3],
                "work_type": ("Плановые работы", "Диагностика оборудования", "Подготовка площадки")[(index - 1) % 3],
            })
    return today, projects, registry, tasks, alerts, procurement, dispatch
