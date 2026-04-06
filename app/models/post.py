import enum
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class PostStatus(str, enum.Enum):
    DRAFT = "draft"          # шаг 1-2 не завершён
    READY = "ready"          # все источники настроены, готов к публикации
    PUBLISHED = "published"  # опубликован


class ChannelStatus(str, enum.Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(512), nullable=True)  # через запятую
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, native_enum=False), default=PostStatus.DRAFT, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    images: Mapped[list["PostImage"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostImage.order",
    )
    channels: Mapped[list["PostChannel"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
    )

    def __str__(self) -> str:
        return self.title


class PostImage(Base):
    __tablename__ = "post_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    post: Mapped["Post"] = relationship(back_populates="images")


class PostChannel(Base):
    """Версия поста под конкретный источник публикации."""
    __tablename__ = "post_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)

    source_type: Mapped[str] = mapped_column(String(64), nullable=False)  # "telegram", "vk", ...
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Переопределения — если None, используется значение из Post
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[ChannelStatus] = mapped_column(
        Enum(ChannelStatus, native_enum=False), default=ChannelStatus.PENDING, nullable=False
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    post: Mapped["Post"] = relationship(back_populates="channels")

    @property
    def effective_title(self) -> str:
        return self.title or self.post.title

    @property
    def effective_description(self) -> str | None:
        return self.description or self.post.description
