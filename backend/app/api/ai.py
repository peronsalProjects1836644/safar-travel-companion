import hashlib
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.core.deps import current_user, get_db, get_settings_dep, limit_user
from app.core.errors import AppError
from app.models.companion import ChatIn
from app.repositories import trips as trips_repo
from app.services import chat as chat_svc
from app.services import usage
from app.services.ai import AIUnavailable

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
async def ai_status(
    request: Request, user: dict = Depends(current_user), db=Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
):
    ai = request.app.state.ai
    return {
        "available": ai.available,
        "model": settings.openai_model if ai.available else None,
        "remaining_today": await usage.remaining_today(db, settings, str(user["_id"])),
    }


@router.post("/chat", dependencies=[Depends(limit_user("chat", 20, 60))])
async def chat(
    body: ChatIn, request: Request,
    user: dict = Depends(current_user), db=Depends(get_db), settings: Settings = Depends(get_settings_dep),
):
    """Streams the assistant's answer as server-sent events: {"delta": "..."} then [DONE]."""
    ai = request.app.state.ai
    if not ai.available:
        raise AppError(503, "ai_unavailable", "The AI assistant is not available right now.")
    if body.messages[-1].role != "user":
        raise AppError(422, "invalid_messages", "The last message must be from the user.")
    trip = None
    if body.trip_id:
        trip = await trips_repo.get_owned(db, body.trip_id, str(user["_id"]))
    await usage.consume(db, settings, str(user["_id"]))
    context = await chat_svc.build_context(db, trip, body.messages[-1].content)
    tag = hashlib.sha256(str(user["_id"]).encode()).hexdigest()[:16]
    messages = [m.model_dump() for m in body.messages]

    async def events():
        try:
            async for piece in ai.chat_stream(context, messages, tag):
                yield f"data: {json.dumps({'delta': piece})}\n\n"
            yield "data: [DONE]\n\n"
        except AIUnavailable:
            msg = {"message": "The assistant is unavailable right now. Please try again."}
            yield f"event: error\ndata: {json.dumps(msg)}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
