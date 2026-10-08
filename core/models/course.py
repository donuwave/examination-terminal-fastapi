from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models import Base


if TYPE_CHECKING:
    from .profile import Profile
    from .course_student import CourseStudentAssociation
    from .course_test import CourseTestAssociation
    from .course_material import CourseMaterial
    from .course_category import CourseCategory
    from .course_section import CourseSection


class Course(Base):
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_category.id"), nullable=True, index=True
    )
    category: Mapped["CourseCategory | None"] = relationship(
        "CourseCategory", lazy="joined"
    )

    teacher_id: Mapped[int] = mapped_column(ForeignKey("profile.id"), nullable=False)
    teacher: Mapped["Profile"] = relationship("Profile", lazy="joined")

    students: Mapped[list["CourseStudentAssociation"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    tests: Mapped[list["CourseTestAssociation"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    materials: Mapped[list["CourseMaterial"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )
    sections: Mapped[list["CourseSection"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CourseSection.position",
    )
