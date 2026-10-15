from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models import Base

if TYPE_CHECKING:
    from .profile import Profile


class Notification(Base):
    """Уведомление пользователю. Текст готов к показу: так же его потом можно отправить письмом."""

    __tablename__ = "notification"
    __table_args__ = (Index("ix_notification_user_created", "user_id", "created_at"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    # Путь внутри приложения, куда ведёт уведомление.
    link: Mapped[str | None] = mapped_column(String, nullable=True)
    # Кто совершил действие, если в тексте названо его имя: по нему в интерфейсе делается ссылка на профиль.
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("profile.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped["Profile | None"] = relationship("Profile", foreign_keys=[actor_id], lazy="joined")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=datetime.now)
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)


    @property
    def actor_name(self) -> str | None:
        if self.actor is None:
            return None
        full = " ".join(part for part in (self.actor.first_name, self.actor.last_name) if part)
        return full or self.actor.email


class NotificationPref(Base):
    """Какие уведомления пользователь отключил или включил. Нет записи — действует значение по умолчанию (включено)."""

    __tablename__ = "notification_pref"
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_notification_pref"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
