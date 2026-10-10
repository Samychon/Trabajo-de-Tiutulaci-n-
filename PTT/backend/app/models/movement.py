import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AuthMethod(str, enum.Enum):
    FINGERPRINT = "fingerprint"
    PASSWORD = "password"


class MovementStatus(str, enum.Enum):
    PENDING_AUTHORIZATION = "pending_authorization"
    OPEN = "open"  # autorizado y en uso, esperando devolucion via RFID
    CLOSED = "closed"  # devuelto


class Movement(Base):
    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    responsible_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    authorized_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(300), nullable=False)
    auth_method: Mapped[AuthMethod | None] = mapped_column(Enum(AuthMethod), nullable=True)
    status: Mapped[MovementStatus] = mapped_column(
        Enum(MovementStatus), default=MovementStatus.PENDING_AUTHORIZATION, nullable=False
    )
    checkout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship()
    responsible_user: Mapped["User"] = relationship(foreign_keys=[responsible_user_id])
    authorized_by: Mapped["User | None"] = relationship(foreign_keys=[authorized_by_user_id])
    location: Mapped["Location"] = relationship()

    @property
    def usage_duration_seconds(self) -> int | None:
        if self.checkout_at is None or self.checkin_at is None:
            return None
        return int((self.checkin_at - self.checkout_at).total_seconds())

    @property
    def item_code(self) -> str:
        return self.item.code

    @property
    def item_name(self) -> str:
        return self.item.name

    @property
    def responsible_name(self) -> str:
        return self.responsible_user.full_name

    @property
    def authorizer_name(self) -> str | None:
        return self.authorized_by.full_name if self.authorized_by else None

    @property
    def location_name(self) -> str:
        return self.location.name
