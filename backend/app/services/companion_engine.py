"""Live Travel Companion rules. Pure functions: no AI call and no I/O per GPS update."""

import math

from app.core.geo import fmt_hhmm, haversine_km, parse_hhmm, travel_minutes
from app.services.schedule import DAY_END


def evaluate_progress(
    stops: list[dict], lat: float, lng: float, now_min: int, *,
    arrival_radius_m: float, speed_kmh: float, detour: float,
) -> dict:
    """Which stops were reached, which one is next, and how late the user will be."""
    arrived = [
        i for i, s in enumerate(stops)
        if not s.get("visited_at") and haversine_km(lat, lng, s["lat"], s["lng"]) * 1000 <= arrival_radius_m
    ]
    done = {i for i, s in enumerate(stops) if s.get("visited_at")} | set(arrived)
    next_idx = next((i for i in range(len(stops)) if i not in done), None)
    nxt, delay = None, None
    if next_idx is not None:
        s = stops[next_idx]
        dist = haversine_km(lat, lng, s["lat"], s["lng"])
        eta = travel_minutes(dist, speed_kmh, detour)
        planned = parse_hhmm(s["start_time"])
        delay = now_min + eta - planned
        nxt = {
            "index": next_idx, "place_id": s["place_id"], "name": s["name"],
            "lat": s["lat"], "lng": s["lng"], "distance_km": round(dist, 2),
            "eta_min": eta, "eta_clock": fmt_hhmm(now_min + eta), "planned_start": s["start_time"],
        }
    return {"arrived": arrived, "next": nxt, "delay_min": delay, "done": len(done), "total": len(stops)}


def shift_schedule(stops: list[dict], from_index: int, delay_min: int, day_end: int = DAY_END) -> dict:
    """Push the remaining stops later by the delay (rounded up to 5 minutes)."""
    if delay_min <= 0:
        return {"changes": [], "at_risk": [], "shift_min": 0}
    shift = int(math.ceil(delay_min / 5.0) * 5)
    changes, at_risk = [], []
    for i in range(from_index, len(stops)):
        if stops[i].get("visited_at"):
            continue
        start = parse_hhmm(stops[i]["start_time"]) + shift
        changes.append({"index": i, "start_time": fmt_hhmm(start)})
        if start + stops[i]["duration_min"] > day_end:
            at_risk.append(i)
    return {"changes": changes, "at_risk": at_risk, "shift_min": shift}


def rank_suggestions(
    lat: float, lng: float, candidates: list[dict], *, interests: list[str],
    wet: bool, remaining_min: int | None, speed_kmh: float, detour: float, limit: int = 3,
) -> list[dict]:
    """Score nearby places on distance, interests and weather. Deterministic."""
    scored = []
    for p in candidates:
        d = haversine_km(lat, lng, p["lat"], p["lng"])
        if d > 25:
            continue
        travel = travel_minutes(d, speed_kmh, detour)
        if remaining_min is not None and travel + p["avg_visit_minutes"] > remaining_min:
            continue
        interest = p["category"] in interests
        weather_fit = 1.0 if not wet else (1.0 if p.get("indoor") else 0.2)
        score = 0.4 * math.exp(-d / 5) + 0.35 * (1.0 if interest else 0.3) + 0.15 * weather_fit + 0.10
        reasons = [f"{d:.1f} km away"]
        if wet and p.get("indoor"):
            reasons.append("indoors, good for wet weather")
        if interest:
            reasons.append("matches your interests")
        scored.append(
            {
                "place_id": p["_id"], "name": p["name"], "category": p["category"],
                "lat": p["lat"], "lng": p["lng"], "distance_km": round(d, 2),
                "eta_min": travel, "visit_min": p["avg_visit_minutes"],
                "score": round(score, 3), "reason": ", ".join(reasons),
            }
        )
    scored.sort(key=lambda s: (-s["score"], s["distance_km"], s["name"]))
    return scored[:limit]
