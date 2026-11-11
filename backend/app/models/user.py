import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.common import APIModel, BudgetLevel, Category, Pace


def normalize_phone(raw: str) -> str:
    """Return digits in international form without '+', e.g. 03001234567 -> 923001234567.

    Pakistani local numbers (leading 0, 11 digits) are converted to +92.
    """
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = "92" + digits[1:]
    if not 10 <= len(digits) <= 15:
        raise ValueError("Enter a valid phone number, including the country code.")
    return digits


class EmergencyContact(APIModel):
    name: str = Field(min_length=1, max_length=60)
    phone: str

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class Preferences(APIModel):
    interests: list[Category] = Field(default_factory=list, max_length=6)
    budget_level: BudgetLevel = "mid"
    pace: Pace = "balanced"


class RegisterIn(APIModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password must contain at least one letter and one number.")
        return v


class LoginIn(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(APIModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class ProfileUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    preferences: Preferences | None = None
    emergency_contacts: list[EmergencyContact] | None = Field(default=None, max_length=5)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    preferences: Preferences
    emergency_contacts: list[EmergencyContact]
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenPair
