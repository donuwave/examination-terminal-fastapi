from typing import List, Literal, Optional

from pydantic import BaseModel

from api_v1.test_progress.schemas import StudentBrief

# finished — прошёл все разделы, active — занимается, stalled — давно не было попыток,
# new — ещё не начинал.
StudentStatus = Literal["finished", "active", "stalled", "new"]


class SectionStat(BaseModel):
    id: int
    title: str
    position: int
    tests_count: int
    # Сколько студентов дошли до раздела (он открыт или сдан) и сколько его сдали.
    reached: int
    passed: int


class TestStat(BaseModel):
    test_id: int
    name: str
    section_title: Optional[str] = None
    students_total: int
    passed: int
    waiting: int
    attempted: int
    avg_best_percent: Optional[int] = None
    avg_attempts_to_pass: Optional[float] = None


class StudentStat(BaseModel):
    student: StudentBrief
    sections_passed: int
    sections_total: int
    avg_best_percent: Optional[int] = None
    last_activity_at: Optional[int] = None
    status: StudentStatus


class CourseAnalytics(BaseModel):
    students_total: int
    finished_total: int
    stalled_total: int
    avg_progress_percent: int
    sections: List[SectionStat]
    tests: List[TestStat]
    students: List[StudentStat]


class QuestionStat(BaseModel):
    text: str
    answered: int
    correct: int
    correct_percent: int
    # Самый частый неверный ответ и сколько раз его выбрали.
    top_wrong: Optional[str] = None
    top_wrong_count: int = 0


class Bucket(BaseModel):
    label: str
    count: int


class TestAnalytics(BaseModel):
    test_id: int
    name: str
    attempts_total: int
    students_attempted: int
    pass_rate_percent: Optional[int] = None
    avg_percent: Optional[int] = None
    avg_duration_seconds: Optional[int] = None
    timed_out: int
    questions: List[QuestionStat]
    distribution: List[Bucket]
