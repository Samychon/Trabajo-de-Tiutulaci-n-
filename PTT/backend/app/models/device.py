import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class DeviceType(str, enum.Enum):
    ESP32_CONTROLLER = "esp32_controller"
    RFID_READER = "rfid_reader"
    BIOMETRIC_READER = "biometric_reader"
    BARCODE_SCANNER = "barcode_scanner"
    BUZZER = "buzzer"


class DeviceStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPROMISED = "compromised"  # zero trust: revocacion inmediata ante sospecha de compromiso


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_uid: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    type: Mapped[DeviceType] = mapped_column(Enum(DeviceType), nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    secret_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)  # secreto HMAC cifrado (Fernet)
    status: Mapped[DeviceStatus] = mapped_column(Enum(DeviceStatus), default=DeviceStatus.ACTIVE, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    location: Mapped["Location | None"] = relationship()


class DeviceRequestNonce(Base):
    __tablename__ = "device_request_nonces"

    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(32), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
