from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.encrypted import EncryptedString


class MAXSource(Base):
    __tablename__ = "max_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Токен бота (хранится зашифрованным)
    bot_token: Mapped[str] = mapped_column(EncryptedString, nullable=False)

    # Числовой ID канала/чата
    chat_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # Промпты для AI-обработки контента перед публикацией (markdown)
    ai_prompt_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_prompt_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Автоматическая AI-генерация при открытии шага 3 визарда (TASK-008)
    auto_generate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __str__(self) -> str:
        return self.name
