"""
Тестовые фикстуры для Postery.

Стратегия:
- in-memory SQLite — реальная БД без Alembic (_migrate() не вызывается).
- app.database.SessionLocal патчится, чтобы воркер использовал тестовую сессию.
- SECRET_KEY выставляется до любого импорта app-модулей.
"""
import os

# Обязательно до первого импорта app.config
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-0000000000000000")

import pytest
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Импортируем Base и все модели, чтобы таблицы были зарегистрированы в метаданных
from app.database import Base
import app.models.post          # noqa: F401 — Post, PostChannel, PostImage
import app.models.sources.telegram  # noqa: F401 — TelegramSource
import app.models.sources.vk        # noqa: F401 — VKSource
import app.models.sources.max_messenger  # noqa: F401 — MAXSource
import app.models.admin_user        # noqa: F401
import app.models.user              # noqa: F401

from app.models.post import Post, PostChannel, PostStatus, ChannelStatus
from app.models.sources.telegram import TelegramSource


# ---------------------------------------------------------------------------
# Движок — in-memory SQLite, одна БД на весь прогон тестов
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


# ---------------------------------------------------------------------------
# Сессия с откатом транзакции после каждого теста (savepoint pattern)
# ---------------------------------------------------------------------------

@pytest.fixture
def db(engine):
    """
    Возвращает сессию в открытой транзакции.
    После теста транзакция откатывается — изоляция без сброса схемы.
    """
    connection = engine.connect()
    transaction = connection.begin()

    TestSession = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = TestSession()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Фабрики объектов
# ---------------------------------------------------------------------------

@pytest.fixture
def make_tg_source(db):
    """Фабрика TelegramSource. Возвращает callable(name, bot_token, chat_id)."""
    def _factory(name="Test Channel", bot_token="test-token-123", chat_id="-100123456789"):
        source = TelegramSource(
            name=name,
            bot_token=bot_token,
            chat_id=chat_id,
            thread_id=None,
            is_active=True,
        )
        db.add(source)
        db.flush()
        return source
    return _factory


@pytest.fixture
def make_post(db):
    """
    Фабрика Post.
    Возвращает callable(title, status, description, tags).
    """
    def _factory(
        title="Test Post",
        status=PostStatus.READY,
        description="Test description",
        tags=None,
    ):
        post = Post(
            title=title,
            status=status,
            description=description,
            tags=tags,
        )
        db.add(post)
        db.flush()
        return post
    return _factory


@pytest.fixture
def make_channel(db):
    """
    Фабрика PostChannel.
    Возвращает callable(post, source, source_type, status, scheduled_at).
    """
    def _factory(
        post,
        source,
        source_type="telegram",
        status=ChannelStatus.PENDING,
        scheduled_at=None,
    ):
        channel = PostChannel(
            post_id=post.id,
            source_type=source_type,
            source_id=source.id,
            status=status,
            scheduled_at=scheduled_at,
        )
        db.add(channel)
        db.flush()
        return channel
    return _factory
