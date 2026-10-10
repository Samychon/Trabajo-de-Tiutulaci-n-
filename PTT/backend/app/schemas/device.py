from pydantic import BaseModel

from app.models.device import DeviceType


class DeviceRegisterRequest(BaseModel):
    device_uid: str
    type: DeviceType
    location_id: int | None = None


class DeviceRegisterResponse(BaseModel):
    device_uid: str
    shared_secret: str  # se entrega UNA sola vez en texto plano al aprovisionar el dispositivo


class RfidEventIn(BaseModel):
    tag_code: str
    event_type: str  # "entrada" | "salida"


class BiometricScanIn(BaseModel):
    sensor_slot_id: str
