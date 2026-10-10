import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RfidEventType(str, enum.Enum):
    ENTRADA = "entrada"
    SALIDA = "salida"


class RfidEvent(Base):
    __tablename__ = "rfid_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    tag_code: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    event_type: Mapped[RfidEventType] = mapped_column(Enum(RfidEventType), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    movement_id: Mapped[int | None] = mapped_column(ForeignKey("movements.id"), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    device: Mapped["Device"] = relationship()
    movement: Mapped["Movement | None"] = relationship()
