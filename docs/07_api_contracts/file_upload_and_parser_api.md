# Спецификация API: Загрузка файлов и Управление Парсером
## Модуль: Ingestion & Parser API | Проект: Smart Enterprise Hub (MVP)

Данный документ описывает протокол загрузки разнородных Excel-документов, получение предпросмотра структуры, подтверждение сопоставления колонок и сохранение в каноническую базу.

---

## 1. `POST /api/v1/files/upload` — Загрузка файла (Drag & Drop)

Принимает бинарный файл (`multipart/form-data`), производит потоковое вычисление хеша SHA-256, проверяет дедупликацию, сохраняет в хранилище и запускает быструю нормализацию.

### Запрос:
- Header: `Content-Type: multipart/form-data`
- Body Form Data: `file: <binary_stream>` (расширения: `.xlsx`, `.xls`, `.csv`, до 25 МБ).

### Успешный ответ (201 Created):
```json
{
  "success": true,
  "data": {
    "file_id": "c1000000-0000-0000-0000-000000000001",
    "original_name": "Реестр_объектов_СМР_Август.xlsx",
    "file_size_bytes": 1048576,
    "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "status": "awaiting_confirmation",
    "sheets": ["Лист1", "Сводная"],
    "is_cached_template": false
  },
  "error": null
}
```

### Ответ при обнаружении дубликата (409 Conflict):
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "DUPLICATE_FILE",
    "message": "Этот файл уже был загружен в систему ранее",
    "details": {
      "existing_file_id": "c0000000-0000-0000-0000-000000000099",
      "original_name": "Реестр_объектов_СМР_Август.xlsx",
      "uploaded_at": "2026-10-10T09:15:00Z"
    }
  }
}
```

---

## 2. `GET /api/v1/files/{file_id}/mapping-preview` — Предпросмотр сопоставления колонок

Возвращает распознанную структуру таблицы, предварительное решение ИИ (или кэша) и первые 3 строки сырых нормализованных данных для отображения пользователю в шторке UI.

### Query-параметры:
- `sheet_name` (опционально, по умолчанию первый активный лист).

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "file_id": "c1000000-0000-0000-0000-000000000001",
    "sheet_name": "Лист1",
    "suggested_domain": "production_tenders",
    "confidence_score": 0.96,
    "source_type": "ai_inference",
    "total_rows_detected": 142,
    "columns_mapping": [
      {
        "source_column": "Объект строительства",
        "sample_values": ["Кислородный цех №101", "Котельная БМК-12", "Склад готовой продукции"],
        "target_field": "project_name",
        "confidence": 0.99,
        "is_required": true
      },
      {
        "source_column": "Цена контракта, руб.",
        "sample_values": ["12 500 000.00", "4 800 000.00", "31 000 000.00"],
        "target_field": "contract_sum",
        "confidence": 0.98,
        "is_required": true
      },
      {
        "source_column": "Закрыто актами КС",
        "sample_values": ["8 200 000.00", "4 800 000.00", "12 000 000.00"],
        "target_field": "completed_sum",
        "confidence": 0.95,
        "is_required": false
      },
      {
        "source_column": "Срок выполнения работ",
        "sample_values": ["15.10.2026", "01.11.2026", "20.12.2026"],
        "target_field": "deadline_date",
        "confidence": 0.97,
        "is_required": true
      },
      {
        "source_column": "Куратор от заказчика",
        "sample_values": ["Петров В.А.", "Сидоров М.И.", "Иванов И.И."],
        "target_field": "curator_name",
        "confidence": 0.91,
        "is_required": false
      },
      {
        "source_column": "Внутренний артикул 1С",
        "sample_values": ["ART-0941", "ART-0942", "ART-0943"],
        "target_field": null,
        "confidence": 0.30,
        "is_required": false
      }
    ],
    "available_canonical_fields": [
      { "field": "project_name", "label": "Название объекта / проекта", "required": true },
      { "field": "project_code", "label": "Номер / шифр контракта", "required": false },
      { "field": "contract_sum", "label": "Сумма договора (руб.)", "required": true },
      { "field": "completed_sum", "label": "Выполнено / Закрыто по КС (руб.)", "required": false },
      { "field": "paid_sum", "label": "Оплачено заказчиком (руб.)", "required": false },
      { "field": "debt_sum", "label": "Остаток долга (руб.)", "required": false },
      { "field": "deadline_date", "label": "Срок сдачи / Дедлайн", "required": true },
      { "field": "curator_name", "label": "Ответственный куратор", "required": false }
    ]
  },
  "error": null
}
```

---

## 3. `POST /api/v1/files/{file_id}/mapping-confirm` — Подтверждение сопоставления и импорт

Пользователь подтверждает предложенную структуру или вносит свои корректировки. Сервер:
1. Сохраняет шаблон в `file_templates` (для бесплатного парсинга аналогичных файлов в будущем).
2. Запускает извлечение строк и записывает их в целевую доменную таблицу.
3. Запускает расчет алертов и рисков по добавленным записям.

### Запрос:
```json
{
  "sheet_name": "Лист1",
  "domain_category": "production_tenders",
  "template_name": "Реестр договоров ПТО 2026",
  "mappings": {
    "Объект строительства": "project_name",
    "Цена контракта, руб.": "contract_sum",
    "Закрыто актами КС": "completed_sum",
    "Срок выполнения работ": "deadline_date",
    "Куратор от заказчика": "curator_name",
    "Внутренний артикул 1С": "ignore"
  }
}
```

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "file_id": "c1000000-0000-0000-0000-000000000001",
    "status": "processed",
    "imported_rows_count": 142,
    "alerts_triggered_count": 3,
    "template_saved": true
  },
  "error": null
}
```

---

## 4. `GET /api/v1/files` — Список загруженных файлов

### Query-параметры:
`page=1&limit=20&status=processed`

### Ответ (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": "c1000000-0000-0000-0000-000000000001",
      "original_name": "Реестр_объектов_СМР_Август.xlsx",
      "file_size_bytes": 1048576,
      "status": "processed",
      "uploaded_by": "Иванов Иван Иванович",
      "created_at": "2026-10-11T14:30:00Z"
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

## 5. `DELETE /api/v1/files/{file_id}` — Мягкое удаление файла

Помечает файл и все извлеченные из него строки канонических таблиц как удаленные (`deleted_at = NOW()`).

### Ответ (200 OK):
```json
{
  "success": true,
  "data": { "message": "Файл и связанные записи успешно помечены удаленными" }
}
```
