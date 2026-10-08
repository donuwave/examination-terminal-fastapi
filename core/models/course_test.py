from typing import TYPE_CHECKING

from sqlalchemy import UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models import Base

if TYPE_CHECKING:
    from .course import Course
    from .test import Test


class CourseTestAssociation(Base):
    __tablename__ = "course_test_association"
    __table_args = UniqueConstraint(
        "course_id", "test_id", name="id_unique_course_test"
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    test_id: Mapped[int] = mapped_column(ForeignKey("test.id"))
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_section.id", ondelete="SET NULL"), nullable=True, index=True
    )

    test: Mapped["Test"] = relationship(back_populates="courses")
    course: Mapped["Course"] = relationship(back_populates="tests")
