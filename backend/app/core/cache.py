"""MongoDB-backed cache with a fresh window and a stale grace window.

Stale entries are kept for a while so we can still answer when a free
upstream service is down. A TTL index removes entries after `expires_at`.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.core.timeutil import as_utc, utcnow


@dataclass
class CacheHit:
    value: Any
    fresh: bool


async def cache_get(db, key: str) -> CacheHit | None:
    doc = await db.cache.find_one({"_id": key})
    if not doc:
        return None
    now = utcnow()
    if as_utc(doc["expires_at"]) <= now:
        return None
    return CacheHit(doc["value"], as_utc(doc["fresh_until"]) > now)


async def cache_set(db, key: str, value: Any, fresh_seconds: float, stale_grace_seconds: float = 0) -> None:
    fresh_until = utcnow() + timedelta(seconds=fresh_seconds)
    await db.cache.update_one(
        {"_id": key},
        {
            "$set": {
                "value": value,
                "fresh_until": fresh_until,
                "expires_at": fresh_until + timedelta(seconds=stale_grace_seconds),
            }
        },
        upsert=True,
    )
