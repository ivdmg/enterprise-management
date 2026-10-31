# Задачи для Backend-разработчика: Google Drive пайплайн, Парсеры 1С/Excel, Risk Engine и Сидирование данных (v2.0)
## Роль: Senior Python / FastAPI / SQLAlchemy Developer | Проект: Smart Enterprise Hub

---

## 🎯 Системный промпт для Backend-агента (Скопируйте в новый чат)

> **Твоя роль**: Ты — ведущий Senior Backend разработчик платформы Smart Enterprise Hub.
> **Твоя цель**: Обеспечить бесперебойную и отказоустойчивую работу серверной части: настроить надежный пайплайн синхронизации файлов с Google Диском, реализовать гибкий парсинг реальных документов (Excel-сметы, счета на оплату, банковские выписки 1CClientBankExchange), доработать Risk Engine для автоматического расчета штрафов по 44-ФЗ и контроля банковских гарантий, а также подготовить инструмент мгновенного наполнения базы данных реалистичными демо-данными (Seed CLI).
>
> **Стек и библиотеки**:
> - **Python 3.11+ + FastAPI + SQLAlchemy 2.0 (Async) + Alembic + Pydantic v2**.
> - Фоновые задачи: **APScheduler / BackgroundTasks**.
> - Работа с документами: **OpenPyXL, Pandas, PyPDF2 / pdfplumber**.
> - Внешние API: **Google Drive API v3 (google-api-python-client, google-auth)**.
> - База данных: **SQLite (dev) / PostgreSQL (prod)**.
>
> **Критические правила разработки**:
> 1. **НЕ трогать фронтенд (`frontend/`)**. Все изменения строго внутри [`backend/`](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend).
> 2. **Строгая типизация и Pydantic v2**: Все эндпоинты должны быть защищены Pydantic-схемами (`backend/app/schemas/`). Никаких нетипизированных `dict` в ответах API.
> 3. **Никаких 500 ошибок при битых файлах**: Ошибки парсинга документов должны перехватываться и возвращать HTTP 422 с детальным описанием (номер строки, отсутствующая колонка, формат числа), а файл помечаться статусом `error` с сохранением причины в БД.
> 4. **Асинхронные транзакции**: Все операции записи в БД выполняются через `async with session.begin()` с гарантией отката при исключениях.
> 5. **Безопасность Google API**: Реализовать экспоненциальную задержку (Exponential Backoff) при обработке квот Google Drive (HTTP 429) и защитить системные папки от удаления.

---

## 📚 Контекст и файлы для изучения

1. [backend/app/main.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/main.py) — точка входа FastAPI, middleware, CORS, подключение роутеров.
2. [backend/app/core/config.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/core/config.py) — конфигурация (Pydantic Settings), переменные окружения Google Drive, пути к хранилищу.
3. [backend/app/api/v1/router.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/router.py) — реестр эндпоинтов API v1.
4. [backend/app/services/google_drive.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/google_drive.py) и [backend/app/services/drive_sync.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/drive_sync.py) — сервис работы с Google Drive.
5. [backend/app/services/template_parser.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/template_parser.py) — парсеры входящих Excel-файлов, счетов и выписок.
6. [backend/app/services/alerts_engine.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/alerts_engine.py) — движок генерации алертов и расчета рисков.
7. [backend/app/models/](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/models/) — ORM-модели (Project, Procurement, Dispatch, Finance, Task, Alert, File).

---

## 🚦 Правила ведения статуса задач в этом документе

Разработчик обязан вести статус по мере выполнения:
- `[ ] ⏳ В очереди` — задача ожидает старта.
- `[-] 🔄 В работе` — ведется написание кода.
- `[x] ✅ Завершено (Краткий отчет)` — код написан, протестирован через pytest/curl.
- `[!] ⚠️ Блокер` — есть вопрос или внешняя зависимость.

---

## 🛠️ Backlog задач для Backend-разработчика

### ФАЗА 1: Интеграция с Google Drive и надежный пайплайн синхронизации (P0)

- [x] ✅ **Задача BE-1.1: Автоматическая инициализация структуры папок на Google Диске**
  - Файлы: [backend/app/services/google_drive.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/google_drive.py), [backend/app/core/config.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/core/config.py), [backend/app/api/v1/sync.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/sync.py)
  - Отчет:
    - Добавлен метод `init_folders(root_folder_id)` в `GoogleDriveClient`, создающий 6 стандартных папок (`01_Сметы_и_Тендеры`, `02_Счета_Снабжения`, `03_Банк_и_Касса`, `04_Путевые_листы`, `05_Обработано`, `99_Ошибки_парсинга`).
    - Реализован эндпоинт `POST /api/v1/sync/init-folders` с Pydantic-схемами `InitFoldersRequest` и `InitFoldersResponse`.
    - Поддержана аутентификация через Service Account: чтение `credentials.json`, а также прямого JSON или Base64-строки из `GOOGLE_SERVICE_ACCOUNT_JSON`.
    - Папки защищены от удаления через `PROTECTED_FOLDERS`.

