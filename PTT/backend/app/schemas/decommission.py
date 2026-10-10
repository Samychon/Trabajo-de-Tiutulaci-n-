from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemDecommissionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=500)
    confirmation_password: str = Field(min_length=1, max_length=128)


class ItemDecommissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    decommissioned_by_user_id: int
    reason: str
    description: str
    notes: str | None
    decommissioned_at: datetime
    item_code: str
    item_name: str
    administrator_name: str