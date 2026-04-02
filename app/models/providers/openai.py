from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.encrypted import EncryptedString


class OpenAIProvider(Base):
    __tablename__ = "openai_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    api_key: Mapped[str] = mapped_column(EncryptedString, nullable=False)

    # Опционально: кастомный endpoint (Azure, прокси и т.д.)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __str__(self) -> str:
        return "OpenAI"
