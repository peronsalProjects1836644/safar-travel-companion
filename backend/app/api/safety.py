from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.core.config import Settings
from app.core.deps import current_user, get_db, get_settings_dep, limit_user
from app.models.companion import SosIn
from app.services import safety as svc
from app.services.emergency import EMERGENCY_NUMBERS

router = APIRouter(prefix="/safety", tags=["safety"])


@router.get("/emergency-numbers")
async def emergency_numbers():
    return EMERGENCY_NUMBERS


@router.get("/nearby")
async def nearby(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    kind: Literal["hospital", "police", "pharmacy"] = "hospital",
    radius_m: int = Query(5000, ge=500, le=20000),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
):
    return await svc.nearby_help(request.app.state.http, db, settings, lat, lng, kind, radius_m)


@router.post("/sos", dependencies=[Depends(limit_user("sos", 10, 60))])
async def sos(body: SosIn, user: dict = Depends(current_user), db=Depends(get_db)):
    """Returns ready-made WhatsApp links with the user's location for each emergency contact."""
    return await svc.create_sos(db, user, body.lat, body.lng, body.note)