- [x] ✅ **Задача BE-1.2: Фоновый поллинг изменений и скачивание новых документов**
  - Файлы: [backend/app/services/drive_sync.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/drive_sync.py), [backend/app/core/scheduler.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/core/scheduler.py), [backend/app/services/google_drive.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/google_drive.py)
  - Отчет:
    - Фоновый опрос настроен через APScheduler с интервалом `SYNC_INTERVAL_SECONDS` (по умолчанию 120с).
    - В `GoogleDriveClient.list_files_in_folder` поддержана фильтрация по `modified_after` и типам документов.
    - Реализована функция `execute_with_backoff` для экспоненциальной задержки при HTTP 429/5xx (1s, 2s, 4s).
    - Файлы скачиваются во временное хранилище `storage/incoming/`, создается запись `UploadedFile` со статусом `uploaded`.

- [x] ✅ **Задача BE-1.3: Перемещение обработанных файлов на Google Диске**
  - Файлы: [backend/app/services/drive_sync.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/drive_sync.py), [backend/app/services/google_drive.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/google_drive.py)
  - Отчет:
    - Реализован метод `move_file(file_id, target_folder_name_or_id, current_folder_id, description)` для Live Drive API (`removeParents`/`addParents`) и Mock Drive.
    - При успешном парсинге файл перемещается в `05_Обработано`.
    - При ошибке парсинга файл перемещается в `99_Ошибки_парсинга`, статус в БД переводится в `error` с записью причины в `error_message`, а в метаданные Drive пишется текст ошибки в поле `description`.

---

### ФАЗА 2: Отказоустойчивые парсеры документов (Excel, 1C, PDF) (P0)

- [x] ✅ **Задача BE-2.1: Нечеткое сопоставление колонок (Fuzzy Matching) в Excel-парсере**
  - Файл: [backend/app/services/template_parser.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/template_parser.py)
  - Отчет:
    - Создан синонимический словарь `COLUMN_ALIASES` и функция нормализации названий колонок `normalize_column_name` (приведение к нижнему регистру, очистка спецсимволов и пробелов).
    - Реализован класс `FuzzyColumnMatcher` с поддержкой точного совпадения нормализованных алиасов и подстрочного поиска.
    - Реализована функция `find_header_row`, которая автоматически определяет первую строку заголовков в первых 25 строках таблицы, игнорируя шапки компании и декоративные строки.
    - Все парсеры стандартных шаблонов (сметы/тендеры, ДДС/касса, закупки/ТМЦ, диспетчеризация, задачи) переведены на использование FuzzyColumnMatcher.

- [x] ✅ **Задача BE-2.2: Парсер банковских выписок формата 1CClientBankExchange (.txt)**
  - Файл: [backend/app/services/template_parser.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/template_parser.py)
  - Отчет:
    - Реализован метод `parse_1c_client_bank_exchange`, парсящий секции `СекцияДокумент=Платежное поручение` с поддержкой кодировок Windows-1251 и UTF-8.
    - Извлекаются поля `Номер`, `Дата`, `Сумма`, `Плательщик`, `Получатель`, `НазначениеПлатежа`, `ПлательщикРасчСчет`.
    - Реализована категоризация:
      - При оплате по счету / за материалы/арматуру/бетон транзакция относится к статье «Оплата ТМЦ и материалов», а соответствующая позиция в реестре `ProcurementItem` переводится в статус `Оплачено`.
      - При выплатах заработной платы / под отчет создается запись в реестре `PayrollRecord` со статусом `paid`.
      - Все финансовые движения сохраняются в таблицу `CashflowOperation`.

- [x] ✅ **Задача BE-2.3: Graceful Error Handling и валидация входящих файлов**
  - Файлы: [backend/app/api/v1/files.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/files.py), [backend/app/main.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/main.py), [backend/app/schemas/files.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/schemas/files.py), [backend/app/services/template_parser.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/template_parser.py)
  - Отчет:
    - Создано исключение `DocumentValidationError` и Pydantic-схемы `FileValidationErrorResponse`, `FileValidationErrorDetail`.
    - Добавлен глобальный обработчик в `main.py`, возвращающий HTTP 422 с детализированным JSON: `status`, `message`, `details` (с указанием номера строки, колонки и ошибки).
    - В эндпоинте `/api/v1/files/upload` перехватываются ошибки чтения поврежденных файлов и неизвестных расширений, файл сохраняется со статусом `failed`/`error` и понятным логом в `error_message`.

