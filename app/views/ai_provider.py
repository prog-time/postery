from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette_admin.views import CustomView

from app.database import SessionLocal
from app.models.providers import AIProvider, ProviderType

_LIST_URL = "/admin/ai-provider/list"


class AIProviderWizardView(CustomView):
    def __init__(self, **kwargs):
        super().__init__(
            path="/ai-provider/wizard",
            template_path="ai_provider/openai.html",
            methods=["GET", "POST"],
            add_to_menu=False,
            **kwargs,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        pk = request.query_params.get("pk")
        wizard_url = str(request.url).split("?")[0]

        if pk:
            return await self._handle_edit(request, templates, int(pk), wizard_url)

        provider_type = request.query_params.get("type", "")
        if provider_type not in ("openai", "gigachat"):
            return RedirectResponse(_LIST_URL, status_code=302)

        if request.method == "POST":
            return await self._post_create(request, templates, provider_type, wizard_url)
        return self._render(request, templates, provider_type, wizard_url)

    # ── Create ────────────────────────────────────────────────────────────────

    def _render(self, request, templates, provider_type, wizard_url,
                provider=None, errors=None, form=None):
        """Универсальный рендер — create и edit."""
        editing = provider is not None
        with SessionLocal() as db:
            already_exists = (
                not editing and
                db.query(AIProvider).filter_by(
                    provider_type=ProviderType(provider_type)
                ).first() is not None
            )
        return templates.TemplateResponse(
            request=request,
            name=f"ai_provider/{provider_type}.html",
            context={
                "provider_type":  provider_type,
                "wizard_url":     wizard_url,
                "list_url":       _LIST_URL,
                "editing":        editing,
                "provider":       provider,
                "already_exists": already_exists,
                "errors":         errors or {},
                "form":           form or {},
            },
        )

    async def _post_create(self, request, templates, provider_type, wizard_url):
        form    = await request.form()
        api_key  = (form.get("api_key") or "").strip()
        base_url = (form.get("base_url") or "").strip() or None
        scope    = (form.get("scope") or "").strip() or None
        is_active = form.get("is_active") == "on"

        errors: dict[str, str] = {}
        if not api_key:
            errors["api_key"] = "Обязательное поле"

        with SessionLocal() as db:
            if db.query(AIProvider).filter_by(
                provider_type=ProviderType(provider_type)
            ).first():
                errors["provider_type"] = "Провайдер этого типа уже добавлен"

        if errors:
            return self._render(request, templates, provider_type, wizard_url,
                                errors=errors, form=dict(form))

        with SessionLocal() as db:
            if is_active:
                db.query(AIProvider).update({"is_active": False})
                db.flush()
            db.add(AIProvider(
                provider_type=ProviderType(provider_type),
                api_key=api_key,
                base_url=base_url,
                scope=scope,
                is_active=is_active,
            ))
            db.commit()

        return RedirectResponse(_LIST_URL, status_code=302)

    # ── Edit ──────────────────────────────────────────────────────────────────

    async def _handle_edit(self, request, templates, pk, wizard_url):
        with SessionLocal() as db:
            provider = db.get(AIProvider, pk)
            if not provider:
                return RedirectResponse(_LIST_URL, status_code=302)
            # detach a plain copy of needed attributes
            provider_type = provider.provider_type.value
            provider_data = {
                "id":        provider.id,
                "provider_type": provider_type,
                "base_url":  provider.base_url,
                "scope":     provider.scope,
                "is_active": provider.is_active,
            }

        if request.method == "POST":
            return await self._post_edit(request, templates, pk, provider_type,
                                         provider_data, wizard_url)
        return self._render(request, templates, provider_type, wizard_url,
                            provider=provider_data)

    async def _post_edit(self, request, templates, pk, provider_type,
                         provider_data, wizard_url):
        form     = await request.form()
        api_key  = (form.get("api_key") or "").strip()
        base_url = (form.get("base_url") or "").strip() or None
        scope    = (form.get("scope") or "").strip() or None
        is_active = form.get("is_active") == "on"

        with SessionLocal() as db:
            provider = db.get(AIProvider, pk)
            if api_key:
                provider.api_key = api_key
            provider.base_url  = base_url
            provider.scope     = scope
            provider.is_active = is_active
            if is_active:
                db.query(AIProvider).filter(AIProvider.id != pk).update(
                    {"is_active": False}
                )
            db.commit()

        return RedirectResponse(_LIST_URL, status_code=302)
