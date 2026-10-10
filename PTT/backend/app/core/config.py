from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Sistema de Gestion y Monitoreo de Inventario IPI2"
    API_V1_PREFIX: str = "/api/v1"

    # Base de datos
    DATABASE_URL: str

    # JWT de sesion de usuario
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 3

    # Zero trust: secreto por dispositivo cifrado en reposo (Fernet), nunca en texto plano en BD
    DEVICE_SECRET_ENCRYPTION_KEY: str
    DEVICE_TIMESTAMP_TOLERANCE_SECONDS: int = 30

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    REDIS_URL: str = "redis://localhost:6379/0"

    ENVIRONMENT: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
