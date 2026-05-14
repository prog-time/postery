# Postery

Postery — инструмент для управления публикациями сразу в несколько соцсетей и мессенджеров. Telegram, ВКонтакте, MAX — один пост, одна кнопка.

Вопросы, идеи, баги — всё в нашей группе:

**Telegram** - [t.me/postery_app](https://t.me/postery_app)

**Документация** - [https://postery.lyashchuk.pro](https://postery.lyashchuk.pro/)

<img alt="Postery Preview" src="src/preview.png" width="800"/>

---

## Возможности

- **Мультиплатформенность** — публикация в Telegram, ВКонтакте и MAX одновременно
- **Расписание** — укажи дату и время, Postery опубликует сам
- **Фотографии** — прикрепляй одно или несколько изображений к посту
- **AI-помощник** — улучшает и переформулирует текст через OpenAI или GigaChat
- **Индивидуальный текст** — разные подписи для разных площадок
- **Календарь** — наглядное отображение всех запланированных публикаций

---

## Подключение каналов

Перед первой публикацией добавьте хотя бы один канал в разделе **Источники**:

| Платформа | Что нужно |
|-----------|-----------|
| Telegram | Токен бота + ID канала |
| ВКонтакте | Токен группы |
| MAX | Токен + ID чата |

---

## Как опубликовать пост

1. **Все посты** → **Создать пост**
2. Напишите заголовок, текст, добавьте фото
3. Выберите каналы для публикации
4. При необходимости — настройте текст для каждого канала отдельно и укажите время

---

## AI-помощник

Postery умеет улучшать тексты с помощью нейросетей. 

Поддерживаются:
- **OpenAI** (ChatGPT / GPT-4o)
- **GigaChat** (Сбер)

Добавьте API-ключ в разделе **AI Провайдеры**. Одновременно активен только один провайдер.

---

## Пользователи и роли

| Роль | Возможности |
|------|-------------|
| Суперадмин | Полный доступ: посты, источники, пользователи, AI |
| Редактор | Создание и редактирование постов и источников |

Создать или обновить суперадмина:

```bash
python create_superadmin.py
```

---

## Быстрый старт (Docker)

Самый простой способ развернуть Postery на сервере — три команды:

```bash
git clone https://github.com/prog-time/postery.git
cp .env.example .env
# Откройте .env и задайте SECRET_KEY (обязательно) и INITIAL_ADMIN_* (рекомендуется)
docker compose up -d
```

После запуска:
- Приложение доступно на `http://localhost:8000`
- Админка — на `http://localhost:8000/admin`
- Данные (БД, фото, логи) хранятся в `./data/` на хосте и переживают пересборку образа

> **Безопасность:** по умолчанию создаётся пользователь `admin` с паролем `admin`.
> Это небезопасно. Задайте `INITIAL_ADMIN_USERNAME` и `INITIAL_ADMIN_PASSWORD` в `.env`
> до первого старта, или смените пароль через `python create_superadmin.py` после запуска.

### Переменные окружения

Все переменные описаны в `.env.example`. Ключевые:

| Переменная | Обязательна | Описание |
|------------|:-----------:|---------|
| `SECRET_KEY` | Да | Hex-32 ключ; шифрует токены в БД и подписывает сессии |
| `DATABASE_URL` | — | SQLite по умолчанию; поддерживается PostgreSQL |
| `PUBLIC_BASE_URL` | — | Базовый URL приложения (без `/`). Нужен для абсолютных `image_urls` в webhook payload |
| `TZ` | — | Часовой пояс контейнера (по умолч. `Europe/Moscow`) |
| `LOG_LEVEL` | — | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `INITIAL_ADMIN_USERNAME` | — | Логин суперадмина при первом старте |
| `INITIAL_ADMIN_PASSWORD` | — | Пароль суперадмина при первом старте |

> **`PUBLIC_BASE_URL`** нужен, если вы используете webhook-канал и хотите, чтобы получатель
> получал абсолютные ссылки на изображения (например `https://postery.example.com/data/uploads/…`).
> Без этой переменной `image_urls` будут относительными — получатель не сможет скачать файлы,
> не зная хост Postery.

### Выбор базы данных

Образ поддерживает обе БД из коробки — драйверы SQLite (`sqlite3`, stdlib) и PostgreSQL (`psycopg2-binary`) включены в `requirements.txt`.

```bash
# SQLite (по умолчанию, файл в ./data/admin.db, ничего настраивать не нужно):
DATABASE_URL=sqlite:///data/admin.db

# PostgreSQL (внешний сервер):
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Postery не разворачивает Postgres-сервер сам — используйте внешнюю инсталляцию (managed-сервис, отдельный контейнер, on-prem).

### arm64 (Apple Silicon / AWS Graviton)

В `requirements.txt` закреплено `cryptography<43`. Начиная с версии 43 пакет `cryptography`
перестал поставлять готовые wheels для arm64 и требует компиляции Rust-тулчейна. Закрепление
позволяет собрать образ через `build-essential + libffi-dev` (уже установлены в `Dockerfile`)
без дополнительных зависимостей.

Проверить состояние контейнера:

```bash
docker compose ps        # статус должен быть healthy через ~30 с
docker compose logs -f   # потоковый вывод логов
```

Обновить до новой версии:

```bash
git pull
docker compose up -d --build
```

### Разработка с hot-reload

В репозитории есть `docker-compose.override.yml`. Docker Compose подхватывает его автоматически — без флагов.

При старте override добавляет в сервис `app`:

- bind-mount исходников (`.:/app`) — любые правки `.py`-файлов сразу попадают в контейнер;
- флаг `--reload` для uvicorn — приложение перезапускается без пересборки образа;
- `PYTHONDONTWRITEBYTECODE=1` — `.pyc`-файлы не засоряют хостовую файловую систему.

```bash
# Первый старт (образ строится один раз):
docker compose up -d --build

# После любых правок кода — просто:
docker compose up -d
# --build НЕ нужен; uvicorn перезагрузит изменения сам

# --build всё ещё нужен при изменении requirements.txt или Dockerfile:
docker compose up -d --build
```

Для прод-деплоя override нужно явно исключить:

```bash
docker compose -f docker-compose.yml up -d --build
```

---

## Запуск (локальная разработка)

> `start.sh` предназначен для локальной разработки и в Docker-образ не включён.

### 1. Создайте `.env`

```bash
cp .env.example .env
```

### 2. Задайте секретный ключ

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Вставьте результат в `.env`:

```
SECRET_KEY=<сгенерированный-ключ>
```

Без заданного `SECRET_KEY` приложение не запустится.

> **Важно:** не меняйте `SECRET_KEY` после первого запуска — все зашифрованные данные (токены, ключи API) станут нечитаемыми.

### 3. Запустить приложение

```bash
./start.sh
```

### 4. Авторизоваться

1) Откройте **http://localhost:8000/admin** в браузере.
2) Войдите: логин `admin`, пароль `admin`
3) Сразу после входа смените пароль в разделе «Пользователи».

---

## Webhook-канал

Webhook позволяет получать публикации Postery на любой HTTP-эндпоинт — собственный сервис,
n8n, Make, Zapier и т. д.

### Настройка

1. Добавьте источник типа **Webhook** в разделе «Источники».
2. Укажите `Webhook URL` — адрес, куда Postery будет отправлять POST-запросы.
3. (Опционально) укажите `Secret` — любая строка; Postery будет подписывать каждый запрос
   заголовком `X-Postery-Signature`.
4. Нажмите «Подтвердить» — Postery отправит на ваш URL запрос с `"type": "confirmation"`
   и ждёт в ответе 8-символьный код подтверждения.

### Формат payload

Каждая публикация — POST с `Content-Type: application/json`:

```json
{
  "type": "publish",
  "source_id": 42,
  "object": {
    "post_id": 17,
    "title": "Заголовок поста",
    "description": "Текст поста для этого канала",
    "tags": ["маркетинг", "новости"],
    "published_at": "2026-05-13T09:00:00+00:00",
    "image_urls": [
      "https://postery.example.com/data/uploads/17/photo.jpg"
    ]
  }
}
```

| Поле | Тип | Описание |
|------|-----|---------|
| `type` | `"publish"` | Всегда `"publish"` для публикаций |
| `source_id` | int | ID webhook-источника |
| `object.post_id` | int | ID поста |
| `object.title` | str | Эффективный заголовок (из настроек канала или общего поста) |
| `object.description` | str \| null | Текст поста для данного канала |
| `object.tags` | list[str] | Теги без символа `#` |
| `object.published_at` | ISO 8601 UTC | Время публикации |
| `object.image_urls` | list[str] | URL изображений (абсолютные при заданном `PUBLIC_BASE_URL`, иначе относительные) |

### image_urls и PUBLIC_BASE_URL

По умолчанию `image_urls` содержат относительные пути вида `/data/uploads/17/photo.jpg`.
Получатель вне Postery не сможет скачать изображение по такому пути.

Задайте `PUBLIC_BASE_URL` в `.env`:

```env
PUBLIC_BASE_URL=https://postery.example.com
```

После этого `image_urls` станут абсолютными:

```
https://postery.example.com/data/uploads/17/photo.jpg
```

### Верификация подписи

Если у источника задан `Secret`, каждый запрос содержит заголовок:

```
X-Postery-Signature: sha256=<hex-digest>
```

Алгоритм: HMAC-SHA256 от тела запроса (bytes) с ключом `Secret`.

Пример верификации на Python:

```python
import hashlib, hmac

def verify(body: bytes, secret: str, header: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)
```

### Код подтверждения

При настройке нового источника Postery отправляет запрос вида:

```json
{"type": "confirmation", "source_id": 42}
```

Ваш эндпоинт должен вернуть 8-символьный hex-код. Код детерминирован: зависит от
`webhook_url`, текущей даты и `SECRET_KEY`. Алгоритм: `HMAC-SHA1("<url>:<YYYY-MM-DD>", SECRET_KEY)[:8]`.
