from fastapi import APIRouter, Depends, Query

from app.core.deps import get_db, require_admin
from app.core.errors import AppError
from app.models.common import APIModel
from app.models.place import PlaceBase, PlaceCreate, PlaceOut
from app.repositories import trips as trips_repo
from app.repositories import users as users_repo
from app.services import places as places_svc
from app.services import usage

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class UserFlag(APIModel):
    disabled: bool


@router.get("/stats")
async def stats(db=Depends(get_db)):
    return {
        "users": await users_repo.count(db),
        "trips": await trips_repo.count(db),
        "places": await db.places.count_documents({}),
        "active_shares": await db.shares.count_documents({}),
        "ai_calls_today": await usage.global_today(db),
        "trips_by_source": {
            "ai": await db.trips.count_documents({"source": "ai"}),
            "rules": await db.trips.count_documents({"source": "rules"}),
        },
    }


@router.get("/users")
async def list_users(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db=Depends(get_db)):
    rows = await users_repo.list_users(db, limit, offset)
    return [
        {
            "id": str(r["_id"]), "email": r["email"], "name": r["name"], "role": r.get("role", "user"),
            "disabled": bool(r.get("disabled")), "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.patch("/users/{user_id}")
async def set_user_disabled(user_id: str, body: UserFlag, admin: dict = Depends(require_admin), db=Depends(get_db)):
    if user_id == str(admin["_id"]):
        raise AppError(422, "cannot_disable_self", "You cannot disable your own account.")
    updated = await users_repo.update(db, user_id, {"disabled": body.disabled})
    if not updated:
        raise AppError(404, "user_not_found", "User not found.")
    return {"id": user_id, "disabled": body.disabled}


@router.post("/places", response_model=PlaceOut, status_code=201)
async def create_place(body: PlaceCreate, db=Depends(get_db)):
    return places_svc.to_out(await places_svc.create_place(db, body, body.id))


@router.put("/places/{place_id}", response_model=PlaceOut)
async def replace_place(place_id: str, body: PlaceBase, db=Depends(get_db)):
    return places_svc.to_out(await places_svc.replace_place(db, place_id, body))


@router.delete("/places/{place_id}", status_code=204)
async def delete_place(place_id: str, db=Depends(get_db)):
    await places_svc.delete_place(db, place_id)
