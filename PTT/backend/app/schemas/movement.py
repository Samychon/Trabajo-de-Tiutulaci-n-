from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.movement import AuthMethod, MovementStatus


class MovementCreate(BaseModel):
    item_id: int
    responsible_user_id: int
    location_id: int
    purpose: str


class MovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    responsible_user_id: int
    authorized_by_user_id: int | None
    location_id: int
    purpose: str
    auth_method: AuthMethod | None
    status: MovementStatus
    checkout_at: datetime | None
    checkin_at: datetime | None
    item_code: str
    item_name: str
    responsible_name: str
    authorizer_name: str | None
    location_name: str


class MovementOption(BaseModel):
    id: int
    name: str


class MovementOptions(BaseModel):
    users: list[MovementOption]
    locations: list[MovementOption]
