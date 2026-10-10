import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class WarehouseRequestStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    ENVIADA = "enviada"


class WarehouseRequest(Base):
    __tablename__ = "warehouse_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[WarehouseRequestStatus] = mapped_column(
        Enum(WarehouseRequestStatus), default=WarehouseRequestStatus.PENDIENTE, nullable=False
    )
    document_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["WarehouseRequestItem"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    requested_by: Mapped["User"] = relationship(foreign_keys=[requested_by_user_id])
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    rejected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rejected_by: Mapped["User | None"] = relationship(foreign_keys=[rejected_by_user_id])

    @property
    def requester_name(self) -> str:
        return self.requested_by.full_name

    @property
    def approver_name(self) -> str | None:
        return self.approved_by.full_name if self.approved_by else None

    @property
    def rejecter_name(self) -> str | None:
        return self.rejected_by.full_name if self.rejected_by else None


class WarehouseRequestItem(Base):
    __tablename__ = "warehouse_request_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("warehouse_requests.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    request: Mapped["WarehouseRequest"] = relationship(back_populates="items")
    category: Mapped["Category | None"] = relationship()

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None
