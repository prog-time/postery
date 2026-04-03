import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.encrypted import EncryptedString


class ProviderType(str, enum.Enum):
    OPENAI   = "openai"
    GIGACHAT = "gigachat"


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType), nullable=False
    )

    # Основной секрет: API key (OpenAI) или Authorization key (GigaChat)
    api_key: Mapped[str] = mapped_column(EncryptedString, nullable=False)

    # Только для OpenAI: кастомный endpoint (Azure, прокси и т.д.)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Только для GigaChat: GIGACHAT_API_PERS или GIGACHAT_API_CORP
    scope: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Базовый системный промпт — применяется ко всем запросам генерации.
    # Включается перед source/custom prompt через двойной перенос строки.
    # Если пустой — ведёт себя как раньше (нет глобальной инструкции).
    base_prompt: Mapped[str | None] = mapped_column(String, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __str__(self) -> str:
        labels = {ProviderType.OPENAI: "OpenAI", ProviderType.GIGACHAT: "GigaChat"}
        return labels.get(self.provider_type, "AI Provider")
