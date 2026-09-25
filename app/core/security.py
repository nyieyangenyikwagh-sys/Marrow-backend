from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import jwt
from jwt import InvalidTokenError as JWTError
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from app.core.config import settings

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("timing-equalization-only")


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _token(subject, user_type, kind, lifetime):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(subject), "type": kind, "user_type": user_type,
                       "jti": str(uuid4()), "iat": now, "exp": now + lifetime},
                      settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject, user_type="customer", expires_delta=None):
    return _token(subject, user_type, user_type,
                  expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(subject, user_type="customer"):
    return _token(subject, user_type, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token):
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                         options={"require": ["sub", "type", "user_type", "jti", "exp", "iat"]})
    try:
        UUID(payload["sub"])
    except (ValueError, TypeError):
        raise JWTError("Invalid subject")
    if payload["user_type"] not in ("customer", "admin"):
        raise JWTError("Invalid user type")
    return payload
