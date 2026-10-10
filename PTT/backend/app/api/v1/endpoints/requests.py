from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.models.item import Category
from app.models.warehouse_request import WarehouseRequest, WarehouseRequestItem, WarehouseRequestStatus
from app.schemas.warehouse_request import WarehouseRequestCreate, WarehouseRequestRead, WarehouseRequestReject
from app.services.audit_service import record_audit

router = APIRouter()


@router.post(
    "",
    response_model=WarehouseRequestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("administrador", "encargado_inventario"))],
)
def create_request(
    payload: WarehouseRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> WarehouseRequest:
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe incluir al menos un item")

    category_ids = {item.category_id for item in payload.items if item.category_id is not None}
    if category_ids:
        existing_ids = {row[0] for row in db.query(Category.id).filter(Category.id.in_(category_ids)).all()}
        if existing_ids != category_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Una o mas categorias no existen")

    request = WarehouseRequest(requested_by_user_id=current_user.id, status=WarehouseRequestStatus.PENDIENTE)
    request.items = [WarehouseRequestItem(**item.model_dump()) for item in payload.items]
    db.add(request)
    try:
        db.flush()
        record_audit(
            db, user_id=current_user.id, action="warehouse_request.create", entity_type="warehouse_request",
            entity_id=request.id, details={"item_count": len(payload.items)}, commit=False,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pudo registrar la solicitud") from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(request)
    return request


@router.get("", response_model=list[WarehouseRequestRead], dependencies=[Depends(get_current_user)])
def list_requests(db: Session = Depends(get_db)) -> list[WarehouseRequest]:
    return (
        db.query(WarehouseRequest)
        .options(
            selectinload(WarehouseRequest.requested_by),
            selectinload(WarehouseRequest.approved_by),
            selectinload(WarehouseRequest.rejected_by),
            selectinload(WarehouseRequest.items).selectinload(WarehouseRequestItem.category),
        )
        .order_by(WarehouseRequest.created_at.desc())
        .all()
    )


@router.post(
    "/{request_id}/approve",
    response_model=WarehouseRequestRead,
    dependencies=[Depends(require_roles("administrador"))],
)
def approve_request(
    request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> WarehouseRequest:
    request = db.query(WarehouseRequest).filter(WarehouseRequest.id == request_id).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    if request.status != WarehouseRequestStatus.PENDIENTE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La solicitud ya fue procesada")

    request.status = WarehouseRequestStatus.APROBADA
    request.approved_by_user_id = current_user.id
    record_audit(
        db, user_id=current_user.id, action="warehouse_request.approve", entity_type="warehouse_request",
        entity_id=request.id, details={"status": WarehouseRequestStatus.APROBADA.value}, commit=False,
    )
    db.commit()
    db.refresh(request)
    return request


@router.post(
    "/{request_id}/send",
    response_model=WarehouseRequestRead,
    dependencies=[Depends(require_roles("administrador"))],
)
def send_request(
    request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> WarehouseRequest:
    request = db.query(WarehouseRequest).filter(WarehouseRequest.id == request_id).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    if request.status != WarehouseRequestStatus.APROBADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solo se pueden enviar solicitudes aprobadas")

    request.status = WarehouseRequestStatus.ENVIADA
    record_audit(
        db, user_id=current_user.id, action="warehouse_request.send", entity_type="warehouse_request",
        entity_id=request.id, details={"status": WarehouseRequestStatus.ENVIADA.value}, commit=False,
    )
    db.commit()
    db.refresh(request)
    return request


@router.post(
    "/{request_id}/reject",
    response_model=WarehouseRequestRead,
    dependencies=[Depends(require_roles("administrador"))],
)
def reject_request(
    request_id: int,
    payload: WarehouseRequestReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WarehouseRequest:
    request = db.query(WarehouseRequest).filter(WarehouseRequest.id == request_id).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    if request.status != WarehouseRequestStatus.PENDIENTE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La solicitud ya fue procesada")

    request.status = WarehouseRequestStatus.RECHAZADA
    request.rejected_by_user_id = current_user.id
    request.rejected_at = datetime.now(timezone.utc)
    request.rejection_reason = payload.reason
    record_audit(
        db, user_id=current_user.id, action="warehouse_request.reject", entity_type="warehouse_request",
        entity_id=request.id, details={"status": WarehouseRequestStatus.RECHAZADA.value}, commit=False,
    )
    db.commit()
    db.refresh(request)
    return request
