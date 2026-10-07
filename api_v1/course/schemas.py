from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from api_v1.course_test.schemas import Test, TestInCourse
from api_v1.profile.schemas import ProfileGet


class CategoryGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CourseBase(BaseModel):
    id: int
    name: str
    description: str
    teacher_id: int
    teacher: ProfileGet
    category: Optional[CategoryGet] = None


class Course(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class CourseGet(Course):
    students: Optional[list[ProfileGet]]
    tests: Optional[list[Test]]

    @field_validator("students", mode="before")
    @classmethod
    def flatten_students(cls, value):
        if not value:
            return []
        return [assoc.student for assoc in value]

    @field_validator("tests", mode="before")
    @classmethod
    def flatten_tests(cls, value):
        if not value:
            return []
        return [assoc.test for assoc in value]


class CourseItemGet(CourseGet):
    tests: Optional[list[TestInCourse]]


class CourseUpdatePartial(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None


class CatalogCourse(BaseModel):
    """Курс в общем каталоге. Без списка студентов: чужие данные не раскрываем."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    category: Optional[CategoryGet] = None
    teacher: ProfileGet
    students_count: int
    tests_count: int
    is_member: bool
