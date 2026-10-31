# Руководство по предотвращению оверинжиниринга (Zero-Overengineering Guide)
## Проект: Smart Enterprise Hub (MVP)

Главный риск ранней стадии любого B2B-стартапа — потратить месяцы и бюджет на сложную инфраструктуру (Kubernetes, Kafka, Microservices, Sharding, тяжелые брокеры), которая не приносит ценности клиенту. Данное руководство устанавливает жесткие инженерные границы для команды разработчиков.

---

## 1. Сравнительная матрица: «Оверинжиниринг» против «Наш Lean MVP»

| Аспект системы | Корпоративный Overengineering (Чего мы НЕ делаем) | Наш Lean MVP подход (Что мы реализуем) | Бизнес-выгода Lean подхода |
| :--- | :--- | :--- | :--- |
| **Архитектура бэкенда** | 5–8 микросервисов (Auth, Parser, Alerts, Analytics, Gateway), gRPC / RabbitMQ | **Монолитный модульный бэкенд на FastAPI** в едином процессе | Нет сетевого оверхеда, отладка в 1 клик, запуск одной командой `uvicorn`. |
| **Очереди задач** | Celery + RabbitMQ / Apache Kafka + Flower Dashboard | **FastAPI `BackgroundTasks` + внутренний `APScheduler`** | Экономия 250+ МБ RAM, отсутствие рассинхронизации брокера и БД. |
| **Кэширование** | Кластер Redis / Memcached Sentinel | **In-memory LRU-кэш (`cachetools`) + индексы PostgreSQL** | Экономия 60 МБ RAM, нет риска сбоя отдельного сервиса кэша. |
| **Объектное хранилище** | Развертывание MinIO в Docker или платный AWS S3 бакет | **Локальный Persistent Volume с абстракцией `IStorageService`** | 0 ₽ затрат, 0 МБ лишней памяти, готовность к S3 в 1 строчку конфига. |
| **Фронтенд** | Server-Side Rendering (Next.js / SSR Node-сервер) | **Чистый клиентский SPA (React 18 + Vite)**, отдаваемый как статика | 0 МБ оперативной памяти Node.js на сервере, кэширование браузером. |
| **Оркестрация** | Kubernetes (k8s), Helm, Istio Service Mesh | **Один лаконичный `docker-compose.yml`** | Запуск на VPS за 180 ₽/мес без девопс-инженера. |

---

## 2. Бюджет аппаратных ресурсов (VPS 1 vCPU / 1 GB–2 GB RAM)

Ниже представлен детальный расчет потребления системных ресурсов при одновременной работе 10 компаний (до 15 пользователей):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        РАСПРЕДЕЛЕНИЕ RAM НА VPS                        │
├───────────────────────────────┬────────────────────────┬───────────────┤
│ Компонент                     │ Потребление в покое    │ Пик нагрузки  │
├───────────────────────────────┼────────────────────────┼───────────────┤
│ Linux OS (Ubuntu 22.04 LTS)   │ ~ 90 МБ                │ ~ 120 МБ      │
│ PostgreSQL 16 (Tuned Alpine)  │ ~ 110 МБ               │ ~ 160 МБ      │
│ FastAPI Backend + Worker      │ ~ 95 МБ                │ ~ 180 МБ      │
│ Nginx Reverse Proxy           │ ~ 15 МБ                │ ~ 25 МБ       │
├───────────────────────────────┼────────────────────────┼───────────────┤
│ ИТОГО ПОТРЕБЛЕНИЕ:            │ ~ 310 МБ               │ ~ 485 МБ      │
│ СВОБОДНЫЙ ЗАПАС (на 1GB VPS): │ > 600 МБ               │ > 500 МБ      │
└───────────────────────────────┴────────────────────────┴───────────────┘
```

> [!NOTE]
> При пиковых операциях парсинга файлов в 25 МБ библиотека `python-calamine` на Rust выделяет память кратковременно и мгновенно освобождает её, не создавая долгосрочной утечки памяти.

---

## 3. Образец производственного `docker-compose.yml`

Все приложение состоит всего из **двух легковесных контейнеров**:

```yaml
version: '3.8'

services:
  # База данных PostgreSQL 16
  postgres:
    image: postgres:16-alpine
    container_name: enterprise_hub_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: enterprise_hub
      POSTGRES_USER: ${DB_USER:-hub_user}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-secure_mvp_pass}
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./infra/postgres/low-memory.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    deploy:
      resources:
        limits:
          memory: 256M

  # Бэкенд API + Статический билд фронтенда + Nginx
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: enterprise_hub_app
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    environment:
      DATABASE_URL: postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE
      JWT_SECRET: ${JWT_SECRET}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      STORAGE_DRIVER: local
      STORAGE_LOCAL_PATH: /app/data/uploads
    volumes:
      - app_uploads:/app/data/uploads
      - ./certbot/conf:/etc/letsencrypt
    depends_on:
      - postgres
    deploy:
      resources:
        limits:
          memory: 384M

volumes:
  pg_data:
  app_uploads:
```

---

## 4. Стратегия масштабирования (Scale Triggers)

Мы не усложняем систему заранее, но фиксируем четкие метрики, при достижении которых команда производит апгрейд:

1. **Триггер добавления Redis**:
   - *Когда*: Количество одновременно загружаемых файлов в минуту превышает 20 шт. или число активных пользователей превышает 100 человек онлайн.
   - *Что делаем*: Подключаем Redis-контейнер и переводим `BackgroundTasks` на легкий `ARQ` или `Celery`.
2. **Триггер переезда на S3**:
   - *Когда*: Общий объем загруженных файлов компании превышает 40 ГБ или требуется распределенный доступ из разных дата-центров.
   - *Что делаем*: Меняем `STORAGE_DRIVER=s3` в `.env` и включаем бакет Yandex Object Storage (стоимость ~30 ₽ за 10 ГБ).
3. **Триггер шардирования / репликации БД**:
   - *Когда*: Размер PostgreSQL базы данных превышает 50 ГБ.
   - *Что делаем*: Подключаем Read-реплику для аналитических отчетов. В фазе MVP один инстанс PostgreSQL без проблем держит 50+ ГБ.
