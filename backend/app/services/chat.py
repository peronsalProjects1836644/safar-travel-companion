"""Builds the grounding context for the chatbot from our own data."""

import re

from app.services import places as places_svc


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


async def build_context(db, trip: dict | None, last_user_text: str, max_places: int = 6) -> str:
    lines: list[str] = []
    destination = trip["destination"] if trip else None
    if trip:
        lines.append(f"The user's trip: {trip['title']} ({trip['destination']}, {trip['days']} days).")
        for day in trip["itinerary"]:
            names = ", ".join(f"{s['name']} at {s['start_time']}" for s in day["stops"])
            lines.append(f"Day {day['day']}: {names}")
    text = last_user_text.lower()
    for d in await places_svc.destinations(db):
        if d["name"].lower() in text:
            destination = d["name"]
            break
    pool = await places_svc.destination_places(db, destination) if destination else []
    if not pool:
        pool = (await db.places.find({}).limit(300).to_list(length=None))
    qwords = _words(last_user_text)

    def overlap(p: dict) -> int:
        return len(qwords & _words(p.get("search_text", "")))

    top = sorted(pool, key=lambda p: (-overlap(p), p["name"]))[:max_places]
    if top:
        lines.append("Known places:")
        for p in top:
            lines.append(f"- {p['name']} ({p['destination']}, {p['category']}): {p.get('description', '')}")
    return "\n".join(lines) if lines else "No extra context."
