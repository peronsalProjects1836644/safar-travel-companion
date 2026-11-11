import asyncio
import itertools
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services import geocode as geocode_svc
from app.services import places as places_svc
from tests.fakes import FakeDB, FakeOpenAI

# name, destination, region, category, lat, lng, price, minutes, indoor, seasons, tags
PLACES = [
    ("Badshahi Mosque", "Lahore", "Punjab", "religious", 31.5883, 74.3107, 0, 60, False, ["winter", "spring", "autumn"], ["mughal"]),
    ("Lahore Fort", "Lahore", "Punjab", "heritage", 31.5889, 74.3150, 1, 90, False, ["winter", "spring", "autumn"], ["mughal"]),
    ("Shalimar Gardens", "Lahore", "Punjab", "parks", 31.5859, 74.3811, 1, 75, False, ["winter", "spring"], ["garden"]),
    ("Minar-e-Pakistan", "Lahore", "Punjab", "parks", 31.5925, 74.3095, 0, 45, False, [], ["monument"]),
    ("Lahore Museum", "Lahore", "Punjab", "museums", 31.5686, 74.3085, 1, 90, True, [], ["museum"]),
    ("Wazir Khan Mosque", "Lahore", "Punjab", "heritage", 31.5826, 74.3236, 1, 60, False, [], ["mughal"]),
    ("Jahangir's Tomb", "Lahore", "Punjab", "heritage", 31.6200, 74.3050, 1, 60, False, [], ["mughal"]),
    ("Fort Road Food Street", "Lahore", "Punjab", "food", 31.5880, 74.3140, 2, 90, False, [], ["food"]),
    ("Baltit Fort", "Hunza", "Gilgit-Baltistan", "heritage", 36.3258, 74.6652, 2, 90, False, ["summer"], []),
    ("Altit Fort", "Hunza", "Gilgit-Baltistan", "heritage", 36.3190, 74.6600, 2, 75, False, ["summer"], []),
    ("Attabad Lake", "Hunza", "Gilgit-Baltistan", "lakes", 36.3167, 74.8167, 1, 120, False, ["summer"], []),
    ("Passu Cones", "Hunza", "Gilgit-Baltistan", "mountains", 36.4690, 74.8780, 0, 90, False, ["summer"], []),
    ("Tiny Fort", "Tiny", "Test", "heritage", 30.0, 70.0, 0, 60, False, [], []),
    ("Tiny Park", "Tiny", "Test", "parks", 30.01, 70.01, 0, 60, False, [], []),
]

WEATHER_JSON = {
    "current": {"time": "2026-10-26T10:00", "temperature_2m": 24.5, "weather_code": 1, "wind_speed_10m": 6.0, "precipitation": 0.0},
    "daily": {
        "time": ["2026-10-26", "2026-10-27", "2026-10-28"],
        "weather_code": [1, 3, 63],
        "temperature_2m_max": [28.0, 27.0, 22.0],
        "temperature_2m_min": [15.0, 14.0, 13.0],
        "precipitation_probability_max": [5, 20, 80],
    },
}
NOMINATIM_JSON = [
    {"name": "Badshahi Mosque", "display_name": "Badshahi Mosque, Lahore, Punjab, Pakistan", "lat": "31.5883", "lon": "74.3107", "type": "mosque"}
]
OVERPASS_JSON = {
    "elements": [
        {"type": "node", "lat": 31.5700, "lon": 74.3100, "tags": {"name": "Test Hospital", "amenity": "hospital", "emergency": "yes"}},
        {"type": "way", "center": {"lat": 31.5900, "lon": 74.3200}, "tags": {"name": "Far Hospital"}},
        {"type": "node", "lat": 40.0, "lon": 80.0, "tags": {"name": "Very Far"}},
    ]
}


class Clock:
    """Controllable replacement for utcnow in the companion service."""

    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass
class Ctx:
    client: TestClient
    db: FakeDB
    ai: FakeOpenAI
    settings: Settings
    http: respx.MockRouter
    weather: respx.Route
    nominatim: respx.Route
    overpass: respx.Route

    def run(self, coro):
        return asyncio.run(coro)


def make_settings(**overrides) -> Settings:
    base = dict(
        jwt_secret="t" * 40,
        nominatim_contact_email="test@example.com",
        admin_email="admin@example.com",
        admin_password="AdminPass123",
        openai_api_key="",
        ai_daily_limit_per_user=30,
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


async def _seed(db):
    items = []
    for name, dest, region, cat, lat, lng, price, minutes, indoor, seasons, tags in PLACES:
        data = {
            "name": name, "destination": dest, "region": region, "category": cat, "tags": tags,
            "description": f"{name} test description.", "lat": lat, "lng": lng, "price_level": price,
            "avg_visit_minutes": minutes, "indoor": indoor, "best_season": seasons,
            "image_url": None, "source_url": None, "advisory": None, "verified": False,
        }
        items.append((places_svc.slugify(f"{name} {dest}"), data))
    await places_svc.upsert_many(db, items)


@pytest.fixture(autouse=True)
def no_geocode_delay(monkeypatch):
    monkeypatch.setattr(geocode_svc, "MIN_INTERVAL_S", 0)


def build_ctx(settings: Settings | None = None, ai_enabled: bool = True):
    settings = settings or make_settings()
    db = FakeDB()
    asyncio.run(_seed(db))
    fake_ai = FakeOpenAI()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        weather = router.get(url__regex=r"https://api\.open-meteo\.com/.*").mock(
            return_value=httpx.Response(200, json=WEATHER_JSON)
        )
        nominatim = router.get(url__regex=r"https://nominatim\.openstreetmap\.org/.*").mock(
            return_value=httpx.Response(200, json=NOMINATIM_JSON)
        )
        overpass = router.post(url__regex=r"https://overpass[^/]*/api/interpreter").mock(
            return_value=httpx.Response(200, json=OVERPASS_JSON)
        )
        app = create_app(
            settings, db=db, openai_client=fake_ai if ai_enabled else None,
            http_client=httpx.AsyncClient(headers={"User-Agent": settings.user_agent}),
        )
        with TestClient(app) as client:
            yield Ctx(client, db, fake_ai, settings, router, weather, nominatim, overpass)


@pytest.fixture
def ctx():
    yield from build_ctx()


@pytest.fixture
def ctx_no_ai():
    yield from build_ctx(ai_enabled=False)


_counter = itertools.count(1)


def register(client: TestClient, email: str | None = None, name: str = "Ali Khan", password: str = "Passw0rd123"):
    email = email or f"user{next(_counter)}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "name": name, "password": password})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['tokens']['access_token']}"}, body


def admin_headers(client: TestClient):
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "AdminPass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def plan_body(**overrides):
    body = {
        "destination": "Lahore",
        "start_date": (date.today() + timedelta(days=7)).isoformat(),
        "days": 2,
        "travelers": 2,
        "budget_level": "mid",
        "interests": ["heritage", "food"],
        "pace": "balanced",
    }
    body.update(overrides)
    return body


def utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=UTC)
