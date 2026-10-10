from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BiometricTemplate(Base):
    """Referencia al template de huella guardado en el modulo sensor; jamas se guarda la imagen cruda."""

    __tablename__ = "biometric_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    sensor_slot_id: Mapped[str] = mapped_column(String(50), nullable=False)  # ID interno del modulo (ej. slot AS608)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="biometric_templates")
    device: Mapped["Device"] = relationship()
