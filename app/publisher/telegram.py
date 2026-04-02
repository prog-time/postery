"""Публикация PostChannel в Telegram через Bot API."""
import json
import httpx

TG_API = "https://api.telegram.org/bot{token}/{method}"


async def publish(text: str, source, image_paths: list[str]) -> tuple[bool, str | None]:
    """
    text        — готовый HTML-текст поста.
    source      — ORM TelegramSource (только простые атрибуты).
    image_paths — абсолютные пути к файлам.
    """
    token = source.bot_token
    chat_id = source.chat_id
    thread_id = source.thread_id

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if not image_paths:
                await _send_message(client, token, chat_id, thread_id, text)
            elif len(image_paths) == 1:
                await _send_photo(client, token, chat_id, thread_id, image_paths[0], text)
            else:
                await _send_media_group(client, token, chat_id, thread_id, image_paths, text)

        return True, None

    except httpx.HTTPStatusError as e:
        return False, f"Telegram HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return False, str(e)[:500]


async def _send_message(client, token, chat_id, thread_id, text):
    params = {"chat_id": chat_id, "text": text or "—", "parse_mode": "HTML"}
    if thread_id:
        params["message_thread_id"] = thread_id
    r = await client.post(TG_API.format(token=token, method="sendMessage"), data=params)
    r.raise_for_status()


async def _send_photo(client, token, chat_id, thread_id, img_path, caption):
    params = {"chat_id": chat_id, "caption": caption or "", "parse_mode": "HTML"}
    if thread_id:
        params["message_thread_id"] = thread_id
    with open(img_path, "rb") as f:
        r = await client.post(
            TG_API.format(token=token, method="sendPhoto"),
            data=params,
            files={"photo": f},
        )
    r.raise_for_status()


async def _send_media_group(client, token, chat_id, thread_id, img_paths, caption):
    media = []
    for i, _ in enumerate(img_paths[:10]):
        item = {"type": "photo", "media": f"attach://photo{i}"}
        if i == 0 and caption:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
        media.append(item)

    files = {}
    handles = []
    try:
        for i, path in enumerate(img_paths[:10]):
            fh = open(path, "rb")
            handles.append(fh)
            files[f"photo{i}"] = fh

        params = {"chat_id": chat_id, "media": json.dumps(media)}
        if thread_id:
            params["message_thread_id"] = thread_id

        r = await client.post(
            TG_API.format(token=token, method="sendMediaGroup"),
            data=params,
            files=files,
        )
        r.raise_for_status()
    finally:
        for fh in handles:
            fh.close()
