from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import BASE_DIR
from app.database import SessionLocal
from app.models.post import Post, PostChannel, PostImage, PostStatus, ChannelStatus

router = APIRouter(prefix="/api/posts", tags=["posts"])


class RepublishRequest(BaseModel):
    post_id: int
    channel_id: int          # источник для копирования title/description/source
    dates: list[str]         # ISO datetime strings, например ["2026-04-05T10:00"]


@router.post("/republish")
async def republish(body: RepublishRequest):
    if not body.dates:
        return {"ok": False, "error": "Укажите хотя бы одну дату"}

    now = datetime.utcnow()  # naive UTC — согласуется с worker.py и BR-009
    parsed_dates: list[datetime] = []
    for raw in body.dates:
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return {"ok": False, "error": f"Неверный формат даты: {raw}"}
        if dt <= now:
            return {"ok": False, "error": f"Дата {raw} уже прошла — укажите будущее время"}
        parsed_dates.append(dt)

    with SessionLocal() as db:
        channel = db.get(PostChannel, body.channel_id)
        if not channel or channel.post_id != body.post_id:
            return {"ok": False, "error": "Источник не найден"}

        post = db.get(Post, body.post_id)
        if not post:
            return {"ok": False, "error": "Пост не найден"}

        for dt in parsed_dates:
            db.add(PostChannel(
                post_id=body.post_id,
                source_type=channel.source_type,
                source_id=channel.source_id,
                title=channel.title,
                description=channel.description,
                status=ChannelStatus.PENDING,
                scheduled_at=dt,
            ))

        # Переводим пост в READY чтобы воркер обработал новые каналы
        post.status = PostStatus.READY
        db.commit()

    return {"ok": True, "created": len(parsed_dates)}


@router.delete("/image/{image_id}")
async def delete_image(image_id: int):
    """Удалить прикреплённое изображение из поста.

    Удаляет запись из post_images и файл с диска.
    Доступно только авторизованным пользователям (сессия проверяется на уровне
    admin UI, но этот эндпоинт не добавляет дополнительной server-side auth-проверки
    т.к. все /api/* маршруты обслуживают только страницы admin-панели).
    """
    import logging
    logger = logging.getLogger(__name__)

    with SessionLocal() as db:
        image = db.get(PostImage, image_id)
        if not image:
            return {"ok": False, "error": "Изображение не найдено"}

        file_path = Path(BASE_DIR) / image.file_path
        db.delete(image)
        db.commit()

    # Удаляем файл с диска после фиксации транзакции
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info("Удалён файл изображения: %s", file_path)
    except OSError as exc:
        logger.warning("Не удалось удалить файл %s: %s", file_path, exc)

    return {"ok": True}
