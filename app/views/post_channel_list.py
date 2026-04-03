from math import ceil

from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.database import SessionLocal
from app.models import TelegramSource, VKSource, MAXSource
from app.models.post import Post, PostChannel, PostStatus, ChannelStatus

_LIST_URL        = "/admin/posts"
_PER_PAGE_DEFAULT = 20
_PER_PAGE_OPTIONS = (5, 10, 20, 50, 100)

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
        page     = max(1, int(request.query_params.get("page", 1)))
        search   = request.query_params.get("q", "").strip()
        try:
            per_page = int(request.query_params.get("per_page", _PER_PAGE_DEFAULT))
        except ValueError:
            per_page = _PER_PAGE_DEFAULT
        if per_page not in _PER_PAGE_OPTIONS:
            per_page = _PER_PAGE_DEFAULT

        filter_source   = request.query_params.get("source", "").strip()
        filter_status   = request.query_params.get("status", "").strip()

        with SessionLocal() as db:
            tg  = {s.id: s for s in db.query(TelegramSource).all()}
            vk  = {s.id: s for s in db.query(VKSource).all()}
            mx  = {s.id: s for s in db.query(MAXSource).all()}

            # Опции для фильтра «Источник»
            source_options = []
            for s in sorted(tg.values(), key=lambda x: x.name):
                source_options.append({"value": f"telegram:{s.id}", "label": s.name, "type": "Telegram"})
            for s in sorted(vk.values(), key=lambda x: x.name):
                source_options.append({"value": f"vk:{s.id}", "label": s.name, "type": "ВКонтакте"})
            for s in sorted(mx.values(), key=lambda x: x.name):
                source_options.append({"value": f"max:{s.id}", "label": s.name, "type": "MAX"})

            q = db.query(Post).options(joinedload(Post.channels)).order_by(Post.created_at.desc())
            if search:
                q = q.filter(Post.title.ilike(f"%{search}%"))
            if filter_status:
                post_statuses = {s.value for s in PostStatus}
                if filter_status in post_statuses:
                    q = q.filter(Post.status == filter_status)
                else:
                    q = q.filter(Post.channels.any(PostChannel.status == filter_status))
            if filter_source:
                parts = filter_source.split(":")
                if len(parts) == 2:
                    try:
                        q = q.filter(Post.channels.any(
                            (PostChannel.source_type == parts[0]) &
                            (PostChannel.source_id == int(parts[1]))
                        ))
                    except ValueError:
                        filter_source = ""

            total_posts = q.count()
            posts = q.offset((page - 1) * per_page).limit(per_page).all()
            post_rows = [_build_post_row(p, tg, vk, mx) for p in posts]

        total_pages  = max(1, ceil(total_posts / per_page))
        failed_count = sum(1 for p in post_rows if p["has_failed"])

        return templates.TemplateResponse(
            request=request,
            name="posts/channel_list.html",
            context={
                "post_rows":        post_rows,
                "page":             page,
                "per_page":         per_page,
                "per_page_options": _PER_PAGE_OPTIONS,
                "total_pages":      total_pages,
                "total_posts":      total_posts,
                "search":           search,
                "list_url":         _LIST_URL,
                "failed_count":     failed_count,
                "source_options":   source_options,
                "filter_source":    filter_source,
                "filter_status":    filter_status,
            },
        )


def _build_post_row(post: Post, tg: dict, vk: dict, mx: dict) -> dict:
    channels = []
    has_failed = False
    for ch in post.channels:
        t   = ch.source_type
        src = (tg if t == "telegram" else vk if t == "vk" else mx).get(ch.source_id)
        if ch.status.value == "failed":
            has_failed = True
        channels.append({
            "channel_id":   ch.id,
            "ch_title":     ch.title or post.title,
            "source_type":  t,
            "source_icon":  _SOURCE_ICONS.get(t, "fa-solid fa-circle"),
            "source_label": _SOURCE_LABELS.get(t, t),
            "source_name":  src.name if src else f"#{ch.source_id}",
            "ch_status":    ch.status.value,
            "scheduled_at": ch.scheduled_at,
            "published_at": ch.published_at,
            "error_msg":    ch.error_message,
        })
    return {
        "post_id":      post.id,
        "post_title":   post.title,
        "post_tags":    post.tags,
        "post_status":  post.status.value,
        "post_created": post.created_at,
        "has_failed":   has_failed,
        "channels":     channels,
    }
