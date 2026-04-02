from sqlalchemy import types
from app.crypto import encrypt, decrypt


class EncryptedString(types.TypeDecorator):
    """
    Хранит строку в БД в зашифрованном виде (Fernet).
    Приложение всегда работает с расшифрованным значением.
    """
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Перед записью в БД — зашифровать."""
        if value is not None:
            return encrypt(value)
        return value

    def process_result_value(self, value, dialect):
        """После чтения из БД — расшифровать."""
        if value is not None:
            try:
                return decrypt(value)
            except Exception:
                # Значение ещё не зашифровано (legacy plain-text) — вернуть как есть
                return value
        return value
