from typing import List

from pydantic import BaseModel, ConfigDict, Field

from api_v1.course_material.schemas import MaterialGet


class SectionTest(BaseModel):
    id: int
    name: str
    time_limit: int
    questions_count: int


class SectionGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    position: int
    materials: List[MaterialGet]
    tests: List[SectionTest]


class SectionTitle(BaseModel):
    title: str = Field(min_length=1, max_length=200)
