"""Turns an ordered list of stops into clock times. Pure functions, no I/O."""

from app.core.geo import haversine_km, parse_hhmm, travel_minutes

LUNCH_START = 12 * 60 + 30
LUNCH_END = 13 * 60 + 30
DAY_END = 21 * 60 + 30
START_MIN, START_MAX, START_DEFAULT = 7 * 60, 11 * 60, 9 * 60


def clamp_start(hhmm: str | None) -> int:
    try:
        value = parse_hhmm(hhmm) if hhmm else START_DEFAULT
    except (ValueError, AttributeError):
        value = START_DEFAULT
    return max(START_MIN, min(START_MAX, value))


def schedule_stops(
    stops: list[dict], start_min: int, speed_kmh: float, detour: float = 1.3, day_end: int = DAY_END
) -> list[tuple[int, int]]:
    """Return (start, end) minutes for as many stops as fit in the day (at least one).

    Each stop needs lat, lng and duration_min. Travel time between stops comes from
    straight-line distance with a detour factor, and a lunch window is skipped.
    """
    slots: list[tuple[int, int]] = []
    cur = start_min
    prev = None
    for s in stops:
        if prev is not None:
            cur += travel_minutes(haversine_km(prev["lat"], prev["lng"], s["lat"], s["lng"]), speed_kmh, detour)
        if LUNCH_START <= cur < LUNCH_END:
            cur = LUNCH_END
        end = cur + s["duration_min"]
        if slots and end > day_end:
            break
        slots.append((cur, end))
        cur, prev = end, s
    return slots


def day_distance_km(stops: list[dict]) -> float:
    return sum(
        haversine_km(a["lat"], a["lng"], b["lat"], b["lng"]) for a, b in zip(stops, stops[1:])
    )
