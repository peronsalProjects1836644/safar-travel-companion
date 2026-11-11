"""Live session handling: one active trip per user, latest position only (no history)."""

import logging
import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings
from app.core.errors import AppError
from app.core.timeutil import as_utc, utcnow
from app.repositories import trips as trips_repo
from app.services import places as places_svc
from app.services import weather as weather_svc
from app.services.companion_engine import evaluate_progress, rank_suggestions, shift_schedule
from app.services.schedule import DAY_END

log = logging.getLogger("app.companion")


def _first_name(user: dict) -> str:
    return (user.get("name") or "A traveler").split()[0]


async def start_trip(db, settings: Settings, user: dict, trip_id: str, day: int) -> dict:
    trip = await trips_repo.get_owned(db, trip_id, str(user["_id"]))
    if day > trip["days"]:
        raise AppError(422, "invalid_day", f"This trip has {trip['days']} days.")
    await trips_repo.set_fields(db, trip["_id"], {"status": "active", "active_day": day})
    now = utcnow()
    await db.live_sessions.update_one(
        {"_id": str(user["_id"])},
        {
            "$set": {
                "trip_id": str(trip["_id"]), "day": day, "name": _first_name(user),
                "started_at": now, "expires_at": now + timedelta(hours=settings.live_session_hours),
            },
            "$unset": {"last_ping_at": "", "last_state": ""},
        },
        upsert=True,
    )
    trip["status"], trip["active_day"] = "active", day
    return trip


async def complete_trip(db, user: dict, trip_id: str) -> dict:
    trip = await trips_repo.get_owned(db, trip_id, str(user["_id"]))
    await trips_repo.set_fields(db, trip["_id"], {"status": "completed"})
    await db.live_sessions.delete_one({"_id": str(user["_id"]), "trip_id": str(trip["_id"])})
    trip["status"] = "completed"
    return trip


