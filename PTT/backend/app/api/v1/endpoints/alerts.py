from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, require_roles
from app.core.security import verify_password
from app.models.alert import Alert, AlertStatus, DeactivationMethod
from app.models.user import User
from app.schemas.alert import AlertDeactivateRequest, AlertRead
from app.services.audit_service import record_audit

router = APIRouter()


@router.get("", response_model=list[AlertRead], dependencies=[Depends(get_current_user)])
def list_alerts(db: Session = Depends(get_db)) -> list[Alert]:
    return (
        db.query(Alert)
        .options(selectinload(Alert.item), selectinload(Alert.device), selectinload(Alert.resolved_by))
        .order_by(Alert.triggered_at.desc())
        .all()
    )


@router.post(
    "/{alert_id}/deactivate",
    response_model=AlertRead,
    dependencies=[Depends(require_roles("administrador"))],
)
def deactivate_alert(alert_id: int, payload: AlertDeactivateRequest, db: Session = Depends(get_db)) -> Alert:
    """Solo el administrador puede desactivar una alarma; huella pendiente de integracion segura."""
    if payload.method == DeactivationMethod.FINGERPRINT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verificacion biometrica no disponible")

    alert = db.query(Alert).filter(Alert.id == alert_id).with_for_update().first()
    if alert is None or alert.status != AlertStatus.ACTIVA:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Alerta no valida")

    admin: User | None = None
    candidate = db.query(User).filter(User.username == payload.username).first()
    if candidate is not None and candidate.is_active and verify_password(payload.password or "", candidate.hashed_password):
        admin = candidate

    if admin is None or admin.role.name != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un administrador puede desactivar la alarma")

    alert.status = AlertStatus.RESUELTA
    alert.resolved_by_user_id = admin.id
    alert.resolved_at = datetime.now(timezone.utc)
    alert.deactivation_method = payload.method
    alert.resolution_notes = payload.resolution_notes

    record_audit(
        db, user_id=admin.id, action="alert.deactivate", entity_type="alert", entity_id=alert.id, commit=False
    )
    db.commit()
    db.refresh(alert)
    return alert
