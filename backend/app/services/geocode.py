"""Place search through Nominatim, following the OSM usage policy:
identifying User-Agent, at most 1 request per second for the whole app,
results cached, no autocomplete (callers must send an explicit search).
"""

import asyncio
import logging
import re
import time

import httpx

from app.core.cache import cache_get, cache_set
from app.core.config import Settings
from app.core.errors import AppError

log = logging.getLogger("app.geocode")

URL = "https://nominatim.openstreetmap.org/search"
MIN_INTERVAL_S = 1.1


class Geocoder:
    def __init__(self, http: httpx.AsyncClient, settings: Settings):
        self._http = http
        self._settings = settings
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def search(self, db, query: str, limit: int = 5) -> list[dict]:
        if not self._settings.nominatim_contact_email:
            raise AppError(
                503, "geocoding_not_configured",
                "Place search is not configured yet (NOMINATIM_CONTACT_EMAIL is missing).",
            )
        normalized = re.sub(r"\s+", " ", query.strip().lower())
        key = f"geo:{self._settings.geocode_country_codes}:{limit}:{normalized}"
        hit = await cache_get(db, key)
        if hit and hit.fresh:
            return hit.value
        params = {
            "q": query.strip(),
            "format": "jsonv2",
            "limit": limit,
            "countrycodes": self._settings.geocode_country_codes,
            "accept-language": "en",
        }
        async with self._lock:
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                resp = await self._http.get(URL, params=params, timeout=10)
                resp.raise_for_status()
                rows = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("Nominatim request failed: %s", exc)
                if hit:
                    return hit.value
                raise AppError(503, "geocoding_unavailable", "Place search is temporarily unavailable.") from None
            finally:
                self._last_call = time.monotonic()
        results = [
            {
                "name": r.get("name") or r.get("display_name", "").split(",")[0],
                "display_name": r.get("display_name", ""),
                "lat": float(r["lat"]),
                "lng": float(r["lon"]),
                "type": r.get("type"),
            }
            for r in rows
        ]
        await cache_set(
            db, key, results,
            fresh_seconds=self._settings.geocode_fresh_days * 86400,
            stale_grace_seconds=self._settings.cache_stale_grace_hours * 3600,
        )
        return results
