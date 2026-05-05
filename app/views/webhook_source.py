import logging
import re

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.database import SessionLocal
from app.models import WebhookSource
from app.publisher.webhook import confirmation_code as _confirmation_code

log_audit = logging.getLogger("admin.audit")

_LIST_URL = "/admin/webhook-source/list"

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class WebhookSourceWizardView(CustomView):
    def __init__(self, **kwargs):
        super().__init__(
            path="/webhook-source/wizard",
            template_path="source/webhook.html",
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

        # Вычисляем код подтверждения для отображения в UI.
        # Приоритет: данные формы (если есть ошибка и форма перерендерится),
        # затем сохранённые данные источника, иначе None.
        url_for_code = (
            (form or {}).get("webhook_url")
            or (source or {}).get("webhook_url")
            or ""
        )
        code = _confirmation_code(url_for_code) if url_for_code else None

        return templates.TemplateResponse(
            request=request,
            name="source/webhook.html",
            context={
                "wizard_url":        wizard_url,
                "list_url":          _LIST_URL,
                "editing":           editing,
                "source":            source,
                "errors":            errors or {},
                "form":              form or {},
                "confirmation_code": code,
            },
        )

    async def _post_create(self, request, templates, wizard_url):
        form = await request.form()
        name        = (form.get("name") or "").strip()
        webhook_url = (form.get("webhook_url") or "").strip()
        secret      = (form.get("secret") or "").strip() or None
        is_active   = form.get("is_active") == "on"

        errors: dict[str, str] = {}
        if not name:
            errors["name"] = "Обязательное поле"
        if not webhook_url:
            errors["webhook_url"] = "Обязательное поле"
        elif not _URL_RE.match(webhook_url):
            errors["webhook_url"] = "URL должен начинаться с http:// или https://"

        if errors:
            return self._render(request, templates, wizard_url,
                                errors=errors, form=dict(form))

        with SessionLocal() as db:
            source = WebhookSource(
                name=name,
                webhook_url=webhook_url,
                secret=secret,
                is_active=is_active,
            )
            db.add(source)
            db.commit()
            user_id = request.session.get("user_id")
            log_audit.info(
                "Source created source_type=webhook source_id=%d user_id=%s",
                source.id, user_id,
            )

        return RedirectResponse(_LIST_URL, status_code=302)

    # ── Edit ──────────────────────────────────────────────────────────────────

    async def _handle_edit(self, request, templates, pk, wizard_url):
        with SessionLocal() as db:
            source = db.get(WebhookSource, pk)
            if not source:
                return RedirectResponse(_LIST_URL, status_code=302)
            source_data = {
                "id":                    source.id,
                "name":                  source.name,
                "webhook_url":           source.webhook_url,
                "ai_prompt_title":       source.ai_prompt_title,
                "ai_prompt_description": source.ai_prompt_description,
                "auto_generate":         source.auto_generate,
                "is_active":             source.is_active,
            }

        if request.method == "POST":
            return await self._post_edit(request, templates, pk, source_data, wizard_url)
        return self._render(request, templates, wizard_url, source=source_data)

    async def _post_edit(self, request, templates, pk, source_data, wizard_url):
        form = await request.form()
        name        = (form.get("name") or "").strip()
        webhook_url = (form.get("webhook_url") or "").strip()
        secret      = (form.get("secret") or "").strip() or None
        ai_prompt_title       = (form.get("ai_prompt_title") or "").strip() or None
        ai_prompt_description = (form.get("ai_prompt_description") or "").strip() or None
        auto_generate = form.get("auto_generate") == "on"
        is_active     = form.get("is_active") == "on"

        errors: dict[str, str] = {}
        if not name:
            errors["name"] = "Обязательное поле"
        if not webhook_url:
            errors["webhook_url"] = "Обязательное поле"
        elif not _URL_RE.match(webhook_url):
            errors["webhook_url"] = "URL должен начинаться с http:// или https://"

        if errors:
            return self._render(request, templates, wizard_url,
                                source=source_data, errors=errors, form=dict(form))

        with SessionLocal() as db:
            source = db.get(WebhookSource, pk)
            source.name                  = name
            source.webhook_url           = webhook_url
            source.ai_prompt_title       = ai_prompt_title
            source.ai_prompt_description = ai_prompt_description
            source.auto_generate         = auto_generate
            source.is_active             = is_active
            if secret:
                source.secret = secret
            db.commit()
            user_id = request.session.get("user_id")
            log_audit.info(
                "Source modified source_type=webhook source_id=%d user_id=%s",
                source.id, user_id,
            )

        return RedirectResponse(_LIST_URL, status_code=302)
