"""Trip planning.

Flow: rank real places -> ask OpenAI for an ordering (validated against those places) ->
fall back to a rule-based plan if AI is unavailable, over quota or invalid ->
compute times, distances and budget in code.
"""

import hashlib
import json
import logging
import math
import re
from collections import Counter
from datetime import date, timedelta

from app.core.cache import cache_get, cache_set
from app.core.config import Settings
from app.core.errors import AppError
from app.core.geo import fmt_hhmm, nearest_neighbor_order, parse_hhmm, two_opt
from app.models.trip import PlanRequest
from app.services import budget as budget_svc
from app.services import places as places_svc
from app.services import usage
from app.services.ai import AIInvalid, AIService, AIUnavailable
from app.services.schedule import clamp_start, day_distance_km, schedule_stops

log = logging.getLogger("app.planner")

STOPS_PER_DAY = {"relaxed": (2, 3), "balanced": (3, 4), "packed": (4, 6)}
MAX_PRICE = {"budget": 1, "mid": 2, "premium": 3}
SEASON_BY_MONTH = {
    12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn",
}
THEMES = {
    "heritage": "History and heritage", "nature": "Nature and scenery", "mountains": "Mountain views",
    "lakes": "Lakes and water", "beaches": "Beach and coast", "parks": "Parks and gardens",
    "museums": "Museums and culture", "religious": "Landmarks and worship", "food": "Food and bazaars",
    "shopping": "Markets and shopping", "adventure": "Adventure day", "family": "Family day out",
}
TIPS = {
    "heritage": "Go early to avoid the crowds and the midday heat.",
    "nature": "Carry water and wear comfortable shoes.",
    "mountains": "Check road and weather conditions before you set out.",
    "lakes": "Carry a jacket, as it can be cooler near the water.",
    "beaches": "Only swim where it is clearly safe to do so.",
    "parks": "Morning or evening visits are the most comfortable.",
    "museums": "Check opening days before you go.",
    "religious": "Dress modestly and follow local etiquette.",
    "food": "Ask about prices first and pick busy, clean places.",
    "shopping": "Bargain politely and keep valuables safe.",
    "adventure": "Use licensed guides and check safety conditions.",
    "family": "Plan breaks and carry snacks and water.",
}


class DraftError(ValueError):
    """A plan draft did not satisfy the rules."""


def recommended_days(n_places: int) -> int:
    """About two stops a day is a comfortable pace, so this is how long the places we have can fill."""
    return max(1, math.ceil(n_places / 2))


def season_for(d: date) -> str:
    return SEASON_BY_MONTH[d.month]


def _clean(value, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]", " ", value).strip()[:limit]


# ---------------------------------------------------------------- candidate ranking

def rank_candidates(places: list[dict], interests: list[str], budget_level: str, season: str, limit: int) -> list[dict]:
    def score(p: dict) -> float:
        s = 0.0
        if p["category"] in interests:
            s += 3
        if any(t in interests for t in p.get("tags", [])):
            s += 1
        seasons = p.get("best_season") or []
        s += 1.5 if (not seasons or season in seasons) else -1
        if p.get("price_level", 0) > MAX_PRICE[budget_level]:
            s -= 1.5
        return s

    return sorted(places, key=lambda p: (-score(p), p["name"]))[:limit]


# ---------------------------------------------------------------- drafts

