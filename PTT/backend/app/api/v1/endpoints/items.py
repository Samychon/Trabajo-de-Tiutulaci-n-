import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, require_roles
from app.core.security import verify_password
from app.models.item import Category, Item, ItemStatus, ItemType
from app.models.location import Location
from app.models.movement import Movement, MovementStatus
from app.models.decommission import ItemDecommission
from app.models.user import User
from app.schemas.decommission import ItemDecommissionCreate, ItemDecommissionRead
from app.schemas.item import ItemCreate, ItemRead
from app.services.audit_service import record_audit

router = APIRouter()


@router.get(
    "/decommissions",
    response_model=list[ItemDecommissionRead],
    dependencies=[Depends(require_roles("administrador"))],
)
def list_decommissions(db: Session = Depends(get_db)) -> list[ItemDecommission]:
    return (
        db.query(ItemDecommission)
        .options(selectinload(ItemDecommission.item), selectinload(ItemDecommission.decommissioned_by))
        .order_by(ItemDecommission.decommissioned_at.desc())
        .all()
    )


@router.post(
    "/{item_id}/decommission",
    response_model=ItemDecommissionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("administrador"))],
)
def decommission_item(
    item_id: int,
    payload: ItemDecommissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ItemDecommission:
    if not verify_password(payload.confirmation_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contrasena administrativa incorrecta")

    item = db.query(Item).filter(Item.id == item_id).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Articulo no encontrado")
    if item.status == ItemStatus.BAJA or db.query(ItemDecommission.id).filter(ItemDecommission.item_id == item.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El articulo ya tiene una baja registrada")
    active_movement = db.query(Movement.id).filter(
        Movement.item_id == item.id,
        Movement.status.in_([MovementStatus.PENDING_AUTHORIZATION, MovementStatus.OPEN]),
    ).first()
    if active_movement:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se puede dar de baja un articulo con movimientos pendientes o abiertos")

    decommission = ItemDecommission(
        item_id=item.id,
        decommissioned_by_user_id=current_user.id,
        reason=payload.reason,
        description=payload.description,
        notes=payload.notes,
    )
    item.status = ItemStatus.BAJA
    db.add(decommission)
    try:
        db.flush()
        record_audit(
            db,
            user_id=current_user.id,
            action="item.decommission",
            entity_type="item_decommission",
            entity_id=decommission.id,
            commit=False,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El articulo ya tiene una baja registrada") from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(decommission)
    return decommission


def _get_or_create_by_name(db: Session, model, name: str):
    instance = db.query(model).filter(model.name == name).first()
    if instance is not None:
        return instance
    try:
        with db.begin_nested():
            instance = model(name=name)
            db.add(instance)
    except IntegrityError:
        instance = db.query(model).filter(model.name == name).one()
    return instance


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("administrador", "encargado_inventario"))],
)
def create_item(payload: ItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Item:
    if payload.code and db.query(Item).filter(Item.code == payload.code).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Codigo ya registrado")

    try:
        category_id = payload.category_id
        if payload.category_name:
            category_id = _get_or_create_by_name(db, Category, payload.category_name).id

        location_id = None
        if payload.location_name:
            location_id = _get_or_create_by_name(db, Location, payload.location_name).id

        prefixes = {
            "Motor": "MOT", "Bomba": "BOM", "Taladro": "TAL", "Herramienta manual": "HER",
            "Instrumento": "INS", "Equipo": "EQU", "Material": "MAT", "Otro": "ART",
        }
        prefix = prefixes.get(payload.category_name, "MAT" if payload.type == ItemType.MATERIAL else "HER")
        code = payload.code or f"{prefix}-{secrets.token_hex(6).upper()}"
        item = Item(
            code=code, name=payload.name, description=payload.description, type=payload.type,
            category_id=category_id, location_id=location_id, specs=payload.specs.model_dump() if payload.specs else None,
            rfid_tag=payload.rfid_tag,
        )
        db.add(item)
        db.flush()
        record_audit(
            db, user_id=current_user.id, action="item.create", entity_type="item", entity_id=item.id, commit=False
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Codigo, categoria o ubicacion ya registrados") from exc

    db.refresh(item)
    return item


@router.get("", response_model=list[ItemRead], dependencies=[Depends(get_current_user)])
def list_items(db: Session = Depends(get_db)) -> list[Item]:
    return db.query(Item).all()


@router.get("/lookup/{code}", response_model=ItemRead, dependencies=[Depends(get_current_user)])
def lookup_item(code: str, db: Session = Depends(get_db)) -> Item:
    item = db.query(Item).filter((Item.code == code) | (Item.rfid_tag == code)).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")
    return item
