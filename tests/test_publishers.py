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
from app.publisher import webhook as webhook_publisher


# ---------------------------------------------------------------------------
# Вспомогательные объекты
# ---------------------------------------------------------------------------

def make_tg_source(bot_token="testtoken123", chat_id="-100999888777", thread_id=None):
    return SimpleNamespace(bot_token=bot_token, chat_id=chat_id, thread_id=thread_id)


def make_vk_source(access_token="vk-token-123", group_id=123456):
    return SimpleNamespace(access_token=access_token, group_id=group_id)


def make_webhook_source(webhook_url="https://example.com/hook", secret=None):
    src = SimpleNamespace(
        id=1,
        webhook_url=webhook_url,
        secret=secret,
    )
    src._channel_context = {
        "post_id": 42,
        "title": "Test Post",
        "description": "Test description",
        "tags": "тег1, тег2",
    }
    return src


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


# ===========================================================================
# WEBHOOK TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# Тест W1: webhook.publish() при 2xx возвращает (True, None)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_2xx_returns_success():
    """При HTTP 2xx должен возвращать (True, None)."""
    source = make_webhook_source()

    respx.post("https://example.com/hook").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )

    success, error = await webhook_publisher.publish("text", source, image_paths=[])

    assert success is True
    assert error is None


# ---------------------------------------------------------------------------
# Тест W2: webhook.publish() при не-2xx возвращает (False, str с кодом)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_non_2xx_returns_false():
    """При HTTP не-2xx должен возвращать (False, str), не бросать исключение."""
    source = make_webhook_source()

    respx.post("https://example.com/hook").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    success, error = await webhook_publisher.publish("text", source, image_paths=[])

    assert success is False
    assert isinstance(error, str)
    assert "404" in error


# ---------------------------------------------------------------------------
# Тест W3: webhook.publish() при таймауте возвращает (False, str), не кидает
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_timeout_returns_false():
    """При таймауте должен возвращать (False, str), а не бросать исключение."""
    source = make_webhook_source()

    respx.post("https://example.com/hook").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    success, error = await webhook_publisher.publish("text", source, image_paths=[])

    assert success is False
    assert isinstance(error, str)
    assert "timeout" in error.lower()


# ---------------------------------------------------------------------------
# Тест W4: webhook.publish() с секретом добавляет X-Postery-Signature
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_with_secret_adds_signature():
    """При заданном secret запрос должен содержать X-Postery-Signature."""
    source = make_webhook_source(secret="my-secret")

    captured_headers = {}

    def capture(request, *args, **kwargs):
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    respx.post("https://example.com/hook").mock(side_effect=capture)

    success, error = await webhook_publisher.publish("text", source, image_paths=[])

    assert success is True
    sig_header = captured_headers.get("x-postery-signature", "")
    assert sig_header.startswith("sha256="), f"Expected sha256= prefix, got: {sig_header!r}"


# ---------------------------------------------------------------------------
# Тест W5: webhook.publish() без секрета НЕ добавляет X-Postery-Signature
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_without_secret_no_signature():
    """Без секрета заголовок X-Postery-Signature не должен присутствовать."""
    source = make_webhook_source(secret=None)

    captured_headers = {}

    def capture(request, *args, **kwargs):
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    respx.post("https://example.com/hook").mock(side_effect=capture)

    await webhook_publisher.publish("text", source, image_paths=[])

    assert "x-postery-signature" not in captured_headers


# ---------------------------------------------------------------------------
# Тест W6: envelope содержит ожидаемые ключи (VK-style, breaking change)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_payload_structure():
    """Envelope должен иметь ключи type/source_id/object, type=='publish'."""
    import json as _json
    source = make_webhook_source()

    captured_body = {}

    def capture(request, *args, **kwargs):
        captured_body["data"] = _json.loads(request.content)
        return httpx.Response(200)

    respx.post("https://example.com/hook").mock(side_effect=capture)

    await webhook_publisher.publish("text", source, image_paths=[])

    envelope = captured_body["data"]
    # Верхний уровень — envelope
    for key in ("type", "source_id", "object"):
        assert key in envelope, f"Missing envelope key: {key}"
    assert envelope["type"] == "publish"
    assert envelope["source_id"] == 1

    # object содержит поля поста
    obj = envelope["object"]
    for field in ("post_id", "title", "description", "tags", "published_at", "image_urls"):
        assert field in obj, f"Missing object field: {field}"
    assert obj["post_id"] == 42
    assert isinstance(obj["tags"], list)
    assert isinstance(obj["image_urls"], list)
    # source_id не должен дублироваться внутри object
    assert "source_id" not in obj


