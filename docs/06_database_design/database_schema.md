# Проектирование реляционной схемы базы данных (Database Schema)
## СУБД: PostgreSQL 16 | Проект: Smart Enterprise Hub (MVP)

В данном документе представлена архитектура реляционной базы данных для платформы. Схема спроектирована с учетом строгой изоляции мультиарендности (`company_id`), ссылочной целостности, высокой производительности аналитических запросов и гибкости за счет использования полей `JSONB`.

---

## 1. Концептуальные принципы моделирования

1. **Строгая мультиарендность (Tenant Isolation)**:
   - Каждая таблица бизнес-данных (`tender_projects`, `cashflow_operations`, `uploaded_files` и т.д.) содержит обязательный внешний ключ `company_id REFERENCES companies(id) ON DELETE CASCADE`.
   - Запросы выборки всегда индексируются с префиксом `company_id`, что гарантирует физическую невозможность утечки данных между организациями.
2. **Первичные ключи на базе UUID v4**:
   - Предотвращают подбор идентификаторов перебором (IDOR-атаки) и упрощают миграции/репликации данных в будущем.
3. **Двойной слой хранения (Реляционный + JSONB)**:
   - Ключевые показатели (суммы, даты, статусы, ответственные) хранятся в строгих типизированных колонках (`NUMERIC(15,2)`, `DATE`, `VARCHAR`), что гарантирует математическую точность и быстрые SQL-агрегации (`SUM`, `AVG`, `COUNT`).
   - Нестандартные атрибуты конкретного Excel-файла (например, *«Номер секции здания»*, *«Код субподрядчика»*) сохраняются в колонке `custom_attributes JSONB`, сохраняя гибкость без изменения схемы БД.
4. **Мягкое удаление (Soft Deletes)**:
   - Таблицы данных содержат поле `deleted_at TIMESTAMP NULL`. Удаленные документы и проекты не стираются физически сразу, что защищает от случайных ошибок пользователей.
5. **Аудит и временные метки**:
   - Каждая таблица содержит `created_at` и `updated_at` (поддерживается автоматическими триггерами PostgreSQL).

---

## 2. Диаграмма связей сущностей (Entity Relationship Diagram)

```mermaid
erDiagram
    COMPANIES ||--o{ USERS : "has members"
    COMPANIES ||--o{ UPLOADED_FILES : "owns files"
    COMPANIES ||--o{ FILE_TEMPLATES : "learned templates"
    COMPANIES ||--o{ TENDER_PROJECTS : "executes"
    COMPANIES ||--o{ CASHFLOW_OPERATIONS : "tracks cash"
    COMPANIES ||--o{ PAYROLL_RECORDS : "pays wages"
    COMPANIES ||--o{ OPERATIONAL_TASKS : "manages"
    COMPANIES ||--o{ SYSTEM_ALERTS : "receives"
    COMPANIES ||--|| INTEGRATION_SETTINGS : "configures"

    USERS ||--o{ UPLOADED_FILES : "uploads"
    USERS ||--o{ SYSTEM_ALERTS : "resolves"

    UPLOADED_FILES ||--o{ PARSING_JOBS : "has runs"
    UPLOADED_FILES ||--o{ TENDER_PROJECTS : "populates"
    UPLOADED_FILES ||--o{ CASHFLOW_OPERATIONS : "populates"
    UPLOADED_FILES ||--o{ PAYROLL_RECORDS : "populates"
    UPLOADED_FILES ||--o{ OPERATIONAL_TASKS : "populates"

    SYSTEM_ALERTS ||--o{ NOTIFICATION_LOGS : "delivers via"

    COMPANIES {
        uuid id PK
        varchar name
        varchar inn
        varchar timezone
        boolean is_active
        timestamp created_at
    }

    USERS {
        uuid id PK
        uuid company_id FK
        varchar email
        varchar password_hash
        varchar full_name
        varchar role
        bigint telegram_chat_id
        boolean is_active
        timestamp created_at
    }

    UPLOADED_FILES {
        uuid id PK
        uuid company_id FK
        uuid uploaded_by_user_id FK
        varchar original_name
        varchar storage_path
        bigint file_size_bytes
        varchar sha256_hash
        varchar status
        text error_message
        timestamp created_at
        timestamp deleted_at
    }

    FILE_TEMPLATES {
        uuid id PK
        uuid company_id FK
        varchar template_name
        varchar sheet_name
        varchar headers_fingerprint
        varchar domain_category
        jsonb column_mapping
        numeric confidence_score
        int match_count
        timestamp updated_at
    }

    PARSING_JOBS {
        uuid id PK
        uuid file_id FK
        timestamp started_at
        timestamp finished_at
        varchar status
        numeric confidence_score
        varchar ai_model_used
        int extracted_rows_count
        jsonb detected_headers
        int execution_time_ms
    }

    TENDER_PROJECTS {
        uuid id PK
        uuid company_id FK
        uuid file_id FK
        varchar project_code
        varchar project_name
        varchar customer_name
        varchar curator_name
        numeric contract_sum
        numeric completed_sum
        numeric paid_sum
        numeric debt_sum
        date start_date
        date deadline_date
        varchar status
        varchar risk_level
        numeric penalty_amount_calculated
        jsonb custom_attributes
    }

    CASHFLOW_OPERATIONS {
        uuid id PK
        uuid company_id FK
        uuid file_id FK
        date operation_date
        varchar counterparty
        varchar direction
        varchar category
        numeric planned_amount
        numeric actual_amount
        boolean is_paid
        varchar account_name
        date payment_due_date
    }

    PAYROLL_RECORDS {
        uuid id PK
        uuid company_id FK
        uuid file_id FK
        varchar payroll_period
        varchar employee_name
        varchar department
        numeric accrued_amount
        numeric paid_amount
        numeric debt_amount
        date payment_due_date
        varchar status
    }

    OPERATIONAL_TASKS {
        uuid id PK
        uuid company_id FK
        uuid file_id FK
        varchar task_title
        text description
        varchar responsible_person
        date due_date
        varchar status
        varchar priority
        numeric estimated_penalty_amount
    }

    SYSTEM_ALERTS {
        uuid id PK
        uuid company_id FK
        varchar domain_category
        varchar severity
        varchar alert_type
        uuid entity_id
        varchar title
        text description
        numeric calculated_financial_impact
        date trigger_date
        boolean is_resolved
        timestamp resolved_at
        uuid resolved_by_user_id FK
    }

    NOTIFICATION_LOGS {
        uuid id PK
        uuid alert_id FK
        varchar channel
        varchar recipient_target
        varchar status
        text error_message
        timestamp sent_at
    }

    INTEGRATION_SETTINGS {
        uuid id PK
        uuid company_id FK
        boolean telegram_bot_enabled
        varchar telegram_bot_token
        bigint telegram_channel_id
        boolean daily_digest_enabled
        varchar daily_digest_time
        jsonb alert_rules
    }
```

