"""
Симметричное шифрование чувствительных строк (Fernet / AES-128-CBC + HMAC).
Ключ выводится из SECRET_KEY через SHA-256.
"""
import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    from app.config import SECRET_KEY
    digest = hashlib.sha256(SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt(value: str) -> str:
    """Зашифровать строку → base64-токен."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Расшифровать base64-токен → строку."""
    return _fernet().decrypt(value.encode()).decode()


def mask(value: str, visible: int = 4) -> str:
    """Показать последние `visible` символов, остальное — буллеты."""
    if not value:
        return ""
    suffix = value[-visible:] if len(value) > visible else value
    return "***" + suffix
