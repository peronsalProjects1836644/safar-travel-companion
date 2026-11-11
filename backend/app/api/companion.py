"""Live Travel Companion: WebSocket, a REST fallback, and expiring share links."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import Settings
from app.core.deps import authenticate_token, current_user, get_db, get_settings_dep, limit_ip, limit_user
from app.core.errors import AppError
from app.models.companion import LocationIn, ShareCreate, ShareOut
from app.services import companion as svc

log = logging.getLogger("app.companion.ws")
router = APIRouter(tags=["companion"])

IDLE_TIMEOUT_S = 120
MAX_MESSAGE_CHARS = 2000


@router.websocket("/ws/companion")
async def companion_ws(ws: WebSocket):
    """Protocol: send {"type":"auth","token":"<access token>"}, then {"type":"location","lat":..,"lng":..}."""
    await ws.accept()
    db, settings, http = ws.app.state.db, ws.app.state.settings, ws.app.state.http
    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=10))
        if first.get("type") != "auth":
            raise AppError(401, "not_authenticated", "Send an auth message first.")
        user = await authenticate_token(db, settings, str(first.get("token", "")))
        tracker = await svc.Tracker.for_user(db, settings, http, user)
    except AppError as exc:
        await ws.send_json({"type": "error", "code": exc.code, "message": exc.message})
        await ws.close(code=4404 if exc.code == "no_active_trip" else 4401)
        return
    except (TimeoutError, ValueError, WebSocketDisconnect, AttributeError):
        await _safe_close(ws, 4401)
        return

    await ws.send_json({"type": "ready", "trip_id": str(tracker.trip["_id"]), "day": tracker.day_idx + 1})
    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=IDLE_TIMEOUT_S)
            except TimeoutError:
                await ws.send_json({"type": "idle"})
                await ws.close(code=1000)
                return
            if len(raw) > MAX_MESSAGE_CHARS:
                await ws.send_json({"type": "error", "code": "message_too_large", "message": "Message too large."})
                continue
            try:
                msg = json.loads(raw)
                kind = msg.get("type")
            except (ValueError, AttributeError):
                await ws.send_json({"type": "error", "code": "bad_message", "message": "Invalid message."})
                continue
            if kind == "ping":
                await ws.send_json({"type": "pong"})
            elif kind == "reload":
                tracker = await svc.Tracker.for_user(db, settings, http, user)
                await ws.send_json({"type": "ready", "trip_id": str(tracker.trip["_id"]), "day": tracker.day_idx + 1})
            elif kind == "location":
                try:
                    loc = LocationIn.model_validate({k: v for k, v in msg.items() if k != "type"})
                except ValidationError:
                    await ws.send_json({"type": "error", "code": "bad_location", "message": "Invalid location."})
                    continue
                try:
                    await ws.send_json(await tracker.update(loc.lat, loc.lng, loc.accuracy_m))
                except AppError as exc:
                    await ws.send_json({"type": "error", "code": exc.code, "message": exc.message})
            else:
                await ws.send_json({"type": "error", "code": "unknown_type", "message": "Unknown message type."})
    except WebSocketDisconnect:
        return
    except Exception:
        log.exception("Companion websocket failed")
        await _safe_close(ws, 1011)


async def _safe_close(ws: WebSocket, code: int) -> None:
    try:
        await ws.close(code=code)
    except RuntimeError:
        pass


@router.post("/companion/location", dependencies=[Depends(limit_user("loc", 30, 60))])
async def post_location(
    body: LocationIn, request: Request,
    user: dict = Depends(current_user), db=Depends(get_db), settings: Settings = Depends(get_settings_dep),
):
    """REST fallback for networks where WebSockets are blocked."""
    tracker = await svc.Tracker.for_user(db, settings, request.app.state.http, user)
    return await tracker.update(body.lat, body.lng, body.accuracy_m)


@router.post("/share", response_model=ShareOut, status_code=201, dependencies=[Depends(limit_user("share", 10, 3600))])
async def create_share(
    body: ShareCreate, user: dict = Depends(current_user), db=Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
):
    return await svc.create_share(db, settings, user, body.hours)


@router.get("/share/{token}", dependencies=[Depends(limit_ip("share-read", 60, 60))])
async def read_share(token: str, db=Depends(get_db)):
    """Public, read-only. Shows first name, trip title and the latest position only."""
    return await svc.read_share(db, token)


@router.delete("/share/{token}", status_code=204)
async def revoke_share(token: str, user: dict = Depends(current_user), db=Depends(get_db)):
    await svc.revoke_share(db, user, token)
