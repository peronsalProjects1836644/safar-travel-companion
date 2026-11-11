"""Nearby hospitals, police stations and pharmacies (Overpass API) plus SOS links."""

import json
import logging
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.cache import cache_get, cache_set
from app.core.config import Settings
from app.core.geo import bounding_box, haversine_km
from app.core.timeutil import utcnow
from app.services import places as places_svc
from app.services.emergency import EMERGENCY_NUMBERS

log = logging.getLogger("app.safety")

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HOSPITALS_FILE = Path(__file__).resolve().parents[2] / "data" / "major_hospitals.json"
SEARCH_WORD = {"hospital": "hospital", "police": "police station", "pharmacy": "pharmacy"}
KINDS = {
    "hospital": '["amenity"="hospital"]',
    "police": '["amenity"="police"]',
    "pharmacy": '["amenity"="pharmacy"]',
}
CELL_MARGIN_M = 1000  # query a little wider than asked, because cache cells are ~1 km


def _major_hospitals() -> dict[str, list[str]]:
    try:
        data = json.loads(HOSPITALS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, list)}


def _maps_search(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote(query)}"


async def fallback_for(db, lat: float, lng: float, kind: str) -> dict:
    """Always-available help: a map search near the point plus well known hospitals of the closest destination."""
    word = SEARCH_WORD[kind]
    near = await places_svc.nearby(db, lat, lng, 150, limit=1)
    dest = near[0][1]["destination"] if near else None
    named = []
    if kind == "hospital" and dest:
        for name in _major_hospitals().get(dest, []):
            named.append({"name": name, "area": dest, "maps_url": _maps_search(f"{name} {dest}")})
    return {
        "destination": dest,
        "search_url": f"https://www.google.com/maps/search/{quote(word)}/@{lat:.5f},{lng:.5f},14z",
        "named": named,
    }


def _parse_nominatim(rows: list[dict]) -> list[dict]:
    items = []
    for r in rows:
        try:
            lat, lng = float(r["lat"]), float(r["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        name = r.get("name") or (r.get("display_name") or "").split(",")[0].strip()
        items.append({"name": name or "Unnamed", "lat": lat, "lng": lng, "phone": None, "emergency": False})
    return items


async def _nominatim_nearby(http: httpx.AsyncClient, settings: Settings, kind: str, lat: float, lng: float, radius_m: int) -> list[dict]:
    """Second source from the same OpenStreetMap data, used when every Overpass server is busy."""
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_m / 1000)
    resp = await http.get(
        NOMINATIM_URL,
        params={
            "q": SEARCH_WORD[kind], "format": "jsonv2", "limit": 25, "bounded": 1,
            "viewbox": f"{min_lng:.5f},{max_lat:.5f},{max_lng:.5f},{min_lat:.5f}",
            "countrycodes": settings.geocode_country_codes,
        },
        timeout=12,
    )
    resp.raise_for_status()
    return _parse_nominatim(resp.json())


def _query(kind: str, lat: float, lng: float, radius_m: int) -> str:
    return (
        f"[out:json][timeout:10];nwr{KINDS[kind]}(around:{radius_m},{lat:.4f},{lng:.4f});out center 60;"
    )


def _parse(elements: list[dict]) -> list[dict]:
    items = []
    for el in elements:
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lng is None:
            continue
        tags = el.get("tags") or {}
        items.append(
            {
                "name": tags.get("name") or tags.get("name:en") or "Unnamed",
                "lat": lat,
                "lng": lng,
                "phone": tags.get("phone") or tags.get("contact:phone"),
                "emergency": tags.get("emergency") == "yes",
            }
        )
    return items


async def nearby_help(
    http: httpx.AsyncClient, db, settings: Settings, lat: float, lng: float, kind: str, radius_m: int
) -> dict:
    cell_lat, cell_lng = round(lat, 2), round(lng, 2)
    key = f"help:{kind}:{cell_lat}:{cell_lng}:{radius_m}"
    hit = await cache_get(db, key)
    source = "cache"
    if hit and hit.fresh:
        raw = hit.value
    else:
        raw, source = None, "unavailable"
        for url in OVERPASS_URLS:
            try:
                resp = await http.post(
                    url, data={"data": _query(kind, cell_lat, cell_lng, radius_m + CELL_MARGIN_M)}, timeout=7
                )
                resp.raise_for_status()
                raw = _parse(resp.json().get("elements", []))
                await cache_set(
                    db, key, raw,
                    fresh_seconds=settings.safety_fresh_days * 86400,
                    stale_grace_seconds=settings.cache_stale_grace_hours * 3600,
                )
                source = "live"
                break
            except (httpx.HTTPError, ValueError, AttributeError) as exc:
                log.warning("Overpass %s failed: %s", url, exc)
        if raw is None and settings.nominatim_contact_email:
            try:
                raw = await _nominatim_nearby(http, settings, kind, cell_lat, cell_lng, radius_m + CELL_MARGIN_M)
                await cache_set(
                    db, key, raw,
                    fresh_seconds=settings.safety_fresh_days * 86400,
                    stale_grace_seconds=settings.cache_stale_grace_hours * 3600,
                )
                source = "live"
            except (httpx.HTTPError, ValueError, AttributeError) as exc:
                log.warning("Nominatim nearby search failed: %s", exc)
        if raw is None:
            raw, source = (hit.value, "stale") if hit else ([], "unavailable")
    items = []
    for it in raw:
        d = haversine_km(lat, lng, it["lat"], it["lng"])
        if d * 1000 <= radius_m:
            items.append({**it, "distance_km": round(d, 2)})
    items.sort(key=lambda i: i["distance_km"])
    return {
        "kind": kind,
        "source": source,
        "items": items[:15],
        "emergency_numbers": EMERGENCY_NUMBERS,
        "fallback": await fallback_for(db, lat, lng, kind),
    }


def map_link(lat: float, lng: float) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lng:.6f}#map=17/{lat:.6f}/{lng:.6f}"


async def create_sos(db, user: dict, lat: float, lng: float, note: str | None) -> dict:
    link = map_link(lat, lng)
    text = f"EMERGENCY: {user['name']} needs help. Location: {link}"
    if note:
        text += f" Note: {note}"
    contacts = [
        {
            "name": c["name"],
            "phone": c["phone"],
            "whatsapp_url": f"https://wa.me/{c['phone']}?text={quote(text)}",
        }
        for c in user.get("emergency_contacts", [])
    ]
    await db.sos_events.insert_one(
        {
            "user_id": str(user["_id"]),
            "lat": lat,
            "lng": lng,
            "note": note,
            "created_at": utcnow(),
            "expires_at": utcnow() + timedelta(days=90),
        }
    )
    return {
        "message": text,
        "map_url": link,
        "contacts": contacts,
        "emergency_numbers": EMERGENCY_NUMBERS,
    }
