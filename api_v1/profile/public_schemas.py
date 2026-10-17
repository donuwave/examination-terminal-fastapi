from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CategoryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class PublicProfile(BaseModel):
    """Профиль для постороннего: без почты и личных данных."""

    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    has_avatar: bool = False
    # Unix-секунды регистрации.
    created_at: int
    # Возраст и пол: видны владельцу и преподавателю студента.
    age: Optional[int] = None
    gender: Optional[int] = None


class PrivateProfile(PublicProfile):
    """Профиль, где можно показать почту: свой или студент своего курса."""

    email: str


class ProfileCourse(BaseModel):
    id: int
    name: str
    category: Optional[CategoryBrief] = None
    enrollment: str
    students_count: int
    tests_count: int
    # Может ли смотрящий открыть курс: он его преподаватель или студент курса.
    is_member: bool
    # Прогресс есть только там, где его вправе видеть смотрящий.
    sections_passed: Optional[int] = None
    sections_total: Optional[int] = None
    avg_best_percent: Optional[int] = None
    # Последняя попытка или просмотр материала, unix-секунды. Видно тем же, кому виден прогресс.
    last_activity_at: Optional[int] = None


class ProfileCourses(BaseModel):
    courses: List[ProfileCourse]
    total: int
