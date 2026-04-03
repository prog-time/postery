from datetime import datetime, timedelta
from typing import Any

import anyio
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin.contrib.sqla import Admin, ModelView
from starlette_admin.views import CustomView, DropDown
from starlette_admin import (
    StringField, IntegerField, BooleanField, DateTimeField, EnumField,
)
from starlette_admin.actions import link_row_action
from starlette_admin.exceptions import FormValidationError

from app.config import SECRET_KEY, TEMPLATES_DIR, STATICS_DIR
from app.database import engine, SessionLocal
from app.models import TelegramSource, VKSource, MAXSource, AdminUser, Role
from app.models import Post, PostChannel, PostStatus, ChannelStatus
from app.models.providers import AIProvider, ProviderType
from app.auth import RoleAuthProvider, SuperadminOnly, EditorAccessMixin
from app.views.posts import PostWizardView
from app.views.post_channel_list import PostChannelListView
from app.views.calendar import CalendarView
from app.views.ai_provider import AIProviderWizardView
from app.views.telegram_source import TelegramSourceWizardView
from app.views.vk_source import VKSourceWizardView
from app.views.max_source import MAXSourceWizardView
from app.fields import TokenField, PasswordField, TranslatedEnumField
from app.auth import hash_password


# ── AI провайдеры: вспомогательные функции ──────────────────────────────────

def _do_deactivate_others(obj_id: int) -> None:
    """Деактивирует все AI-провайдеры, кроме текущего."""
    with SessionLocal() as db:
        db.query(AIProvider).filter(AIProvider.id != obj_id).update({"is_active": False})
        db.commit()


# ── Dashboard ────────────────────────────────────────────────────────────────

class DashboardView(CustomView):
    def __init__(self, **kwargs):
        kwargs.setdefault("label", "Аналитика")
        kwargs.setdefault("icon", "fa-solid fa-chart-pie")
        super().__init__(
            path="/",
            template_path="dashboard.html",
            add_to_menu=True,
            **kwargs,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        with SessionLocal() as db:
            posts_total     = db.query(Post).count()
            posts_draft     = db.query(Post).filter(Post.status == PostStatus.DRAFT).count()
            posts_ready     = db.query(Post).filter(Post.status == PostStatus.READY).count()
            posts_published = db.query(Post).filter(Post.status == PostStatus.PUBLISHED).count()

            ch_pending   = db.query(PostChannel).filter(PostChannel.status == ChannelStatus.PENDING).count()
            _cutoff = datetime.now() - timedelta(days=7)
            ch_published = (
                db.query(PostChannel)
                .filter(
                    PostChannel.status == ChannelStatus.PUBLISHED,
                    PostChannel.published_at >= _cutoff,
                )
                .count()
            )
            ch_failed    = db.query(PostChannel).filter(PostChannel.status == ChannelStatus.FAILED).count()

            tg_count  = db.query(TelegramSource).count()
            vk_count  = db.query(VKSource).count()
            max_count = db.query(MAXSource).count()

            recent = [
                {
                    "source_type": ch.source_type,
                    "title":       ch.effective_title,
                    "published_at": ch.published_at,
                }
                for ch in (
                    db.query(PostChannel)
                    .filter(PostChannel.status == ChannelStatus.PUBLISHED)
                    .order_by(PostChannel.published_at.desc())
                    .limit(7)
                    .all()
                )
            ]
            failed = [
                {
                    "source_type":   ch.source_type,
                    "title":         ch.effective_title,
                    "error_message": ch.error_message,
                }
                for ch in (
                    db.query(PostChannel)
                    .filter(PostChannel.status == ChannelStatus.FAILED)
                    .order_by(PostChannel.id.desc())
                    .limit(7)
                    .all()
                )
            ]
            active_provider = (
                db.query(AIProvider).filter(AIProvider.is_active.is_(True)).first()
            )
            active_provider_name = str(active_provider) if active_provider else None

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "posts_total":     posts_total,
                "posts_draft":     posts_draft,
                "posts_ready":     posts_ready,
                "posts_published": posts_published,
                "ch_pending":      ch_pending,
                "ch_published":    ch_published,
                "ch_failed":       ch_failed,
                "tg_count":        tg_count,
                "vk_count":        vk_count,
                "max_count":       max_count,
                "recent":          recent,
                "failed":          failed,
                "active_provider": active_provider_name,
            },
        )


# ── Источники публикации ─────────────────────────────────────────────────────

