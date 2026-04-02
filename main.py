import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, Base, SessionLocal
from app.admin import create_admin
from app.routers.main import router
from app.models.admin_user import AdminUser, Role
from app.auth import hash_password
from app.worker import run_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

Base.metadata.create_all(bind=engine)


def _migrate() -> None:
    """Добавляет колонки, отсутствующие в уже существующих таблицах."""
    migrations = [
        ("telegram_sources", "ai_prompt_title",       "TEXT"),
        ("telegram_sources", "ai_prompt_description", "TEXT"),
        ("vk_sources",       "ai_prompt_title",       "TEXT"),
        ("vk_sources",       "ai_prompt_description", "TEXT"),
        ("max_sources",      "ai_prompt_title",       "TEXT"),
        ("max_sources",      "ai_prompt_description", "TEXT"),
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

app.include_router(router)

# SessionMiddleware передаётся внутрь Admin согласно документации
admin = create_admin()
admin.mount_to(app)
