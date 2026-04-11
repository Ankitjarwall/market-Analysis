"""Pydantic schemas for authentication."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    capital: float
    trade_mode: str
    auto_settings: dict | None
    telegram_chat_id: str | None
    is_active: bool
    last_login: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(pattern="^(admin|analyst|viewer)$")
    capital: float = Field(default=200_000, gt=0)
    telegram_chat_id: str | None = None


class UpdateUserRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|analyst|viewer)$")
    is_active: bool | None = None
    capital: float | None = Field(default=None, gt=0)
    trade_mode: str | None = Field(default=None, pattern="^(auto|manual)$")
    telegram_chat_id: str | None = None


class ChangeCapitalRequest(BaseModel):
    capital: float = Field(gt=0)


class ChangeTradeModeRequest(BaseModel):
    mode: str = Field(pattern="^(auto|manual)$")
