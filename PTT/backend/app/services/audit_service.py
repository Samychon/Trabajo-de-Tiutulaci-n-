from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit(
    db: Session,
    *,
    user_id: int | None = None,
    device_id: int | None = None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    ip_address: str | None = None,
    details: dict | None = None,
    commit: bool = True,
) -> None:
    """Escribe una entrada append-only; permite compartir la transaccion de la operacion."""
    log = AuditLog(
        user_id=user_id,
        device_id=device_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        details=details,
    )
    db.add(log)
    if commit:
        db.commit()
