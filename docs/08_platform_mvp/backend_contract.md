# BE-00 — Контракты централизованной платформы

Проект для реализации BE-01–06 и FE-01/02. Состояние сверено по исходникам и Alembic. Живые сервисы и БД не проверялись.

## Инвентаризация и границы

| Область | Сейчас | Действие |
| --- | --- | --- |
| Идентичность | companies, users; глобальная уникальность email, bearer JWT; проверка активной компании и пользователя в api/deps.py | Вывести клиентские и платформенные сессии в разные пространства. Разрешить повтор email между компаниями после закрытия старого входа. Не выводить company_id из тела запроса, заголовка или строки запроса |
| Предметные строки | tender_projects, cashflow_operations, payroll_records, procurement_items, fleet_dispatch_records, operational_tasks; company_id на моделях, ссылки file_id по одному ID | Перепроверить вложенные и массовые операции, привязать ссылки к компании составными FK. При существующем ON DELETE SET NULL сохранять company_id, обнулять только ссылочный ID либо использовать согласованный явный порядок очистки |
| Файлы | uploaded_files и file_templates имеют company_id; parsing_jobs получает принадлежность через uploaded_files | Добавить company_id в задания с обратным заполнением через файл. API /files (листинг, upload, upload-and-assign, mapping-preview/confirm, DELETE) проверяет право и владение до чтения содержимого и записи. Проверить дедупликацию хеша, удаление и безопасную распаковку |
| Хранилище | LocalStorageService и ключ tenants/{company_id}/{YYYY}/{MM}/{sha256}{ext}, хранение и парсинг по локальному пути | Проверять префикс по сегментам, не по startswith строки пути. Разрешать ключ только из строки владельца, проверить выход через символические ссылки. При будущем скачивании или экспорте применять тот же ACL, запрещать общий кеш и прямую раздачу каталога. Готовый клиентский API выгрузок в роутере не обнаружен |
| Сигналы и настройки | system_alerts, integration_settings, audit_logs имеют company_id; notification_logs привязан через alert_id; часть ссылок на users содержит только ID | Заполнить company_id в notification_logs через alert, ограничить actor и resolver компанией. Проверить /alerts*, /integrations/telegram*, /settings/key-rate и /auth/telegram-link. Сырые настройки, получатели и ключи не попадают в поддержку |
| Источники | drive_catalog, engineer_documents (JSON на companies), sync, customer_tenders; глобальная конфигурация Drive, планировщик из lifespan и asyncio.create_task при ручном запуске | Подключения на компанию, запрет межклиентских чтений, отдельный исполнитель и БД заданий. Проверить статус на обоих клиентах, права листинга и границы при смене источника. В прежней версии SyncStatusData раскрывал глобальный root_folder_link. Переходная правка возвращает ссылку только при совпадении аутентифицированной компании с владельцем настроенного источника. Для новой схемы проверять доступ к каждой интеграции. Сохранить два листа, удаление строки, ручную стадию и неизвестные суммы |
| Остальной API | /dashboard (summary, alerts/critical, finance, projects, payroll, projects/{id}/stage), /tasks (включая operational и status), /dispatch/records*, /procurement/items* | Зафиксировать карту endpoint → модуль → действие, применить tenant guard также на агрегатах, поиске, сопоставлении выписки и каскадном изменении. /dashboard/summary скрывает показатели отключённых модулей |
| Общие процессы | /health проверяет доступность процесса; статусы Drive в памяти | Оставить liveness, добавить heartbeat исполнителя и безопасную проекцию доступности. Отделить общий сбой от сбоя источника |

Защита слоя хранения: транзакция устанавливает локальный проверенный контекст до первого доступа к tenant-таблице. RLS с USING и WITH CHECK, deny при отсутствии контекста, роль приложения не владелец и без BYPASSRLS. Не переиспользовать контекст в пуле; при commit и новом запросе в рамках HTTP устанавливать контекст заново. Проверить фоновые транзакции, bulk, rollback и повтор A → B. Для начального входа ограниченная функция/роль разрешает только точный поиск по нормализованным code/email и возвращает минимальные поля. Рабочее чтение выполняется с tenant scope после аутентификации. Инициализация scope должна учитывать get_db и endpoint-ы, которые сами делают commit и refresh: на первой SQL-операции каждой новой транзакции необходимо заново применить проверенный scope. Воркер получает scope из доверенной очереди, планировщик читает служебную проекцию расписаний, а не клиентские данные.

### Граница BE-01 в коде

