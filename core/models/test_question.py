from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from core.models import Base

if TYPE_CHECKING:
    from .test import Test
    from .question import Question


class TestQuestionAssociation(Base):
    __tablename__ = "test_question_association"
    __table_args = UniqueConstraint(
        "question_id", "test_id", name="id_unique_question_test"
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"))
    test_id: Mapped[int] = mapped_column(ForeignKey("test.id"))
    # Порядок вопроса в редакторе. Студенту вопросы показываются вперемешку.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    test: Mapped["Test"] = relationship(back_populates="questions")
    question: Mapped["Question"] = relationship(back_populates="tests")
