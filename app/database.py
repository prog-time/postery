import importlib.util
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/admin.db")

# Дефолтный Docker-образ собирается без psycopg2 (см. Issue #6 — PostgreSQL
# поддерживается опционально). Если пользователь оставил в .env строку
# подключения к Postgres, выдаём понятное сообщение вместо ModuleNotFoundError
# в недрах SQLAlchemy и crashloop'а контейнера.
if DATABASE_URL.startswith(("postgres://", "postgresql://", "postgresql+psycopg2://")):
    if importlib.util.find_spec("psycopg2") is None:
        raise RuntimeError(
            "DATABASE_URL указывает на PostgreSQL, но драйвер psycopg2 не установлен.\n"
            "В дефолтном Docker-образе Postery поддержка Postgres отключена.\n"
            "Варианты:\n"
            "  1) Используйте SQLite: DATABASE_URL=sqlite:///data/admin.db (по умолчанию).\n"
            "  2) Установите psycopg2 локально: pip install psycopg2-binary.\n"
            "  3) Соберите образ с psycopg2-binary в requirements.txt."
        )

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
