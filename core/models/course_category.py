from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class CourseCategory(Base):
    """Справочник типов курсов: математика, программирование и т.д."""

    __tablename__ = "course_category"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
