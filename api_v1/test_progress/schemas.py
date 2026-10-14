from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict

from api_v1.course_test.schemas import Test

# new — не начинал, in_progress — попытка идёт, passed — сдан, retry — можно пересдать,
# cooldown — ждёт паузу перед пересдачей, waiting — попытки закончились, решает преподаватель.
TestStatus = Literal["new", "in_progress", "passed", "retry", "cooldown", "waiting"]


class TestState(BaseModel):
    """Где студент находится по тесту курса."""

    status: TestStatus
    attempts_used: int
    attempts_allowed: int
    best_percent: Optional[int] = None
    active_attempt_id: Optional[int] = None
    last_attempt_id: Optional[int] = None
    next_attempt_at: Optional[int] = None


class TestProgressResultTest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text_question: str
    kind: str = "single"
    options: List[str]
    # Правильные ответы открываются, когда тест сдан или попытки закончились.
    correct_answer: Optional[str] = None
    correct_answers: Optional[List[str]] = None
    student_answer: Optional[str] = None
    student_answers: Optional[List[str]] = None
    # Верен ли ответ: заполняется после завершения, даже если сам правильный ответ скрыт.
    is_correct: Optional[bool] = None


class TestProgressTest(BaseModel):
    """Одна попытка прохождения теста."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    participant_id: int
    test_id: int
    course_id: int
    status: int
    attempt_no: int = 1
    attempt_date: Optional[int] = None
    finished_at: Optional[int] = None
    count_current_answer: Optional[int] = None
    passed: Optional[bool] = None
    created_at: datetime
    timelimit: int
    test: Test
    result_test: List[TestProgressResultTest]
    # Сколько секунд осталось, пока попытка идёт.
    remaining_time: Optional[int] = None
    # Состояние студента по тесту (в списках не заполняется).
    state: Optional[TestState] = None


class AnswerIn(BaseModel):
    """Ответ студента на один вопрос. Правильность считает сервер."""

    id: int
    student_answer: Optional[str] = None
    # Для вопросов с несколькими ответами.
    student_answers: Optional[List[str]] = None


class StartIn(BaseModel):
    course_id: int
    test_id: int


class GrantIn(BaseModel):
    course_id: int
    test_id: int
    student_id: int


class StudentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TestResultRow(BaseModel):
    """Строка результатов теста для преподавателя: один студент курса."""

    student: StudentBrief
    status: TestStatus
    attempts_used: int
    attempts_allowed: int
    best_percent: Optional[int] = None
    last_attempt_id: Optional[int] = None
    last_finished_at: Optional[int] = None


class AttemptStats(BaseModel):
    finished: int
    passed_tests: int
