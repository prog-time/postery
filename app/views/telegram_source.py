from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.database import SessionLocal
from app.models import TelegramSource

_LIST_URL = "/admin/telegram-source/list"


class TelegramSourceWizardView(CustomView):
    def __init__(self, **kwargs):
        super().__init__(
            path="/telegram-source/wizard",
            template_path="source/telegram.html",
            methods=["GET", "POST"],
            add_to_menu=False,
            **kwargs,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        pk = request.query_params.get("pk")
        wizard_url = str(request.url).split("?")[0]

        if pk:
            return await self._handle_edit(request, templates, int(pk), wizard_url)

        if request.method == "POST":
            return await self._post_create(request, templates, wizard_url)
        return self._render(request, templates, wizard_url)

    # ── Create ────────────────────────────────────────────────────────────────

    def _render(self, request, templates, wizard_url,
                source=None, errors=None, form=None):
        editing = source is not None
        return templates.TemplateResponse(
            request=request,
            name="source/telegram.html",
            context={
                "wizard_url":  wizard_url,
                "list_url":    _LIST_URL,
                "editing":     editing,
                "source":      source,
                "errors":      errors or {},
                "form":        form or {},
            },
        )

    async def _post_create(self, request, templates, wizard_url):
        form = await request.form()
        name      = (form.get("name") or "").strip()
        bot_token = (form.get("bot_token") or "").strip()
        chat_id   = (form.get("chat_id") or "").strip()
        thread_id_raw = (form.get("thread_id") or "").strip()
        is_active = form.get("is_active") == "on"

        errors: dict[str, str] = {}
        if not name:
            errors["name"] = "Обязательное поле"
        if not bot_token:
            errors["bot_token"] = "Обязательное поле"
        if not chat_id:
            errors["chat_id"] = "Обязательное поле"

        thread_id = None
        if thread_id_raw:
            try:
                thread_id = int(thread_id_raw)
            except ValueError:
                errors["thread_id"] = "Должно быть числом"

        if errors:
            return self._render(request, templates, wizard_url,
                                errors=errors, form=dict(form))

        with SessionLocal() as db:
            db.add(TelegramSource(
                name=name,
                bot_token=bot_token,
                chat_id=chat_id,
                thread_id=thread_id,
                is_active=is_active,
            ))
            db.commit()

        return RedirectResponse(_LIST_URL, status_code=302)

    # ── Edit ──────────────────────────────────────────────────────────────────

    async def _handle_edit(self, request, templates, pk, wizard_url):
        with SessionLocal() as db:
            source = db.get(TelegramSource, pk)
            if not source:
                return RedirectResponse(_LIST_URL, status_code=302)
            source_data = {
                "id":                   source.id,
                "name":                 source.name,
                "chat_id":              source.chat_id,
                "thread_id":            source.thread_id,
                "ai_prompt_title":      source.ai_prompt_title,
                "ai_prompt_description": source.ai_prompt_description,
                "is_active":            source.is_active,
            }

        if request.method == "POST":
            return await self._post_edit(request, templates, pk, source_data, wizard_url)
        return self._render(request, templates, wizard_url, source=source_data)

    async def _post_edit(self, request, templates, pk, source_data, wizard_url):
        form = await request.form()
        name      = (form.get("name") or "").strip()
        bot_token = (form.get("bot_token") or "").strip()
        chat_id   = (form.get("chat_id") or "").strip()
        thread_id_raw = (form.get("thread_id") or "").strip()
        ai_prompt_title       = (form.get("ai_prompt_title") or "").strip() or None
        ai_prompt_description = (form.get("ai_prompt_description") or "").strip() or None
        is_active = form.get("is_active") == "on"

        errors: dict[str, str] = {}
        if not name:
            errors["name"] = "Обязательное поле"
        if not chat_id:
            errors["chat_id"] = "Обязательное поле"

        thread_id = None
        if thread_id_raw:
            try:
                thread_id = int(thread_id_raw)
            except ValueError:
                errors["thread_id"] = "Должно быть числом"

        if errors:
            return self._render(request, templates, wizard_url,
                                source=source_data, errors=errors, form=dict(form))

        with SessionLocal() as db:
            source = db.get(TelegramSource, pk)
            source.name                 = name
            source.chat_id              = chat_id
            source.thread_id            = thread_id
            source.ai_prompt_title      = ai_prompt_title
            source.ai_prompt_description = ai_prompt_description
            source.is_active            = is_active
            if bot_token:
                source.bot_token = bot_token
            db.commit()

        return RedirectResponse(_LIST_URL, status_code=302)
