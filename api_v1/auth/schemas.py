from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class AuthBase(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class ResetRequest(BaseModel):
    email: EmailStr


class ResetVerify(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResetConfirm(ResetVerify):
    password: str = Field(min_length=6, max_length=128)