Миграция 006 вводит RLS и составные проверки ссылок. Составные проверки работают на уровне PostgreSQL и сохраняют существующие каскадные связи ORM. Новые миграции не должны удалять их по одному лишь результату автоматической генерации. Company_id задач разбора и уведомлений переносится от родительских файлов и сигналов. Некорректная историческая связь блокирует миграцию вместо автоматического перевода данных между компаниями.

При отдельной настройке `DATABASE_RUNTIME_URL` и `DATABASE_WORKER_URL` используются две непривилегированные роли без членства в роли владельца таблиц. Ролям явно выдаются только права на используемые операции. Для runtime это операции клиентского API и закрытого входа. Для worker это scoped-доступ к импортируемым таблицам и запись статуса; команды платформы и учётки пользователей вне его грантов. У журнала аудита выдать INSERT и SELECT в нужном контуре, без UPDATE и DELETE. Роль панели и служебные проекции добавляются с BE-05. Отдельный `DATABASE_URL` остаётся подключением для Alembic. Если новые URL отсутствуют, действует совместимость существующего демо, владелец таблиц PostgreSQL обходит RLS. Режим с URL владельца пригоден для совместимости и технических проверок; коммерческий пилот требует проверки непривилегированных ролей.

Старый планировщик в режиме RLS получает явно привязанную компанию Google Drive; очередь нескольких живых интеграций добавляется в BE-04. Mock Drive при отдельной роли использует каталог на компанию. Автоматизированная проверка реальных SQL-политик выполняется через одноразовый PG16 командой `backend/tests/platform_pilot/run.py --postgres-bin <bin> --tenant-rls-only`.

## Права

| Операция | viewer | manager | admin (директор) | support | owner |
| --- | --- | --- | --- | --- | --- |
| Клиентские бизнес-данные, включённые модули | Чтение | Чтение и разрешённые мутации | Чтение и мутации | — | — |
| Сотрудники, аудит, запрос нового доступа | — | — | Своя компания, изменение имени/доступа/статуса обычного сотрудника, запрос приглашения | Выдача/отзыв приглашения по подтверждённой заявке | Первичный директор и восстановление директорского доступа |
| Интеграции | Статус разрешённых модулей | Статус | Статус, запрос повтора | Диагностика, черновики настройки, проверка и безопасный повтор | То же, публикация и откат конфигурации |
| Компании и инциденты | — | — | — | Просмотр служебных проекций, инциденты | То же, создание, активация и пауза |
| Платформенные роли | — | — | — | — | Выдача и отзыв |

Директор не меняет пароль сотрудника, не создаёт активную учётку, не назначает администратора. Последний активный директор защищён. Повышение до директора требует действия владельца и подтверждённой передачи полномочий. У прав доступа и состояния модулей есть серверные проверки. Скрытие кнопки служит только UX. Платформенная проекция имеет отдельные SQL-гранты и минимум полей, платформа не входит от лица клиента.

## Формат и безопасность API

JSON API под /api/v1. Формат ResponseEnvelope сохраняется: {success, data, error, meta}. error = {code, message, details}; meta содержит timestamp, на списках page/limit/total_items/total_pages. UTC ISO 8601, идентификаторы UUID, page=1 и limit=20 (максимум 100), стабильная сортировка с ID. Для мутаций запрещать поля вне заявленной схемы. X-Request-ID возвращается для диагностики. Session endpoint и ответы с клиентскими данными получают Cache-Control: no-store.

Сессия в непрозрачной HttpOnly Secure host-only cookie; разные имена и хосты/проверки назначения для client/platform. SameSite и проверка Origin плюс X-CSRF-Token на изменениях. GET /auth/csrf и GET /platform/auth/csrf возвращают {csrf_token}, привязанный к серверному challenge или сессии; получить свежий после входа и ротации. Состояния сессии active → revoked/expired, refresh однократный, конкурентные запросы на клиенте координируются, повтор прежнего refresh отзывает цепочку. Смена роли, пароля, email или блокировка отзывает текущие сессии. Истечение и проверка статуса компании применяются также при refresh. Любая учётка платформы проходит MFA; директор обязан пройти её при входе на коммерческом пилоте. TOTP secrets шифруются, коды восстановления хешируются и гасятся при использовании.

