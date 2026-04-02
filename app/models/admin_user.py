import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Role(str, enum.Enum):
    SUPERADMIN = "superadmin"  # полный доступ ко всему
    EDITOR = "editor"          # только просмотр и редактирование источников


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.EDITOR, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"
