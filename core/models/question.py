from sqlalchemy import ARRAY, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from core.models import Base

if TYPE_CHECKING:
    from .test_question import TestQuestionAssociation


class Question(Base):
    text_question: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    correct_answer: Mapped[str] = mapped_column(String, nullable=False)
    # single: один верный вариант; multiple: несколько верных; text: ответ вводится текстом.
    kind: Mapped[str] = mapped_column(String, nullable=False, default="single", server_default="single")
    # Все верные ответы: у single один, у multiple несколько, у text допустимые написания.
    correct_answers: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )

    tests: Mapped[list["TestQuestionAssociation"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )
