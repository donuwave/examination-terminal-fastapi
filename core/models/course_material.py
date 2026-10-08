from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models import Base

if TYPE_CHECKING:
    from .course import Course
    from .course_section import CourseSection


class CourseMaterial(Base):
    """Теоретический материал курса: заголовок, текст и прикреплённые файлы."""

    __tablename__ = "course_material"

    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_section.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="materials")
    section: Mapped["CourseSection | None"] = relationship(back_populates="materials")
    files: Mapped[list["MaterialFile"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="MaterialFile.id",
    )


class MaterialFile(Base):
    __tablename__ = "material_file"

    material_id: Mapped[int] = mapped_column(
        ForeignKey("course_material.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)

    material: Mapped["CourseMaterial"] = relationship(back_populates="files")
