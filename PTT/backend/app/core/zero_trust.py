"""Puerta de enlace zero-trust para endpoints de hardware (ESP32/RFID/biometrico).

Ningun dispositivo se considera confiable por estar en la red local: cada
peticion debe traer su identidad (X-Device-Id), una marca de tiempo fresca
(X-Timestamp), un nonce unico (X-Nonce) y una firma HMAC (X-Signature)
que incluya metodo, ruta y cuerpo. Se valida en cada llamada.
"""

import re
import time
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.security import decrypt_device_secret, device_request_message, verify_device_signature
from app.models.device import Device, DeviceRequestNonce, DeviceStatus

settings = get_settings()


async def verify_device_request(
    request: Request,
    x_device_id: str = Header(...),
    x_timestamp: str = Header(...),
    x_signature: str = Header(...),
    x_nonce: str = Header(...),
    db: Session = Depends(get_db),
) -> Device:
    device = db.query(Device).filter(Device.device_uid == x_device_id).first()
    if device is None or device.status != DeviceStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Dispositivo no reconocido o inactivo")

    try:
        ts = int(x_timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Timestamp invalido") from exc

    if abs(time.time() - ts) > settings.DEVICE_TIMESTAMP_TOLERANCE_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Timestamp fuera de rango (posible replay)")

    if re.fullmatch(r"[0-9a-f]{32}", x_nonce) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nonce invalido")

    secret = decrypt_device_secret(device.secret_encrypted)
    message = device_request_message(
        x_device_id, x_timestamp, x_nonce, request.method, request.url.path, await request.body()
    )
    if not verify_device_signature(secret, message, x_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma invalida")

    now = datetime.now(timezone.utc)
    db.query(DeviceRequestNonce).filter(
        DeviceRequestNonce.device_id == device.id, DeviceRequestNonce.expires_at < now
    ).delete(synchronize_session=False)
    db.add(
        DeviceRequestNonce(
            device_id=device.id,
            nonce=x_nonce,
            expires_at=datetime.fromtimestamp(ts + settings.DEVICE_TIMESTAMP_TOLERANCE_SECONDS + 1, timezone.utc),
        )
    )
    device.last_seen_at = now
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Solicitud repetida") from exc

    return device