| HTTP | Код | Когда |
| --- | --- | --- |
| 401 | INVALID_CREDENTIALS, SESSION_REQUIRED | Неверная комбинация кода, email и пароля даёт один внешний ответ, сессия истекла или отозвана |
| 403 | FORBIDDEN, MODULE_DISABLED, CSRF_FAILED, COMPANY_PAUSED | Не хватает прав после входа, модуль отключён, сессия корректна, но контекст приостановлен либо запрос не прошёл CSRF |
| 404 | NOT_FOUND | Запись отсутствует или недоступна в текущем scope, одинаковый ответ |
| 409 | CONFLICT, STALE_REVISION, RUN_ALREADY_ACTIVE, LAST_DIRECTOR | Устаревшая версия, неподходящий переход, активный запуск или блокировка последнего директора |
| 410 | LINK_UNAVAILABLE | Ссылка истекла, уже использована или отозвана, без раскрытия иных данных |
| 422 | VALIDATION_ERROR | details содержит только допустимые имена полей и коды правил, без исходных значений |
| 429 | RATE_LIMITED | Единые лимиты по входу, MFA и восстановлению, Retry-After |
| 500/503 | INTERNAL_SERVER_ERROR, SERVICE_UNAVAILABLE | Безопасное сообщение и идентификатор запроса |

Повторяемые create/publish/retry используют Idempotency-Key в контексте актор + компания + действие. Один ключ с тем же телом возвращает тот же результат, с другим телом — 409. Конкурентные PATCH и transitions проверяют version перед изменением. Повтор автоматической попытки не равен новой ручной постановке. Истёкший результат идемпотентности не отменяет проверку уникальности сущности или активного запуска.

## Клиентский API

| Маршрут | Запрос | data и эффект |
| --- | --- | --- |
| POST /auth/login | {company_code,email,password} | {step:"authenticated",profile} с cookie либо {step:"mfa_required" или "mfa_enrollment_required",challenge_id,expires_at} без сессии |
| POST /auth/mfa/setup, /auth/mfa/verify | {challenge_id} для setup; {challenge_id,code} для verify | setup возвращает одноразовые параметры TOTP только для зачисления; verify возвращает authenticated при успехе |
| GET /auth/me | cookie | profile = {id,email,full_name,role,company:{id,code,name},permissions:[...]} |
| POST /auth/refresh, /auth/logout | cookie и CSRF | refresh ротирует cookie и возвращает profile; logout отзывает и очищает cookie, data null |
| POST /auth/invitation/accept | {token,password,full_name} | {state:"accepted"}; ссылка активирует ожидающую учётку и гасится атомарно; далее штатный login |
| POST /auth/password/forgot, /auth/password/reset | {company_code,email}; {token,password} | forgot всегда 202 {state:"accepted"}; reset подтверждает смену и отзывает сессии |
| GET /company/users; PATCH /company/users/{user_id} | список; {version,full_name?,role?,is_active?} | пользователь {id,full_name,email,role,is_active,version}; PATCH только обычного сотрудника; смена email отдельным подтверждением |
| POST /company/users/{user_id}/email-change; POST /auth/email-change/confirm | {version,new_email}; {token} | 202 при создании; подтверждение проверяет актуальность запроса, уникальность и отзывает сессии |
| GET/POST /company/access-requests | filters state; {email,full_name,role,reason?} | запрос {id,email,role,state,created_at}; вход в поддержку по безопасной проекции |
| GET /company/modules | cookie | {revision,modules:[{id,label,order,permissions}]} только разрешённые разделы |
| GET /company/integrations; POST /company/integrations/{integration_id}/retry-request | cookie; {reason?} | безопасный IntegrationStatus; запрос директором создаёт служебное событие без запуска от имени клиента |
| GET /company/audit | фильтры actor_id,action,entity_type,from,to | [{id,actor_id,actor_name,action,entity_type,entity_id,result,changes,created_at}]; changes ограничен полями по правилам модуля |

Смена email требует повторного подтверждения полномочий директора, уведомления старого адреса, подтверждения нового и повторной проверки версии сотрудника. Ссылки приглашения, сброса и смены адреса используют криптографически случайный токен с хешем в БД, срок и назначение проверяются сервером. Срок приглашения 48 ч, сброса 30 мин как стартовые настройки. Значения передавать в POST, при переходе из письма очистить URL от токена до сторонних запросов и исключить токен из access-логов. Не возвращать его в платформенном API.

Коды разрешений на новую область: company.team.read, company.team.write, company.access.request, company.audit.read, company.sources.read, company.sources.retry_request. Для бизнес-операций использовать {module}.read / {module}.write и дополнительные права для административных мутаций. Стартовые ID модулей: overview, contracts, engineer_documents, projects, finance, procurement, dispatch, tasks, sources, files, settings; источники и файлы не должны быть обходом ACL предметного модуля.

## Платформенный API

