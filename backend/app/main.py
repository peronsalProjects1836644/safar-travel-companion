"""Application factory.

Run locally:  uvicorn app.main:app --reload
On a small host use ONE worker (the rate limiter and geocoder throttle live in memory).
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api import admin, ai, auth, companion, info, places, safety, trips
from app.core.config import Settings, get_settings
from app.core.deps import limit_ip
from app.core.errors import register_handlers
from app.core.ratelimit import RateLimiter
from app.db import ensure_indexes
from app.services import auth as auth_svc
from app.services.ai import AIService
from app.services.geocode import Geocoder

log = logging.getLogger("app")


def create_app(settings: Settings | None = None, *, db=None, openai_client=None, http_client=None) -> FastAPI:
    """`db`, `openai_client` and `http_client` can be injected (used by the tests)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mongo = None
        if db is None:
            from pymongo import AsyncMongoClient

            mongo = AsyncMongoClient(settings.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=8000)
            app.state.db = mongo[settings.mongodb_db]
        else:
            app.state.db = db
        await ensure_indexes(app.state.db)
        await auth_svc.seed_admin(app.state.db, settings)

        own_http = http_client is None
        app.state.http = http_client or httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent},
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )
        client = openai_client
        if client is None and settings.openai_api_key:
            from openai import AsyncOpenAI  # imported lazily to keep start-up light

            client = AsyncOpenAI(
                api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds, max_retries=1
            )
        app.state.ai = AIService(client, settings)
        app.state.geocoder = Geocoder(app.state.http, settings)
        app.state.limiter = RateLimiter()
        if not settings.openai_api_key and openai_client is None:
            log.warning("OPENAI_API_KEY is not set: trips use the standard planner and chat is off.")
        yield
        if own_http:
            await app.state.http.aclose()
        if mongo is not None:
            await mongo.close()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Backend for the AI-powered smart tour and live travel companion.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    register_handlers(app)

    app.add_middleware(GZipMiddleware, minimum_size=800)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    @app.middleware("http")
    async def request_meta(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - started) * 1000:.0f}"
        return response

    api = APIRouter(prefix="/api/v1", dependencies=[Depends(limit_ip("api", 240, 60))])
    for module in (auth, places, info, safety, trips, ai, companion, admin):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["system"])
    async def ready(request: Request):
        await request.app.state.db.command("ping")
        return {"status": "ready"}

    @app.get("/", include_in_schema=False)
    async def root():
        return {"name": settings.app_name, "docs": "/docs", "health": "/health"}

    return app
