from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models import Base

if TYPE_CHECKING:
    from .course import Course
    from .course_material import CourseMaterial


class CourseSection(Base):
    """Раздел курса: материалы по порядку и тест (или тесты) в конце."""

    __tablename__ = "course_section"

    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="sections")
    materials: Mapped[list["CourseMaterial"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="CourseMaterial.id",
    )
