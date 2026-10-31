# Спецификация API: Дашборд и Аналитика
## Модуль: Dashboard & Analytics API | Проект: Smart Enterprise Hub (MVP)

Данный документ описывает эндпоинты агрегации данных для экранов первого взгляда руководителя («Где горит?»), аналитики движения денежных средств, производственных объектов и фонда оплаты труда.

---

## 1. `GET /api/v1/dashboard/summary` — Главный экран руководителя («Executive Fire-Panel»)

Критический эндпоинт первого экрана. Рассчитывает сводную статистику за секунды.

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "financial_health": {
      "current_cash_balance": 18450200.00,
      "forecast_14d_inflow": 4200000.00,
      "forecast_14d_outflow": 5850000.00,
      "is_cash_gap_predicted": false,
      "gap_deficit_amount": 0.00,
      "gap_date": null
    },
    "production_health": {
      "total_active_projects": 12,
      "total_portfolio_sum": 148500000.00,
      "average_completion_percent": 64.2,
      "projects_at_risk_count": 3,
      "total_calculated_penalties": 482000.00
    },
    "alerts_overview": {
      "critical_count": 2,
      "warning_count": 4,
      "info_count": 7
    },
    "top_fire_items": [
      {
        "id": "e0000000-0000-0000-0000-000000000001",
        "severity": "CRITICAL",
        "title": "Срыв срока: Кислородный цех №101",
        "description": "Отставание 4 дня. Расчетная неустойка по контракту 44-ФЗ: 48 200 ₽.",
        "financial_impact": 48200.00,
        "due_date": "2026-10-07",
        "responsible": "Петров В.А."
      },
      {
        "id": "e0000000-0000-0000-0000-000000000002",
        "severity": "CRITICAL",
        "title": "Истекает банковская гарантия",
        "description": "Гарантия ПАО Сбербанк по объекту №104 истекает через 3 дня.",
        "financial_impact": 1200000.00,
        "due_date": "2026-10-14",
        "responsible": "Кузнецов Д.В."
      }
    ]
  },
  "error": null,
  "meta": { "generated_at": "2026-10-11T14:45:00Z" }
}
```

---

## 2. `GET /api/v1/dashboard/finance` — Аналитика движения ДС и кассы

### Query-параметры:
- `period`: `month`, `quarter`, `year` (по умолчанию `month`).
- `start_date`, `end_date`: кастомный диапазон дат.

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "total_incoming": 24500000.00,
    "total_outgoing": 19200000.00,
    "net_cash_flow": 5300000.00,
    "dynamics": [
      { "date": "2026-10-01", "incoming": 1200000.00, "outgoing": 450000.00 },
      { "date": "2026-10-02", "incoming": 800000.00, "outgoing": 1100000.00 }
    ],
    "top_debtors": [
      { "counterparty": "АО МосИнжПроект", "debt_sum": 4150000.00, "overdue_days": 12 },
      { "counterparty": "ООО ПромТехСтрой", "debt_sum": 2100000.00, "overdue_days": 0 }
    ],
    "top_creditors": [
      { "counterparty": "Северсталь Дистрибуция", "debt_sum": 1800000.00, "payment_due_date": "2026-10-18" }
    ]
  },
  "error": null
}
```

---

## 3. `GET /api/v1/dashboard/projects` — Реестр тендеров и производства

### Query-параметры:
- `status`: `in_progress`, `completed`, `all`.
- `risk_level`: `critical`, `warning`, `normal`.

### Ответ (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": "d0000000-0000-0000-0000-000000000001",
      "project_code": "ТЭП-101",
      "project_name": "Кислородный цех №101",
      "customer_name": "ООО МеталлургСтрой",
      "curator_name": "Петров В.А.",
      "contract_sum": 14200000.00,
      "completed_sum": 8400000.00,
      "paid_sum": 7000000.00,
      "debt_sum": 1400000.00,
      "completion_percent": 59.1,
      "start_date": "2026-05-01",
      "deadline_date": "2026-10-07",
      "days_overdue": 4,
      "risk_level": "critical",
      "penalty_amount_calculated": 48200.00
    }
  ],
  "meta": {
    "page": 1,
    "limit": 20,
    "total_items": 1
  }
}
```

---

## 4. `GET /api/v1/dashboard/payroll` — Аналитика фонда оплаты труда

### Query-параметры:
- `period`: `2026-09` (месяц начисления).

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "period": "2026-09",
    "total_accrued": 4250000.00,
    "total_paid": 3800000.00,
    "total_debt": 450000.00,
    "next_payment_deadline": "2026-10-15",
    "by_department": [
      { "department": "Монтажный участок №1", "accrued": 2100000.00, "paid": 2100000.00, "debt": 0.00 },
      { "department": "ПТО и проектировщики", "accrued": 1200000.00, "paid": 950000.00, "debt": 250000.00 },
      { "department": "АУП и руководство", "accrued": 950000.00, "paid": 750000.00, "debt": 200000.00 }
    ]
  },
  "error": null
}
```