---

## 3. Детальный разбор доменных таблиц

### 3.1. Ядро мультиарендности и пользователей
- **`companies`**: Организация-клиент (арендатор). Хранит реквизиты, статус подписки, часовой пояс для корректной отправки утреннего дайджеста.
- **`users`**: Учетные записи сотрудников с разделением прав (`admin`, `manager`, `viewer`) и возможностью связки с Telegram аккаунтом.

### 3.2. Хранилище файлов и кэш схем парсинга
- **`uploaded_files`**: Реестр физических файлов с контрольной суммой SHA-256 для исключения дубликатов и статусом жизненного цикла (`uploaded` $\rightarrow$ `profiling` $\rightarrow$ `awaiting_confirmation` $\rightarrow$ `processed` / `failed`).
- **`file_templates`**: Ключевой компонент удешевления ИИ. Хранит отпечаток заголовков (`headers_fingerprint`) и подтвержденный маппинг колонок (`column_mapping`). При повторной загрузке файла маппинг применяется мгновенно с 0 затрат на LLM.
- **`parsing_jobs`**: Журнал сессий обработки таблиц. Позволяет мониторить время выполнения, точность модели (`confidence_score`) и расследовать сбои.

### 3.3. Канонические бизнес-домены (Canonical Data Models)
- **`tender_projects` (Домен 1: Производство и тендеры)**: Учет объектов строительства/контрактов. Позволяет рассчитывать отставание по срокам, остаток дебиторки и прогнозируемый штраф.
- **`cashflow_operations` (Домен 2: Финансы и касса)**: Реестр приходов и расходов. Обеспечивает построение графика ликвидности и выявление кассовых разрывов.
- **`payroll_records` (Домен 3: ФОТ и кадры)**: Фонд оплаты труда по подразделениям и сотрудникам. Позволяет отслеживать задолженность по зарплате перед коллективом.
- **`operational_tasks` (Домен 4: Поручения и комплаенс)**: Контрольные точки, сдача отчетов, продление банковских гарантий.

### 3.4. Риски, алерты и интеграции
- **`system_alerts`**: Централизованный реестр выявленных инцидентов (`CRITICAL`, `WARNING`, `INFO`). Хранит точный расчет ущерба (`calculated_financial_impact`), статус решения и ответственного.
- **`notification_logs`**: История рассылки в Telegram, браузерные пуши и Email.
- **`integration_settings`**: Настройки интеграции компании (токен Telegram-бота, время утренней рассылки, пороговые значения срабатывания тревог).

---

## 4. Стратегия индексов и оптимизация производительности

Для гарантии выборки данных дашборда быстрее 25 мс создаются специализированные индексы:

1. **Композитные индексы для фильтрации по компании**:
   - `idx_tender_projects_company_status`: `(company_id, status, deadline_date)`
   - `idx_cashflow_company_date`: `(company_id, operation_date, direction)`
   - `idx_alerts_company_unresolved`: `(company_id, is_resolved, severity)` — критически важен для мгновенной отрисовки счетчика алертов на колокольчике.
2. **Индексы дедупликации**:
   - `idx_files_company_hash`: `(company_id, sha256_hash)` — обеспечивает мгновенную проверку при Drag-and-Drop загрузке.
   - `idx_templates_lookup`: `(company_id, headers_fingerprint)` — быстрый поиск в кэше шаблонов за 1 мс.
3. **GIN-индексы для JSONB**:
   - `idx_templates_mapping_gin`: GIN-индекс по полю `column_mapping` для быстрого поиска по каноническим именам полей.
