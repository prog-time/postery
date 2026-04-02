from dataclasses import dataclass
from typing import Any

from starlette.requests import Request
from starlette_admin.fields import StringField
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