Префикс /platform. /auth/login принимает {email,password}, без company_code; login и MFA используют те же шаги с отдельной cookie. /auth/me возвращает {id,email,full_name,role,permissions}; /auth/refresh, /auth/logout и /auth/csrf аналогичны по форме с платформенной сессией. Потеря MFA восстанавливается по подтверждённому процессу владельца либо отдельной процедуре для последнего владельца. Список/выдача платформенных ролей через GET/POST /operators, изменение доступа через PATCH /operators/{operator_id}; только owner, закрытый процесс приглашения с обязательной MFA, запрет отключения последнего владельца.

| Маршрут (после /platform) | Вход | data |
| --- | --- | --- |
| GET /status | — | {status,worker_heartbeat_at,queue_depth,active_incident_count} |
| GET/POST /companies | фильтры state,health,search; POST {code,name} | CompanySummary |
| GET /companies/{id}; POST /companies/{id}/transitions | {version,to,reason} для перехода | CompanySummary |
| GET /companies/{id}/config; POST /companies/{id}/config/revisions | {base_revision,modules:[{id,label?,order,enabled,settings?}]} | {revision,state,modules,version} |
| POST /companies/{id}/config/revisions/{revision}/publish, /rollback | {expected_active_revision,reason} | активная ревизия, rollback создаёт новую ревизию из ранее утверждённой |
| GET/POST /companies/{id}/integrations | POST {type,label,adapter_id,adapter_version,module_id,source_ref,secret_ref,schedule,stale_after_seconds} | IntegrationStatus; secret_ref и source_ref на чтении не возвращаются |
| PATCH /companies/{id}/integrations/{integration_id} | {version,label?,adapter_version?,source_ref?,secret_ref?,schedule?,stale_after_seconds?,enabled?} | IntegrationStatus |
| POST /companies/{id}/integrations/{integration_id}/runs | {mode:"preview" или "import",reason,expected_integration_version,approved_preview_id?} | 202 RunSummary; изменённый профиль требует одобренного preview |
| POST /companies/{id}/runs/{run_id}/approve | {expected_integration_version,reason} | {approved_preview_id,expires_at}; только owner после подтверждения директора, привязка к версии и отпечатку источника |
| GET /companies/{id}/runs; GET /companies/{id}/runs/{run_id} | filters integration_id,state | RunSummary; preview содержит агрегаты и коды ошибок, сверка строк проходит в клиентском контуре |
| GET /companies/{id}/incidents; GET /companies/{id}/incidents/{incident_id} | state,severity,integration_id | IncidentSummary |
| POST /companies/{id}/incidents/{incident_id}/transitions | {version,to,reason,assignee_id?} | IncidentSummary |
| GET /companies/{id}/events | filters integration_id,severity,from,to | [{id,code,message,severity,next_step,integration_id,run_id,request_id,created_at}] |
| GET /companies/{id}/access-requests; GET/POST /companies/{id}/invitations | state; POST {access_request_id?,email?,full_name?,role?} | support для сотрудника обязан указать подтверждённый access_request_id; owner для директора задаёт email/имя/role=admin. InvitationSummary |
| POST /companies/{id}/access-requests/{request_id}/decline | {version,reason} | заявка со state=declined |
| POST /companies/{id}/invitations/{invitation_id}/reissue, /revoke | {version,reason} | InvitationSummary, письма создаются в транзакционном outbox |

CompanySummary = {id,code,name,state,health,modules:[{id,label}],integration_count,last_success_at,open_incident_count,assignee_id,version}. health healthy/degraded/unknown. IntegrationStatus = {id,label,type,module_id,adapter_id,adapter_version,status,last_success_at,last_attempt_at,next_attempt_at,stale_after_seconds,version,error?:{code,message,next_step,request_id}}. Статусы unchecked/running/current/stale/needs_attention/paused. Клиент получает только интеграции видимых модулей и понятные тексты. RunSummary = {id,integration_id,mode,state,attempt_count,adapter_version,release_version,request_id,created_at,started_at,finished_at,rows_processed,warning_count,error?}. IncidentSummary = {id,integration_id,severity,state,code,message,impact,next_step,run_id,assignee_id,version,opened_at,updated_at}. InvitationSummary = {id,email,role,state,created_at,expires_at,delivery_state,version}. Поля company_id допустимы как часть маршрута платформы, каждая связь с вложенным ID проверяется. Для экранов приглашений email доступен только с отдельным разрешением платформы.

Панель читает allowlist полей из проекций через ограниченную роль. Никаких ячеек, вложений, ссылок на исходники, текстов исключений, токенов и секретов. Комментарии инцидентов следует проверять на чувствительные данные, они не попадают в технические логи. Команды на изменения могут вызывать выделенные узкие операции с проверками, без прямого доступа платформы к бизнес-таблицам. Платформенный аудит содержит актор, действие, время, результат, company_id и correlation ID, без параметров с секретами. Для owner предусмотреть GET /platform/audit с фильтрами actor_id, company_id, action, from, to.

