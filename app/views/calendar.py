import calendar
import json
from collections import defaultdict
from datetime import date, datetime

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.database import SessionLocal
from app.models import TelegramSource, VKSource, MAXSource, WebhookSource
from app.models.post import Post, PostChannel

_SOURCE_ICONS = {
    "telegram": "fa-brands fa-telegram",
    "vk":       "fa-brands fa-vk",
    "max":      "fa-solid fa-message",
    "webhook":  "fa fa-link",
}
_SOURCE_COLORS = {
    "telegram": "#0088cc",
    "vk":       "#4680c2",
    "max":      "#5b5ea6",
    "webhook":  "#64748b",
}
_MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
_MONTHS_GEN_RU = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
_WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class CalendarView(CustomView):
    def __init__(self, **kwargs):
        super().__init__(
            path="/calendar",
            template_path="calendar.html",
            methods=["GET"],
            **kwargs,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        today = date.today()
        try:
            year  = int(request.query_params.get("year",  today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            year, month = today.year, today.month

        # Границы месяца
        _, days_in_month = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end   = date(year, month, days_in_month)

        prev_month = month - 1 or 12
        prev_year  = year - (1 if month == 1 else 0)
        next_month = month % 12 + 1
        next_year  = year + (1 if month == 12 else 0)

        with SessionLocal() as db:
            tg  = {s.id: s for s in db.query(TelegramSource).all()}
            vk  = {s.id: s for s in db.query(VKSource).all()}
            mx  = {s.id: s for s in db.query(MAXSource).all()}
            wh  = {s.id: s for s in db.query(WebhookSource).all()}

            # PostChannels с датой в этом месяце
            channels = (
                db.query(PostChannel)
                .join(Post)
                .filter(
                    PostChannel.scheduled_at.isnot(None) |
                    PostChannel.published_at.isnot(None)
                )
                .all()
            )

            # Группируем по дате (YYYY-MM-DD)
            # day_data[date_str] = { "sources": set(), "hours": {hour: [entries]} }
            day_data: dict[str, dict] = defaultdict(lambda: {"sources": set(), "hours": defaultdict(list)})

            for ch in channels:
                dt: datetime | None = ch.published_at or ch.scheduled_at
                if not dt:
                    continue
                d = dt.date()
                if not (month_start <= d <= month_end):
                    continue

                ds = d.isoformat()
                day_data[ds]["sources"].add(ch.source_type)

                src_map = {"telegram": tg, "vk": vk, "max": mx, "webhook": wh}
                src_obj = src_map.get(ch.source_type, {}).get(ch.source_id)

                day_data[ds]["hours"][dt.hour].append({
                    "post_id":     ch.post_id,
                    "post_title":  ch.post.title,
                    "source_type": ch.source_type,
                    "source_icon": _SOURCE_ICONS.get(ch.source_type, "fa-circle"),
                    "source_color": _SOURCE_COLORS.get(ch.source_type, "#999"),
                    "source_name": src_obj.name if src_obj else f"#{ch.source_id}",
                    "status":      ch.status.value,
                    "time":        dt.strftime("%H:%M"),
                })

        # Превращаем в сериализуемый dict для JS
        js_data: dict[str, dict] = {}
        for ds, v in day_data.items():
            js_data[ds] = {
                "sources": [
                    {"type": t, "icon": _SOURCE_ICONS.get(t, "fa-circle"),
                     "color": _SOURCE_COLORS.get(t, "#999")}
                    for t in sorted(v["sources"])
                ],
                "hours": {
                    str(h): sorted(entries, key=lambda x: x["time"])
                    for h, entries in sorted(v["hours"].items())
                },
            }

        # Сетка календаря: список недель (каждая — 7 дней)
        cal = calendar.monthcalendar(year, month)  # list of weeks, 0 = outside month
        weeks = []
        for week in cal:
            row = []
            for day_num in week:
                if day_num == 0:
                    row.append(None)
                else:
                    d = date(year, month, day_num)
                    ds = d.isoformat()
                    row.append({
                        "date":     d,
                        "date_str": ds,
                        "is_today": d == today,
                        "sources":  js_data.get(ds, {}).get("sources", []),
                        "has_data": ds in js_data,
                    })
            weeks.append(row)

        return templates.TemplateResponse(
            request=request,
            name="calendar.html",
            context={
                "year":          year,
                "month":         month,
                "month_name":    _MONTHS_RU[month],
                "months_gen":    _MONTHS_GEN_RU,
                "weekdays":      _WEEKDAYS_RU,
                "weeks":         weeks,
                "today":         today,
                "prev_year":     prev_year,
                "prev_month":    prev_month,
                "next_year":     next_year,
                "next_month":    next_month,
                "js_data":       json.dumps(js_data, ensure_ascii=False).replace("</", "<\\/"),
            },
        )
