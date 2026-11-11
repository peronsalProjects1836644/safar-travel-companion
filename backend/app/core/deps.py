"""FastAPI dependencies: database, settings, authentication, rate limits."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import HTTPConnection

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import decode_token
from app.repositories import users as users_repo

_bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    return request.app.state.db


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def client_ip(request: HTTPConnection, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # With one trusted proxy, the last entry is the address that proxy saw.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


async def authenticate_token(db, settings: Settings, token: str) -> dict:
    payload = decode_token(settings.jwt_secret, token, "access")
    user = await users_repo.get_by_id(db, payload["sub"])
    if not user:
        raise AppError(401, "invalid_token", "Invalid authentication token.")
    if user.get("disabled"):
        raise AppError(403, "account_disabled", "This account has been disabled.")
    return user


async def current_user(
    request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> dict:
    if creds is None:
        raise AppError(
            401, "not_authenticated", "Please sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await authenticate_token(request.app.state.db, request.app.state.settings, creds.credentials)


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise AppError(403, "forbidden", "Administrator access is required.")
    return user


def _check(request: HTTPConnection, key: str, limit: int, window_s: float) -> None:
    ok, retry = request.app.state.limiter.allow(key, limit, window_s)
    if not ok:
        raise AppError(
            429, "rate_limited", "Too many requests. Please slow down and try again shortly.",
            headers={"Retry-After": str(int(retry) + 1)},
        )


def limit_ip(name: str, limit: int, window_s: float):
    async def dep(request: HTTPConnection) -> None:
        ip = client_ip(request, request.app.state.settings.trust_proxy)
        _check(request, f"{name}:ip:{ip}", limit, window_s)

    return dep


def limit_user(name: str, limit: int, window_s: float):
    async def dep(request: Request, user: dict = Depends(current_user)) -> None:
        _check(request, f"{name}:user:{user['_id']}", limit, window_s)

    return dep
