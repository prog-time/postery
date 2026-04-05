"""
Фоновый воркер публикации.

Каждые POLL_INTERVAL секунд проверяет PostChannel со статусом PENDING,
у которых scheduled_at IS NULL (публиковать сразу) или scheduled_at <= now().
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import or_

from app.config import BASE_DIR, MAX_ATTEMPTS, RETRY_DELAY_MINUTES
from app.database import SessionLocal
from app.models.post import PostChannel, ChannelStatus, PostStatus
from app.models.sources.telegram import TelegramSource
from app.models.sources.vk import VKSource
from app.models.sources.max_messenger import MAXSource
from app.publisher import telegram as tg_publisher
from app.publisher import vk as vk_publisher
from app.publisher import max_messenger as max_publisher

log = logging.getLogger("worker")

POLL_INTERVAL = 30  # секунд


async def run_worker():
    log.info("Worker started (poll every %ds)", POLL_INTERVAL)
    while True:
        try:
            await _process_due_channels()
        except Exception:
            log.exception("Worker iteration failed")
        await asyncio.sleep(POLL_INTERVAL)


async def _process_due_channels():
    now = datetime.utcnow()  # naive UTC — совпадает с тем, что хранит datetime-local input после конвертации на фронте

    with SessionLocal() as db:
        due = (
            db.query(PostChannel)
            .filter(
                PostChannel.status == ChannelStatus.PENDING,
                or_(PostChannel.scheduled_at == None, PostChannel.scheduled_at <= now),
                or_(PostChannel.retry_after == None, PostChannel.retry_after <= now),
            )
            .all()
        )

    for channel in due:
        await _publish_channel(channel.id)


async def _publish_channel(channel_id: int):
    with SessionLocal() as db:
        channel = db.get(PostChannel, channel_id)
        if not channel or channel.status != ChannelStatus.PENDING:
            return

        post = channel.post

        # Проверяем: пост должен быть READY
        if post.status not in (PostStatus.READY, PostStatus.PUBLISHED):
            return

        # Загружаем source
        source = None
        if channel.source_type == "telegram":
            source = db.get(TelegramSource, channel.source_id)
        elif channel.source_type == "vk":
            source = db.get(VKSource, channel.source_id)
        elif channel.source_type == "max":
            source = db.get(MAXSource, channel.source_id)

        if not source:
            channel.status = ChannelStatus.FAILED
            channel.error_message = "Source not found"
            db.commit()
            log.warning("Channel %d: source not found", channel_id)
            return

        log.info("Publishing channel %d → %s / %s", channel_id, channel.source_type, source.name)

        # Загружаем все данные синхронно пока сессия открыта —
        # async-паблишеры не должны делать lazy-load во время await
        from app.publisher.utils import build_text
        image_paths = [str(BASE_DIR / img.file_path) for img in post.images]
        text_html  = build_text(channel, post, bold_title=True)
        text_plain = build_text(channel, post, bold_title=False)
        log.info("Channel %d: %d image(s) to attach", channel_id, len(image_paths))

        if channel.source_type == "telegram":
            success, error = await tg_publisher.publish(text_html, source, image_paths)
        elif channel.source_type == "vk":
            success, error = await vk_publisher.publish(text_plain, source, image_paths)
        elif channel.source_type == "max":
            success, error = await max_publisher.publish(text_plain, source, image_paths)
        else:
            success, error = False, f"Unsupported source type: {channel.source_type}"

        if success:
            channel.status = ChannelStatus.PUBLISHED
            channel.published_at = datetime.utcnow()
            channel.error_message = None
            # attempt is preserved for analytics (per AC-6)
        else:
            channel.attempt += 1
            channel.error_message = error[:500] if error else None

            if channel.attempt < MAX_ATTEMPTS:
                # Остаётся PENDING; следующая попытка через attempt * RETRY_DELAY_MINUTES мин
                delay_minutes = channel.attempt * RETRY_DELAY_MINUTES
                channel.retry_after = datetime.utcnow() + timedelta(minutes=delay_minutes)
                log.warning(
                    "Channel %d: attempt %d/%d, retry in %d min",
                    channel_id, channel.attempt, MAX_ATTEMPTS, delay_minutes,
                )
            else:
                channel.status = ChannelStatus.FAILED
                channel.retry_after = None
                log.error("Channel %d failed: %s", channel_id, error)

        # Если все каналы опубликованы — помечаем пост
        db.flush()
        db.refresh(post)
        all_done = all(
            ch.status == ChannelStatus.PUBLISHED for ch in post.channels
        )
        if all_done:
            post.status = PostStatus.PUBLISHED

        db.commit()

        if success:
            log.info("Channel %d published successfully", channel_id)
