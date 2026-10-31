# Словарь данных (Data Dictionary)
## СУБД: PostgreSQL 16 | Проект: Smart Enterprise Hub (MVP)

В данном документе приведено исчерпывающее описание всех сущностей, полей, типов данных, ограничений и бизнес-правил реляционной базы данных.

---

## 1. Таблица `companies` (Организации-клиенты / Тенанты)

Якорная сущность мультиарендности. Изолирует данные различных юридических лиц.

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ организации. |
| `name` | `VARCHAR(255)` | NO | - | Официальное наименование организации (например, *ООО «ГлавСтрой»*). |
| `inn` | `VARCHAR(12)` | YES | NULL | ИНН организации (10 или 12 цифр). |
| `kpp` | `VARCHAR(9)` | YES | NULL | КПП организации (9 цифр). |
| `timezone` | `VARCHAR(50)` | YES | `'Europe/Moscow'` | Часовой пояс для планирования утреннего дайджеста. |
| `is_active` | `BOOLEAN` | NO | `true` | Флаг активности компании (блокировка при неоплате). |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Дата и время регистрации компании. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Дата последнего изменения профиля. |

---

## 2. Таблица `users` (Пользователи и права доступа)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ пользователя. |
| `company_id` | `UUID` | NO | - | Внешний ключ $\rightarrow$ `companies.id` (ON DELETE CASCADE). |
| `email` | `VARCHAR(255)` | NO | - | Уникальный логин (E-mail) для входа в систему. |
| `password_hash` | `VARCHAR(255)` | NO | - | Хеш пароля (Argon2id или Bcrypt). |
| `full_name` | `VARCHAR(255)` | NO | - | ФИО сотрудника. |
| `role` | `user_role_enum` | NO | `'viewer'` | Роль: `admin` (управление всем), `manager` (загрузка и правка), `viewer` (только просмотр). |
| `telegram_chat_id`| `BIGINT` | YES | NULL | Идентификатор чата в Telegram для отправки персональных уведомлений. |
| `is_active` | `BOOLEAN` | NO | `true` | Флаг доступа учетной записи. |
| `last_login_at` | `TIMESTAMPTZ` | YES | NULL | Время последней успешной авторизации. |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время создания аккаунта. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время последнего обновления. |

---

