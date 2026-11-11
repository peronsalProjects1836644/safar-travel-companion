"""Weather from Open-Meteo (free, no key), cached per ~1 km grid cell."""

import logging

import httpx

from app.core.cache import cache_get, cache_set
from app.core.config import Settings
from app.core.errors import AppError

log = logging.getLogger("app.weather")

URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes as documented by Open-Meteo.
WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Dense freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Violent showers",
    85: "Light snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}
_WET = set(range(51, 68)) | set(range(71, 78)) | {80, 81, 82, 85, 86, 95, 96, 99}


def is_wet(code: int | None) -> bool:
    return code in _WET


def _label(code) -> str:
    return WMO.get(code, "Unknown")


def _normalize(raw: dict) -> dict:
    cur, daily = raw["current"], raw["daily"]
    code = cur.get("weather_code")
    return {
        "current": {
            "temp_c": cur.get("temperature_2m"),
            "code": code,
            "label": _label(code),
            "wind_kmh": cur.get("wind_speed_10m"),
            "precipitation_mm": cur.get("precipitation"),
            "is_wet": is_wet(code),
        },
        "daily": [
            {
                "date": daily["time"][i],
                "code": daily["weather_code"][i],
                "label": _label(daily["weather_code"][i]),
                "temp_max_c": daily["temperature_2m_max"][i],
                "temp_min_c": daily["temperature_2m_min"][i],
                "precip_probability": daily["precipitation_probability_max"][i],
                "is_wet": is_wet(daily["weather_code"][i]),
            }
            for i in range(len(daily["time"]))
        ],
    }


async def get_weather(http: httpx.AsyncClient, db, settings: Settings, lat: float, lng: float, days: int = 3) -> dict:
    key = f"wx:{lat:.2f}:{lng:.2f}:{days}"
    hit = await cache_get(db, key)
    if hit and hit.fresh:
        return {**hit.value, "stale": False}
    params = {
        "latitude": round(lat, 2),
        "longitude": round(lng, 2),
        "current": "temperature_2m,weather_code,wind_speed_10m,precipitation",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": days,
    }
    try:
        resp = await http.get(URL, params=params, timeout=10)
        resp.raise_for_status()
        data = _normalize(resp.json())
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        log.warning("Open-Meteo request failed: %s", exc)
        if hit:
            return {**hit.value, "stale": True}
        raise AppError(503, "weather_unavailable", "Weather is temporarily unavailable.") from None
    await cache_set(
        db, key, data,
        fresh_seconds=settings.weather_fresh_minutes * 60,
        stale_grace_seconds=settings.cache_stale_grace_hours * 3600,
    )
    return {**data, "stale": False}
