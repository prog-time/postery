import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/source", tags=["source"])


# ── Webhook ───────────────────────────────────────────────────────────────────

class WebhookTestRequest(BaseModel):
    webhook_url: str


@router.post("/webhook/test")
async def test_webhook(body: WebhookTestRequest):
    return await _test_webhook(body.webhook_url)


async def _test_webhook(webhook_url: str) -> dict:
    """Отправляет тестовый POST на указанный URL. Успех — любой HTTP 2xx."""
    import re
    if not re.match(r"^https?://", webhook_url, re.IGNORECASE):
        return {"ok": False, "error": "URL должен начинаться с http:// или https://"}

    stub_payload = {
        "post_id": None,
        "source_id": None,
        "title": "Postery test",
        "description": "This is a test ping from Postery.",
        "tags": [],
        "published_at": None,
        "image_urls": [],
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                webhook_url,
                json=stub_payload,
                headers={"Content-Type": "application/json"},
            )
        if resp.is_success:
            return {"ok": True, "message": f"Подключение успешно (HTTP {resp.status_code})"}
        else:
            truncated = resp.text[:200]
            return {"ok": False, "error": f"Сервер вернул HTTP {resp.status_code}: {truncated}"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Превышено время ожидания (30 с)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── VK ────────────────────────────────────────────────────────────────────────

class VKTestRequest(BaseModel):
    access_token: str
    group_id: int


@router.post("/vk/test")
async def test_vk(body: VKTestRequest):
    return await _test_vk(body.access_token, body.group_id)


async def _test_vk(access_token: str, group_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.vk.com/method/groups.getById",
                params={
                    "group_ids": group_id,
                    "access_token": access_token,
                    "v": "5.199",
                },
            )
        data = resp.json()
        if "error" in data:
            msg = data["error"].get("error_msg", "Ошибка VK API")
            return {"ok": False, "error": msg}
        groups = data.get("response", {}).get("groups", [])
        if not groups:
            return {"ok": False, "error": "Группа не найдена"}
        name = groups[0].get("name", f"id{group_id}")
        return {"ok": True, "message": f"Подключение успешно ({name})"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Превышено время ожидания"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class MAXTestRequest(BaseModel):
    bot_token: str
    chat_id: str | None = None


@router.post("/max/test")
async def test_max(body: MAXTestRequest):
    return await _test_max(body.bot_token, body.chat_id)


async def _test_max(bot_token: str, chat_id: str | None) -> dict:
    base = "https://botapi.max.ru"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/me", headers={"Authorization": f"Bearer {bot_token}"})
            if resp.status_code != 200:
                try:
                    msg = resp.json().get("message") or f"HTTP {resp.status_code}"
                except Exception:
                    msg = f"HTTP {resp.status_code}"
                return {"ok": False, "error": f"Неверный токен: {msg}"}

            bot_info = resp.json()
            bot_name = bot_info.get("username") or bot_info.get("name", "")

            if chat_id:
                resp2 = await client.get(
                    f"{base}/chats/{chat_id}",
                    headers={"Authorization": f"Bearer {bot_token}"},
                )
                if resp2.status_code != 200:
                    try:
                        msg = resp2.json().get("message") or f"HTTP {resp2.status_code}"
                    except Exception:
                        msg = f"HTTP {resp2.status_code}"
                    label = f"@{bot_name}" if bot_name else "бот"
                    return {
                        "ok": False,
                        "error": f"Бот {label} найден, но нет доступа к чату: {msg}",
                    }

            label = f"@{bot_name}" if bot_name else "бот"
            return {"ok": True, "message": f"Подключение успешно ({label})"}

    except httpx.TimeoutException:
        return {"ok": False, "error": "Превышено время ожидания"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class TelegramTestRequest(BaseModel):
    bot_token: str
    chat_id: str | None = None


@router.post("/telegram/test")
async def test_telegram(body: TelegramTestRequest):
    return await _test_telegram(body.bot_token, body.chat_id)


async def _test_telegram(bot_token: str, chat_id: str | None) -> dict:
    base = f"https://api.telegram.org/bot{bot_token}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Проверяем токен
            resp = await client.get(f"{base}/getMe")
            if resp.status_code != 200:
                try:
                    msg = resp.json().get("description") or f"HTTP {resp.status_code}"
                except Exception:
                    msg = f"HTTP {resp.status_code}"
                return {"ok": False, "error": f"Неверный токен: {msg}"}

            bot_info = resp.json().get("result", {})
            bot_name = bot_info.get("username", "")

            # Проверяем доступ к каналу/чату
            if chat_id:
                resp2 = await client.get(f"{base}/getChat", params={"chat_id": chat_id})
                if resp2.status_code != 200:
                    try:
                        msg = resp2.json().get("description") or f"HTTP {resp2.status_code}"
                    except Exception:
                        msg = f"HTTP {resp2.status_code}"
                    return {
                        "ok": False,
                        "error": f"Бот @{bot_name} найден, но нет доступа к чату: {msg}",
                    }

            label = f"@{bot_name}" if bot_name else "бот"
            return {"ok": True, "message": f"Подключение успешно ({label})"}

    except httpx.TimeoutException:
        return {"ok": False, "error": "Превышено время ожидания"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
