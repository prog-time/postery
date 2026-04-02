import uuid
import warnings

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai-provider", tags=["ai-provider"])


class TestRequest(BaseModel):
    provider_type: str
    api_key: str
    base_url: str | None = None
    scope: str | None = None


@router.post("/test")
async def test_connection(body: TestRequest):
    if body.provider_type == "openai":
        return await _test_openai(body.api_key, body.base_url)
    if body.provider_type == "gigachat":
        return await _test_gigachat(body.api_key, body.scope)
    return {"ok": False, "error": "Неизвестный тип провайдера"}


async def _test_openai(api_key: str, base_url: str | None) -> dict:
    base = (base_url.rstrip("/") if base_url else "https://api.openai.com")
    url = base + "/v1/models"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code == 200:
            return {"ok": True}
        try:
            msg = resp.json().get("error", {}).get("message") or f"HTTP {resp.status_code}"
        except Exception:
            msg = f"HTTP {resp.status_code}"
        return {"ok": False, "error": msg}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Превышено время ожидания"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def _test_gigachat(api_key: str, scope: str | None) -> dict:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.post(
                    "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                    headers={
                        "Authorization": f"Basic {api_key}",
                        "RqUID": str(uuid.uuid4()),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"scope": scope or "GIGACHAT_API_PERS"},
                )
        if resp.status_code == 200:
            return {"ok": True}
        return {"ok": False, "error": f"HTTP {resp.status_code}: ошибка аутентификации"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Превышено время ожидания"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
