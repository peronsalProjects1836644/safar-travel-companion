"""Database indexes. The app talks to MongoDB through PyMongo's native async client."""

import logging

log = logging.getLogger("app.db")


async def ensure_indexes(db) -> None:
    try:
        await db.users.create_index("email", unique=True)
        await db.places.create_index([("destination_key", 1), ("category", 1)])
        await db.places.create_index([("lat", 1), ("lng", 1)])
        await db.trips.create_index([("user_id", 1), ("created_at", -1)])
        # TTL indexes: MongoDB removes documents once expires_at has passed.
        for name in ("cache", "live_sessions", "shares", "sos_events"):
            await db[name].create_index("expires_at", expireAfterSeconds=0)
    except Exception:  # never block startup on index creation
        log.exception("Could not create indexes")
