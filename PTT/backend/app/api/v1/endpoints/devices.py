import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.security import encrypt_device_secret
from app.core.zero_trust import verify_device_request
from app.models.device import Device
from app.models.item import Item, ItemStatus
from app.models.movement import Movement, MovementStatus
from app.models.rfid_event import RfidEvent, RfidEventType
from app.schemas.device import DeviceRegisterRequest, DeviceRegisterResponse, RfidEventIn
from app.services.alert_service import raise_unauthorized_exit_alert

router = APIRouter()


@router.post(
    "/register",
    response_model=DeviceRegisterResponse,
    dependencies=[Depends(require_roles("administrador"))],
)
def register_device(payload: DeviceRegisterRequest, db: Session = Depends(get_db)) -> DeviceRegisterResponse:
    """Aprovisionamiento manual por el administrador; el secreto se muestra una sola vez."""
    raw_secret = secrets.token_urlsafe(32)
    device = Device(
        device_uid=payload.device_uid,
        type=payload.type,
        location_id=payload.location_id,
        secret_encrypted=encrypt_device_secret(raw_secret),
    )
    db.add(device)
    db.commit()
    return DeviceRegisterResponse(device_uid=device.device_uid, shared_secret=raw_secret)


@router.post("/events/rfid", status_code=status.HTTP_202_ACCEPTED)
def ingest_rfid_event(
    payload: RfidEventIn, db: Session = Depends(get_db), device: Device = Depends(verify_device_request)
) -> dict:
    event = RfidEvent(device_id=device.id, tag_code=payload.tag_code, event_type=RfidEventType(payload.event_type))
    db.add(event)
    db.flush()

    open_movement = (
        db.query(Movement)
        .join(Item, Movement.item_id == Item.id)
        .filter(Movement.status == MovementStatus.OPEN, Item.rfid_tag == payload.tag_code)
        .first()
    )

    if payload.event_type == "salida" and open_movement is None:
        raise_unauthorized_exit_alert(db, device=device, tag_code=payload.tag_code)
    elif payload.event_type == "entrada" and open_movement is not None:
        open_movement.status = MovementStatus.CLOSED
        open_movement.checkin_at = datetime.now(timezone.utc)
        open_movement.item.status = ItemStatus.DEVUELTA
        event.movement_id = open_movement.id

    event.processed = True
    db.commit()
    return {"status": "processed"}