class Tracker:
    """Applies one GPS update to the user's active trip and returns the new state."""

    def __init__(self, db, settings: Settings, http: httpx.AsyncClient, user: dict, trip: dict, day: int):
        self.db, self.settings, self.http = db, settings, http
        self.user, self.trip, self.day_idx = user, trip, day - 1

    @classmethod
    async def for_user(cls, db, settings: Settings, http: httpx.AsyncClient, user: dict) -> "Tracker":
        session = await db.live_sessions.find_one({"_id": str(user["_id"])})
        if not session:
            raise AppError(404, "no_active_trip", "Start a trip first to use the live companion.")
        trip = await trips_repo.get_owned(db, session["trip_id"], str(user["_id"]))
        if trip.get("status") != "active":
            raise AppError(404, "no_active_trip", "Start a trip first to use the live companion.")
        return cls(db, settings, http, user, trip, session["day"])

    @property
    def stops(self) -> list[dict]:
        return self.trip["itinerary"][self.day_idx]["stops"]

    async def update(self, lat: float, lng: float, accuracy_m: float | None = None) -> dict:
        s = self.settings
        now = utcnow()
        uid = str(self.user["_id"])
        session = await self.db.live_sessions.find_one({"_id": uid}) or {}
        last = as_utc(session.get("last_ping_at"))
        if last and session.get("last_state") and (now - last).total_seconds() < s.min_ping_seconds:
            return {**session["last_state"], "throttled": True}

        local = now.astimezone(ZoneInfo(s.timezone))
        now_min = local.hour * 60 + local.minute
        stops = self.stops
        progress = evaluate_progress(
            stops, lat, lng, now_min,
            arrival_radius_m=s.arrival_radius_m, speed_kmh=s.drive_speed_kmh, detour=s.detour_factor,
        )

        for i in progress["arrived"]:
            stops[i]["visited_at"] = now
            await self.db.trips.update_one(
                {"_id": self.trip["_id"]},
                {"$set": {f"itinerary.{self.day_idx}.stops.{i}.visited_at": now}},
            )

        schedule_updated, at_risk = False, []
        delay = progress["delay_min"]
        if progress["next"] and delay is not None and delay >= s.delay_threshold_min:
            shift = shift_schedule(stops, progress["next"]["index"], delay)
            if shift["changes"]:
                updates = {}
                for ch in shift["changes"]:
                    stops[ch["index"]]["start_time"] = ch["start_time"]
                    updates[f"itinerary.{self.day_idx}.stops.{ch['index']}.start_time"] = ch["start_time"]
                await self.db.trips.update_one({"_id": self.trip["_id"]}, {"$set": updates})
                schedule_updated, at_risk = True, shift["at_risk"]

        wet, weather = False, None
        try:
            wx = await weather_svc.get_weather(self.http, self.db, s, lat, lng, days=1)
            weather = {"label": wx["current"]["label"], "temp_c": wx["current"]["temp_c"], "is_wet": wx["current"]["is_wet"]}
            wet = wx["current"]["is_wet"]
        except AppError:
            pass

        planned_ids = {st["place_id"] for d in self.trip["itinerary"] for st in d["stops"]}
        nearby = await places_svc.nearby(self.db, lat, lng, 25, limit=60)
        candidates = [d for _, d in nearby if d["_id"] not in planned_ids]
        remaining = max(0, DAY_END - now_min)
        suggestions = rank_suggestions(
            lat, lng, candidates, interests=self.trip.get("interests", []), wet=wet,
            remaining_min=remaining, speed_kmh=s.drive_speed_kmh, detour=s.detour_factor,
        )

        day_complete = progress["next"] is None
        state = {
            "type": "state",
            "day": self.day_idx + 1,
            "next_stop": progress["next"],
            "arrived": [stops[i]["name"] for i in progress["arrived"]],
            "delay_min": delay,
            "schedule_updated": schedule_updated,
            "at_risk_stops": [stops[i]["name"] for i in at_risk],
            "progress": {"done": progress["done"], "total": progress["total"]},
            "day_complete": day_complete,
            "weather": weather,
            "suggestions": suggestions,
        }

        if day_complete and stops and self.day_idx + 1 >= self.trip["days"]:
            if self.trip.get("status") != "completed":
                await trips_repo.set_fields(self.db, self.trip["_id"], {"status": "completed"})
                self.trip["status"] = "completed"
            state["trip_complete"] = True

        await self.db.live_sessions.update_one(
            {"_id": uid},
            {
                "$set": {
                    "lat": lat, "lng": lng, "accuracy_m": accuracy_m, "updated_at": now,
                    "last_ping_at": now, "last_state": state,
                    "expires_at": now + timedelta(hours=s.live_session_hours),
                }
            },
            upsert=True,
        )
        return state


# ------------------------------------------------------------------ sharing

async def create_share(db, settings: Settings, user: dict, hours: int) -> dict:
    hours = min(hours, settings.share_max_hours)
    token = secrets.token_urlsafe(16)
    now = utcnow()
    expires = now + timedelta(hours=hours)
    await db.shares.insert_one(
        {"_id": token, "user_id": str(user["_id"]), "created_at": now, "expires_at": expires}
    )
    return {"token": token, "expires_at": expires}


async def read_share(db, token: str) -> dict:
    share = await db.shares.find_one({"_id": token})
    if not share or as_utc(share["expires_at"]) <= utcnow():
        raise AppError(404, "share_not_found", "This sharing link has expired or does not exist.")
    session = await db.live_sessions.find_one({"_id": share["user_id"]}) or {}
    trip_title = None
    if session.get("trip_id"):
        try:
            trip = await trips_repo.get_owned(db, session["trip_id"], share["user_id"])
            trip_title = trip["title"]
        except AppError:
            pass
    location = None
    if session.get("lat") is not None:
        location = {
            "lat": session["lat"], "lng": session["lng"],
            "accuracy_m": session.get("accuracy_m"), "updated_at": session.get("updated_at"),
        }
    return {
        "name": session.get("name", "A traveler"),
        "trip_title": trip_title,
        "location": location,
        "expires_at": share["expires_at"],
    }


async def revoke_share(db, user: dict, token: str) -> None:
    res = await db.shares.delete_one({"_id": token, "user_id": str(user["_id"])})
    if res.deleted_count == 0:
        raise AppError(404, "share_not_found", "This sharing link does not exist.")
