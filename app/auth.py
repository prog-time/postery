import bcrypt
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.exceptions import FormValidationError, LoginFailed

from app.database import SessionLocal
from app.models.admin_user import AdminUser as AdminUserModel, Role


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


class RoleAuthProvider(AuthProvider):
    """
    Сессионная аутентификация с ролями.
    В request.state.user хранится объект AdminUserModel.
    """

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        if not username or not password:
            raise FormValidationError({"username": "Введите логин и пароль"})

        with SessionLocal() as db:
            user = (
                db.query(AdminUserModel)
                .filter_by(username=username, is_active=True)
                .first()
            )

        if not user or not verify_password(password, user.password_hash):
            raise LoginFailed("Неверный логин или пароль")

        request.session.update({"user_id": user.id, "role": user.role.value})
        return response

    async def is_authenticated(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        if not user_id:
            return False

        with SessionLocal() as db:
            user = db.get(AdminUserModel, user_id)

        if not user or not user.is_active:
            return False

        request.state.user = user
        return True

    def get_admin_user(self, request: Request) -> AdminUser | None:
        user = getattr(request.state, "user", None)
        if not user:
            return None
        return AdminUser(username=user.username, photo_url=None)

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response


# ── Миксин для ролевого контроля доступа ────────────────────────────────────

class SuperadminOnly:
    """View доступен только superadmin-ам."""
    export_types: list = []
    column_visibility: bool = False
    search_builder: bool = False

    def is_accessible(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return user is not None and user.role == Role.SUPERADMIN

    def inaccessible_callback(self, request: Request) -> Response:
        from starlette.responses import RedirectResponse
        return RedirectResponse(request.url_for("admin:index"), status_code=302)


class EditorAccessMixin:
    """
    Доступен superadmin и editor.
    editor не может удалять записи.
    """
    export_types: list = []
    column_visibility: bool = False
    search_builder: bool = False

    def is_accessible(self, request: Request) -> bool:
        return getattr(request.state, "user", None) is not None

    def can_delete(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return user is not None and user.role == Role.SUPERADMIN

    def can_create(self, request: Request) -> bool:
        return getattr(request.state, "user", None) is not None

    def can_edit(self, request: Request) -> bool:
        return getattr(request.state, "user", None) is not None
