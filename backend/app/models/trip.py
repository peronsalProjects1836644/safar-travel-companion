from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field, field_validator

from app.models.common import HHMM, APIModel, BudgetLevel, Category, Pace


class PlanRequest(APIModel):
    destination: str = Field(min_length=1, max_length=80)
    start_date: date
    days: int = Field(ge=1, le=7)
    travelers: int = Field(default=1, ge=1, le=20)
    budget_level: BudgetLevel = "mid"
    interests: list[Category] = Field(min_length=1, max_length=6)
    pace: Pace = "balanced"
    notes: str | None = Field(default=None, max_length=200)
    budget_total_pkr: int | None = Field(default=None, ge=1000, le=100_000_000)

    @field_validator("start_date")
    @classmethod
    def _start_date(cls, v: date) -> date:
        today = date.today()
        if v < today - timedelta(days=1) or v > today + timedelta(days=730):
            raise ValueError("Start date must be within the next two years.")
        return v

    @field_validator("interests")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))


class TripStop(BaseModel):
    place_id: str
    name: str
    category: str
    lat: float
    lng: float
    start_time: HHMM
    duration_min: int
    tip: str = ""
    price_level: int = 0
    indoor: bool = False
    image_url: str | None = None
    visited_at: datetime | None = None


class DayPlan(BaseModel):
    day: int
    date: str
    theme: str
    stops: list[TripStop]
    distance_km: float = 0.0


class BudgetEstimate(BaseModel):
    currency: str = "PKR"
    low: int
    high: int
    total: int
    per_person: int
    breakdown: dict[str, int]
    fit: str | None = None  # "within", "borderline" or "over" when a budget was given
    note: str


class TripOut(BaseModel):
    id: str
    title: str
    summary: str = ""
    destination: str
    start_date: str
    days: int
    travelers: int
    budget_level: str
    interests: list[str]
    pace: str
    itinerary: list[DayPlan]
    tips: list[str] = []
    budget: BudgetEstimate
    source: str  # "ai" or "rules"
    status: str  # planned, active, completed
    active_day: int = 1
    created_at: datetime
    notice: str | None = None
    recommended_days: int | None = None


class TripSummary(BaseModel):
    id: str
    title: str
    destination: str
    start_date: str
    days: int
    status: str
    source: str
    stop_count: int
    created_at: datetime


class TripPatch(APIModel):
    title: str = Field(min_length=1, max_length=80)


class StopAdd(APIModel):
    day: int = Field(ge=1, le=7)
    place_id: str


class StartTripIn(APIModel):
    day: int = Field(default=1, ge=1, le=7)
