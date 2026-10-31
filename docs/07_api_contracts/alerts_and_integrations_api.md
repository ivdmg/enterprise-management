# Спецификация API: Риски, Алерты и Интеграция с Telegram
## Модуль: Alerts & Integrations API | Проект: Smart Enterprise Hub (MVP)

Данный документ описывает протокол управления рисками, закрытия алертов и настройки интеграции с Telegram-ботом компании.

---

## 1. `GET /api/v1/alerts` — Реестр выявленных алертов и рисков

### Query-параметры:
- `severity`: `CRITICAL`, `WARNING`, `INFO` (опционально).
- `is_resolved`: `false` (по умолчанию `false` — только активные угрозы).
- `domain_category`: `production_tenders`, `cashflow_debt` (опционально).

### Ответ (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": "e0000000-0000-0000-0000-000000000001",
      "severity": "CRITICAL",
      "domain_category": "production_tenders",
      "alert_type": "DEADLINE_BREACH",
      "title": "Срыв срока сдачи КС-2: Кислородный цех №101",
      "description": "Объект просрочен на 4 дня. Расчетная неустойка (1/300 ключевой ставки): 48 200 ₽.",
      "calculated_financial_impact": 48200.00,
      "trigger_date": "2026-10-07",
      "is_resolved": false,
      "entity_type": "tender_projects",
      "entity_id": "d0000000-0000-0000-0000-000000000001",
      "created_at": "2026-10-08T08:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "limit": 20,
    "total_unresolved_critical": 1
  }
}
```

---

## 2. `POST /api/v1/alerts/{alert_id}/resolve` — Закрытие алерта

Позволяет руководителю или менеджеру отметить инцидент как устраненный, указав причину (например: *«Дополнительное соглашение на перенос срока подписано заказчиком»*).

### Запрос:
```json
{
  "resolution_comment": "Доп. соглашение №2 подписано 11.10.2026, срок перенесен на 25.10.2026."
}
```

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "id": "e0000000-0000-0000-0000-000000000001",
    "is_resolved": true,
    "resolved_at": "2026-10-11T14:50:00Z",
    "resolved_by": "Иванов Иван Иванович"
  },
  "error": null
}
```

---

## 3. `GET /api/v1/integrations/telegram` — Настройки Telegram-бота

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "telegram_bot_enabled": true,
    "bot_username": "SmartEnterpriseHubBot",
    "group_channel_connected": true,
    "daily_digest_enabled": true,
    "daily_digest_time": "08:30",
    "alert_rules": {
      "deadline_warning_days": 5,
      "cash_gap_forecast_days": 14,
      "notify_on_critical_instant": true
    }
  },
  "error": null
}
```

---

## 4. `PATCH /api/v1/integrations/telegram` — Обновление настроек рассылки

### Запрос:
```json
{
  "daily_digest_enabled": true,
  "daily_digest_time": "09:00",
  "telegram_bot_enabled": true
}
```

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "message": "Настройки интеграции успешно обновлены"
  }
}
```

---

## 5. `POST /api/v1/integrations/telegram/test-send` — Отправка тестового уведомления

Отправляет тестовое сообщение в подключенный чат руководителя для проверки связи.

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "status": "delivered",
    "message": "Тестовое сообщение успешно доставлено в Telegram"
  }
}
```

---

## 6. `POST /api/v1/telegram/webhook` — Входящий вебхук от Telegram Bot API

Обрабатывает нажатия интерактивных inline-кнопок директором прямо из интерфейса Telegram:
- Кнопка *«✅ Отметить решенным»* $\rightarrow$ закрывает алерт в БД.
- Кнопка *«📊 Открыть в дашборде»* $\rightarrow$ генерирует защищенную ссылку на объект.