## 3. Таблица `uploaded_files` (Реестр загруженных документов)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ файла. |
| `company_id` | `UUID` | NO | - | Внешний ключ $\rightarrow$ `companies.id` (ON DELETE CASCADE). |
| `uploaded_by_user_id`| `UUID` | YES | NULL | Внешний ключ $\rightarrow$ `users.id` (кто загрузил). |
| `original_name` | `VARCHAR(255)` | NO | - | Исходное имя загруженного файла. |
| `storage_path` | `VARCHAR(500)` | NO | - | Физический путь в томе (`tenants/{company_id}/.../{hash}.xlsx`). |
| `file_size_bytes`| `BIGINT` | NO | - | Размер файла в байтах (лимит до 25 МБ). |
| `mime_type` | `VARCHAR(100)` | NO | - | MIME-тип (например, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`). |
| `sha256_hash` | `VARCHAR(64)` | NO | - | Контрольная сумма содержимого файла для дедупликации. |
| `status` | `file_status_enum`| NO | `'uploaded'` | Статус обработки: `uploaded`, `profiling`, `awaiting_confirmation`, `processed`, `failed`. |
| `error_message` | `TEXT` | YES | NULL | Текст ошибки, если парсинг завершился сбоем. |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Дата и время загрузки файла. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Дата последнего изменения статуса. |
| `deleted_at` | `TIMESTAMPTZ` | YES | NULL | Метка мягкого удаления. |

---

## 4. Таблица `file_templates` (Кэш сопоставлений колонок / Fingerprints)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ сохраненного шаблона. |
| `company_id` | `UUID` | NO | - | Внешний ключ $\rightarrow$ `companies.id` (ON DELETE CASCADE). |
| `template_name` | `VARCHAR(255)` | NO | - | Человекочитаемое имя шаблона (например, *«Реестр договоров ПТО»*). |
| `sheet_name` | `VARCHAR(255)` | YES | `'Sheet1'` | Имя листа в Excel-книге. |
| `headers_fingerprint`| `VARCHAR(64)` | NO | - | SHA-256 хеш нормализованного списка названий колонок. |
| `domain_category`| `domain_category_enum`| NO | - | Канонический домен (`production_tenders`, `cashflow_debt` и т.д.). |
| `column_mapping` | `JSONB` | NO | - | JSON-словарь сопоставления: `{"Договорная цена, руб.": "contract_sum", ...}`. |
| `confidence_score`| `NUMERIC(5,2)` | YES | `1.00` | Уверенность распознавания (1.00 при подтверждении человеком). |
| `match_count` | `INT` | NO | `1` | Счетчик успешных повторных применений шаблона. |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Дата создания шаблона. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Дата последнего применения/корректировки. |

---

## 5. Домен 1: Таблица `tender_projects` (Тендеры, СМР и контракты)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ проекта/объекта. |
| `company_id` | `UUID` | NO | - | Внешний ключ $\rightarrow$ `companies.id` (ON DELETE CASCADE). |
| `file_id` | `UUID` | YES | NULL | Внешний ключ $\rightarrow$ `uploaded_files.id` (источник данных). |
| `project_code` | `VARCHAR(100)` | YES | NULL | Номер/шифр контракта (например, *№ 44-ФЗ/2026-09*). |
| `project_name` | `VARCHAR(500)` | NO | - | Наименование объекта строительства / тендера. |
| `customer_name` | `VARCHAR(255)` | YES | NULL | Заказчик / генподрядчик. |
| `curator_name` | `VARCHAR(255)` | YES | NULL | Ответственный менеджер / прораб / куратор. |
| `contract_sum` | `NUMERIC(15,2)`| NO | `0.00` | Общая договорная цена с НДС. |
| `completed_sum` | `NUMERIC(15,2)`| NO | `0.00` | Объем выполненных работ (подписано КС-2/КС-3). |
| `paid_sum` | `NUMERIC(15,2)`| NO | `0.00` | Фактически оплаченная заказчиком сумма. |
| `debt_sum` | `NUMERIC(15,2)`| NO | `0.00` | Остаток к оплате / дебиторская задолженность. |
| `start_date` | `DATE` | YES | NULL | Плановая дата начала работ. |
| `deadline_date` | `DATE` | YES | NULL | Контрольный дедлайн сдачи объекта. |
| `actual_completion_date`| `DATE` | YES | NULL | Фактическая дата сдачи объекта. |
| `status` | `VARCHAR(50)` | NO | `'in_progress'` | Статус: `in_progress`, `completed`, `suspended`, `overdue`. |
| `risk_level` | `project_risk_enum`| NO | `'normal'` | Оценка риска: `normal`, `warning`, `critical`. |
| `penalty_amount_calculated`| `NUMERIC(15,2)`| NO | `0.00` | Начисленный расчетный штраф за дни просрочки. |
| `custom_attributes`| `JSONB` | YES | `'{}'` | Дополнительные колонки из нестандартных таблиц. |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Дата добавления записи. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Дата пересчета показателей. |
| `deleted_at` | `TIMESTAMPTZ` | YES | NULL | Метка мягкого удаления. |

---

## 6. Домен 2: Таблица `cashflow_operations` (Движение ДС и касса)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ транзакции/операции. |
| `company_id` | `UUID` | NO | - | Внешний ключ $\rightarrow$ `companies.id` (ON DELETE CASCADE). |
| `file_id` | `UUID` | YES | NULL | Источник $\rightarrow$ `uploaded_files.id`. |
| `operation_date` | `DATE` | NO | - | Дата совершения / планирования платежа. |
| `counterparty` | `VARCHAR(255)` | YES | NULL | Контрагент (поставщик, субподрядчик, покупатель). |
| `direction` | `cashflow_direction_enum`| NO | - | Направление: `incoming` (приход), `outgoing` (расход). |
| `category` | `VARCHAR(100)` | YES | NULL | Статья ДДС (Материалы, Налоги, Аренда, Выручка). |
| `planned_amount` | `NUMERIC(15,2)`| NO | `0.00` | Плановая сумма платежа. |
| `actual_amount` | `NUMERIC(15,2)`| NO | `0.00` | Фактически списанная / зачисленная сумма. |
| `is_paid` | `BOOLEAN` | NO | `false` | Проведен ли платеж банком. |
| `account_name` | `VARCHAR(100)` | YES | NULL | Расчетный счет / банк (например, *«Точка Р/С 40702...»*). |
| `payment_due_date`| `DATE` | YES | NULL | Крайний срок платежа (для кредиторской задолженности). |
| `document_number`| `VARCHAR(100)` | YES | NULL | Номер платежного поручения / счета. |
| `notes` | `TEXT` | YES | NULL | Назначение платежа / примечание. |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Временная метка создания. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Временная метка обновления. |
| `deleted_at` | `TIMESTAMPTZ` | YES | NULL | Метка мягкого удаления. |

---

## 7. Домен 3: Таблица `payroll_records` (ФОТ и выплаты)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ записи начисления. |
| `company_id` | `UUID` | NO | - | Внешний ключ $\rightarrow$ `companies.id` (ON DELETE CASCADE). |
| `file_id` | `UUID` | YES | NULL | Источник $\rightarrow$ `uploaded_files.id`. |
| `payroll_period` | `VARCHAR(20)` | NO | - | Период начисления (например, `'2026-09'`). |
| `employee_name` | `VARCHAR(255)` | NO | - | ФИО сотрудника / бригадира. |
| `department` | `VARCHAR(150)` | YES | NULL | Отдел / участок (например, *«Монтажный участок №2»*). |
| `role_title` | `VARCHAR(150)` | YES | NULL | Должность. |
| `accrued_amount` | `NUMERIC(15,2)`| NO | `0.00` | Начислено к выплате (с учетом оклада и премий). |
| `paid_amount` | `NUMERIC(15,2)`| NO | `0.00` | Фактически выплачено. |
| `debt_amount` | `NUMERIC(15,2)`| NO | `0.00` | Остаток задолженности предприятия перед сотрудником. |
| `payment_due_date`| `DATE` | YES | NULL | Плановая дата выплаты зарплаты по ТК РФ. |
| `status` | `payroll_status_enum`| NO | `'accrued'` | Статус: `accrued`, `partially_paid`, `paid`, `overdue`. |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время создания записи. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время обновления записи. |
| `deleted_at` | `TIMESTAMPTZ` | YES | NULL | Метка мягкого удаления. |

---

## 8. Домен 4: Таблица `operational_tasks` (Поручения и комплаенс)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ задачи. |
| `company_id` | `UUID` | NO | - | Внешний ключ $\rightarrow$ `companies.id` (ON DELETE CASCADE). |
| `file_id` | `UUID` | YES | NULL | Источник $\rightarrow$ `uploaded_files.id`. |
| `task_title` | `VARCHAR(500)` | NO | - | Краткое содержание задачи / предписания. |
| `description` | `TEXT` | YES | NULL | Подробное описание. |
| `responsible_person`| `VARCHAR(255)`| YES | NULL | Ответственный исполнитель. |
| `due_date` | `DATE` | YES | NULL | Контрольный срок исполнения. |
| `status` | `task_status_enum`| NO | `'pending'` | Статус: `pending`, `in_progress`, `completed`, `overdue`. |
| `priority` | `task_priority_enum`| NO | `'medium'`| Приоритет: `low`, `medium`, `high`, `urgent`. |
| `penalty_risk_desc`| `TEXT` | YES | NULL | Описание последствий срыва (штраф ГАТИ, неустойка). |
| `estimated_penalty_amount`| `NUMERIC(15,2)`| NO | `0.00` | Расчетная сумма штрафа при просрочке. |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время фиксации задачи. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время обновления статуса. |
| `deleted_at` | `TIMESTAMPTZ` | YES | NULL | Метка мягкого удаления. |

---

## 9. Таблица `system_alerts` (Реестр выявленных рисков и алертов)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ алерта. |
| `company_id` | `UUID` | NO | - | Внешний ключ $\rightarrow$ `companies.id` (ON DELETE CASCADE). |
| `domain_category`| `domain_category_enum`| NO | - | Источник события (`production_tenders`, `cashflow_debt`...). |
| `severity` | `alert_severity_enum` | NO | - | Критичность: `CRITICAL` (красный), `WARNING` (желтый), `INFO` (синий). |
| `alert_type` | `VARCHAR(50)` | NO | - | Системный тип: `DEADLINE_BREACH`, `CASH_GAP`, `WAGE_OVERDUE`. |
| `entity_type` | `VARCHAR(50)` | YES | NULL | Имя таблицы источника (`tender_projects`, `cashflow_operations`). |
| `entity_id` | `UUID` | YES | NULL | ID целевой строки в соответствующей таблице. |
| `title` | `VARCHAR(300)` | NO | - | Заголовок оповещения (например, *«Срыв срока: Объект №101»*). |
| `description` | `TEXT` | NO | - | Детальный расчет финансовых последствий и рекомендация. |
| `calculated_financial_impact`| `NUMERIC(15,2)`| NO | `0.00` | Финансовый ущерб (сумма пени или прогнозируемый кассовый разрыв). |
| `trigger_date` | `DATE` | NO | `CURRENT_DATE` | Дата возникновения триггера. |
| `is_resolved` | `BOOLEAN` | NO | `false` | Статус решения: закрыт ли инцидент. |
| `resolved_at` | `TIMESTAMPTZ` | YES | NULL | Время закрытия инцидента. |
| `resolved_by_user_id`| `UUID` | YES | NULL | Кто отметил инцидент решенным. |
| `resolution_comment` | `TEXT` | YES | NULL | Комментарий при закрытии алерта. |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время генерации события. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время изменения статуса. |

---

## 10. Таблица `integration_settings` (Интеграции и боты)

| Поле | Тип | Nullable | Default | Описание и бизнес-правила |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `UUID` | NO | `uuid_generate_v4()` | Первичный ключ настроек. |
| `company_id` | `UUID` | NO | - | Уникальный внешний ключ $\rightarrow$ `companies.id`. |
| `telegram_bot_enabled`| `BOOLEAN`| NO | `false` | Включена ли отправка в Telegram. |
| `telegram_bot_token`| `VARCHAR(255)`| YES | NULL | Персональный токен бота (или общий системный бот). |
| `telegram_channel_id`| `BIGINT` | YES | NULL | ID группового чата руководства в Telegram. |
| `daily_digest_enabled`| `BOOLEAN`| NO | `true` | Включен ли утренний дайджест. |
| `daily_digest_time`| `VARCHAR(5)`| NO | `'08:30'` | Время рассылки по часовому поясу компании. |
| `alert_rules` | `JSONB` | YES | - | Правила чувствительности (пороги дней до дедлайна, лимиты). |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время создания настроек. |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Время обновления настроек. |
