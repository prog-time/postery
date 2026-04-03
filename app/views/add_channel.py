from datetime import datetime

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.auth import EditorAccessMixin
from app.database import SessionLocal
from app.models import TelegramSource, VKSource, MAXSource
from app.models.post import Post, PostChannel, PostStatus, ChannelStatus

_LIST_URL = "/admin/posts"


class AddChannelView(EditorAccessMixin, CustomView):
    def __init__(self, **kwargs):
        super().__init__(
            path="/posts/add-channel",
            template_path="posts/add_channel.html",
            methods=["GET", "POST"],
            **kwargs,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        if request.method == "POST":
            return await self._handle_post(request, templates)
        return self._handle_get(request, templates)

    def _handle_get(self, request: Request, templates: Jinja2Templates) -> Response:
        post_id = request.query_params.get("post_id")
        with SessionLocal() as db:
            post = db.get(Post, int(post_id)) if post_id else None
            tg_sources = db.query(TelegramSource).filter(TelegramSource.is_active.is_(True)).order_by(TelegramSource.name).all()
            vk_sources = db.query(VKSource).filter(VKSource.is_active.is_(True)).order_by(VKSource.name).all()
            mx_sources = db.query(MAXSource).filter(MAXSource.is_active.is_(True)).order_by(MAXSource.name).all()

        return templates.TemplateResponse(
            request=request,
            name="posts/add_channel.html",
            context={
                "post":       post,
                "tg_sources": tg_sources,
                "vk_sources": vk_sources,
                "mx_sources": mx_sources,
            },
        )

    async def _handle_post(self, request: Request, templates: Jinja2Templates) -> Response:
        form = await request.form()
        post_id      = form.get("post_id", "")
        source_raw   = form.get("source", "").strip()
        title        = (form.get("title") or "").strip() or None
        description  = (form.get("description") or "").strip() or None
        scheduled_at = form.get("scheduled_at", "").strip()

        form_data = {
            "selected_source":   source_raw,
            "form_title":        form.get("title", ""),
            "form_description":  form.get("description", ""),
            "form_scheduled_at": scheduled_at,
        }

        parts = source_raw.split(":") if source_raw else []
        if len(parts) != 2:
            return self._render_with_error(request, templates, post_id, "Выберите источник", form_data)

        source_type, source_id_str = parts
        try:
            source_id = int(source_id_str)
        except ValueError:
            return self._render_with_error(request, templates, post_id, "Выберите источник", form_data)

        with SessionLocal() as db:
            post = db.get(Post, int(post_id))
            if post is None:
                return self._render_with_error(request, templates, post_id, "Пост не найден", form_data)

            channel = PostChannel(
                post_id=post.id,
                source_type=source_type,
                source_id=source_id,
                title=title,
                description=description,
            )

            if scheduled_at:
                try:
                    channel.scheduled_at = datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M")
                except ValueError:
                    return self._render_with_error(request, templates, post_id, "Неверный формат даты", form_data)

            if post.status == PostStatus.DRAFT:
                post.status = PostStatus.READY

            db.add(channel)
            db.commit()

        return RedirectResponse(_LIST_URL, status_code=302)

    def _render_with_error(
        self,
        request: Request,
        templates: Jinja2Templates,
        post_id: str,
        error: str,
        form_data: dict | None = None,
    ) -> Response:
        with SessionLocal() as db:
            post = db.get(Post, int(post_id)) if post_id else None
            tg_sources = db.query(TelegramSource).filter(TelegramSource.is_active.is_(True)).order_by(TelegramSource.name).all()
            vk_sources = db.query(VKSource).filter(VKSource.is_active.is_(True)).order_by(VKSource.name).all()
            mx_sources = db.query(MAXSource).filter(MAXSource.is_active.is_(True)).order_by(MAXSource.name).all()

        return templates.TemplateResponse(
            request=request,
            name="posts/add_channel.html",
            context={
                "post":       post,
                "tg_sources": tg_sources,
                "vk_sources": vk_sources,
                "mx_sources": mx_sources,
                "error":      error,
                **(form_data or {}),
            },
        )
