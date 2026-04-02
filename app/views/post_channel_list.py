from math import ceil

from sqlalchemy.orm import joinedload
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.database import SessionLocal
from app.models import TelegramSource, VKSource, MAXSource
from app.models.post import Post, PostChannel

_LIST_URL = "/admin/posts"
_PER_PAGE = 20

_SOURCE_ICONS = {
    "telegram": "fa-brands fa-telegram",
    "vk":       "fa-brands fa-vk",
    "max":      "fa-solid fa-message",
}
_SOURCE_LABELS = {
    "telegram": "Telegram",
    "vk":       "ВКонтакте",
    "max":      "MAX",
}


class PostChannelListView(CustomView):
    def __init__(self, **kwargs):
        super().__init__(
            path="/posts",
            template_path="posts/channel_list.html",
            methods=["GET", "POST"],
            **kwargs,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        if request.method == "POST":
            return await self._handle_delete(request)
        return self._render_list(request, templates)

    # ── Delete ────────────────────────────────────────────────────────────────

    async def _handle_delete(self, request: Request) -> Response:
        form = await request.form()
        channel_id = form.get("delete_channel_id")
        post_id    = form.get("delete_post_id")

        with SessionLocal() as db:
            if channel_id:
                channel = db.get(PostChannel, int(channel_id))
                if channel:
                    db.delete(channel)
                    db.commit()
            elif post_id:
                post = db.get(Post, int(post_id))
                if post:
                    db.delete(post)
                    db.commit()

        referer = request.headers.get("referer", _LIST_URL)
        return RedirectResponse(referer, status_code=302)

    # ── List ──────────────────────────────────────────────────────────────────

    def _render_list(self, request: Request, templates: Jinja2Templates) -> Response:
        page   = max(1, int(request.query_params.get("page", 1)))
        search = request.query_params.get("q", "").strip()

        with SessionLocal() as db:
            # Предзагружаем все источники для быстрого поиска по имени
            tg  = {s.id: s for s in db.query(TelegramSource).all()}
            vk  = {s.id: s for s in db.query(VKSource).all()}
            mx  = {s.id: s for s in db.query(MAXSource).all()}

            q = db.query(Post).options(joinedload(Post.channels)).order_by(Post.created_at.desc())
            if search:
                q = q.filter(Post.title.ilike(f"%{search}%"))

            total_posts = q.count()
            posts = q.offset((page - 1) * _PER_PAGE).limit(_PER_PAGE).all()

            rows = []
            for post in posts:
                if post.channels:
                    for ch in post.channels:
                        rows.append(_build_row(post, ch, tg, vk, mx))
                else:
                    rows.append(_build_row(post, None, tg, vk, mx))

        # Для пагинации считаем по постам, а не по строкам
        total_pages = max(1, ceil(total_posts / _PER_PAGE))

        return templates.TemplateResponse(
            request=request,
            name="posts/channel_list.html",
            context={
                "rows":        rows,
                "page":        page,
                "total_pages": total_pages,
                "total_posts": total_posts,
                "search":      search,
                "list_url":    _LIST_URL,
            },
        )


def _build_row(post: Post, channel: PostChannel | None,
               tg: dict, vk: dict, mx: dict) -> dict:
    source_name = source_icon = source_label = None
    if channel:
        t = channel.source_type
        source_icon  = _SOURCE_ICONS.get(t, "fa-solid fa-circle")
        source_label = _SOURCE_LABELS.get(t, t)
        if t == "telegram":
            src = tg.get(channel.source_id)
        elif t == "vk":
            src = vk.get(channel.source_id)
        else:
            src = mx.get(channel.source_id)
        source_name = src.name if src else f"#{channel.source_id}"

    return {
        "post_id":       post.id,
        "post_title":    post.title,
        "post_tags":     post.tags,
        "post_status":   post.status.value,
        "post_created":  post.created_at,
        "channel_id":    channel.id if channel else None,
        "source_type":   channel.source_type if channel else None,
        "source_icon":   source_icon,
        "source_label":  source_label,
        "source_name":   source_name,
        "ch_status":     channel.status.value if channel else None,
        "scheduled_at":  channel.scheduled_at if channel else None,
        "published_at":  channel.published_at if channel else None,
        "error_msg":     channel.error_message if channel else None,
    }
