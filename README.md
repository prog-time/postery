# posting.iliya-code.ru — Автопостинг

Система управления и автоматической публикации контента в Telegram, ВКонтакте и MAX Мессенджер с поддержкой AI-генерации текста.

## Возможности

- **Мультиплатформенная публикация** — Telegram, ВКонтакте, MAX Мессенджер
- **Планировщик** — публикация по расписанию или немедленно
- **Кастомизация под источник** — свои заголовок и текст для каждого канала
- **AI-генерация** — переработка текста через OpenAI или GigaChat
- **Изображения** — поддержка одного и нескольких фото
- **Роли** — Суперадмин и Редактор
- **Шифрование** — все токены хранятся зашифрованными (Fernet)
- **Календарь публикаций** — визуальный обзор по дням

## Стек

| Компонент | Технология |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| Admin UI | Starlette-Admin |
| БД | SQLite + SQLAlchemy |
| Шаблоны | Jinja2 |
| HTTP | httpx |
| Шифрование | cryptography (Fernet) |
| Пароли | bcrypt |

## Быстрый старт

```bash
./start.sh
```

Скрипт создаёт виртуальное окружение, устанавливает зависимости и запускает сервер.

После запуска:
- Приложение: http://localhost:8000
- Админ-панель: http://localhost:8000/admin
- API-документация: http://localhost:8000/docs

Логин по умолчанию: `admin` / `admin`

### Ручной запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Структура проекта

```
posting.iliya-code.ru/
├── main.py                    # Точка входа: FastAPI, миграции, дефолтный admin
├── create_superadmin.py       # CLI для создания/смены суперадмина
├── start.sh                   # Скрипт автозапуска
├── requirements.txt
├── data/
│   ├── admin.db               # SQLite база данных
│   └── uploads/               # Загруженные изображения
├── admin/
│   ├── templates/             # Jinja2-шаблоны
│   └── statics/               # CSS, JS, favicon
└── app/
    ├── config.py              # SECRET_KEY, пути к шаблонам и статике
    ├── database.py            # SQLAlchemy engine, SessionLocal, Base
    ├── auth.py                # Авторизация, хэши, миксины ролей
    ├── admin.py               # Фабрика Admin-панели
    ├── worker.py              # Фоновый воркер (публикация каждые 30 сек)
    ├── models/
    │   ├── post.py            # Post, PostImage, PostChannel
    │   ├── admin_user.py      # AdminUser (роли: superadmin, editor)
    │   ├── sources/           # TelegramSource, VKSource, MAXSource
    │   └── providers/         # AIProvider (OpenAI, GigaChat)
    ├── routers/
    │   ├── source.py          # POST /api/source/{telegram,vk,max}/test
    │   ├── ai_provider.py     # POST /api/ai-provider/test
    │   └── ai_generate.py     # POST /api/ai/generate
    ├── publisher/
    │   ├── telegram.py        # Публикация в Telegram
    │   ├── vk.py              # Публикация в ВКонтакте
    │   └── max_messenger.py   # Публикация в MAX
    └── views/
        ├── posts.py           # Визард создания поста (3 шага)
        ├── post_channel_list.py
        ├── calendar.py
        ├── telegram_source.py
        ├── vk_source.py
        └── max_source.py
```

## Модели данных

### Post
| Поле | Тип | Описание |
|------|-----|----------|
| `title` | String | Заголовок |
| `description` | Text | Текст поста |
| `tags` | String | Теги через запятую → #хэштеги |
| `status` | Enum | `draft` / `ready` / `published` |

### PostChannel
Привязка поста к конкретному источнику. Один пост — несколько каналов.

| Поле | Тип | Описание |
|------|-----|----------|
| `source_type` | String | `telegram` / `vk` / `max` |
| `source_id` | Integer | ID источника |
| `title` | Text | Переопределение заголовка (необязательно) |
| `description` | Text | Переопределение текста (необязательно) |
| `status` | Enum | `pending` / `published` / `failed` |
| `scheduled_at` | DateTime | Время публикации (null = немедленно) |

### Источники (TelegramSource / VKSource / MAXSource)
| Поле | Описание |
|------|----------|
| `name` | Человекочитаемое имя |
| `bot_token` / `access_token` | Зашифрованный токен |
| `chat_id` / `group_id` | Идентификатор канала |
| `ai_prompt_title` | Промпт для AI-генерации заголовка |
| `ai_prompt_description` | Промпт для AI-генерации текста |
| `is_active` | Используется при выборе источника |

### AIProvider
| Поле | Описание |
|------|----------|
| `provider_type` | `openai` или `gigachat` |
| `api_key` | Зашифрованный ключ |
| `base_url` | Кастомный endpoint (OpenAI, необязательно) |
| `scope` | `GIGACHAT_API_PERS` / `GIGACHAT_API_CORP` |
| `is_active` | Одновременно активен только один провайдер |

## API

| Метод | URL | Описание |
|-------|-----|----------|
| `POST` | `/api/source/telegram/test` | Проверить Telegram-источник |
| `POST` | `/api/source/vk/test` | Проверить VK-источник |
| `POST` | `/api/source/max/test` | Проверить MAX-источник |
| `POST` | `/api/ai-provider/test` | Проверить AI-провайдера |
| `POST` | `/api/ai/generate` | Сгенерировать текст через AI |

### POST /api/ai/generate

```json
{
  "text": "Исходный текст",
  "source_type": "telegram",
  "source_id": 1,
  "field": "description"
}
```

Берёт промпт из настроек источника (`ai_prompt_title` или `ai_prompt_description`), отправляет в активный AI-провайдер, возвращает переработанный текст.

## Создание поста

Публикация проходит в 3 шага:

1. **Содержание** — заголовок, текст, теги, изображения
2. **Источники** — выбор каналов для публикации
3. **Настройка** — для каждого канала опционально переопределить заголовок/текст, задать время

На шагах 3 доступна кнопка **✨ AI** рядом с полями — генерирует текст на основе AI-промпта источника.

## Фоновый воркер

Каждые 30 секунд проверяет базу на наличие `PostChannel` со статусом `pending` и `scheduled_at ≤ now()`. Публикует контент, обновляет статусы. Если все каналы поста опубликованы — пост переходит в `published`.

## Управление пользователями

```bash
python create_superadmin.py
```

Два типа ролей:
- **Superadmin** — полный доступ, включая управление пользователями и AI-провайдерами
- **Editor** — управление источниками и постами

## Продакшен

Перед деплоем обязательно поменяйте `SECRET_KEY` в `app/config.py`:

```python
SECRET_KEY = "ваш-секретный-ключ-минимум-32-символа"
```

Также смените пароль дефолтного admin-пользователя через `create_superadmin.py`.
