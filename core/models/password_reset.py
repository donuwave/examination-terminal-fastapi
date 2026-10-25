from datetime import datetime

from sqlalchemy import ForeignKey, Integer, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PasswordReset(Base):
    """Код для сброса пароля. Сам код не хранится, только его хэш."""

    __tablename__ = "password_reset"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    # Сколько раз код вводили неверно: после лимита код сгорает.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), default=datetime.utcnow
    )
