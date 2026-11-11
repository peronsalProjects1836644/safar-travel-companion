from bson import ObjectId
from bson.errors import InvalidId

from app.core.errors import AppError
from app.core.timeutil import utcnow


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise AppError(404, "trip_not_found", "Trip not found.") from None


async def create(db, doc: dict) -> dict:
    doc["created_at"] = utcnow()
    res = await db.trips.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def get_owned(db, trip_id: str, user_id: str) -> dict:
    doc = await db.trips.find_one({"_id": oid(trip_id), "user_id": user_id})
    if not doc:
        raise AppError(404, "trip_not_found", "Trip not found.")
    return doc


async def list_for_user(db, user_id: str, limit: int = 50) -> list[dict]:
    cur = db.trips.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
    return await cur.to_list(length=None)


async def set_fields(db, trip_id, fields: dict) -> None:
    await db.trips.update_one({"_id": trip_id}, {"$set": fields})


async def delete(db, trip_id: str, user_id: str) -> None:
    res = await db.trips.delete_one({"_id": oid(trip_id), "user_id": user_id})
    if res.deleted_count == 0:
        raise AppError(404, "trip_not_found", "Trip not found.")


async def count(db) -> int:
    return await db.trips.count_documents({})


def to_out(doc: dict) -> dict:
    out = {k: v for k, v in doc.items() if k not in {"_id", "user_id"}}
    out["id"] = str(doc["_id"])
    return out


def to_summary(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "destination": doc["destination"],
        "start_date": doc["start_date"],
        "days": doc["days"],
        "status": doc.get("status", "planned"),
        "source": doc.get("source", "rules"),
        "stop_count": sum(len(d["stops"]) for d in doc["itinerary"]),
        "created_at": doc["created_at"],
    }
