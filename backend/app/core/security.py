"""Password hashing and JWT helpers."""

from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.errors import AppError
from app.core.timeutil import utcnow

# Memory-conscious Argon2id settings (OWASP minimum profile: 19 MiB, t=2, p=1)
# so a small free instance is not stressed by a few simultaneous logins.
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_DUMMY_HASH = _hasher.hash("timing-equaliser-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy(password: str) -> None:
    """Burn the same time as a real check so unknown emails are not detectable."""
    verify_password(_DUMMY_HASH, password)


def create_token(secret: str, subject: str, role: str, token_type: str, lifetime: timedelta) -> str:
    now = utcnow()
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(secret: str, token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError:
        raise AppError(401, "token_expired", "Your session has expired. Please sign in again.") from None
    except jwt.PyJWTError:
        raise AppError(401, "invalid_token", "Invalid authentication token.") from None
    if payload.get("type") != expected_type:
        raise AppError(401, "invalid_token", "Invalid authentication token.")
    return payload
