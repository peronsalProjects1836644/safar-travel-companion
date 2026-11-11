"""Weather and place search (geocoding) endpoints."""

from fastapi import APIRouter, Depends, Query, Request

from app.core.config import Settings
from app.core.deps import current_user, get_db, get_settings_dep, limit_user
from app.services import weather as weather_svc

router = APIRouter(tags=["info"])


@router.get("/weather")
async def weather(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    days: int = Query(3, ge=1, le=7),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
):
    return await weather_svc.get_weather(request.app.state.http, db, settings, lat, lng, days)


@router.get("/geocode/search", dependencies=[Depends(limit_user("geocode", 20, 60))])
async def geocode_search(
    request: Request,
    q: str = Query(..., min_length=3, max_length=100),
    db=Depends(get_db),
    _user: dict = Depends(current_user),
):
    """Explicit search only. Typing suggestions come from /places/suggest instead."""
    return await request.app.state.geocoder.search(db, q)
