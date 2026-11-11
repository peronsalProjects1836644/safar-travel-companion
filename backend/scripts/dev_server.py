"""Runs the API with an in-memory database. No MongoDB or Docker needed.

    python -m scripts.dev_server

Everything is wiped when you stop it (accounts, trips, shares). Places are loaded from
data/places_geocoded.json, so run `python -m scripts.seed_places --geocode` first.
Weather, place search and nearby help use the real internet; OpenAI is used only if OPENAI_API_KEY is set.
Meant for local testing only. Use MongoDB Atlas for anything real.
"""

import argparse
import asyncio
import os
import secrets

import uvicorn

from app.core.config import Settings
from app.main import create_app
from app.services import places as places_svc
from scripts.seed_places import OUT, build_items, load
from tests.fakes import FakeDB

DEV_ADMIN = ("admin@example.com", "AdminPass123")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8010)
    args = ap.parse_args()

    os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(48))
    os.environ.setdefault("ADMIN_EMAIL", DEV_ADMIN[0])
    os.environ.setdefault("ADMIN_PASSWORD", DEV_ADMIN[1])
    settings = Settings()

    db = FakeDB()
    items, skipped = build_items(load(OUT))
    asyncio.run(places_svc.upsert_many(db, items))
    print(f"Loaded {len(items)} places into memory ({len(skipped)} skipped).")
    if not items:
        print("No places yet. Run: python -m scripts.seed_places --geocode")
    print(f"Admin login: {settings.admin_email} / {settings.admin_password}")
    print("AI:", "on" if settings.openai_api_key else "off (no OPENAI_API_KEY, built-in planner is used)")
    uvicorn.run(create_app(settings, db=db), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
