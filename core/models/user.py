from datetime import datetime

from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

from .mixins import ProfileRelationMixin


class User(ProfileRelationMixin, Base):
    _profile_back_populates = "user"
    _profile_id_unique = True

    email: Mapped[str] = mapped_column(String, nullable=False)
    password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Когда пароль менялся последний раз: токены, выданные раньше, недействительны для продления сессии.
    password_changed_at: Mapped[datetime | None] = mapped_column(nullable=True)
