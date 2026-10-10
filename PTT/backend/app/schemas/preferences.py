from typing import Literal

from pydantic import BaseModel, ConfigDict


class UserPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_default_period: Literal["week", "month"]
    alert_status_filter: Literal["all", "activa", "resuelta"]
    alert_type_filter: Literal[
        "all", "salida_no_autorizada", "falla_dispositivo", "manipulacion_sensor"
    ]


class UserPreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_default_period: Literal["week", "month"]
    alert_status_filter: Literal["all", "activa", "resuelta"]
    alert_type_filter: Literal[
        "all", "salida_no_autorizada", "falla_dispositivo", "manipulacion_sensor"
    ]