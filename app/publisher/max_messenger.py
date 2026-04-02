"""Публикация в канал MAX (botapi.max.ru)."""
import logging
import httpx

log = logging.getLogger("publisher.max")

MAX_API = "https://botapi.max.ru"


async def publish(text: str, source, image_paths: list[str]) -> tuple[bool, str | None]:
    token   = source.bot_token
    chat_id = source.chat_id

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            attachments = []

            if image_paths:
                for path in image_paths[:10]:
                    att = await _upload_image(client, token, path)
                    if att:
                        attachments.append(att)
                        log.info("MAX image uploaded: %s", att.get("payload", {}).get("token", "?"))

            body: dict = {
                "recipient": {"chat_id": chat_id},
                "type": "text",
                "text": text or "—",
            }
            if attachments:
                body["attachments"] = attachments

            r = await client.post(
                f"{MAX_API}/messages",
                params={"access_token": token},
                json=body,
            )
            r.raise_for_status()
            data = r.json()

            if data.get("code"):
                return False, f"MAX error {data['code']}: {data.get('message', '')}"

            log.info("MAX message sent, mid=%s", data.get("message", {}).get("mid"))
            return True, None

    except httpx.HTTPStatusError as e:
        return False, f"HTTP {e.response.status_code}: {e.response.text[:500]}"
    except Exception:
        import traceback
        return False, traceback.format_exc(limit=5)


async def _upload_image(client: httpx.AsyncClient, token: str, path: str) -> dict | None:
    """Загружает изображение и возвращает attachment-объект для MAX API."""
    # 1. Получаем URL для загрузки
    r = await client.post(
        f"{MAX_API}/uploads",
        params={"access_token": token, "type": "image"},
    )
    r.raise_for_status()
    data = r.json()

    if data.get("code"):
        raise RuntimeError(f"MAX uploads error {data['code']}: {data.get('message', '')}")

    upload_url = data.get("url")
    if not upload_url:
        raise RuntimeError(f"MAX uploads: no url in response: {data}")

    # 2. Загружаем файл
    with open(path, "rb") as f:
        up = await client.post(upload_url, files={"data": f})
    up.raise_for_status()
    up_data = up.json()
    log.debug("MAX upload response: %s", up_data)

    # 3. Формируем attachment
    photo_token = up_data.get("token") or (up_data.get("photos", [{}])[0].get("token"))
    if not photo_token:
        raise RuntimeError(f"MAX upload: cannot get photo token from: {up_data}")

    return {
        "type": "image",
        "payload": {"token": photo_token},
    }
