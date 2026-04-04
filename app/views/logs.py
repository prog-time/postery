"""Admin UI страница просмотра и скачивания логов (TASK-LOG-005)."""
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.config import BASE_DIR
from app.auth import SuperadminOnly

LOGS_FILE = BASE_DIR / "data" / "logs" / "app.log"
DISPLAY_LINES = 500


class LogsView(SuperadminOnly, CustomView):
    def __init__(self, **kwargs):
        kwargs.setdefault("label", "Логи приложения")
        kwargs.setdefault("icon", "fa-solid fa-file-lines")
        super().__init__(
            path="/logs",
            template_path="logs.html",
            add_to_menu=True,
            **kwargs,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        lines = []
        if LOGS_FILE.exists():
            text = LOGS_FILE.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()[-DISPLAY_LINES:]
        return templates.TemplateResponse(
            "logs.html",
            {"request": request, "lines": lines, "total": len(lines)},
        )
