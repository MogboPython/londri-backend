import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
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

