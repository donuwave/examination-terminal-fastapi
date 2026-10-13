from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models import Base

if TYPE_CHECKING:
    from .course import Course
    from .profile import Profile

APPLICATION, INVITATION = "application", "invitation"
PENDING, ACCEPTED, DECLINED, CANCELLED = "pending", "accepted", "declined", "cancelled"


class CourseRequest(Base):
    """Заявка студента на курс или приглашение преподавателя студенту.

    Пока запись ждёт решения (`pending`), для пары «курс и студент» может быть только одна.
    """

    __tablename__ = "course_request"
    __table_args__ = (
        Index(
            "uq_course_request_pending",
            "course_id",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default=PENDING, server_default=PENDING)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=datetime.now)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)

    course: Mapped["Course"] = relationship("Course", lazy="joined")
    student: Mapped["Profile"] = relationship("Profile", lazy="joined")
