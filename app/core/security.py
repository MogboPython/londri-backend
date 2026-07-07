import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as redis
from jose import jwt
from passlib.context import CryptContext

from .config import settings

BLACKLISTED_JTI_PREFIX = "blacklisted_jti:"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def _create_token(data: dict[str, Any], expires_delta: timedelta, jti: str | None = None) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    if jti is not None:
        payload["jti"] = jti
    else:
        payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        {"sub": subject, "role": role, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str, role: str) -> str:
    return _create_token(
        {"sub": subject, "role": role, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def compute_token_ttl(payload: dict[str, Any]) -> int:
    """Return remaining seconds until token expiry.  Returns 0 if already expired."""
    exp = payload.get("exp")
    if exp is None:
        return 0
    remaining = int(exp - datetime.now(timezone.utc).timestamp())
    return max(remaining, 0)


async def blacklist_token_jti(jti: str, ttl: int, redis_client: redis.Redis) -> None:
    """Store a JTI in Redis so it's recognised as revoked."""
    if ttl <= 0:
        return
    key = f"{BLACKLISTED_JTI_PREFIX}{jti}"
    await redis_client.setex(key, ttl, "1")


async def is_jti_blacklisted(jti: str, redis_client: redis.Redis) -> bool:
    """Return True if the JTI has been blacklisted."""
    key = f"{BLACKLISTED_JTI_PREFIX}{jti}"
    return await redis_client.exists(key) == 1

def decode_token(token: str) -> dict[str, Any]:
    """Raises JWTError on invalid/expired tokens."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

def generate_otp(length: int = 6) -> str:
    """Cryptographically-secure numeric OTP."""
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])

# def encrypt_password(self, password):
#     key = self.key
#     encrypt_key = key.encode()
#     encrypted_pass = Fernet(encrypt_key).encrypt(password.encode())
#     encrypted_pass = encrypted_pass.decode()
#     return key, encrypted_pass
# def decrypt_password(self, encrypted):
#     key = self.key
#     key = key.encode()
#     password = encrypted.encode()
#     decrypted_pass = Fernet(key).decrypt(password)
#     return decrypted_pass.decode()

