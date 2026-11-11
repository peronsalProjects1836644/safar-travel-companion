from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId

from app.core.timeutil import utcnow


def _oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def get_by_email(db, email: str) -> dict | None:
    return await db.users.find_one({"email": email.lower()})


async def get_by_id(db, user_id: str) -> dict | None:
    oid = _oid(user_id)
    return await db.users.find_one({"_id": oid}) if oid else None


async def insert(db, *, email: str, name: str, password_hash: str, role: str = "user") -> dict:
    doc = {
        "email": email.lower(),
        "name": name,
        "password_hash": password_hash,
        "role": role,
        "disabled": False,
        "preferences": {"interests": [], "budget_level": "mid", "pace": "balanced"},
        "emergency_contacts": [],
        "created_at": utcnow(),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def update(db, user_id: str, changes: dict) -> dict | None:
    oid = _oid(user_id)
    if not oid:
        return None
    if changes:
        await db.users.update_one({"_id": oid}, {"$set": changes})
    return await db.users.find_one({"_id": oid})


async def list_users(db, limit: int, offset: int) -> list[dict]:
    cur = db.users.find({}, {"password_hash": 0}).sort("created_at", -1).skip(offset).limit(limit)
    return await cur.to_list(length=None)


async def count(db) -> int:
    return await db.users.count_documents({})


def to_out(doc: dict) -> dict:
    created: datetime = doc["created_at"]
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "name": doc["name"],
        "role": doc.get("role", "user"),
        "preferences": doc.get("preferences", {}),
        "emergency_contacts": doc.get("emergency_contacts", []),
        "created_at": created,
    }
