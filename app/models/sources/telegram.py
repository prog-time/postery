from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.encrypted import EncryptedString


class TelegramSource(Base):
    __tablename__ = "telegram_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Человекочитаемое название, например "Новостной канал"
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Токен бота, полученный от @BotFather (хранится зашифрованным)
    bot_token: Mapped[str] = mapped_column(EncryptedString, nullable=False)

    # ID чата или username (@mychannel / -1001234567890)
    chat_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # ID темы в группе-форуме (необязательно)
    thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Промпты для AI-обработки контента перед публикацией (markdown)
    ai_prompt_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_prompt_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __str__(self) -> str:
        return self.name
