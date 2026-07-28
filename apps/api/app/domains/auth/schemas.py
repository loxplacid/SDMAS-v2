from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator


class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    display_name: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        stripped = v.strip().lower()
        if "@" not in stripped:
            raise ValueError("Invalid email address")
        return stripped

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Username cannot be empty")
        if len(stripped) < 3:
            raise ValueError("Username must be at least 3 characters")
        return stripped

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("display_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name cannot be empty")
        return stripped


class UserLogin(BaseModel):
    login: str
    password: str


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip().lower()
        if "@" not in stripped:
            raise ValueError("Invalid email address")
        return stripped

    @field_validator("display_name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name cannot be empty")
        return stripped


class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip().lower()
        if "@" not in stripped:
            raise ValueError("Invalid email address")
        return stripped

    @field_validator("display_name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name cannot be empty")
        return stripped

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"admin", "staff"}
        if v not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(sorted(allowed))}")
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int