---

### ФАЗА 3: Risk Engine и расчет неустоек 44-ФЗ / 223-ФЗ (P0)

- [x] ✅ **Задача BE-3.1: Расчет штрафов и пеней по 44-ФЗ с учетом ключевой ставки ЦБ РФ**
  - Файлы: [backend/app/services/alerts_engine.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/alerts_engine.py), [backend/app/core/config.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/core/config.py), [backend/app/schemas/alerts.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/schemas/alerts.py), [backend/app/api/v1/alerts.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/alerts.py)
  - Отчет:
    - В `Settings` добавлен параметр `KEY_RATE_PERCENT: float = 19.0` (по умолчанию 19.0%).
    - Реализован метод `AlertsEngine.calculate_44fz_penalty` по формуле 44-ФЗ:
      $$\text{Пени} = (\text{Цена контракта} - \text{Стоимость исполненных обязательств}) \times \text{Дни просрочки} \times \frac{1}{300} \times \text{Ключевая ставка ЦБ}$$
    - Реализованы эндпоинты `GET /api/v1/settings/key-rate` и `PATCH /api/v1/settings/key-rate` для чтения и обновления ставки в разрезе тенанта (через `IntegrationSetting.alert_rules["key_rate_percent"]`).
    - При срыве срока автоматически формируется алерт `DEADLINE_BREACH` со статусом `critical` в `SystemAlert`, рассчитывается точная сумма неустойки и объект отображается в блоке инцидентов сводки и виджете «Где горит?».

- [x] ✅ **Задача BE-3.2: Контроль сроков действия банковских гарантий (Риск РНП)**
  - Файлы: [backend/app/services/alerts_engine.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/alerts_engine.py), [backend/app/schemas/dashboard.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/schemas/dashboard.py), [backend/app/api/v1/dashboard.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/dashboard.py)
  - Отчет:
    - Реализована функция `AlertsEngine.calculate_bg_risk_level`:
      - При remaining $\le 5$ дней и незавершенном объекте $\rightarrow$ статус риска `critical`, генерация алерта `BANK_GUARANTEE_EXPIRING` с текстом: «Срок банковской гарантии истекает через N дн. Риск включения в РНП!».
      - При remaining от 6 до 15 дней $\rightarrow$ статус риска `warning`, генерация алерта: «Необходимо продлить БГ или подписать КС-2».
      - При просрочке (remaining < 0) $\rightarrow$ критический алерт `BANK_GUARANTEE_EXPIRED` с риском расторжения и РНП.
    - В схему `ProjectDashboardItem` и эндпоинт `GET /api/v1/dashboard/projects` добавлено строго типизированное поле `bg_risk_level: "critical" | "warning" | "ok"` и `bank_guarantee_expiry`.
    - Написаны и успешно пройдены тесты в `backend/tests/test_alerts_and_dashboard.py` (48/48 тестов во всем наборе проходят).

---

### ФАЗА 4: Seed-скрипт наполнения базы демо-данными (P1)

