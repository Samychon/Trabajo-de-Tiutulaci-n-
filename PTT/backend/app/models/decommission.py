from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ItemDecommission(Base):
    __tablename__ = "item_decommissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), unique=True, nullable=False)
    decommissioned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decommissioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship(back_populates="decommission")
    decommissioned_by: Mapped["User"] = relationship()

    @property
    def item_code(self) -> str:
        return self.item.code

    @property
    def item_name(self) -> str:
        return self.item.name

    @property
    def administrator_name(self) -> str:
        return self.decommissioned_by.full_name