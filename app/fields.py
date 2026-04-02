from dataclasses import dataclass, field
from typing import Any

from starlette.requests import Request
from starlette_admin.fields import StringField, EnumField
from starlette_admin._types import RequestAction

from app.crypto import mask


@dataclass
class TokenField(StringField):
    """
    Поле для хранения чувствительных токенов:
    - в списке и детальном просмотре — маскированное значение (••••••xxxx)
    - в форме редактирования — password-input (символы скрыты)
    - в форме создания — пустой password-input
    """
    input_type: str = "password"
    placeholder: str = "Введите токен"

    async def serialize_value(
        self, request: Request, value: Any, action: RequestAction
    ) -> Any:
        if not value:
            return ""
        if action in (RequestAction.LIST, RequestAction.DETAIL):
            return mask(str(value))
        # EDIT / CREATE — передаём реальное значение; браузер скроет его за точками
        return str(value)


@dataclass
class TranslatedEnumField(EnumField):
    """EnumField, отображающий человекочитаемые подписи из choices в списке и деталях."""

    async def serialize_value(
        self, request: Request, value: Any, action: RequestAction
    ) -> Any:
        if action in (RequestAction.LIST, RequestAction.DETAIL):
            lookup = dict(self.choices) if self.choices else {}
            raw = value.value if hasattr(value, "value") else str(value)
            return lookup.get(raw, raw)
        return await super().serialize_value(request, value, action)


@dataclass
class PasswordField(StringField):
    """
    Поле для смены пароля:
    - всегда отображается пустым (не показывает текущий хэш)
    - если оставить пустым при редактировании — пароль не меняется
    """
    input_type: str = "password"
    placeholder: str = "Введите новый пароль"

    async def serialize_value(
        self, request: Request, value: Any, action: RequestAction
    ) -> Any:
        return ""
