"""
Тесты кэширования OAuth-токена GigaChat.
"""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-0000000000000000")

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx

import app.routers.ai_generate as ai_module
from app.routers.ai_generate import _get_gigachat_token, _gigachat_cache


def _reset_cache():
    _gigachat_cache["token"] = None
    _gigachat_cache["expires_at"] = datetime.min
    _gigachat_cache["api_key_hash"] = None


@pytest.fixture(autouse=True)
def clear_cache():
    _reset_cache()
    yield
    _reset_cache()


# ---------------------------------------------------------------------------
# Вспомогательный mock для OAuth-эндпоинта
# ---------------------------------------------------------------------------

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"


@respx.mock
@pytest.mark.asyncio
async def test_token_fetched_once_on_two_calls():
    """При двух последовательных вызовах OAuth-запрос совершается только один раз."""
    oauth_route = respx.post(OAUTH_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-abc"})
    )

    token1, err1 = await _get_gigachat_token("key123", "GIGACHAT_API_PERS")
    token2, err2 = await _get_gigachat_token("key123", "GIGACHAT_API_PERS")

    assert err1 is None
    assert err2 is None
    assert token1 == "tok-abc"
    assert token2 == "tok-abc"
    assert oauth_route.call_count == 1, "OAuth должен вызываться только раз при валидном кэше"


@respx.mock
@pytest.mark.asyncio
async def test_cache_invalidated_on_key_change():
    """При смене api_key кэш сбрасывается и выполняется новый OAuth-запрос."""
    respx.post(OAUTH_URL).mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok-first"}),
            httpx.Response(200, json={"access_token": "tok-second"}),
        ]
    )

    token1, _ = await _get_gigachat_token("key-A", None)
    token2, _ = await _get_gigachat_token("key-B", None)

    assert token1 == "tok-first"
    assert token2 == "tok-second"


@respx.mock
@pytest.mark.asyncio
async def test_cache_refreshed_after_expiry():
    """Когда токен истёк (expires_at в прошлом), выполняется новый OAuth-запрос."""
    respx.post(OAUTH_URL).mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok-old"}),
            httpx.Response(200, json={"access_token": "tok-new"}),
        ]
    )

    await _get_gigachat_token("key123", None)

    # Принудительно устареваем кэш
    _gigachat_cache["expires_at"] = datetime.now() - timedelta(seconds=1)

    token, err = await _get_gigachat_token("key123", None)
    assert token == "tok-new"
    assert err is None


@respx.mock
@pytest.mark.asyncio
async def test_cache_not_used_when_less_than_60s_remaining():
    """Кэш не используется, если до истечения меньше 60 секунд (запас 1 минута)."""
    respx.post(OAUTH_URL).mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok-1"}),
            httpx.Response(200, json={"access_token": "tok-2"}),
        ]
    )

    await _get_gigachat_token("key123", None)
    # Устанавливаем expires_at = now + 30s (меньше порога 60s)
    _gigachat_cache["expires_at"] = datetime.now() + timedelta(seconds=30)

    token, err = await _get_gigachat_token("key123", None)
    assert token == "tok-2"
    assert err is None


@respx.mock
@pytest.mark.asyncio
async def test_oauth_error_returned():
    """При ошибке OAuth возвращается (None, error_message)."""
    respx.post(OAUTH_URL).mock(return_value=httpx.Response(401))

    token, err = await _get_gigachat_token("bad-key", None)
    assert token is None
    assert "401" in err
