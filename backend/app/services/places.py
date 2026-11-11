"""Curated places: search, suggestions, nearby lookups and admin edits."""

import re

from app.core.errors import AppError
from app.core.geo import bounding_box, haversine_km
from app.core.timeutil import utcnow
from app.models.place import PlaceBase, PlaceOut

_OUT_FIELDS = set(PlaceOut.model_fields) - {"id", "distance_km"}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:100] or "place"


def _search_text(data: dict) -> str:
    parts = [data["name"], data["destination"], data["region"], data["category"], *data.get("tags", [])]
    return " ".join(parts).lower()


def make_doc(data: dict, place_id: str, created_at=None) -> dict:
    doc = {k: data.get(k) for k in _OUT_FIELDS}
    doc["tags"] = data.get("tags") or []
    doc["best_season"] = data.get("best_season") or []
    doc["_id"] = place_id
    doc["destination_key"] = data["destination"].lower()
    doc["search_text"] = _search_text(data)
    doc["created_at"] = created_at or utcnow()
    doc["updated_at"] = utcnow()
    return doc


def to_out(doc: dict, distance_km: float | None = None) -> dict:
    out = {k: doc.get(k) for k in _OUT_FIELDS}
    out["id"] = doc["_id"]
    out["tags"] = out["tags"] or []
    out["best_season"] = out["best_season"] or []
    if distance_km is not None:
        out["distance_km"] = round(distance_km, 2)
    return out


def _text_filter(q: str) -> list[dict]:
    words = [w for w in re.split(r"\s+", q.lower().strip()) if w]
    return [{"search_text": {"$regex": re.escape(w)}} for w in words[:5]]


async def list_places(db, *, destination=None, category=None, q=None, limit=20, offset=0):
    flt: dict = {}
    if destination:
        flt["destination_key"] = destination.lower()
    if category:
        flt["category"] = category
    if q:
        flt["$and"] = _text_filter(q)
    total = await db.places.count_documents(flt)
    cur = db.places.find(flt).sort("name", 1).skip(offset).limit(limit)
    return await cur.to_list(length=None), total


async def suggest(db, q: str, limit: int = 8) -> list[dict]:
    """Autocomplete from our own dataset (the OSM geocoder forbids autocomplete)."""
    flt = {"$and": _text_filter(q)} if q.strip() else {}
    docs = await db.places.find(flt).limit(60).to_list(length=None)
    ql = q.lower().strip()
    docs.sort(key=lambda d: (not d["name"].lower().startswith(ql), len(d["name"]), d["name"]))
    return docs[:limit]


async def nearby(db, lat: float, lng: float, radius_km: float, category=None, limit=20):
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    flt: dict = {"lat": {"$gte": min_lat, "$lte": max_lat}, "lng": {"$gte": min_lng, "$lte": max_lng}}
    if category:
        flt["category"] = category
    docs = await db.places.find(flt).limit(500).to_list(length=None)
    scored = [(haversine_km(lat, lng, d["lat"], d["lng"]), d) for d in docs]
    scored = sorted((s for s in scored if s[0] <= radius_km), key=lambda s: s[0])
    return scored[:limit]


async def destinations(db) -> list[dict]:
    pipeline = [
        {
            "$group": {
                "_id": "$destination",
                "region": {"$first": "$region"},
                "count": {"$sum": 1},
                "lat": {"$avg": "$lat"},
                "lng": {"$avg": "$lng"},
                "image_url": {"$max": "$image_url"},  # any one photo, null values are ignored
            }
        },
        {"$sort": {"_id": 1}},
    ]
    cursor = await db.places.aggregate(pipeline)
    rows = await cursor.to_list(length=None)
    return [
        {"name": r["_id"], "region": r["region"], "count": r["count"],
         "lat": round(r["lat"], 4), "lng": round(r["lng"], 4), "image_url": r.get("image_url")}
        for r in rows
    ]


async def get_place(db, place_id: str) -> dict:
    doc = await db.places.find_one({"_id": place_id})
    if not doc:
        raise AppError(404, "place_not_found", "Place not found.")
    return doc


async def destination_places(db, destination: str) -> list[dict]:
    return await db.places.find({"destination_key": destination.lower()}).to_list(length=None)


async def create_place(db, data: PlaceBase, place_id: str | None = None) -> dict:
    values = data.model_dump()
    base = place_id or slugify(f"{data.name} {data.destination}")
    candidate, n = base, 1
    while await db.places.find_one({"_id": candidate}):
        if place_id:
            raise AppError(409, "place_exists", "A place with this id already exists.")
        n += 1
        candidate = f"{base}-{n}"
    doc = make_doc(values, candidate)
    await db.places.insert_one(doc)
    return doc


async def replace_place(db, place_id: str, data: PlaceBase) -> dict:
    existing = await get_place(db, place_id)
    doc = make_doc(data.model_dump(), place_id, created_at=existing.get("created_at"))
    await db.places.replace_one({"_id": place_id}, doc)
    return doc


async def delete_place(db, place_id: str) -> None:
    res = await db.places.delete_one({"_id": place_id})
    if res.deleted_count == 0:
        raise AppError(404, "place_not_found", "Place not found.")


async def upsert_many(db, items: list[tuple[str, dict]]) -> int:
    for place_id, data in items:
        existing = await db.places.find_one({"_id": place_id})
        doc = make_doc(data, place_id, created_at=existing.get("created_at") if existing else None)
        await db.places.replace_one({"_id": place_id}, doc, upsert=True)
    return len(items)
