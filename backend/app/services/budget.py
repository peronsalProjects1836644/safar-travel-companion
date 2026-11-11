"""Budget estimate computed in code from a transparent cost model (never by the AI)."""

import json
import math
from functools import lru_cache
from pathlib import Path

_MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "cost_model.json"


@lru_cache
def cost_model() -> dict:
    return json.loads(_MODEL_PATH.read_text(encoding="utf-8"))


def estimate(
    itinerary: list[dict], days: int, travelers: int, level: str, budget_total: int | None = None
) -> dict:
    m = cost_model()
    rooms = math.ceil(travelers / m["people_per_room"])
    vehicles = math.ceil(travelers / m["people_per_vehicle"])
    nights = max(days - 1, 0)
    entry_rates = m["entry_per_person_by_price_level"]
    entries = sum(
        entry_rates[str(min(max(s.get("price_level", 0), 0), 3))]
        for day in itinerary
        for s in day["stops"]
    ) * travelers
    breakdown = {
        "accommodation": rooms * nights * m["accommodation_per_room_night"][level],
        "food": travelers * days * m["food_per_person_day"][level],
        "local_transport": vehicles * days * m["transport_per_vehicle_day"][level],
        "entry_fees": entries,
    }
    total = sum(breakdown.values())
    spread = m["uncertainty"]
    low, high = round(total * (1 - spread)), round(total * (1 + spread))
    fit = None
    if budget_total:
        fit = "within" if high <= budget_total else "over" if low > budget_total else "borderline"
    return {
        "currency": "PKR",
        "low": low,
        "high": high,
        "total": total,
        "per_person": round(total / travelers),
        "breakdown": breakdown,
        "fit": fit,
        "note": "Rough estimate for the whole group. It does not include travel to the destination.",
    }
