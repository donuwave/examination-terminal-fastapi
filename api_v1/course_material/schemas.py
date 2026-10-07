from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MaterialFileGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    size: int


class MaterialGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    description: str
    created_at: datetime
    files: list[MaterialFileGet]
