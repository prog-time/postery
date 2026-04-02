import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.encrypted import EncryptedString


class GigaChatScope(str, enum.Enum):
    PERSONAL = "GIGACHAT_API_PERS"
    CORPORATE = "GIGACHAT_API_CORP"


class GigaChatProvider(Base):
    __tablename__ = "gigachat_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Base64-ключ из личного кабинета GigaChat (хранится зашифрованным)
    credentials: Mapped[str] = mapped_column(EncryptedString, nullable=False)

    scope: Mapped[str] = mapped_column(
        String(64), default="GIGACHAT_API_PERS", nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __str__(self) -> str:
        return "GigaChat"
