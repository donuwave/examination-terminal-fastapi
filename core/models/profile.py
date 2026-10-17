from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, CheckConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .role import Role
    from .course_student import CourseStudentAssociation


class Profile(Base):
    email: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    last_name: Mapped[str] = mapped_column(String, nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    gender: Mapped[int] = mapped_column(
        Integer, CheckConstraint("gender IN (1, 2)"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), default=datetime.now
    )
    # Имя файла аватара в uploads/avatars; None — аватара нет.
    avatar: Mapped[str | None] = mapped_column(String, nullable=True)

    role_id: Mapped[int] = mapped_column(ForeignKey("role.id"), nullable=True)
    role: Mapped["Role"] = relationship("Role", lazy="joined")

    @property
    def has_avatar(self) -> bool:
        return self.avatar is not None

    user: Mapped["User"] = relationship(back_populates="profile")
    courses: Mapped[list["CourseStudentAssociation"]] = relationship(
        back_populates="student"
    )
