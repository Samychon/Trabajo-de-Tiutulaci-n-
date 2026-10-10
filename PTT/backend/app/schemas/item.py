from pydantic import BaseModel, ConfigDict, Field

from app.models.item import ItemStatus, ItemType


class ItemBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    type: ItemType
    category_id: int | None = None


class ItemSpecs(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: str = Field(default="", max_length=150)
    potencia: str = Field(default="", max_length=150)
    velocidad: str = Field(default="", max_length=150)
    modelo: str = Field(default="", max_length=150)


class ItemCreate(ItemBase):
    code: str | None = Field(default=None, min_length=1, max_length=60)
    rfid_tag: str | None = None
    category_name: str | None = Field(default=None, min_length=1, max_length=100)
    location_name: str | None = Field(default=None, min_length=1, max_length=150)
    specs: ItemSpecs | None = None


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfid_tag: str | None
    status: ItemStatus
    photo_url: str | None
    category_name: str | None = None
    location_name: str | None = None
    specs: ItemSpecs | None = None
