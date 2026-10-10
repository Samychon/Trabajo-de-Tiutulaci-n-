import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AlertType(str, enum.Enum):
    SALIDA_NO_AUTORIZADA = "salida_no_autorizada"
    FALLA_DISPOSITIVO = "falla_dispositivo"
    MANIPULACION_SENSOR = "manipulacion_sensor"


class AlertStatus(str, enum.Enum):
    ACTIVA = "activa"
    RESUELTA = "resuelta"


class DeactivationMethod(str, enum.Enum):
    FINGERPRINT = "fingerprint"
    DASHBOARD = "dashboard"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    movement_id: Mapped[int | None] = mapped_column(ForeignKey("movements.id"), nullable=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.ACTIVA, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivation_method: Mapped[DeactivationMethod | None] = mapped_column(Enum(DeactivationMethod), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    item: Mapped["Item | None"] = relationship()
    movement: Mapped["Movement | None"] = relationship()
    device: Mapped["Device | None"] = relationship()
    resolved_by: Mapped["User | None"] = relationship()

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def device_uid(self) -> str | None:
        return self.device.device_uid if self.device else None

    @property
    def resolved_by_name(self) -> str | None:
        return self.resolved_by.full_name if self.resolved_by else None
