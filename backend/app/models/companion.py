from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import APIModel, Lat, Lng


class LocationIn(APIModel):
    lat: Lat
    lng: Lng
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class ShareCreate(APIModel):
    hours: int = Field(default=6, ge=1, le=24)


class ShareOut(BaseModel):
    token: str
    expires_at: datetime


class SosIn(APIModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    note: str | None = Field(default=None, max_length=200)


class ChatMessage(APIModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=1000)


class ChatIn(APIModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=10)
    trip_id: str | None = None
