from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.alert import AlertStatus, AlertType, DeactivationMethod


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: AlertType
    item_id: int | None
    movement_id: int | None
    device_id: int | None
    status: AlertStatus
    triggered_at: datetime
    resolved_at: datetime | None
    item_name: str | None
    device_uid: str | None
    resolved_by_name: str | None
    resolution_notes: str | None


class AlertDeactivateRequest(BaseModel):
    method: DeactivationMethod
    resolution_notes: str | None = Field(default=None, max_length=500)
    username: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, max_length=128)
