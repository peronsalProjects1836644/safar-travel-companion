import logging
from datetime import timedelta

from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import create_token, decode_token, hash_password, verify_dummy, verify_password
from app.models.user import RegisterIn, TokenPair
from app.repositories import users

log = logging.getLogger("app.auth")


def issue_tokens(settings: Settings, user: dict) -> TokenPair:
    sub, role = str(user["_id"]), user.get("role", "user")
    access = create_token(
        settings.jwt_secret, sub, role, "access", timedelta(minutes=settings.access_token_minutes)
    )
    refresh = create_token(
        settings.jwt_secret, sub, role, "refresh", timedelta(days=settings.refresh_token_days)
    )
    return TokenPair(
        access_token=access, refresh_token=refresh, expires_in=settings.access_token_minutes * 60
    )


async def register(db, data: RegisterIn) -> dict:
    if await users.get_by_email(db, data.email):
        raise AppError(409, "email_taken", "An account with this email already exists.")
    password_hash = await run_in_threadpool(hash_password, data.password)
    try:
        return await users.insert(db, email=data.email, name=data.name, password_hash=password_hash)
    except DuplicateKeyError:
        raise AppError(409, "email_taken", "An account with this email already exists.") from None


async def login(db, email: str, password: str) -> dict:
    user = await users.get_by_email(db, email)
    if not user:
        await run_in_threadpool(verify_dummy, password)
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")
    ok = await run_in_threadpool(verify_password, user["password_hash"], password)
    if not ok:
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")
    if user.get("disabled"):
        raise AppError(403, "account_disabled", "This account has been disabled.")
    return user


async def refresh(db, settings: Settings, refresh_token: str) -> TokenPair:
    payload = decode_token(settings.jwt_secret, refresh_token, "refresh")
    user = await users.get_by_id(db, payload["sub"])
    if not user or user.get("disabled"):
        raise AppError(401, "invalid_token", "Invalid authentication token.")
    return issue_tokens(settings, user)


async def seed_admin(db, settings: Settings) -> None:
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD if it does not exist."""
    if not (settings.admin_email and settings.admin_password):
        return
    if await users.get_by_email(db, settings.admin_email):
        return
    password_hash = await run_in_threadpool(hash_password, settings.admin_password)
    await users.insert(
        db, email=settings.admin_email, name="Administrator", password_hash=password_hash, role="admin"
    )
    log.info("Created admin account %s", settings.admin_email)
