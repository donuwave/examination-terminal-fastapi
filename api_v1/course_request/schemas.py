from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class PersonBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class CourseBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    teacher: PersonBrief


class RequestGet(BaseModel):
    """Заявка или приглашение. Кому что показывать, решают эндпоинты."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    created_at: datetime
    student: PersonBrief
    course: CourseBrief


class InviteIn(BaseModel):
    email: EmailStr
