from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from api_v1.course_material.schemas import MaterialGet
from api_v1.test_progress.schemas import TestState


class SectionTest(BaseModel):
    id: int
    name: str
    time_limit: int
    questions_count: int
    pass_percent: int
    max_attempts: int
    retry_delay_minutes: int
    # Состояние студента по тесту; у преподавателя не заполняется.
    state: Optional[TestState] = None


class SectionGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    position: int
    materials: List[MaterialGet]
    tests: List[SectionTest]
    materials_count: int
    tests_count: int
    # Для студента: закрыт ли раздел, пока не сданы тесты предыдущего.
    locked: bool = False
    status: Optional[Literal["open", "passed", "locked"]] = None


class SectionTitle(BaseModel):
    title: str = Field(min_length=1, max_length=200)
