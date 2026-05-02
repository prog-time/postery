"""Публикация PostChannel через HTTP POST (Webhook)."""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

log = logging.getLogger("publisher.webhook")

_TIMEOUT = 30  # секунд — аналогично Telegram-publisher


async def publish(text: str, source, image_paths: list[str]) -> tuple[bool, str | None]:
    """
    Отправляет фиксированный JSON-payload на webhook_url источника.

    text        — готовый plain-текст поста (без HTML-тегов).
    source      — ORM WebhookSource (только простые атрибуты).
    image_paths — абсолютные пути к файлам изображений (используются для
                  формирования публичных URL; сами файлы не передаются).

    Контракт:
    - Никогда не бросает исключение наружу.
    - Возвращает (True, None) при HTTP 2xx.
    - Возвращает (False, error_str) при не-2xx / таймауте / сетевой ошибке.
      error_str содержит HTTP-статус + первые 500 символов тела ответа.
    """
    url = source.webhook_url

    # Строим публичные URL изображений из относительных путей вида
    # "data/uploads/<post_id>/<filename>".  Файловый путь абсолютный —
    # отрезаем всё до "data/uploads".
    image_urls: list[str] = []
    for abs_path in image_paths:
        # Нормализуем разделители и ищем маркер
        normalized = abs_path.replace("\\", "/")
        marker = "data/uploads/"
        idx = normalized.find(marker)
        if idx != -1:
            rel = normalized[idx:]  # data/uploads/...
            image_urls.append(f"/{rel}")
        else:
            image_urls.append(abs_path)

    # Effective title / description берём из уже подготовленного text.
    # Дополнительно передаём структурированные поля через source-контекст,
    # который передаётся снаружи через _publish_channel в worker.py.
    # Payload строится из атрибутов source, полученных через аргумент.
    payload = _build_payload(source=source, image_urls=image_urls)

    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if source.secret:
        sig = hmac.new(
            source.secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Postery-Signature"] = f"sha256={sig}"

    log.info("Webhook publish → url=%s payload_keys=%s", url, list(payload.keys()))

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, content=body_bytes, headers=headers)

        if resp.is_success:
            log.info("Webhook publish success url=%s status=%d", url, resp.status_code)
            return True, None
        else:
            truncated_body = resp.text[:500]
            error = f"Webhook HTTP {resp.status_code}: {truncated_body}"
            log.warning("Webhook non-2xx url=%s status=%d body=%s",
                        url, resp.status_code, truncated_body)
            return False, error

    except httpx.TimeoutException:
        log.warning("Webhook timeout url=%s", url)
        return False, f"Webhook timeout after {_TIMEOUT}s"
    except Exception as exc:
        log.exception("Webhook publish failed url=%s", url)
        return False, f"Webhook error: {str(exc)[:500]}"


def _build_payload(source, image_urls: list[str]) -> dict:
    """Формирует фиксированный JSON-payload для webhook-запроса.

    Поля payload (Issue #4, §Вопросы — принятые defaults):
      post_id        — int, ID поста
      source_id      — int, ID источника
      title          — str, заголовок (effective_title канала)
      description    — str | null, текст поста (effective_description)
      tags           — list[str], теги (разбитые по запятой, без #)
      published_at   — str (ISO 8601 UTC), время публикации
      image_urls     — list[str], публичные URL /data/uploads/...
    """
    # source здесь — WebhookSource; реальные значения поста/канала
    # должны быть переданы через расширенный вызов.  Поля поста
    # инжектируются worker.py через параметр source._channel_context
    # (см. worker.py — мы задаём временный атрибут перед вызовом publish).
    ctx = getattr(source, "_channel_context", {})

    tags_raw = ctx.get("tags") or ""
    tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]

    return {
        "post_id":      ctx.get("post_id"),
        "source_id":    source.id,
        "title":        ctx.get("title"),
        "description":  ctx.get("description"),
        "tags":         tags_list,
        "published_at": datetime.now(tz=timezone.utc).isoformat(),
        "image_urls":   image_urls,
    }
