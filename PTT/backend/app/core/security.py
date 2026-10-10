from datetime import datetime, timedelta, timezone
from typing import Any
import hashlib
import hmac

from cryptography.fernet import Fernet
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, expires_delta: timedelta, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {"sub": subject, "iat": now, "exp": now + expires_delta}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        {"type": "access", "role": role},
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES), {"type": "refresh"})


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("Token invalido o expirado") from exc


def _fernet() -> Fernet:
    return Fernet(settings.DEVICE_SECRET_ENCRYPTION_KEY.encode())


def encrypt_device_secret(raw_secret: str) -> str:
    return _fernet().encrypt(raw_secret.encode()).decode()


def decrypt_device_secret(encrypted_secret: str) -> str:
    return _fernet().decrypt(encrypted_secret.encode()).decode()


def device_request_message(device_id: str, timestamp: str, nonce: str, method: str, path: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    return f"{device_id}.{timestamp}.{nonce}.{method}.{path}.{body_hash}"


def sign_device_payload(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_device_signature(secret: str, message: str, signature: str) -> bool:
    expected = sign_device_payload(secret, message)
    return hmac.compare_digest(expected, signature)
