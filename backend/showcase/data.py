"""Synthetic data for the public showcase, independent of customer sources."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def snapshot():
    today = datetime.now(ZoneInfo("Europe/Samara")).date()

    def day(offset):
        return (today + timedelta(days=offset)).isoformat()

    projects = []
    registry = []
    for index, (name, offset, amount, completion) in enumerate([
        ("Подготовка сервисной площадки", -4, 720_000, 70),
        ("Модернизация зоны приёмки", 5, 460_000, 40),
        ("Монтаж оборудования", 12, 980_000, 25),
        ("Обновление склада", -10, 310_000, 100),
    ], start=1):
        project_id = f"demo-project-{index}"
        code = f"DEMO-{100 + index}"
        customer = f"Учебный заказчик {index}"
        completed = amount * completion // 100
        paid = completed if completion == 100 else completed // 2
        projects.append({
            "id": project_id, "project_code": code, "project_name": name,
            "customer_name": customer, "curator_name": "Куратор демо",
            "contract_sum": amount, "completed_sum": completed, "paid_sum": paid,
            "debt_sum": completed - paid, "completion_percent": completion,
            "start_date": day(-25), "deadline_date": day(offset),
            "status": "completed" if completion == 100 else "active",
            "days_overdue": max(0, -offset) if completion < 100 else 0,
            "risk_level": "critical" if index == 1 else "normal",
            "penalty_amount_calculated": 7200 if index == 1 else 0,
            "tender_stage": "contract",
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
            monitoring[5] = day(-10)
        registry.append({
            "id": project_id, "number": code, "amount": amount, "link": None,
            "curator": "Куратор демо",
            "registry": {"source_row": index + 3, "values": values},
            "monitoring": {"source_row": index + 3, "values": monitoring},
            "registry_columns": [], "monitoring_columns": [], "source_warnings": {},
        })

    project = projects[0]
    tasks = [
        {
            "id": f"demo-task-{index}", "task_title": title,
            "project_id": project["id"], "related_contract": project["project_code"],
            "responsible_role": "manager", "responsible_person": "Куратор демо",
            "due_date": day(offset), "days_remaining": offset, "is_urgent": offset <= 5,
            "source": "manual", "status": status, "priority": priority,
        }
        for index, (title, offset, status, priority) in enumerate([
            ("Согласовать дату приёмки", -4, "overdue", "high"),
            ("Подтвердить поставку комплектующих", 2, "pending", "medium"),
            ("Подготовить акт о завершении работ", 8, "in_progress", "medium"),
        ], start=1)
    ]
    alerts = [{
        "id": "demo-alert-1", "alert_type": "DEADLINE_BREACH", "severity": "CRITICAL",
        "title": "Просрочена приёмка сервисной площадки",
        "description": "Срок истёк четыре дня назад. Требуется согласовать новую дату.",
        "calculated_financial_impact": 7200, "is_resolved": False,
        "created_at": f"{day(-4)}T08:00:00+04:00",
    }]
    procurement = [{
        "id": "demo-supply-1", "project_name": project["project_name"],
        "item_name": "Комплект креплений", "quantity": 12, "unit": "шт.",
        "supplier": "Учебный поставщик", "invoice_amount": 24_000,
        "status": "paid", "delivery_deadline": day(2), "invoice_number": "DEMO-11",
        "created_at": f"{day(-5)}T10:00:00+04:00",
    }]
    dispatch = [{
        "id": "demo-dispatch-1", "shift_date": day(0),
        "target_object": project["project_name"], "resource_type": "crew",
        "unit_name": "Демо-бригада №1", "responsible_person": "Куратор демо",
        "status": "on_site",
    }]
    return today, projects, registry, tasks, alerts, procurement, dispatch


def finance(today, period):
    if period == "year":
        start = today.replace(month=1, day=1)
    elif period == "quarter":
        start = today - timedelta(days=89)
    else:
        start = today.replace(day=1)

    dynamics = [
        {
            "date": (today - timedelta(days=offset)).isoformat(),
            "incoming": 22_000 + (offset * 8111) % 95_000,
            "outgoing": 13_000 + (offset * 6127) % 80_000,
        }
        for offset in range(min((today - start).days, 160), -1, -1)
    ]
    incoming = sum(point["incoming"] for point in dynamics)
    outgoing = sum(point["outgoing"] for point in dynamics)
    return {
        "dynamics": dynamics, "total_incoming": incoming, "total_outgoing": outgoing,
        "net_cash_flow": incoming - outgoing, "top_debtors": [], "top_creditors": [],
    }
