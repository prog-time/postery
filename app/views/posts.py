import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
log_audit = logging.getLogger("admin.audit")

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.config import BASE_DIR, ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_MB, MAX_IMAGES_PER_POST
from app.database import SessionLocal
from app.models.post import Post, PostImage, PostChannel, PostStatus, ChannelStatus
from app.models.sources.telegram import TelegramSource
from app.models.sources.vk import VKSource
from app.models.sources.max_messenger import MAXSource
from app.auth import EditorAccessMixin


UPLOAD_DIR = Path(BASE_DIR) / "data" / "uploads"


# ── Wizard (CustomView) ───────────────────────────────────────────────────────

class PostWizardView(EditorAccessMixin, CustomView):
    def __init__(self, **kwargs):
        super().__init__(
            path="/posts/wizard",
            template_path="posts/step1.html",
            methods=["GET", "POST"],
            **kwargs,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        step = int(request.query_params.get("step", 1))
        post_id = request.query_params.get("post_id")
        channel_id = request.query_params.get("channel_id")

        with SessionLocal() as db:
            if request.method == "POST":
                return await self._post(request, templates, db, step, post_id, channel_id)
            return await self._get(request, templates, db, step, post_id, channel_id)

    # ── GET ───────────────────────────────────────────────────────────────────

    async def _get(self, request, templates, db, step, post_id, channel_id):
        wizard_url = str(request.url).split("?")[0]
        user_id = request.session.get("user_id")

        if step == 1:
            log_audit.info("Post wizard step=1 post_id=%s user_id=%s", post_id, user_id)
            post = db.get(Post, int(post_id)) if post_id else None
            return templates.TemplateResponse(
                request=request,
                name="posts/step1.html",
                context={"step": 1, "post": post, "wizard_url": wizard_url},
            )

        if step == 2:
            log_audit.info("Post wizard step=2 post_id=%s user_id=%s", post_id, user_id)
            post = db.get(Post, int(post_id))
            tg_sources  = db.query(TelegramSource).filter_by(is_active=True).all()
            vk_sources  = db.query(VKSource).filter_by(is_active=True).all()
            max_sources = db.query(MAXSource).filter_by(is_active=True).all()
            selected_tg  = {ch.source_id for ch in post.channels if ch.source_type == "telegram"}
            selected_vk  = {ch.source_id for ch in post.channels if ch.source_type == "vk"}
            selected_max = {ch.source_id for ch in post.channels if ch.source_type == "max"}
            return templates.TemplateResponse(
                request=request,
                name="posts/step2.html",
                context={
                    "step": 2, "post": post,
                    "tg_sources": tg_sources, "vk_sources": vk_sources, "max_sources": max_sources,
                    "selected_tg": selected_tg, "selected_vk": selected_vk, "selected_max": selected_max,
                    "wizard_url": wizard_url,
                },
            )

        if step == 3:
            log_audit.info("Post wizard step=3 post_id=%s user_id=%s", post_id, user_id)
            from_list = request.query_params.get("from_list") == "1"
            post = db.get(Post, int(post_id))
            channel = db.get(PostChannel, int(channel_id))
            source = _resolve_source(db, channel)
            if from_list:
                return templates.TemplateResponse(
                    request=request,
                    name="posts/edit_channel.html",
                    context={
                        "post": post,
                        "channel": channel,
                        "source": source,
                        "wizard_url": wizard_url,
                    },
                )
            next_channel = _next_channel(post, channel)
            auto_generate = bool(source and getattr(source, "auto_generate", False))
            return templates.TemplateResponse(
                request=request,
                name="posts/step3.html",
                context={
                    "step": 3,
                    "post": post,
                    "channel": channel,
                    "source": source,
                    "next_channel": next_channel,
                    "total": len(post.channels),
                    "current_num": post.channels.index(channel) + 1,
                    "wizard_url": wizard_url,
                    "auto_generate": auto_generate,
                },
            )

    # ── POST ──────────────────────────────────────────────────────────────────

    async def _post(self, request, templates, db, step, post_id, channel_id):
        form = await request.form()
        wizard_url = str(request.url).split("?")[0]
        user_id = request.session.get("user_id")

        # ── Шаг 1: создать/обновить пост ────────────────────────────────────
        if step == 1:
            title = (form.get("title") or "").strip()
            if not title:
                post = db.get(Post, int(post_id)) if post_id else None
                return templates.TemplateResponse(
                    request=request,
                    name="posts/step1.html",
                    context={"step": 1, "post": post, "error": "Заголовок обязателен", "form": dict(form), "wizard_url": wizard_url},
                )

            if post_id:
                post = db.get(Post, int(post_id))
                post.title = title
                post.description = (form.get("description") or "").strip() or None
                post.tags = (form.get("tags") or "").strip() or None
            else:
                post = Post(
                    title=title,
                    description=(form.get("description") or "").strip() or None,
                    tags=(form.get("tags") or "").strip() or None,
                )
                db.add(post)
                db.flush()

            # Загрузка изображений — с валидацией типа и размера (TASK-003)
            images = form.getlist("images")
            max_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
            validated: list[tuple] = []  # (img, content) — пары прошедших проверку

            for img in images:
                if not (hasattr(img, "filename") and img.filename):
                    continue
                ext = Path(img.filename).suffix.lower()
                if ext not in ALLOWED_IMAGE_EXTENSIONS:
                    db.rollback()
                    post_ctx = db.get(Post, int(post_id)) if post_id else None
                    return templates.TemplateResponse(
                        request=request,
                        name="posts/step1.html",
                        context={
                            "step": 1,
                            "post": post_ctx,
                            "error": f"Недопустимый формат файла: «{img.filename}». Разрешены: JPG, JPEG, PNG, GIF, WEBP.",
                            "form": dict(form),
                            "wizard_url": wizard_url,
                        },
                    )
                content = await img.read()
                if len(content) > max_bytes:
                    db.rollback()
                    post_ctx = db.get(Post, int(post_id)) if post_id else None
                    return templates.TemplateResponse(
                        request=request,
                        name="posts/step1.html",
                        context={
                            "step": 1,
                            "post": post_ctx,
                            "error": f"Файл «{img.filename}» превышает допустимый размер {MAX_IMAGE_SIZE_MB} МБ.",
                            "form": dict(form),
                            "wizard_url": wizard_url,
                        },
                    )
                validated.append((img, content))

            # Проверка лимита: текущие + новые не должны превышать MAX_IMAGES_PER_POST
            existing_count = len(post.images)
            if existing_count + len(validated) > MAX_IMAGES_PER_POST:
                db.rollback()
                post_ctx = db.get(Post, int(post_id)) if post_id else None
                return templates.TemplateResponse(
                    request=request,
                    name="posts/step1.html",
                    context={
                        "step": 1,
                        "post": post_ctx,
                        "error": (
                            f"Нельзя прикрепить больше {MAX_IMAGES_PER_POST} изображений. "
                            f"Уже прикреплено: {existing_count}, добавляется: {len(validated)}."
                        ),
                        "form": dict(form),
                        "wizard_url": wizard_url,
                    },
                )

            for img, content in validated:
                upload_dir = UPLOAD_DIR / str(post.id)
                upload_dir.mkdir(parents=True, exist_ok=True)

                safe_name = Path(img.filename).name
                if not safe_name:
                    logger.warning("Пропущен файл с небезопасным именем: %r", img.filename)
                    continue
                dest = upload_dir / safe_name
                if not dest.resolve().is_relative_to(upload_dir.resolve()):
                    logger.warning("Path traversal заблокирован: %r → %s", img.filename, dest)
                    continue

                dest.write_bytes(content)
                order = len(post.images)
                db.add(PostImage(
                    post_id=post.id,
                    file_path=str(dest.relative_to(BASE_DIR)),
                    order=order,
                ))

            db.commit()
            log_audit.info("Post saved post_id=%d status=%s user_id=%s", post.id, post.status, user_id)
            return RedirectResponse(f"{wizard_url}?post_id={post.id}&step=2", status_code=302)

        # ── Шаг 2: выбрать источники ─────────────────────────────────────────
        if step == 2:
            post = db.get(Post, int(post_id))
            tg_ids  = [int(x) for x in form.getlist("telegram_sources")]
            vk_ids  = [int(x) for x in form.getlist("vk_sources")]
            max_ids = [int(x) for x in form.getlist("max_sources")]

            if not tg_ids and not vk_ids and not max_ids:
                tg_sources  = db.query(TelegramSource).filter_by(is_active=True).all()
                vk_sources  = db.query(VKSource).filter_by(is_active=True).all()
                max_sources = db.query(MAXSource).filter_by(is_active=True).all()
                selected_tg  = {ch.source_id for ch in post.channels if ch.source_type == "telegram"}
                selected_vk  = {ch.source_id for ch in post.channels if ch.source_type == "vk"}
                selected_max = {ch.source_id for ch in post.channels if ch.source_type == "max"}
                return templates.TemplateResponse(
                    request=request,
                    name="posts/step2.html",
                    context={
                        "step": 2, "post": post,
                        "tg_sources": tg_sources, "vk_sources": vk_sources, "max_sources": max_sources,
                        "selected_tg": selected_tg, "selected_vk": selected_vk, "selected_max": selected_max,
                        "error": "Выберите хотя бы один источник",
                        "wizard_url": wizard_url,
                    },
                )

            # Удалить старые каналы, пересоздать
            for ch in list(post.channels):
                db.delete(ch)
            db.flush()

            for src_id in tg_ids:
                db.add(PostChannel(post_id=post.id, source_type="telegram", source_id=src_id))
            for src_id in vk_ids:
                db.add(PostChannel(post_id=post.id, source_type="vk", source_id=src_id))
            for src_id in max_ids:
                db.add(PostChannel(post_id=post.id, source_type="max", source_id=src_id))

            db.commit()
            db.refresh(post)

            first = post.channels[0]
            return RedirectResponse(
                f"{wizard_url}?post_id={post.id}&step=3&channel_id={first.id}",
                status_code=302,
            )

        # ── Шаг 3: кастомизировать канал ─────────────────────────────────────
        if step == 3:
            channel = db.get(PostChannel, int(channel_id))
            post = channel.post

            channel.title = (form.get("title") or "").strip() or None
            channel.description = (form.get("description") or "").strip() or None

            scheduled_raw = (form.get("scheduled_at") or "").strip()
            if scheduled_raw:
                try:
                    channel.scheduled_at = datetime.fromisoformat(scheduled_raw)
                except ValueError:
                    channel.scheduled_at = None
            else:
                channel.scheduled_at = None

            db.commit()

            # Если редактирование из списка — сразу назад в список
            if (form.get("from_list") == "1" or
                    request.query_params.get("from_list") == "1"):
                return RedirectResponse("/admin/posts", status_code=302)

            nxt = _next_channel(post, channel)
            if nxt:
                return RedirectResponse(
                    f"{wizard_url}?post_id={post.id}&step=3&channel_id={nxt.id}",
                    status_code=302,
                )

            # Все каналы настроены
            post.status = PostStatus.READY
            db.commit()
            log_audit.info("Post saved post_id=%d status=%s user_id=%s", post.id, post.status, user_id)
            return RedirectResponse("/admin/posts", status_code=302)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_source(db, channel: PostChannel):
    if channel.source_type == "telegram":
        return db.get(TelegramSource, channel.source_id)
    if channel.source_type == "vk":
        return db.get(VKSource, channel.source_id)
    if channel.source_type == "max":
        return db.get(MAXSource, channel.source_id)
    return None


def _next_channel(post: Post, current: PostChannel) -> PostChannel | None:
    channels = post.channels
    try:
        idx = next(i for i, c in enumerate(channels) if c.id == current.id)
        return channels[idx + 1] if idx + 1 < len(channels) else None
    except StopIteration:
        return None
