from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.encrypted import EncryptedString


class WebhookSource(Base):
    __tablename__ = "webhook_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Человекочитаемое название, например "Блог WordPress"
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # URL для HTTP POST-запроса (http:// или https://)
    webhook_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    # Опциональный секрет для HMAC-SHA256 подписи (X-Postery-Signature)
    secret: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # Промпты для AI-обработки контента перед публикацией (markdown)
    ai_prompt_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_prompt_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Автоматическая AI-генерация при открытии шага 3 визарда
    auto_generate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __str__(self) -> str:
        return self.name
