# Спецификация API: Аутентификация и Управление Компанией
## Модуль: Auth & Company API | Проект: Smart Enterprise Hub (MVP)

Данный документ описывает эндпоинты регистрации компании, входа пользователей, ротации JWT-токенов, профиля и связки с Telegram.

---

## 1. `POST /api/v1/auth/register` — Регистрация компании и администратора

Создает запись в `companies`, учетную запись первого администратора в `users` и базовые настройки в `integration_settings`.

### Запрос (Request Body):
```json
{
  "company_name": "ООО ГлавСтройИнжиниринг",
  "inn": "7701987654",
  "full_name": "Иванов Иван Иванович",
  "email": "director@glavstroy.ru",
  "password": "StrongPassword123!"
}
```

### Успешный ответ (201 Created):
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "b0000000-0000-0000-0000-000000000001",
      "email": "director@glavstroy.ru",
      "full_name": "Иванов Иван Иванович",
      "role": "admin"
    },
    "company": {
      "id": "a0000000-0000-0000-0000-000000000001",
      "name": "ООО ГлавСтройИнжиниринг",
      "inn": "7701987654"
    },
    "tokens": {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 3600
    }
  },
  "error": null,
  "meta": { "timestamp": "2026-10-11T14:40:00Z" }
}
```

---

## 2. `POST /api/v1/auth/login` — Аутентификация

### Запрос:
```json
{
  "email": "director@glavstroy.ru",
  "password": "StrongPassword123!"
}
```

### Успешный ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "refresh_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "b0000000-0000-0000-0000-000000000001",
      "company_id": "a0000000-0000-0000-0000-000000000001",
      "email": "director@glavstroy.ru",
      "full_name": "Иванов Иван Иванович",
      "role": "admin"
    }
  },
  "error": null,
  "meta": { "timestamp": "2026-10-11T14:40:00Z" }
}
```

---

## 3. `POST /api/v1/auth/refresh` — Обновление access токена

### Запрос:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI..."
}
```

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "refresh_token": "eyJhbGciOiJIUzI1Ni...",
    "expires_in": 3600
  },
  "error": null
}
```

---

## 4. `GET /api/v1/auth/me` — Текущий профиль пользователя

### Запрос:
- Заголовок: `Authorization: Bearer <access_token>`

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "id": "b0000000-0000-0000-0000-000000000001",
    "email": "director@glavstroy.ru",
    "full_name": "Иванов Иван Иванович",
    "role": "admin",
    "telegram_connected": true,
    "company": {
      "id": "a0000000-0000-0000-0000-000000000001",
      "name": "ООО ГлавСтройИнжиниринг",
      "timezone": "Europe/Moscow"
    }
  },
  "error": null
}
```

---

## 5. `POST /api/v1/auth/telegram-link` — Генерация кода связки с Telegram

Генерирует временный токен и прямую ссылку на бота для подключения руководителя.

### Ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "link_code": "TG-LINK-948123",
    "bot_url": "https://t.me/SmartEnterpriseHubBot?start=link_948123",
    "expires_in_seconds": 600
  },
  "error": null
}
```

---

## 6. `GET /api/v1/company/users` — Список сотрудников компании

Доступно только пользователям с ролью `admin`.

### Ответ (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": "b0000000-0000-0000-0000-000000000001",
      "full_name": "Иванов Иван Иванович",
      "email": "director@glavstroy.ru",
      "role": "admin",
      "is_active": true,
      "telegram_chat_id": 987654321,
      "created_at": "2026-10-01T10:00:00Z"
    },
    {
      "id": "b0000000-0000-0000-0000-000000000002",
      "full_name": "Смирнова Елена (ПТО)",
      "email": "pto@glavstroy.ru",
      "role": "manager",
      "is_active": true,
      "telegram_chat_id": null,
      "created_at": "2026-10-02T12:30:00Z"
    }
  ],
  "error": null
}
```

---

## 7. `POST /api/v1/company/users` — Приглашение нового пользователя

### Запрос:
```json
{
  "full_name": "Петров Петр (Бухгалтерия)",
  "email": "buh@glavstroy.ru",
  "role": "manager",
  "initial_password": "TempPassword123!"
}
```

### Ответ (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "b0000000-0000-0000-0000-000000000003",
    "email": "buh@glavstroy.ru",
    "role": "manager",
    "created_at": "2026-10-11T14:45:00Z"
  },
  "error": null
}
```
