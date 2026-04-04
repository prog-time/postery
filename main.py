import asyncio
import logging
import logging.handlers
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY, BASE_DIR
from app.database import engine, Base, SessionLocal
from app.admin import create_admin
from app.routers.main import router
from app.routers.logs import router as logs_router
from app.models.admin_user import AdminUser, Role
from app.auth import hash_password
from app.worker import run_worker

# ── TASK-LOG-004: Запись логов в файл с ротацией ────────────────────────────

_logs_dir = Path(BASE_DIR) / "data" / "logs"
_logs_dir.mkdir(parents=True, exist_ok=True)

_log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_formatter = logging.Formatter(_log_format)

_file_handler = logging.handlers.RotatingFileHandler(
    filename=_logs_dir / "app.log",
    maxBytes=10 * 1024 * 1024,  # 10 МБ
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.DEBUG)
_console_handler.setFormatter(_formatter)

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])

# ── TASK-LOG-003: HTTP middleware для логирования /api/* запросов ────────────

log_http = logging.getLogger("http")


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        start = time.monotonic()
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        duration_ms = int((time.monotonic() - start) * 1000)
        log_http.info("HTTP %s %s → %d (%dms)", method, path, status_code, duration_ms)

Base.metadata.create_all(bind=engine)

# Rate limiter instance shared across the app (TASK-004)
limiter = Limiter(key_func=get_remote_address)


def _migrate() -> None:
    """Добавляет колонки, отсутствующие в уже существующих таблицах."""
    migrations = [
        ("telegram_sources", "ai_prompt_title",       "TEXT"),
        ("telegram_sources", "ai_prompt_description", "TEXT"),
        ("vk_sources",       "ai_prompt_title",       "TEXT"),
        ("vk_sources",       "ai_prompt_description", "TEXT"),
        ("max_sources",      "ai_prompt_title",       "TEXT"),
        ("max_sources",      "ai_prompt_description", "TEXT"),
        # TASK-002: retry mechanism
        ("post_channels",    "attempt",               "INTEGER NOT NULL DEFAULT 0"),
        ("post_channels",    "retry_after",           "DATETIME"),
        # TASK-008: auto-generate flag on sources
        ("telegram_sources", "auto_generate",         "BOOLEAN NOT NULL DEFAULT 0"),
        ("vk_sources",       "auto_generate",         "BOOLEAN NOT NULL DEFAULT 0"),
        ("max_sources",      "auto_generate",         "BOOLEAN NOT NULL DEFAULT 0"),
        # BASE-PROMPT: global base system prompt per AI provider
        ("ai_providers",     "base_prompt",           "TEXT"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            rows = conn.execute(
                __import__("sqlalchemy").text(f"PRAGMA table_info({table})")
            ).fetchall()
            existing = {r[1] for r in rows}
            if column not in existing:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                    )
                )
                conn.commit()


_migrate()


def _backfill_post_images() -> None:
    """Заполняет post_images из файловой системы для постов без записей в БД."""
    import sqlalchemy as sa
    from pathlib import Path

    uploads_dir = Path(BASE_DIR) / "data" / "uploads"
    if not uploads_dir.exists():
        return

    allowed_ext = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    with SessionLocal() as db:
        for post_dir in sorted(uploads_dir.iterdir()):
            if not post_dir.is_dir():
                continue
            try:
                post_id = int(post_dir.name)
            except ValueError:
                continue

            existing = db.execute(
                sa.text("SELECT COUNT(*) FROM post_images WHERE post_id = :pid"),
                {"pid": post_id},
            ).scalar()
            if existing:
                continue

            image_files = sorted(
                f for f in post_dir.iterdir()
                if f.is_file() and f.suffix.lower() in allowed_ext
            )
            for order, img_file in enumerate(image_files):
                rel_path = str(img_file.relative_to(BASE_DIR))
                db.execute(
                    sa.text(
                        "INSERT INTO post_images (post_id, file_path, \"order\") "
                        "VALUES (:pid, :fp, :ord)"
                    ),
                    {"pid": post_id, "fp": rel_path, "ord": order},
                )
        db.commit()


_backfill_post_images()


def init_default_admin() -> None:
    with SessionLocal() as db:
        if not db.query(AdminUser).first():
            db.add(AdminUser(
                username="admin",
                password_hash=hash_password("admin"),
                role=Role.SUPERADMIN,
                is_active=True,
            ))
            db.commit()
            print("Default admin created: admin / admin")


init_default_admin()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Postery", lifespan=lifespan)

# TASK-LOG-003: Middleware логирования /api/* добавляется до SessionMiddleware —
# в Starlette middleware выполняются в обратном порядке добавления,
# поэтому RequestLoggingMiddleware оборачивает цепочку снаружи.
app.add_middleware(RequestLoggingMiddleware)

# SessionMiddleware на уровне основного приложения — даёт доступ к request.session
# в FastAPI-роутерах (/api/*), не только внутри Admin sub-app (TASK-004)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# slowapi: прикрепляем limiter к app.state, регистрируем кастомный обработчик
# (TASK-004). Обработчик возвращает HTTP 200 согласно контракту AI-эндпоинтов.
app.state.limiter = limiter


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    ip = get_remote_address(request)
    logging.getLogger(__name__).warning("Rate limit exceeded for IP %s", ip)
    return JSONResponse(
        status_code=200,
        content={"ok": False, "error": "Слишком много запросов — подождите минуту"},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

app.include_router(router)
app.include_router(logs_router)  # TASK-LOG-005: эндпоинт скачивания логов

# Отдаём загруженные изображения постов по пути /data/uploads/...
_uploads_dir = BASE_DIR / "data" / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/data/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

# Admin sub-app монтируется последним; у него своя SessionMiddleware внутри
admin = create_admin()
admin.mount_to(app)
