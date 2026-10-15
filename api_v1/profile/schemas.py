from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from api_v1.role.schemas import Role


class ProfileBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[int] = Field(
        None, description="Пол: 2 - мужской, 1 - женский", ge=1, le=2
    )


class Profile(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    has_avatar: bool = False


class ProfileUpdate(BaseModel):
    show_details: Optional[bool] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[int] = Field(
        None, description="Пол: 2 - мужской, 1 - женский", ge=1, le=2
    )


class ProfileGet(Profile):
    role: Role
    role_id: int
    created_at: datetime
    show_details: bool = False
