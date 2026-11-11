from fastapi import APIRouter, Depends, Request

from app.core.config import Settings
from app.core.deps import current_user, get_db, get_settings_dep, limit_user
from app.core.errors import AppError
from app.models.trip import PlanRequest, StartTripIn, StopAdd, TripOut, TripPatch, TripSummary
from app.repositories import trips as repo
from app.services import budget as budget_svc
from app.services import companion as companion_svc
from app.services import places as places_svc
from app.services import planner

router = APIRouter(prefix="/trips", tags=["trips"])

MAX_STOPS_PER_DAY = 8


def _recompute(trip: dict) -> None:
    trip["budget"] = budget_svc.estimate(
        trip["itinerary"], trip["days"], trip["travelers"], trip["budget_level"], trip.get("budget_total_pkr")
    )


@router.post("/plan", response_model=TripOut, status_code=201, dependencies=[Depends(limit_user("plan", 6, 600))])
async def plan_trip(
    req: PlanRequest, request: Request,
    user: dict = Depends(current_user), db=Depends(get_db), settings: Settings = Depends(get_settings_dep),
):
    doc, notice = await planner.create_trip(db, settings, request.app.state.ai, user, req)
    doc = await repo.create(db, doc)
    out = repo.to_out(doc)
    out["notice"] = notice
    return out


@router.get("", response_model=list[TripSummary])
async def list_trips(user: dict = Depends(current_user), db=Depends(get_db)):
    return [repo.to_summary(d) for d in await repo.list_for_user(db, str(user["_id"]))]


@router.get("/{trip_id}", response_model=TripOut)
async def get_trip(trip_id: str, user: dict = Depends(current_user), db=Depends(get_db)):
    return repo.to_out(await repo.get_owned(db, trip_id, str(user["_id"])))


@router.patch("/{trip_id}", response_model=TripOut)
async def rename_trip(trip_id: str, body: TripPatch, user: dict = Depends(current_user), db=Depends(get_db)):
    trip = await repo.get_owned(db, trip_id, str(user["_id"]))
    await repo.set_fields(db, trip["_id"], {"title": body.title})
    trip["title"] = body.title
    return repo.to_out(trip)


@router.delete("/{trip_id}", status_code=204)
async def delete_trip(trip_id: str, user: dict = Depends(current_user), db=Depends(get_db)):
    await repo.delete(db, trip_id, str(user["_id"]))


@router.post("/{trip_id}/stops", response_model=TripOut)
async def add_stop(
    trip_id: str, body: StopAdd,
    user: dict = Depends(current_user), db=Depends(get_db), settings: Settings = Depends(get_settings_dep),
):
    trip = await repo.get_owned(db, trip_id, str(user["_id"]))
    if body.day > trip["days"]:
        raise AppError(422, "invalid_day", f"This trip has {trip['days']} days.")
    place = await places_svc.get_place(db, body.place_id)
    if place["destination"].lower() != trip["destination"].lower():
        raise AppError(422, "wrong_destination", "That place is not in this trip's destination.")
    if any(s["place_id"] == place["_id"] for d in trip["itinerary"] for s in d["stops"]):
        raise AppError(409, "already_in_trip", "That place is already part of this trip.")
    day = trip["itinerary"][body.day - 1]
    if len(day["stops"]) >= MAX_STOPS_PER_DAY:
        raise AppError(422, "day_full", f"A day can have at most {MAX_STOPS_PER_DAY} stops.")
    start = 9 * 60
    day["stops"].append(planner._stop_from_place(place, planner.TIPS.get(place["category"], ""), start, start + place["avg_visit_minutes"]))
    planner.reschedule_day(day, settings)
    _recompute(trip)
    await repo.set_fields(db, trip["_id"], {"itinerary": trip["itinerary"], "budget": trip["budget"]})
    return repo.to_out(trip)


@router.delete("/{trip_id}/days/{day}/stops/{index}", response_model=TripOut)
async def remove_stop(
    trip_id: str, day: int, index: int,
    user: dict = Depends(current_user), db=Depends(get_db), settings: Settings = Depends(get_settings_dep),
):
    trip = await repo.get_owned(db, trip_id, str(user["_id"]))
    if not 1 <= day <= trip["days"]:
        raise AppError(422, "invalid_day", f"This trip has {trip['days']} days.")
    stops = trip["itinerary"][day - 1]["stops"]
    if not 0 <= index < len(stops):
        raise AppError(404, "stop_not_found", "Stop not found.")
    if len(stops) == 1:
        raise AppError(422, "day_needs_a_stop", "A day needs at least one stop.")
    stops.pop(index)
    planner.reschedule_day(trip["itinerary"][day - 1], settings)
    _recompute(trip)
    await repo.set_fields(db, trip["_id"], {"itinerary": trip["itinerary"], "budget": trip["budget"]})
    return repo.to_out(trip)


@router.post("/{trip_id}/start", response_model=TripOut)
async def start_trip(
    trip_id: str, body: StartTripIn,
    user: dict = Depends(current_user), db=Depends(get_db), settings: Settings = Depends(get_settings_dep),
):
    return repo.to_out(await companion_svc.start_trip(db, settings, user, trip_id, body.day))


@router.post("/{trip_id}/complete", response_model=TripOut)
async def complete_trip(trip_id: str, user: dict = Depends(current_user), db=Depends(get_db)):
    return repo.to_out(await companion_svc.complete_trip(db, user, trip_id))