class TelegramSourceView(EditorAccessMixin, ModelView):
    icon = "fa-brands fa-telegram"
    label = "Telegram"
    name = "telegram_source"
    pk_attr = "id"

    def can_view_details(self, request) -> bool:
        return False

    def can_create(self, request) -> bool:
        return False

    @link_row_action(
        name="edit",
        text="Редактировать",
        icon_class="fa-solid fa-pen-to-square",
    )
    def row_action_2_edit(self, request: Request, pk) -> str:
        return f"/admin/telegram-source/wizard?pk={pk}"

    fields = [
        IntegerField("id", label="ID", read_only=True, exclude_from_create=True),
        StringField("name", label="Название",
                    help_text="Понятное имя источника, например: Новостной канал"),
        TokenField("bot_token", label="Bot Token",
                   help_text="Токен бота от @BotFather"),
        StringField("chat_id", label="Chat ID",
                    help_text="@username канала или числовой ID (например -1001234567890)"),
        IntegerField("thread_id", label="Thread ID",
                     help_text="ID темы для групп-форумов (необязательно)", required=False),
        BooleanField("is_active", label="Активен"),
        DateTimeField("created_at", label="Создан", read_only=True,
                      exclude_from_create=True, exclude_from_edit=True,
                      output_format="%d.%m.%Y %H:%M"),
    ]

    column_list = ["id", "name", "chat_id", "is_active", "created_at"]
    sortable_fields = ["id", "name", "is_active", "created_at"]
    searchable_fields = ["name", "chat_id"]
    page_size = 20
    page_size_options = [10, 20, 50, -1]


class VKSourceView(EditorAccessMixin, ModelView):
    icon = "fa-brands fa-vk"
    label = "ВКонтакте"
    name = "vk_source"
    pk_attr = "id"

    def can_view_details(self, request) -> bool:
        return False

    def can_create(self, request) -> bool:
        return False

    @link_row_action(
        name="edit",
        text="Редактировать",
        icon_class="fa-solid fa-pen-to-square",
    )
    def row_action_2_edit(self, request: Request, pk) -> str:
        return f"/admin/vk-source/wizard?pk={pk}"

    fields = [
        IntegerField("id", label="ID", read_only=True, exclude_from_create=True),
        StringField("name", label="Название",
                    help_text="Понятное имя, например: Новостная группа"),
        TokenField("access_token", label="Access Token",
                   help_text="Токен сообщества (только текст) или user access token администратора (текст + фото). "
                             "Права: wall, photos, offline"),
        IntegerField("group_id", label="Group ID",
                     help_text="Числовой ID группы (без минуса), например 123456789"),
        BooleanField("is_active", label="Активен"),
        DateTimeField("created_at", label="Создан", read_only=True,
                      exclude_from_create=True, exclude_from_edit=True,
                      output_format="%d.%m.%Y %H:%M"),
    ]

    column_list = ["id", "name", "group_id", "is_active", "created_at"]
    sortable_fields = ["id", "name", "is_active", "created_at"]
    searchable_fields = ["name"]
    page_size = 20


class MAXSourceView(EditorAccessMixin, ModelView):
    icon = "fa-solid fa-message"
    label = "MAX Мессенджер"
    name = "max_source"
    pk_attr = "id"

    def can_view_details(self, request) -> bool:
        return False

    def can_create(self, request) -> bool:
        return False

    @link_row_action(
        name="edit",
        text="Редактировать",
        icon_class="fa-solid fa-pen-to-square",
    )
    def row_action_2_edit(self, request: Request, pk) -> str:
        return f"/admin/max-source/wizard?pk={pk}"

    fields = [
        IntegerField("id", label="ID", read_only=True, exclude_from_create=True),
        StringField("name", label="Название",
                    help_text="Понятное имя, например: Новостной канал MAX"),
        TokenField("bot_token", label="Bot Token",
                   help_text="Токен бота из botapi.max.ru"),
        StringField("chat_id", label="Chat ID",
                    help_text="Числовой ID канала/чата"),
        BooleanField("is_active", label="Активен"),
        DateTimeField("created_at", label="Создан", read_only=True,
                      exclude_from_create=True, exclude_from_edit=True,
                      output_format="%d.%m.%Y %H:%M"),
    ]

    column_list = ["id", "name", "chat_id", "is_active", "created_at"]
    sortable_fields = ["id", "name", "is_active", "created_at"]
    searchable_fields = ["name", "chat_id"]
    page_size = 20


# ── AI провайдеры ────────────────────────────────────────────────────────────

