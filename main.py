import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY
from app.database import engine, Base, SessionLocal
from app.admin import create_admin
from app.routers.main import router
from app.models.admin_user import AdminUser, Role
from app.auth import hash_password
from app.worker import run_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

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

# Admin sub-app монтируется последним; у него своя SessionMiddleware внутри
admin = create_admin()
admin.mount_to(app)
