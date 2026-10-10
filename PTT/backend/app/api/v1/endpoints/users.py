from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db, require_roles
from app.core.security import hash_password, verify_password
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.user import User
from app.models.user_preferences import UserPreferences
from app.schemas.preferences import UserPreferencesRead, UserPreferencesUpdate
from app.schemas.user import RoleRead, UserCreate, UserDeactivateRequest, UserRead, UserReactivateRequest, UserUpdate
from app.services.audit_service import record_audit

router = APIRouter()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("administrador"))],
)
def create_user(
    payload: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> User:
    exists = db.query(User).filter((User.username == payload.username) | (User.email == payload.email)).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuario o correo ya registrado")
    role = db.get(Role, payload.role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol no registrado")

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=payload.role_id,
    )
    db.add(user)
    try:
        db.flush()
        record_audit(db, user_id=current_user.id, action="user.create", entity_type="user", entity_id=user.id, commit=False)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuario o correo ya registrado") from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_roles("administrador"))])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).options(joinedload(User.role)).order_by(User.full_name).all()


@router.get("/roles", response_model=list[RoleRead], dependencies=[Depends(require_roles("administrador"))])
def list_roles(db: Session = Depends(get_db)) -> list[Role]:
    return db.query(Role).order_by(Role.name).all()


@router.get("/me/preferences", response_model=UserPreferencesRead)
def read_my_preferences(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> UserPreferencesRead | UserPreferences:
    preferences = db.get(UserPreferences, current_user.id)
    if preferences is None:
        return UserPreferencesRead(
            report_default_period="week", alert_status_filter="all", alert_type_filter="all"
        )
    return preferences


@router.put("/me/preferences", response_model=UserPreferencesRead)
def update_my_preferences(
    payload: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPreferences:
    db.query(User).filter(User.id == current_user.id).with_for_update().first()
    preferences = db.get(UserPreferences, current_user.id)
    if preferences is None:
        preferences = UserPreferences(user_id=current_user.id, **payload.model_dump())
        db.add(preferences)
    else:
        for field, value in payload.model_dump().items():
            setattr(preferences, field, value)

    db.commit()
    db.refresh(preferences)
    return preferences


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_roles("administrador"))],
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Debe indicar al menos un cambio")
    if any(value is None for field, value in changes.items() if field != "password"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Los campos enviados no pueden ser nulos")

    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if user.id == current_user.id and changes.get("username", user.username) != user.username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No puede cambiar su propio usuario durante la sesion")
    if user.id == current_user.id and changes.get("role_id", user.role_id) != user.role_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No puede cambiar su propio rol durante la sesion")

    identity_fields = {field: changes[field] for field in ("username", "email") if field in changes}
    duplicate_conditions = []
    if "username" in identity_fields:
        duplicate_conditions.append(User.username == identity_fields["username"])
    if "email" in identity_fields:
        duplicate_conditions.append(User.email == identity_fields["email"])
    if duplicate_conditions and db.query(User.id).filter(User.id != user.id, or_(*duplicate_conditions)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuario o correo ya registrado")

    if "role_id" in changes and db.get(Role, changes["role_id"]) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol no registrado")

    password = changes.pop("password", None)
    for field, value in changes.items():
        setattr(user, field, value)
    if password:
        user.hashed_password = hash_password(password)

    audit_details = {"updated_fields": sorted(changes)}
    if password:
        audit_details["password_reset"] = True
    try:
        record_audit(
            db, user_id=current_user.id, action="user.update", entity_type="user", entity_id=user.id,
            details=audit_details, commit=False,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuario o correo ya registrado") from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user


@router.post(
    "/{user_id}/deactivate",
    response_model=UserRead,
    dependencies=[Depends(require_roles("administrador"))],
)
def deactivate_user(
    user_id: int,
    payload: UserDeactivateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if not verify_password(payload.confirmation_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contrasena administrativa incorrecta")

    # Mismo orden de bloqueo en toda desactivacion: evita bloqueos mutuos entre administradores.
    db.query(User.id).join(Role).filter(Role.name == "administrador").order_by(User.id).with_for_update(of=User).all()
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El usuario ya esta inactivo")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No puede desactivar su propia cuenta")
    if user.role.name == "administrador":
        active_admins = db.query(User.id).join(Role).filter(Role.name == "administrador", User.is_active.is_(True)).count()
        if active_admins <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Debe permanecer al menos un administrador activo")

    user.is_active = False
    record_audit(
        db, user_id=current_user.id, action="user.deactivate", entity_type="user", entity_id=user.id,
        details={"is_active": False}, commit=False,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/{user_id}/reactivate",
    response_model=UserRead,
    dependencies=[Depends(require_roles("administrador"))],
)
def reactivate_user(
    user_id: int,
    payload: UserReactivateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if not verify_password(payload.confirmation_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contrasena administrativa incorrecta")

    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if user.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El usuario ya esta activo")

    user.is_active = True
    record_audit(
        db, user_id=current_user.id, action="user.reactivate", entity_type="user", entity_id=user.id,
        details={"is_active": True}, commit=False,
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
