from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class MovementAuthorizationRequest(BaseModel):
    method: str  # "fingerprint" | "password"
    sensor_slot_id: str | None = None
    username: str | None = None
    password: str | None = None
