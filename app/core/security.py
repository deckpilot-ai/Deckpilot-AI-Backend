"""Security utilities: JWT tokens, password hashing, cookie helpers."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import settings

_ph = PasswordHasher()

# ---------------------------------------------------------------------------
# Password hashing (argon2)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return an argon2id hash of the plaintext password."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against its stored argon2id hash."""
    try:
        return _ph.verify(hashed, plain)
    except VerificationError:
        return False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    payload = {
        "sub": user_id,
        "role": role,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

AUTH_COOKIE_NAME = "deckpilotai_token"

COOKIE_PARAMS = {
    "key": AUTH_COOKIE_NAME,
    "httponly": True,
    "samesite": "none" if settings.is_secure_environment else "lax",
    "secure": settings.is_secure_environment,
    "max_age": settings.jwt_expire_minutes * 60,
    "path": "/",
}
