import hashlib
import logging
import uuid
import warnings
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import AI_RATE_LIMIT_PER_MINUTE
from app.database import SessionLocal
from app.models.providers.ai_provider import AIProvider, ProviderType
from app.models.sources.telegram import TelegramSource
from app.models.sources.vk import VKSource
from app.models.sources.max_messenger import MAXSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

# In-process кэш OAuth-токена GigaChat (TTL 29 мин, сбрасывается при смене ключа)
_gigachat_cache: dict = {
    "token": None,
    "expires_at": datetime.min,
    "api_key_hash": None,
}

# Limiter берётся из app.state, куда он прикреплён в main.py (TASK-004)
_limiter = Limiter(key_func=get_remote_address)


class GenerateRequest(BaseModel):
    text: str
    source_type: str        # "telegram" | "vk" | "max"
    source_id: int
    field: str              # "title" | "description"
    prompt: str | None = None  # кастомный промпт; None → берётся из источника


@router.post("/generate")
@_limiter.limit(f"{AI_RATE_LIMIT_PER_MINUTE}/minute")
async def generate_text(request: Request, body: GenerateRequest):
    # Проверка аутентификации: сессия создаётся при входе в Admin (TASK-004)
    if not request.session.get("user_id"):
        return {"ok": False, "error": "Требуется авторизация"}

    with SessionLocal() as db:
        provider = db.query(AIProvider).filter_by(is_active=True).first()
        if not provider:
            return {"ok": False, "error": "Нет активного AI провайдера"}

        if body.prompt is not None and body.prompt.strip():
            ai_prompt = body.prompt.strip()
        else:
            source = _get_source(db, body.source_type, body.source_id)
            if source:
                raw_prompt = (
                    source.ai_prompt_title if body.field == "title"
                    else source.ai_prompt_description
                )
                ai_prompt = (raw_prompt or "").strip()
            else:
                ai_prompt = ""

    system_msg = ai_prompt if ai_prompt else None
    user_msg = body.text.strip()

    if not user_msg:
        return {"ok": False, "error": "Поле пустое — нечего обрабатывать"}

    if provider.provider_type == ProviderType.OPENAI:
        return await _generate_openai(provider.api_key, provider.base_url, system_msg, user_msg)
    if provider.provider_type == ProviderType.GIGACHAT:
        return await _generate_gigachat(provider.api_key, provider.scope, system_msg, user_msg)

    return {"ok": False, "error": "Неизвестный тип провайдера"}


def _get_source(db, source_type: str, source_id: int):
    if source_type == "telegram":
        return db.get(TelegramSource, source_id)
    if source_type == "vk":
        return db.get(VKSource, source_id)
    if source_type == "max":
        return db.get(MAXSource, source_id)
    return None


async def _generate_openai(api_key: str, base_url: str | None, system_msg: str | None, user_msg: str) -> dict:
    base = (base_url.rstrip("/") if base_url else "https://api.openai.com")
    messages = []
    if system_msg:
        messages.append({"role": "system", "content": system_msg})
    messages.append({"role": "user", "content": user_msg})

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "gpt-4o-mini", "messages": messages},
            )
        data = resp.json()
        if resp.status_code != 200:
            msg = data.get("error", {}).get("message") or f"HTTP {resp.status_code}"
            return {"ok": False, "error": msg}
        result = data["choices"][0]["message"]["content"].strip()
        return {"ok": True, "result": result}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Превышено время ожидания"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def _get_gigachat_token(api_key: str, scope: str | None) -> tuple[str | None, str | None]:
    """Возвращает (access_token, error). Использует кэш с TTL 29 мин."""
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    now = datetime.now()
    remaining = (_gigachat_cache["expires_at"] - now).total_seconds()

    if (
        _gigachat_cache["token"]
        and _gigachat_cache["api_key_hash"] == key_hash
        and remaining > 60
    ):
        logger.debug("GigaChat: using cached token (expires in %ds)", int(remaining))
        return _gigachat_cache["token"], None

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                auth_resp = await client.post(
                    "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                    headers={
                        "Authorization": f"Basic {api_key}",
                        "RqUID": str(uuid.uuid4()),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"scope": scope or "GIGACHAT_API_PERS"},
                )
        if auth_resp.status_code != 200:
            return None, f"Ошибка авторизации GigaChat: HTTP {auth_resp.status_code}"
        token = auth_resp.json().get("access_token")
        _gigachat_cache["token"] = token
        _gigachat_cache["expires_at"] = now + timedelta(seconds=29 * 60)
        _gigachat_cache["api_key_hash"] = key_hash
        return token, None
    except Exception as e:
        return None, f"Ошибка авторизации GigaChat: {e}"


async def _generate_gigachat(api_key: str, scope: str | None, system_msg: str | None, user_msg: str) -> dict:
    access_token, err = await _get_gigachat_token(api_key, scope)
    if err:
        return {"ok": False, "error": err}

    messages = []
    if system_msg:
        messages.append({"role": "system", "content": system_msg})
    messages.append({"role": "user", "content": user_msg})

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            async with httpx.AsyncClient(timeout=60, verify=False) as client:
                resp = await client.post(
                    "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"model": "GigaChat", "messages": messages},
                )
        data = resp.json()
        if resp.status_code != 200:
            msg = data.get("message") or f"HTTP {resp.status_code}"
            return {"ok": False, "error": msg}
        result = data["choices"][0]["message"]["content"].strip()
        return {"ok": True, "result": result}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Превышено время ожидания"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
