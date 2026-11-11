"""Daily AI call limits. OpenAI is the only paid service, so it is capped per user and globally."""

from pymongo import ReturnDocument

from app.core.config import Settings
from app.core.errors import AppError
from app.core.timeutil import utcnow


def _day() -> str:
    return utcnow().strftime("%Y-%m-%d")


async def _bump(db, key: str) -> int:
    doc = await db.usage.find_one_and_update(
        {"_id": key},
        {"$inc": {"ai_calls": 1}, "$setOnInsert": {"day": _day()}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["ai_calls"]


async def consume(db, settings: Settings, user_id: str) -> None:
    day = _day()
    if await _bump(db, f"{day}:{user_id}") > settings.ai_daily_limit_per_user:
        raise AppError(
            429, "ai_quota_exceeded",
            "You have reached today's AI limit. Please try again tomorrow.",
        )
    if await _bump(db, f"{day}:__global__") > settings.ai_daily_limit_global:
        raise AppError(
            429, "ai_quota_exceeded",
            "The AI assistant has reached its daily limit. Please try again tomorrow.",
        )


async def remaining_today(db, settings: Settings, user_id: str) -> int:
    doc = await db.usage.find_one({"_id": f"{_day()}:{user_id}"})
    used = doc["ai_calls"] if doc else 0
    return max(0, settings.ai_daily_limit_per_user - used)


async def global_today(db) -> int:
    doc = await db.usage.find_one({"_id": f"{_day()}:__global__"})
    return doc["ai_calls"] if doc else 0
