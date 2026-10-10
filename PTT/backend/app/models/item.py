import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ItemType(str, enum.Enum):
    HERRAMIENTA = "herramienta"
    MATERIAL = "material"


class ItemStatus(str, enum.Enum):
    DISPONIBLE = "disponible"
    EN_USO = "en_uso"
    DEVUELTA = "devuelta"
    BAJA = "baja"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    items: Mapped[list["Item"]] = relationship(back_populates="category")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)  # codigo de barras / QR
    rfid_tag: Mapped[str | None] = mapped_column(String(60), unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type: Mapped[ItemType] = mapped_column(Enum(ItemType), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    specs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.DISPONIBLE, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="items")
    location: Mapped["Location | None"] = relationship()
    decommission: Mapped["ItemDecommission | None"] = relationship(back_populates="item", uselist=False)

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None

    @property
    def location_name(self) -> str | None:
        return self.location.name if self.location else None
