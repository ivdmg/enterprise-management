# Перенос на ноутбук без смены базы и источника

## Что находится в GitHub

Исходники, миграции, Docker/Render-конфигурация, синтетические примеры, docs/, tasks/, agents/, PROJECT_CONTEXT.md и AGENTS.md. Зависимости фронтенда зафиксированы package-lock.json; рабочие версии бэкенда — backend/requirements.lock.txt. Python 3.12 (на исходном компьютере 3.12.14), Node.js 24 (24.13.0).

Git не переносит историю переписки приложения, настройки редактора и установленные плагины. Для нового чата используйте PROJECT_CONTEXT.md; исходные требования сохранены в docs/. Общее состояние продукта сохраняется через ту же облачную базу Neon и ту же папку Google Drive.

## Один раз на исходном компьютере

Запустите `python scripts/export_private_transfer.py` (можно через `.venv/Scripts/python.exe`). Получится `.demo/laptop.private.zip`. Он содержит реальные backend/.env, backend/credentials.json (если используется файл), демодоступы .demo/access.json, настройки Render и локальные копии tenant-файлов, если они есть. Архив не зашифрован. Перенесите его на свой ноутбук напрямую, например через личную флешку. Не загружайте его в репозиторий и не передавайте заказчику.

## На ноутбуке

Установите Git, Python 3.12 и Node.js 24. Затем в PowerShell:

```powershell
git clone https://github.com/ivdmg/enterprise-management.git
cd enterprise-management
```

Распакуйте личный архив прямо в корень этой папки, сохранив пути. Должны появиться backend/.env и backend/credentials.json; пароли лежат в .demo/access.json. Если архив находится рядом с папкой проекта:

```powershell
Expand-Archive -LiteralPath ../laptop.private.zip -DestinationPath . -Force
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

Не копируйте `.venv` или `node_modules` со старого компьютера: их нужно создать заново. Не запускайте seed и setup_demo: облачная база уже содержит компанию, пользователей и реальные записи. Не меняйте DATABASE_URL, GOOGLE_DRIVE_COMPANY_ID и корневую папку Drive на новые.

Для локального запуска:

```powershell
.\start-demo.ps1
```

Приложение откроется по http://127.0.0.1:8080. Войдите прежним пользователем. Для активной разработки можно вместо этого запустить бэкенд из backend/: `../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --reload`, а фронтенд — `npm.cmd --prefix frontend run dev`. Не запускайте оба варианта сервера одновременно.

Если проект уже работает на Render, локальный запуск с тем же .env тоже будет менять рабочую базу. Для экспериментов создайте отдельную тестовую БД. Для обычной разработки и показа на той же базе выключите остальные экземпляры сервера на компьютере/ноутбуке; миграции применяются при запуске Docker на Render. Пользовательские браузеры могут быть открыты одновременно.

## Проверка переноса

- Открывается форма входа, прежние логины работают.
- Видны сводка, реестр и ежедневный мониторинг.
- Google Drive открывает тот же документ «тендеры».
- Синхронизация обновляет тот же набор записей без создания новой компании.
- `git status --short` не показывает .env, credentials.json и приватный архив.

Без личного архива одного клонирования недостаточно: секреты специально исключены из Git. DATABASE_URL и данные Google берутся из backend/.env. Если путь к ключу в .env абсолютный и относится к старому компьютеру, замените только GOOGLE_DRIVE_CREDENTIALS_PATH на `credentials.json`, не создавая новый ключ.
