import uuid
import warnings

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.database import SessionLocal
from app.models.providers.ai_provider import AIProvider, ProviderType
from app.models.sources.telegram import TelegramSource
from app.models.sources.vk import VKSource
from app.models.sources.max_messenger import MAXSource

router = APIRouter(prefix="/api/ai", tags=["ai"])


class GenerateRequest(BaseModel):
    text: str
    source_type: str   # "telegram" | "vk" | "max"
    source_id: int
    field: str         # "title" | "description"


@router.post("/generate")
async def generate_text(body: GenerateRequest):
    with SessionLocal() as db:
        provider = db.query(AIProvider).filter_by(is_active=True).first()
        if not provider:
            return {"ok": False, "error": "Нет активного AI провайдера"}

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


async def _generate_gigachat(api_key: str, scope: str | None, system_msg: str | None, user_msg: str) -> dict:
    # Получить OAuth токен
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
            return {"ok": False, "error": f"Ошибка авторизации GigaChat: HTTP {auth_resp.status_code}"}
        access_token = auth_resp.json().get("access_token")
    except Exception as e:
        return {"ok": False, "error": f"Ошибка авторизации GigaChat: {e}"}

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