## Переходы и инварианты

- Компания draft → active ↔ paused → closed. Активация проверяет валидную ревизию, готовность источников и назначение директора через ожидающее приглашение или активную запись. Preview допускается для draft. При паузе отозвать сессии, погасить приглашения, запретить постановку и публикацию. В черновике выдача первого приглашения допустима, активация учётки возможна после активации компании. Приглашение разрешено отправлять после активации или повторно выпустить по запросу. Переход фиксируется в аудит и проверяется в транзакции публикации.
- Запрос доступа pending → invited → fulfilled после принятия приглашения либо pending → declined. Приглашение pending → accepted/expired/revoked; перевыпуск отзывает предыдущее и создаёт новый токен. Атомарные переходы и уникальный ожидающий активный токен на назначение, фоновый outbox проверяет актуальность записи перед отправкой.
- Конфигурация draft → active → superseded. Одновременно одна активная ревизия. Откат создаёт новую ревизию, ссылки на зарегистрированные адаптеры, совместимость схемы и права проверяются до публикации.
- Запуск queued → running → succeeded/failed/canceled или running → retry_wait → queued. Уникальность активного запуска по компании и интеграции, плановая дедупликация по временному слоту. Воркер берёт аренду с возрастающим поколением, heartbeat и блокировка проверяются вместе с поколением перед commit. Ошибки сети и лимиты повторяются с backoff. Ошибки формата и прав требуют вмешательства. Последний успешный снимок и время успеха сохраняются при неудаче; статус вычисляется по окну свежести. Preview не публикует строки; его approval связывается с ревизией конфигурации и отпечатком источника.
- Инцидент new → in_progress → escalated → verifying → closed, из in_progress возможен verifying, закрытый может вернуться в in_progress. Повтор ошибки создаёт событие и обновляет открытый инцидент по (company, integration, code). Следующая проверка успеха ведёт к verifying. В UI из каталога: SOURCE_ACCESS_REVOKED, SOURCE_TIMEOUT, SOURCE_RATE_LIMITED, SCHEMA_MISMATCH, SOURCE_STALE, WORKER_OFFLINE; последний код платформенный.
- Аудит успешных критичных мутаций записывать атомарно вместе с действием. Ошибки доступа и обращения к платформенным проекциям аудировать отдельным безопасным потоком, без выдачи лишних сведений клиенту.

## Порядок миграций и отключений

1. Текущая вершина 005_engineer_documents. Единый интегратор ревизий; ветки реализации согласуют порядок до присвоения down_revision. Проверить в отдельной БД создание с нуля и обновление существующей схемы.
2. Расширить схему: code и lifecycle компаний, ключи и индексы tenant, перенос company_id из родителей в parsing_jobs и notification_logs, таблицы сессий/приглашений/аудита/конфигураций/очереди. Заполнить данные, валидировать отсутствие несовпадающих ссылок до обязательности и ограничений. Несоответствия фиксировать и исправлять с сохранением владельца, без автоматического переноса строк между компаниями.
3. Заполнить код и базовый профиль действующей компании, перенести привязку источника с ссылкой на секрет без самих секретов. Подготовить существующие локальные файлы и проверки на совместимость. Директорские полномочия активировать по подтверждённой записи, не повышать всех manager.
4. Подключить клиентский API к проверенному scope и отдельной роли, проверить права и RLS в изолированной БД. Включить RLS в согласованной ревизии после адаптации всех путей, включая обработку ошибок, воркер и авторизацию. Начать проверку после остановки старого планировщика на копии.
5. Закрыть POST /auth/register и POST /company/users, заменить login/refresh/me на контракт с cookie и обязательным code при login. Убрать старые bearer токены и перевыпустить доступ, затем снять глобальную уникальность email, оставив ограничение (company_id, normalized_email). Старые конфигурации сервиса могут быть несовместимы после появления дублирующихся адресов.
6. Убрать POST /sync/init-folders и прямой POST /sync/drive-now, переключить GET /sync/status на новую проекцию либо убрать после обновления UI. /drive-catalog сохранить только для привязанной интеграции с явным модулем и правом. Прямое изменение legacy Telegram/settings ограничить админом и модулем; при отсутствии безопасного провайдера выключить соответствующие операции. Не выдавать старые подробности validation errors в новом API.

Критерий готовности контракта к реализации — обе стороны согласовали namespace, коды и поля. Добавление схем, данных или деплой в BE-00 не входят.
