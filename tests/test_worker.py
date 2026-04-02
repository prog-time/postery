"""
Тесты воркера публикации (_publish_channel).

Стратегия:
- Используем реальный in-memory SQLite через фикстуры conftest.py.
- app.database.SessionLocal патчится фейковым контекстным менеджером,
  который возвращает тестовую сессию вместо продакшн-сессии.
- HTTP-вызовы мокируются через respx.
"""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-0000000000000000")

import pytest
import respx
import httpx
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

from app.models.post import Post, PostChannel, PostStatus, ChannelStatus
from app.worker import _publish_channel


def make_session_patcher(db_session):
    """
    Создаёт контекстный менеджер-фабрику, имитирующую SessionLocal().
    Используется для патчинга app.worker.SessionLocal.
    """
    @contextmanager
    def fake_session_local():
        yield db_session

    return fake_session_local


# ---------------------------------------------------------------------------
# Вспомогательная функция: успешный mock Telegram sendMessage
# ---------------------------------------------------------------------------

def tg_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{'{token}'}/{method}"


TG_SEND_MESSAGE_PATTERN = "https://api.telegram.org/bot"


# ---------------------------------------------------------------------------
# Тест 4: PENDING + scheduled_at=None → публикуется
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_pending_no_schedule_publishes(db, make_post, make_tg_source, make_channel):
    """Канал со статусом PENDING и scheduled_at=None должен публиковаться."""
    source = make_tg_source()
    post = make_post(status=PostStatus.READY)
    channel = make_channel(post, source, scheduled_at=None)

    # Mock Telegram API — принимаем любой POST к api.telegram.org
    respx.post(url__startswith=TG_SEND_MESSAGE_PATTERN).mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    with patch("app.worker.SessionLocal", make_session_patcher(db)):
        await _publish_channel(channel.id)

    db.refresh(channel)
    assert channel.status == ChannelStatus.PUBLISHED
    assert channel.published_at is not None


# ---------------------------------------------------------------------------
# Тест 5: scheduled_at в прошлом → публикуется
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_past_schedule_publishes(db, make_post, make_tg_source, make_channel):
    """Канал с scheduled_at в прошлом должен публиковаться."""
    source = make_tg_source()
    post = make_post(status=PostStatus.READY)
    past = datetime.now() - timedelta(hours=1)
    channel = make_channel(post, source, scheduled_at=past)

    respx.post(url__startswith=TG_SEND_MESSAGE_PATTERN).mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    with patch("app.worker.SessionLocal", make_session_patcher(db)):
        await _publish_channel(channel.id)

    db.refresh(channel)
    assert channel.status == ChannelStatus.PUBLISHED


# ---------------------------------------------------------------------------
# Тест 6: scheduled_at в будущем → НЕ публикуется
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_future_schedule_does_not_publish(db, make_post, make_tg_source, make_channel):
    """Канал с scheduled_at в будущем НЕ должен публиковаться."""
    source = make_tg_source()
    post = make_post(status=PostStatus.READY)
    future = datetime.now() + timedelta(hours=2)
    channel = make_channel(post, source, scheduled_at=future)

    # _publish_channel напрямую публикует, даже если время не наступило —
    # фильтрацию делает _process_due_channels.
    # Но канал со scheduled_at в будущем всё равно передаётся в _publish_channel
    # — проверяем, что _process_due_channels его исключает через фильтр.
    # Для теста _publish_channel напрямую: она не проверяет scheduled_at,
    # поэтому тестируем через _process_due_channels.
    from app.worker import _process_due_channels

    with patch("app.worker.SessionLocal", make_session_patcher(db)):
        await _process_due_channels()

    db.refresh(channel)
    # Канал не должен быть опубликован
    assert channel.status == ChannelStatus.PENDING


# ---------------------------------------------------------------------------
# Тест 7: пост со статусом DRAFT → канал пропускается
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_draft_post_channel_skipped(db, make_post, make_tg_source, make_channel):
    """Канал, чей пост имеет статус DRAFT, должен пропускаться воркером."""
    source = make_tg_source()
    post = make_post(status=PostStatus.DRAFT)
    channel = make_channel(post, source)

    with patch("app.worker.SessionLocal", make_session_patcher(db)):
        await _publish_channel(channel.id)

    db.refresh(channel)
    assert channel.status == ChannelStatus.PENDING


# ---------------------------------------------------------------------------
# Тест 8: после публикации последнего канала → post.status = PUBLISHED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_all_channels_published_marks_post_published(db, make_post, make_tg_source, make_channel):
    """После публикации последнего канала пост должен получить статус PUBLISHED."""
    source = make_tg_source()
    post = make_post(status=PostStatus.READY)
    channel = make_channel(post, source)

    respx.post(url__startswith=TG_SEND_MESSAGE_PATTERN).mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    with patch("app.worker.SessionLocal", make_session_patcher(db)):
        await _publish_channel(channel.id)

    db.refresh(post)
    assert post.status == PostStatus.PUBLISHED


# ---------------------------------------------------------------------------
# Тест 9: сбой одного канала не влияет на другой
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_one_channel_failure_does_not_affect_other(db, make_post, make_tg_source, make_channel):
    """
    Сбой публикации одного канала не должен влиять на публикацию другого.
    Используем два канала. Первый — ошибка 500. Второй — успех.
    """
    source1 = make_tg_source(name="Channel 1", bot_token="token-fail", chat_id="-100111")
    source2 = make_tg_source(name="Channel 2", bot_token="token-ok", chat_id="-100222")
    post = make_post(status=PostStatus.READY)
    channel1 = make_channel(post, source1)
    channel2 = make_channel(post, source2)

    call_count = {"n": 0}

    def side_effect(request, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Первый вызов → ошибка
            return httpx.Response(500, text="Internal Server Error")
        # Второй вызов → успех
        return httpx.Response(200, json={"ok": True})

    respx.post(url__startswith=TG_SEND_MESSAGE_PATTERN).mock(side_effect=side_effect)

    with patch("app.worker.SessionLocal", make_session_patcher(db)):
        await _publish_channel(channel1.id)
        await _publish_channel(channel2.id)

    db.refresh(channel1)
    db.refresh(channel2)

    # channel1: должен был получить attempt=1, остаться PENDING (retry) или стать FAILED
    assert channel1.status in (ChannelStatus.PENDING, ChannelStatus.FAILED)
    # channel2: должен быть опубликован
    assert channel2.status == ChannelStatus.PUBLISHED


# ---------------------------------------------------------------------------
# Тест 10: при сбое channel.status = FAILED, error_message не пуст
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_failure_sets_failed_status_and_error_message(db, make_post, make_tg_source, make_channel):
    """
    При исчерпании всех попыток channel.status = FAILED и error_message не пуст.
    Устанавливаем attempt уже на последнем допустимом значении (MAX_ATTEMPTS - 1).
    """
    from app.config import MAX_ATTEMPTS

    source = make_tg_source()
    post = make_post(status=PostStatus.READY)
    channel = make_channel(post, source)

    # Ставим attempt так, чтобы следующая неудача = FAILED
    channel.attempt = MAX_ATTEMPTS - 1
    db.flush()

    respx.post(url__startswith=TG_SEND_MESSAGE_PATTERN).mock(
        return_value=httpx.Response(500, text="Server Error")
    )

    with patch("app.worker.SessionLocal", make_session_patcher(db)):
        await _publish_channel(channel.id)

    db.refresh(channel)
    assert channel.status == ChannelStatus.FAILED
    assert channel.error_message
    assert len(channel.error_message) > 0
