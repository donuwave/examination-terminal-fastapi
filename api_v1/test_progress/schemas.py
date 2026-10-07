from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from api_v1.course_test.schemas import Test


class TestProgressResultTest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text_question: str
    options: List[str]
    # Пока тест идёт, правильные ответы не отдаём.
    correct_answer: Optional[str] = None
    student_answer: Optional[str] = None


class TestProgressTest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participant_id: int
    test_id: int
    course_id: int
    status: int
    attempt_date: Optional[int] = None
    count_current_answer: Optional[int] = None
    created_at: datetime
    deadline_date: int
    timelimit: int
    test: Test
    result_test: List[TestProgressResultTest]
    # Сколько секунд осталось, пока тест идёт (статус 2).
    remaining_time: Optional[int] = None


class AnswerIn(BaseModel):
    """Ответ студента на один вопрос. Правильность считает сервер."""

    id: int
    student_answer: Optional[str] = None
