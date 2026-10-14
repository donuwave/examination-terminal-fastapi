from typing import Optional

from pydantic import BaseModel, Field


class AuthBase(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)
