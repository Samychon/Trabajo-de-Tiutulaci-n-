from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertType
from app.models.device import Device
from app.models.item import Item
from app.services.audit_service import record_audit
from app.ws.connection_manager import alert_manager


def raise_unauthorized_exit_alert(db: Session, *, device: Device, tag_code: str) -> Alert:
    item = db.query(Item).filter(Item.rfid_tag == tag_code).first()

    alert = Alert(type=AlertType.SALIDA_NO_AUTORIZADA, item_id=item.id if item else None, device_id=device.id)
    db.add(alert)
    db.flush()
    record_audit(
        db, device_id=device.id, action="alert.trigger", entity_type="alert", entity_id=alert.id, commit=False
    )
    db.commit()
    db.refresh(alert)

    alert_manager.broadcast_sync({"type": "alert", "alert_id": alert.id, "item_id": alert.item_id})
    return alert