def validate_draft(raw: dict, by_id: dict[str, dict], days: int, max_stops: int) -> dict:
    if not isinstance(raw, dict):
        raise DraftError("the answer must be a JSON object")
    raw_days = raw.get("days")
    if not isinstance(raw_days, list) or len(raw_days) != days:
        raise DraftError(f"expected exactly {days} days")
    seen: set[str] = set()
    out_days = []
    for i, day in enumerate(raw_days, start=1):
        if not isinstance(day, dict):
            raise DraftError(f"day {i} is not an object")
        stops = []
        for s in day.get("stops") or []:
            pid = s.get("place_id") if isinstance(s, dict) else None
            if pid not in by_id:
                raise DraftError(f"unknown place_id {pid!r}; use only ids from `places`")
            if pid in seen:
                continue
            seen.add(pid)
            stops.append({"place_id": pid, "tip": _clean(s.get("tip"), 160)})
        stops = stops[:max_stops]
        if not stops:
            raise DraftError(f"day {i} has no valid stops")
        start = day.get("day_start")
        out_days.append(
            {
                "theme": _clean(day.get("theme"), 60) or "Sightseeing",
                "day_start": start if isinstance(start, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", start) else "09:00",
                "stops": stops,
            }
        )
    tips = [_clean(t, 160) for t in (raw.get("tips") or []) if isinstance(t, str)]
    return {
        "title": _clean(raw.get("title"), 80) or "Your trip",
        "summary": _clean(raw.get("summary"), 300),
        "tips": [t for t in tips if t][:5],
        "days": out_days,
    }


def rule_draft(ranked: list[dict], destination: str, days: int, pace: str) -> dict:
    per_day = STOPS_PER_DAY[pace][1]
    chosen = ranked[: max(days, min(len(ranked), days * per_day))]
    pts = [(p["lat"], p["lng"]) for p in chosen]
    order = two_opt(nearest_neighbor_order(pts, 0), pts)
    seq = [chosen[i] for i in order]
    size, extra = divmod(len(seq), days)
    out_days, idx = [], 0
    for d in range(days):
        take = size + (1 if d < extra else 0)
        chunk, idx = seq[idx : idx + take], idx + take
        top = Counter(p["category"] for p in chunk).most_common(1)[0][0]
        out_days.append(
            {
                "theme": THEMES[top],
                "day_start": "09:00",
                "stops": [{"place_id": p["_id"], "tip": TIPS.get(p["category"], "")} for p in chunk],
            }
        )
    return {
        "title": f"{days}-day trip to {destination}",
        "summary": f"A {days}-day plan around {destination} built from the places that best match your interests.",
        "tips": ["Check weather and road conditions before each day.", "Carry water and some cash."],
        "days": out_days,
    }


def plan_cache_key(req: PlanRequest, season: str, model: str) -> str:
    raw = json.dumps(
        {
            "d": req.destination.lower(), "n": req.days, "i": sorted(req.interests), "p": req.pace,
            "b": req.budget_level, "s": season, "notes": (req.notes or "").strip().lower(),
            "m": model, "v": 1,
        },
        sort_keys=True,
    )
    return "plan:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


# ---------------------------------------------------------------- assembling

def _stop_from_place(p: dict, tip: str, start: int, end: int) -> dict:
    return {
        "place_id": p["_id"], "name": p["name"], "category": p["category"],
        "lat": p["lat"], "lng": p["lng"], "start_time": fmt_hhmm(start),
        "duration_min": end - start, "tip": tip, "price_level": p.get("price_level", 0),
        "indoor": p.get("indoor", False), "image_url": p.get("image_url"), "visited_at": None,
    }


LUNCH_TARGET = 12 * 60


def meal_order(pairs: list[tuple[dict, dict]], start_min: int) -> list[tuple[dict, dict]]:
    """Food stops are meals, so they should not open the day. The first one goes to around lunchtime
    and any others go to the end of the day (dinner). Other stops keep their order."""
    foods = [x for x in pairs if x[0]["category"] == "food"]
    others = [x for x in pairs if x[0]["category"] != "food"]
    if not foods or not others:
        return pairs
    t, at = start_min, len(others)
    for i, (p, _) in enumerate(others):
        if t >= LUNCH_TARGET:
            at = i
            break
        t += p["avg_visit_minutes"] + 20  # rough travel allowance
    return others[:at] + [foods[0]] + others[at:] + foods[1:]


def assemble_days(draft: dict, by_id: dict[str, dict], start_date: date, settings: Settings) -> list[dict]:
    result = []
    for i, d in enumerate(draft["days"]):
        start = clamp_start(d["day_start"])
        pairs = meal_order([(by_id[s["place_id"]], s) for s in d["stops"]], start)
        stops_places = [p for p, _ in pairs]
        d = {**d, "stops": [s for _, s in pairs]}
        items = [{"lat": p["lat"], "lng": p["lng"], "duration_min": p["avg_visit_minutes"]} for p in stops_places]
        slots = schedule_stops(items, start, settings.drive_speed_kmh, settings.detour_factor)
        stops = [
            _stop_from_place(p, s["tip"], a, b)
            for p, s, (a, b) in zip(stops_places, d["stops"], slots)
        ]
        result.append(
            {
                "day": i + 1,
                "date": (start_date + timedelta(days=i)).isoformat(),
                "theme": d["theme"],
                "stops": stops,
                "distance_km": round(day_distance_km(stops), 1),
            }
        )
    return result


def reschedule_day(day: dict, settings: Settings) -> dict:
    """Recompute times and distance after the stops of a day were edited (nothing is dropped)."""
    stops = day["stops"]
    if stops:
        start = parse_hhmm(stops[0]["start_time"])
        slots = schedule_stops(
            [{"lat": s["lat"], "lng": s["lng"], "duration_min": s["duration_min"]} for s in stops],
            start, settings.drive_speed_kmh, settings.detour_factor, day_end=24 * 60 - 1,
        )
        for s, (a, b) in zip(stops, slots):
            s["start_time"], s["duration_min"] = fmt_hhmm(a), b - a
    day["distance_km"] = round(day_distance_km(stops), 1)
    return day


# ---------------------------------------------------------------- orchestration

async def create_trip(db, settings: Settings, ai: AIService, user: dict, req: PlanRequest) -> tuple[dict, str | None]:
    places = await places_svc.destination_places(db, req.destination)
    if not places:
        raise AppError(404, "unknown_destination", f"We do not have places for '{req.destination}' yet.")
    destination = places[0]["destination"]
    recommended = recommended_days(len(places))
    # With fewer places than days we plan only the days the places can fill and leave the rest open.
    plan_days = req.days if len(places) >= req.days else recommended
    stay_note = None
    if req.days > recommended:
        stay_note = (
            f"Recommended stay for {destination} is about {recommended} day{'s' if recommended != 1 else ''} "
            f"with the places we have. "
            + ("The extra days are left open so you can rest or explore on your own."
               if plan_days < req.days else "Your days are planned with a lighter schedule.")
        )
    season = season_for(req.start_date)
    max_stops = STOPS_PER_DAY[req.pace][1]
    limit = min(len(places), max(14, req.days * max_stops * 2), 32)
    ranked = rank_candidates(places, req.interests, req.budget_level, season, limit)
    by_id = {p["_id"]: p for p in ranked}

    def validator(raw: dict) -> dict:
        return validate_draft(raw, by_id, plan_days, max_stops)

    draft, source, notice = None, "rules", None
    if ai.available:
        key = plan_cache_key(req, season, settings.openai_model)
        hit = await cache_get(db, key)
        if hit and hit.fresh:
            try:
                draft, source = validator(hit.value), "ai"
            except DraftError:
                draft = None
        if draft is None:
            try:
                await usage.consume(db, settings, str(user["_id"]))
                payload = {
                    "request": {
                        "destination": destination, "days": plan_days, "interests": req.interests,
                        "pace": req.pace, "budget_level": req.budget_level, "season": season,
                        "traveler_notes": req.notes or "",
                    },
                    "rules": {"max_stops_per_day": max_stops},
                    "places": [
                        {
                            "id": p["_id"], "name": p["name"], "category": p["category"],
                            "price_level": p.get("price_level", 0), "visit_min": p["avg_visit_minutes"],
                            "indoor": p.get("indoor", False), "seasons": p.get("best_season", []),
                            "lat": round(p["lat"], 4), "lng": round(p["lng"], 4),
                        }
                        for p in ranked
                    ],
                }
                tag = hashlib.sha256(str(user["_id"]).encode()).hexdigest()[:16]
                draft = await ai.plan(payload, validator, tag)
                source = "ai"
                await cache_set(db, key, draft, fresh_seconds=settings.plan_cache_days * 86400)
            except AppError as exc:
                if exc.code != "ai_quota_exceeded":
                    raise
                notice = "The daily AI limit was reached, so this plan was built with the standard planner."
            except (AIUnavailable, AIInvalid):
                notice = "The AI planner was unavailable, so this plan was built with the standard planner."
    if draft is None:
        draft, source = rule_draft(ranked, destination, plan_days, req.pace), "rules"

    free = [{"theme": "Free day", "day_start": "09:00", "stops": []} for _ in range(req.days - plan_days)]
    draft = {**draft, "days": draft["days"] + free, "title": re.sub(r"^\d+-day", f"{req.days}-day", draft["title"])}
    itinerary = assemble_days(draft, by_id, req.start_date, settings)
    doc = {
        "user_id": str(user["_id"]),
        "title": draft["title"],
        "summary": draft["summary"],
        "destination": destination,
        "start_date": req.start_date.isoformat(),
        "days": req.days,
        "travelers": req.travelers,
        "budget_level": req.budget_level,
        "interests": list(req.interests),
        "pace": req.pace,
        "budget_total_pkr": req.budget_total_pkr,
        "itinerary": itinerary,
        "tips": draft["tips"],
        "budget": budget_svc.estimate(itinerary, req.days, req.travelers, req.budget_level, req.budget_total_pkr),
        "source": source,
        "status": "planned",
        "active_day": 1,
        "recommended_days": recommended,
    }
    notice = " ".join(x for x in (stay_note, notice) if x) or None
    return doc, notice