# ===========================================================================
# WEBHOOK CONFIRMATION CODE TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# Тест C1: confirmation_code детерминирован для одного URL+дня
# ---------------------------------------------------------------------------

def test_confirmation_code_deterministic():
    """Один и тот же URL в один день даёт один и тот же код."""
    from app.publisher.webhook import confirmation_code
    code1 = confirmation_code("https://example.com/hook")
    code2 = confirmation_code("https://example.com/hook")
    assert code1 == code2


# ---------------------------------------------------------------------------
# Тест C2: разные URL дают разные коды
# ---------------------------------------------------------------------------

def test_confirmation_code_different_urls():
    """Разные URL дают разные коды."""
    from app.publisher.webhook import confirmation_code
    code_a = confirmation_code("https://example.com/hook")
    code_b = confirmation_code("https://other.example.com/hook")
    assert code_a != code_b


# ---------------------------------------------------------------------------
# Тест C3: длина кода ровно 8, только hex-символы
# ---------------------------------------------------------------------------

def test_confirmation_code_format():
    """Код должен быть ровно 8 символов и состоять из hex-цифр."""
    from app.publisher.webhook import confirmation_code
    code = confirmation_code("https://example.com/hook")
    assert len(code) == 8
    assert all(c in "0123456789abcdef" for c in code)


# ---------------------------------------------------------------------------
# Тест C4: код меняется при смене дня (мокаем date.today)
# ---------------------------------------------------------------------------

def test_confirmation_code_rotates_daily():
    """Код для одного URL должен различаться в разные дни."""
    from unittest.mock import patch
    from datetime import date
    from app.publisher.webhook import confirmation_code

    url = "https://example.com/hook"

    with patch("app.publisher.webhook.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 1)
        code_day1 = confirmation_code(url)

    with patch("app.publisher.webhook.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 2)
        code_day2 = confirmation_code(url)

    assert code_day1 != code_day2


# ===========================================================================
# WEBHOOK TEST-ENDPOINT TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# Тест E1: совпадение — возвращает {ok: true}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_test_endpoint_match():
    """Если сервер вернул ожидаемый код — ok=True."""
    from unittest.mock import patch
    from datetime import date
    from app.routers.source import _test_webhook

    url = "https://example.com/hook"

    # Фиксируем дату для предсказуемого кода
    with patch("app.publisher.webhook.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 1)
        from app.publisher.webhook import confirmation_code
        expected = confirmation_code(url)

        respx.post(url).mock(return_value=httpx.Response(200, text=expected))

        result = await _test_webhook(url)

    assert result["ok"] is True
    assert "подтвердил" in result["message"].lower()


# ---------------------------------------------------------------------------
# Тест E2: несовпадение — возвращает {ok: false} с обоими кодами в message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_test_endpoint_mismatch():
    """Если сервер вернул неверный код — ok=False с описанием."""
    from unittest.mock import patch
    from datetime import date
    from app.routers.source import _test_webhook

    url = "https://example.com/hook"

    with patch("app.publisher.webhook.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 1)

        respx.post(url).mock(return_value=httpx.Response(200, text="wrong123"))
        result = await _test_webhook(url)

    assert result["ok"] is False
    assert "wrong123" in result["message"]


# ---------------------------------------------------------------------------
# Тест E3: не-2xx — возвращает {ok: false} с HTTP-статусом
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_test_endpoint_non_2xx():
    """При не-2xx ответе — ok=False с кодом статуса в message."""
    from app.routers.source import _test_webhook

    url = "https://example.com/hook"
    respx.post(url).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    result = await _test_webhook(url)

    assert result["ok"] is False
    assert "500" in result["message"]


# ---------------------------------------------------------------------------
# Тест E4: таймаут — возвращает {ok: false, message: "Таймаут 30 с"}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_webhook_test_endpoint_timeout():
    """При таймауте — ok=False, message содержит 'Таймаут'."""
    from app.routers.source import _test_webhook

    url = "https://example.com/hook"
    respx.post(url).mock(side_effect=httpx.TimeoutException("timeout"))

    result = await _test_webhook(url)

    assert result["ok"] is False
    assert "Таймаут" in result["message"]


# ---------------------------------------------------------------------------
# Тест E5: невалидный URL — возвращает {ok: false} без HTTP-запроса
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_test_endpoint_invalid_url():
    """При невалидном URL — ok=False без обращения к сети."""
    from app.routers.source import _test_webhook

    result = await _test_webhook("ftp://not-http.example.com")

    assert result["ok"] is False
    assert "http" in result["message"].lower()
