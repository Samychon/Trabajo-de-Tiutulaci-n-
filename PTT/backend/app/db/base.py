"""Agrega todos los modelos en un solo punto para que Alembic detecte el metadata completo."""

from app.db.session import Base  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.biometric_template import BiometricTemplate  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_preferences import UserPreferences  # noqa: F401
from app.models.item import Category, Item  # noqa: F401
from app.models.decommission import ItemDecommission  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.movement import Movement  # noqa: F401
from app.models.alert import Alert  # noqa: F401
from app.models.device import Device, DeviceRequestNonce  # noqa: F401
from app.models.rfid_event import RfidEvent  # noqa: F401
from app.models.warehouse_request import WarehouseRequest, WarehouseRequestItem  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
