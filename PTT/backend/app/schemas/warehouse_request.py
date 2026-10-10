from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.warehouse_request import WarehouseRequestStatus


class WarehouseRequestItemIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: int | None = None
    description: str = Field(min_length=1, max_length=300)
    quantity: int = Field(gt=0, le=10000)


class WarehouseRequestCreate(BaseModel):
    items: list[WarehouseRequestItemIn] = Field(min_length=1, max_length=50)


class WarehouseRequestReject(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=500)


class WarehouseRequestItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int | None
    category_name: str | None
    description: str
    quantity: int


class WarehouseRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requested_by_user_id: int
    requester_name: str
    status: WarehouseRequestStatus
    approved_by_user_id: int | None
    approver_name: str | None
    rejected_by_user_id: int | None
    rejecter_name: str | None
    rejected_at: datetime | None
    rejection_reason: str | None
    document_url: str | None
    created_at: datetime
    items: list[WarehouseRequestItemRead]
