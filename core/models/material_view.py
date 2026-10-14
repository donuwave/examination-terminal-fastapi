from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class MaterialView(Base):
    """Студент открыл материал. Нужна аналитике: по ней видно, кто читает, даже если тест ещё не сдан."""

    __tablename__ = "material_view"
    __table_args__ = (UniqueConstraint("student_id", "material_id", name="uq_material_view"),)

    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("course_material.id", ondelete="CASCADE"), nullable=False
    )
    first_viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
