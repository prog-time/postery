"""
Тесты publisher-адаптеров: Telegram и VK.

Стратегия:
- HTTP-вызовы мокируются через respx (работает с httpx).
- Файлы изображений создаются через tmp_path (pytest fixture).
- Источники (source) — простые объектов-заглушки (SimpleNamespace),
  т.к. publisher использует только атрибуты, не ORM.
"""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-0000000000000000")

import pytest
import respx
import httpx
from types import SimpleNamespace

from app.publisher import telegram as tg_publisher
from app.publisher import vk as vk_publisher


# ---------------------------------------------------------------------------
# Вспомогательные объекты
# ---------------------------------------------------------------------------

def make_tg_source(bot_token="testtoken123", chat_id="-100999888777", thread_id=None):
    return SimpleNamespace(bot_token=bot_token, chat_id=chat_id, thread_id=thread_id)


def make_vk_source(access_token="vk-token-123", group_id=123456):
    return SimpleNamespace(access_token=access_token, group_id=group_id)


TG_API_BASE = "https://api.telegram.org/bot"
VK_API_BASE = "https://api.vk.com/method/"


# ===========================================================================
# TELEGRAM TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# Тест 11: telegram.publish() без изображений → sendMessage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_telegram_no_images_calls_send_message():
    """Без изображений должен вызываться sendMessage."""
    source = make_tg_source()

    send_message_route = respx.post(
        url__regex=r"api\.telegram\.org/bot.*/sendMessage"
    ).mock(return_value=httpx.Response(200, json={"ok": True}))

    result = await tg_publisher.publish("Hello World", source, image_paths=[])

    assert result == (True, None)
    assert send_message_route.called


# ---------------------------------------------------------------------------
# Тест 12: telegram.publish() с 1 изображением → sendPhoto
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_telegram_one_image_calls_send_photo(tmp_path):
    """При одном изображении должен вызываться sendPhoto."""
    source = make_tg_source()

    # Создаём временный файл-заглушку изображения
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)  # минимальный JPEG-хедер

    send_photo_route = respx.post(
        url__regex=r"api\.telegram\.org/bot.*/sendPhoto"
    ).mock(return_value=httpx.Response(200, json={"ok": True}))

    result = await tg_publisher.publish("Caption", source, image_paths=[str(img)])

    assert result == (True, None)
    assert send_photo_route.called


# ---------------------------------------------------------------------------
# Тест 13: telegram.publish() с 2+ изображениями → sendMediaGroup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_telegram_multiple_images_calls_send_media_group(tmp_path):
    """При 2+ изображениях должен вызываться sendMediaGroup."""
    source = make_tg_source()

    img1 = tmp_path / "photo1.jpg"
    img2 = tmp_path / "photo2.jpg"
    img1.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
    img2.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

    send_media_group_route = respx.post(
        url__regex=r"api\.telegram\.org/bot.*/sendMediaGroup"
    ).mock(return_value=httpx.Response(200, json={"ok": True}))

    result = await tg_publisher.publish(
        "Caption",
        source,
        image_paths=[str(img1), str(img2)],
    )

    assert result == (True, None)
    assert send_media_group_route.called


# ---------------------------------------------------------------------------
# Тест 15 (Telegram): при HTTP-ошибке возвращает (False, str), не кидает исключение
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_telegram_http_error_returns_false_not_raises():
    """При HTTP-ошибке должен возвращать (False, str), а не бросать исключение."""
    source = make_tg_source()

    respx.post(
        url__regex=r"api\.telegram\.org/bot.*/sendMessage"
    ).mock(return_value=httpx.Response(403, text="Forbidden"))

    success, error = await tg_publisher.publish("text", source, image_paths=[])

    assert success is False
    assert isinstance(error, str)
    assert len(error) > 0


# ===========================================================================
# VK TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# Тест 14: vk.publish() при ошибке VK error 27 → (True, None) (fallback text-only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_vk_error_27_fallback_text_only(tmp_path):
    """
    При ошибке VK error 27 (group token cannot upload photos)
    VK-паблишер должен опубликовать текст без изображений и вернуть (True, None).
    """
    source = make_vk_source()

    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

    # photos.getWallUploadServer → возвращает error 27
    respx.post(
        url__regex=r"api\.vk\.com/method/photos\.getWallUploadServer"
    ).mock(return_value=httpx.Response(200, json={
        "error": {"error_code": 27, "error_msg": "Access denied: group token permissions"}
    }))

    # wall.post → успех
    wall_post_route = respx.post(
        url__regex=r"api\.vk\.com/method/wall\.post"
    ).mock(return_value=httpx.Response(200, json={"response": {"post_id": 42}}))

    success, error = await vk_publisher.publish(
        "Text only post",
        source,
        image_paths=[str(img)],
    )

    assert success is True
    assert error is None
    assert wall_post_route.called


# ---------------------------------------------------------------------------
# Тест 15 (VK): при HTTP-ошибке возвращает (False, str), не кидает исключение
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_vk_http_error_returns_false_not_raises():
    """При HTTP-ошибке должен возвращать (False, str), а не бросать исключение."""
    source = make_vk_source()

    respx.post(
        url__regex=r"api\.vk\.com/method/wall\.post"
    ).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    success, error = await vk_publisher.publish("Text", source, image_paths=[])

    assert success is False
    assert isinstance(error, str)
    assert len(error) > 0
