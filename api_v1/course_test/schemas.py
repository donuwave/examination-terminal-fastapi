from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api_v1.profile.schemas import ProfileGet
from api_v1.questions.schemas import QuestionGet


class TestBase(BaseModel):
    name: str
    time_limit: int
    pass_percent: int = 60
    max_attempts: int = 2
    retry_delay_minutes: int = 120
    creator_id: int
    creator: ProfileGet


class Test(TestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TestInCourse(Test):
    access_test: bool


class ResultTest(BaseModel):
    text_question: str
    options: List[str]
    correct_answer: str
    student_answer: str


class TestGet(Test):
    questions: Optional[list[QuestionGet]] = []

    @field_validator("questions", mode="before")
    @classmethod
    def flatten_students(cls, value):
        if not value:
            return []
        return [assoc.question for assoc in value]


class TestUpdate(BaseModel):
    """Правка настроек теста. Передаются только изменяемые поля."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    time_limit: Optional[int] = Field(None, ge=1)
    pass_percent: Optional[int] = Field(None, ge=1, le=100)
    max_attempts: Optional[int] = Field(None, ge=1, le=10)
    retry_delay_minutes: Optional[int] = Field(None, ge=0, le=10080)


class TestPlacement(BaseModel):
    test_id: int
    course_id: int
    course_name: str
    section_id: Optional[int] = None
    section_title: Optional[str] = None