- [x] ✅ **Задача BE-4.1: Реализация CLI-команды сидирования `python -m app.db.seed`**
  - Файлы: [backend/app/db/seed.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/db/seed.py), [backend/app/schemas/procurement.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/schemas/procurement.py), [backend/app/api/v1/procurement.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/procurement.py), [backend/tests/test_seed.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/tests/test_seed.py)
  - Отчет:
    - Создан полнофункциональный CLI-скрипт `python -m app.db.seed` (время выполнения ~1.37 сек, строго < 3 сек).
    - База данных наполняется согласованным реалистичным набором данных:
      - Тенант: АО «Мосинжстрой» (ИНН 7701234567) и пользователи `admin@mosinzh.ru`, `chief@mosinzh.ru`, `pto@mosinzh.ru`.
      - **5 объектов СМР**: Школа на 1100 мест в мкр. Северный, Мост через р. Истра (ПК 42+00), ЖК «Северное Сияние», ТЦ «Авангард», Логистический парк «Юг» (со всеми степперами от bidding до contract и won).
      - **Банковские гарантии**: 1 гарантия на грани срока (< 4 дней, провоцирует критический риск РНП по Школе), 1 со статусом warning (10 дней), 2 активных и 1 закрытая.
      - **15 счетов ТМЦ в снабжении**: арматура А500С, бетон В25, кирпич, кабель, утеплитель Техноруф, PIR панели со статусами «Счет на оплате», «Оплачено», «В пути», «На объекте».
      - **8 единиц спецтехники в Диспетчерской**: автокран Liebherr, Putzmeister 36м, экскаватор CAT, самосвал КАМАЗ (в ремонте), башенный кран Potain, бульдозер Komatsu (простой), JCB 3CX, ДЗ-98.
      - **10 оперативных задач в Смарт-реестре**: привязаны к объектам и исполнителям (ГИП, снабженец, юрист, диспетчер, бухгалтер).
      - **Risk Engine («Где горит?»)**: автоматически выполняет расчет неустоек 44-ФЗ и генерирует критические алерты по истечению БГ и срыву поставки товарного бетона.
    - Реализован роутер [backend/app/api/v1/procurement.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/procurement.py) с эндпоинтом `GET /api/v1/procurement/items` и добавлен алиас `/api/v1/tasks/operational`.
    - Все эндпоинты `/api/v1/dashboard/summary`, `/api/v1/dashboard/projects`, `/api/v1/procurement/items`, `/api/v1/tasks/operational` проверены интеграционными тестами в `backend/tests/test_seed.py` (50 из 50 тестов проекта успешно проходят).

---

### ФАЗА 5: Аудит действий и API Hardening (P1)

- [x] ✅ **Задача BE-5.1: Логирование смены статусов (Audit Trail)**
  - Файлы: [backend/app/models/audit.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/models/audit.py), [backend/app/services/audit.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/services/audit.py), [backend/app/api/v1/tasks.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/tasks.py), [backend/app/api/v1/procurement.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/procurement.py), [backend/app/api/v1/dashboard.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/api/v1/dashboard.py)
  - Отчет:
    - Создана модель `AuditLog` (`audit_logs`) с полями: `id`, `company_id`, `user_id`, `entity_type` (project, procurement, task), `entity_id`, `old_status`, `new_status`, `ip_address`, `user_agent`, `timestamp`. Добавлены индексы для быстрого поиска по сущностям, тенанту и времени.
    - Реализован централизованный асинхронный сервис `record_audit_log`, извлекающий реальный IP-адрес клиента (`X-Forwarded-For` / `client.host`) и заголовок `User-Agent`.
    - Логирование интегрировано во все критические транзакции смены статусов:
      - `PATCH /api/v1/tasks/{task_id}/status`: логирование смены статуса задачи (`pending` $\rightarrow$ `in_progress` $\rightarrow$ `completed`).
      - `PATCH /api/v1/procurement/items/{item_id}/status`: логирование статуса счетов и поставок ТМЦ («Счет на оплате» $\rightarrow$ «Оплачено» $\rightarrow$ «В пути» $\rightarrow$ «На объекте»).
      - `PATCH /api/v1/dashboard/projects/{project_id}/stage`: логирование перехода стадий тендерных проектов (`tender_stage`).
    - Все записи выполняются в рамках единой асинхронной транзакции БД с гарантией согласованности.

- [x] ✅ **Задача BE-5.2: CORS и конфигурация сетевого доступа**
  - Файл: [backend/app/main.py](file:///c:/Users/Ivan/Desktop/enterprise%20management/backend/app/main.py)
  - Отчет:
    - В `CORSMiddleware` настроен гибкий regex `allow_origin_regex` для поддержки:
      - Локальной разработки: `http://localhost:5173`, `http://127.0.0.1:5173` и любых локальных портов.
      - Локальной сети и мобильного тестирования по Wi-Fi: частных подсетей `192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`.
    - Разрешены все методы HTTP (включая OPTIONS, PATCH, DELETE) и необходимые заголовки авторизации.
    - Покрытие подтверждено тестами в `backend/tests/test_audit_and_cors.py`.

---

## 📋 Чек-лист приемки для System Analyst / Tech Lead

Перед сдачей бэкенда проверить:
1. Запуск `python -m app.db.seed` проходит за < 3 сек и создает полную структуру тестовых данных.
2. Эндпоинты `/api/v1/dashboard/summary`, `/api/v1/dashboard/projects`, `/api/v1/procurement/items`, `/api/v1/tasks/operational` возвращают 200 OK с валидными схемами.
3. Парсер Excel корректно понимает синонимы колонок сметы и не падает с 500 ошибкой при битых строках.
4. Вызов синхронизации Google Диска работает с проверкой наличия папок и обработкой квот.
5. Расчет неустоек 44-ФЗ математически верен и совпадает с контрольными тестами.
