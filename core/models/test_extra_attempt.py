from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class TestExtraAttempt(Base):
    """Дополнительные попытки, которые преподаватель выдал студенту по тесту курса."""

    __tablename__ = "test_extra_attempt"
    __table_args__ = (
        UniqueConstraint("course_id", "test_id", "student_id", name="uq_extra_attempt"),
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), nullable=False
    )
    test_id: Mapped[int] = mapped_column(ForeignKey("test.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("profile.id"), nullable=False)
    extra: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