class AIProviderView(SuperadminOnly, ModelView):
    icon = "fa-solid fa-robot"
    label = "AI провайдеры"
    name = "ai_provider"
    identity = "ai-provider"
    pk_attr = "id"

    def can_view_details(self, request: Request) -> bool:
        return False

    @link_row_action(
        name="edit",
        text="Редактировать",
        icon_class="fa-solid fa-pen-to-square",
    )
    def row_action_2_edit(self, request: Request, pk) -> str:
        return f"/admin/ai-provider/wizard?pk={pk}"

    fields = [
        IntegerField("id", label="ID", read_only=True, exclude_from_create=True),
        EnumField("provider_type", label="Провайдер", enum=ProviderType,
                  choices=[("openai", "OpenAI"), ("gigachat", "GigaChat")]),
        TokenField("api_key", label="API Key / Authorization Key",
                   help_text="OpenAI: секретный ключ (sk-...) · GigaChat: Authorization key из личного кабинета"),
        StringField("base_url", label="Base URL", required=False,
                    help_text="Только для OpenAI. Оставьте пустым для стандартного endpoint. "
                              "Для Azure/прокси: https://..."),
        StringField("scope", label="Scope", required=False,
                    help_text="Только для GigaChat: GIGACHAT_API_PERS (физлицо) или GIGACHAT_API_CORP (корпоративный)"),
        BooleanField("is_active", label="Активен"),
        DateTimeField("created_at", label="Создан", read_only=True,
                      exclude_from_create=True, exclude_from_edit=True,
                      output_format="%d.%m.%Y %H:%M"),
    ]

    column_list = ["id", "provider_type", "api_key", "is_active", "created_at"]
    sortable_fields = ["id", "provider_type", "is_active", "created_at"]
    page_size = 20

    async def before_create(self, request: Request, data: dict, obj: Any) -> None:
        with SessionLocal() as db:
            exists = db.query(AIProvider).filter_by(
                provider_type=obj.provider_type
            ).first()
        if exists:
            raise FormValidationError(
                {"provider_type": "Провайдер этого типа уже добавлен"}
            )

    async def after_create(self, request: Request, obj: Any) -> None:
        if obj.is_active:
            await anyio.to_thread.run_sync(lambda: _do_deactivate_others(obj.id))

    async def after_edit(self, request: Request, obj: Any) -> None:
        if obj.is_active:
            await anyio.to_thread.run_sync(lambda: _do_deactivate_others(obj.id))


# ── Управление (только superadmin) ──────────────────────────────────────────

class AdminUserView(SuperadminOnly, ModelView):
    icon = "fa fa-shield-halved"
    label = "Пользователи"
    name = "admin_user"
    pk_attr = "id"

    fields = [
        IntegerField("id", label="ID", read_only=True, exclude_from_create=True),
        StringField("username", label="Логин"),
        PasswordField("password_hash", label="Пароль", exclude_from_list=True,
                      help_text="Оставьте пустым, чтобы не менять пароль"),
        TranslatedEnumField("role", label="Роль", enum=Role,
                            choices=[("superadmin", "Суперадмин"), ("editor", "Редактор")]),
        BooleanField("is_active", label="Активен"),
        DateTimeField("created_at", label="Создан", read_only=True,
                      exclude_from_create=True, output_format="%d.%m.%Y %H:%M"),
    ]

    column_list = ["id", "username", "role", "is_active", "created_at"]
    sortable_fields = ["id", "username", "role", "is_active"]
    searchable_fields = ["username"]

    async def on_model_change(self, data: dict, model: Any, is_created: bool, request: Request) -> None:
        password = (data.get("password_hash") or "").strip()
        if password:
            data["password_hash"] = hash_password(password)
        elif not is_created:
            data["password_hash"] = model.password_hash


# ── Фабрика Admin ────────────────────────────────────────────────────────────

def create_admin() -> Admin:
    admin = Admin(
        engine,
        title="Postery",
        base_url="/admin",
        route_name="admin",
        templates_dir=TEMPLATES_DIR,
        statics_dir=STATICS_DIR,
        favicon_url="/admin/statics/favicon.svg",
        index_view=DashboardView(),
        auth_provider=RoleAuthProvider(),
        middlewares=[
            Middleware(SessionMiddleware, secret_key=SECRET_KEY),
        ],
    )

    # Посты
    admin.add_view(PostChannelListView(label="Все посты", icon="fa-solid fa-newspaper"))
    admin.add_view(PostWizardView(label="Создать пост", add_to_menu=False))
    admin.add_view(CalendarView(label="Календарь", icon="fa-solid fa-calendar-days"))

    # Источники
    admin.add_view(
        DropDown(
            label="Источники",
            icon="fa fa-share-nodes",
            views=[
                TelegramSourceView(TelegramSource),
                VKSourceView(VKSource),
                MAXSourceView(MAXSource),
            ],
        )
    )
    admin.add_view(TelegramSourceWizardView(label="Добавить Telegram-источник"))
    admin.add_view(VKSourceWizardView(label="Добавить VK-источник"))
    admin.add_view(MAXSourceWizardView(label="Добавить MAX-источник"))

    # AI провайдеры
    admin.add_view(AIProviderView(AIProvider, icon="fa-solid fa-robot"))
    admin.add_view(AIProviderWizardView(label="Добавить провайдера"))

    # Управление
    admin.add_view(
        DropDown(
            label="Управление",
            icon="fa fa-gear",
            views=[
                AdminUserView(AdminUser),
            ],
        )
    )

    return admin
