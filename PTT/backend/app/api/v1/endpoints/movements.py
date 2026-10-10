from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.core.security import verify_password
from app.models.item import Item, ItemStatus
from app.models.location import Location
from app.models.movement import AuthMethod, Movement, MovementStatus
from app.models.user import User
from app.schemas.auth import MovementAuthorizationRequest
from app.schemas.movement import MovementCreate, MovementOptions, MovementRead
from app.services.audit_service import record_audit

router = APIRouter()


@router.get("", response_model=list[MovementRead], dependencies=[Depends(get_current_user)])
def list_movements(db: Session = Depends(get_db)) -> list[Movement]:
    return db.query(Movement).order_by(Movement.created_at.desc()).all()


@router.get("/options", response_model=MovementOptions, dependencies=[Depends(get_current_user)])
def movement_options(db: Session = Depends(get_db)) -> MovementOptions:
    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.full_name).all()
    locations = db.query(Location).order_by(Location.name).all()
    return MovementOptions(
        users=[{"id": user.id, "name": user.full_name} for user in users],
        locations=[{"id": location.id, "name": location.name} for location in locations],
    )


@router.post(
    "",
    response_model=MovementRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("administrador", "encargado_inventario"))],
)
def create_movement(
    payload: MovementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Movement:
    item = db.query(Item).filter(Item.id == payload.item_id).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Articulo no encontrado")
    if item.status not in (ItemStatus.DISPONIBLE, ItemStatus.DEVUELTA):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El item no esta disponible")
    if db.query(Movement).filter(
        Movement.item_id == item.id,
        Movement.status.in_([MovementStatus.PENDING_AUTHORIZATION, MovementStatus.OPEN]),
    ).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El articulo ya tiene una salida pendiente")

    responsible = db.get(User, payload.responsible_user_id)
    if responsible is None or not responsible.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Responsable inexistente o inactivo")
    if db.get(Location, payload.location_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ubicacion no registrada")

    movement = Movement(
        item_id=payload.item_id,
        responsible_user_id=payload.responsible_user_id,
        location_id=payload.location_id,
        purpose=payload.purpose,
        status=MovementStatus.PENDING_AUTHORIZATION,
    )
    db.add(movement)
    try:
        db.flush()
        record_audit(
            db, user_id=current_user.id, action="movement.create", entity_type="movement", entity_id=movement.id,
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(movement)
    return movement


@router.post(
    "/{movement_id}/authorize",
    response_model=MovementRead,
    dependencies=[Depends(require_roles("administrador", "encargado_inventario", "jefe_area"))],
)
def authorize_movement(
    movement_id: int, payload: MovementAuthorizationRequest, db: Session = Depends(get_db)
) -> Movement:
    """Autoriza la salida con contrasena de un jefe de area; huella pendiente de integracion segura."""
    if payload.method == "fingerprint":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verificacion biometrica no disponible")

    movement = db.query(Movement).filter(Movement.id == movement_id).with_for_update().first()
    if movement is None or movement.status != MovementStatus.PENDING_AUTHORIZATION:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Movimiento no valido para autorizar")

    authorizer: User | None = None

    if payload.method == "password":
        candidate = db.query(User).filter(User.username == payload.username).first()
        if candidate is not None and candidate.is_active and verify_password(payload.password or "", candidate.hashed_password):
            authorizer = candidate
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Metodo de autorizacion invalido")

    if authorizer is None or not authorizer.is_active or authorizer.role.name != "jefe_area":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un jefe de area puede autorizar la salida")

    movement.authorized_by_user_id = authorizer.id
    movement.auth_method = AuthMethod.FINGERPRINT if payload.method == "fingerprint" else AuthMethod.PASSWORD
    movement.status = MovementStatus.OPEN
    movement.checkout_at = datetime.now(timezone.utc)

    item = db.query(Item).filter(Item.id == movement.item_id).with_for_update().first()
    item.status = ItemStatus.EN_USO

    record_audit(
        db, user_id=authorizer.id, action="movement.authorize", entity_type="movement", entity_id=movement.id,
        commit=False,
    )
    db.commit()
    db.refresh(movement)
    return movement


@router.post(
    "/{movement_id}/return",
    response_model=MovementRead,
    dependencies=[Depends(require_roles("administrador", "encargado_inventario"))],
)
def return_movement(
    movement_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Movement:
    movement = db.query(Movement).filter(Movement.id == movement_id).with_for_update().first()
    if movement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimiento no encontrado")
    if movement.status != MovementStatus.OPEN:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El movimiento no esta abierto")

    item = db.query(Item).filter(Item.id == movement.item_id).with_for_update().first()
    if item is None or item.status != ItemStatus.EN_USO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El estado del articulo no permite la devolucion")

    movement.status = MovementStatus.CLOSED
    movement.checkin_at = datetime.now(timezone.utc)
    item.status = ItemStatus.DEVUELTA
    record_audit(
        db, user_id=current_user.id, action="movement.return", entity_type="movement", entity_id=movement.id,
        commit=False,
    )
    db.commit()
    db.refresh(movement)
    return movement
