from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import get_db
from app.models.common import CATEGORIES, Category
from app.models.place import DestinationOut, PlaceList, PlaceOut
from app.services import places as svc
from app.services.emergency import EMERGENCY_NUMBERS

router = APIRouter(tags=["places"])

_CACHE = "public, max-age=60"


@router.get("/meta")
async def meta():
    """Static choices for forms, so the frontend never hard-codes them."""
    return {
        "categories": list(CATEGORIES),
        "budget_levels": ["budget", "mid", "premium"],
        "paces": ["relaxed", "balanced", "packed"],
        "seasons": ["winter", "spring", "summer", "autumn"],
        "limits": {"max_days": 7, "max_travelers": 20, "max_interests": 6, "max_emergency_contacts": 5},
        "emergency_numbers": EMERGENCY_NUMBERS,
    }


@router.get("/destinations", response_model=list[DestinationOut])
async def destinations(response: Response, db=Depends(get_db)):
    response.headers["Cache-Control"] = _CACHE
    return await svc.destinations(db)


@router.get("/places", response_model=PlaceList)
async def list_places(
    response: Response,
    destination: str | None = Query(None, max_length=80),
    category: Category | None = None,
    q: str | None = Query(None, max_length=80),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    response.headers["Cache-Control"] = _CACHE
    docs, total = await svc.list_places(
        db, destination=destination, category=category, q=q, limit=limit, offset=offset
    )
    return {"items": [svc.to_out(d) for d in docs], "total": total, "limit": limit, "offset": offset}


@router.get("/places/suggest", response_model=list[PlaceOut])
async def suggest(q: str = Query(..., min_length=1, max_length=80), db=Depends(get_db)):
    return [svc.to_out(d) for d in await svc.suggest(db, q)]


@router.get("/places/nearby", response_model=list[PlaceOut])
async def nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, gt=0, le=50),
    category: Category | None = None,
    limit: int = Query(20, ge=1, le=50),
    db=Depends(get_db),
):
    rows = await svc.nearby(db, lat, lng, radius_km, category, limit)
    return [svc.to_out(d, distance_km=dist) for dist, d in rows]


@router.get("/places/{place_id}", response_model=PlaceOut)
async def get_place(place_id: str, response: Response, db=Depends(get_db)):
    response.headers["Cache-Control"] = _CACHE
    return svc.to_out(await svc.get_place(db, place_id))
