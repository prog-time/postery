from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.database import SessionLocal
from app.models import VKSource

_LIST_URL = "/admin/v-k-source/list"


class VKSourceWizardView(CustomView):
    def __init__(self, **kwargs):
        super().__init__(
            path="/vk-source/wizard",
            template_path="source/vk.html",
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
            name="source/vk.html",
            context={
                "wizard_url": wizard_url,
                "list_url":   _LIST_URL,
                "editing":    editing,
                "source":     source,
                "errors":     errors or {},
                "form":       form or {},
            },
        )

    async def _post_create(self, request, templates, wizard_url):
        form = await request.form()
        name         = (form.get("name") or "").strip()
        access_token = (form.get("access_token") or "").strip()
        group_id_raw = (form.get("group_id") or "").strip()
        is_active    = form.get("is_active") == "on"

        errors: dict[str, str] = {}
        if not name:
            errors["name"] = "Обязательное поле"
        if not access_token:
            errors["access_token"] = "Обязательное поле"

        group_id = None
        if not group_id_raw:
            errors["group_id"] = "Обязательное поле"
        else:
            try:
                group_id = int(group_id_raw)
            except ValueError:
                errors["group_id"] = "Должно быть числом"

        if errors:
            return self._render(request, templates, wizard_url,
                                errors=errors, form=dict(form))

        with SessionLocal() as db:
            db.add(VKSource(
                name=name,
                access_token=access_token,
                group_id=group_id,
                is_active=is_active,
            ))
            db.commit()

        return RedirectResponse(_LIST_URL, status_code=302)

    # ── Edit ──────────────────────────────────────────────────────────────────

    async def _handle_edit(self, request, templates, pk, wizard_url):
        with SessionLocal() as db:
            source = db.get(VKSource, pk)
            if not source:
                return RedirectResponse(_LIST_URL, status_code=302)
            source_data = {
                "id":                    source.id,
                "name":                  source.name,
                "group_id":              source.group_id,
                "ai_prompt_title":       source.ai_prompt_title,
                "ai_prompt_description": source.ai_prompt_description,
                "is_active":             source.is_active,
            }

        if request.method == "POST":
            return await self._post_edit(request, templates, pk, source_data, wizard_url)
        return self._render(request, templates, wizard_url, source=source_data)

    async def _post_edit(self, request, templates, pk, source_data, wizard_url):
        form = await request.form()
        name         = (form.get("name") or "").strip()
        access_token = (form.get("access_token") or "").strip()
        group_id_raw = (form.get("group_id") or "").strip()
        ai_prompt_title       = (form.get("ai_prompt_title") or "").strip() or None
        ai_prompt_description = (form.get("ai_prompt_description") or "").strip() or None
        is_active    = form.get("is_active") == "on"

        errors: dict[str, str] = {}
        if not name:
            errors["name"] = "Обязательное поле"

        group_id = None
        if not group_id_raw:
            errors["group_id"] = "Обязательное поле"
        else:
            try:
                group_id = int(group_id_raw)
            except ValueError:
                errors["group_id"] = "Должно быть числом"

        if errors:
            return self._render(request, templates, wizard_url,
                                source=source_data, errors=errors, form=dict(form))

        with SessionLocal() as db:
            source = db.get(VKSource, pk)
            source.name                  = name
            source.group_id              = group_id
            source.ai_prompt_title       = ai_prompt_title
            source.ai_prompt_description = ai_prompt_description
            source.is_active             = is_active
            if access_token:
                source.access_token = access_token
            db.commit()

        return RedirectResponse(_LIST_URL, status_code=302)
