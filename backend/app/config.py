"""
Configuracion central de la aplicacion.
Todas las variables se leen desde el archivo .env usando pydantic-settings.
"""
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://pca:pca@localhost:5432/pca"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    ENVIRONMENT: str = "development"
    APP_NAME: str = "Peru City Analytics"
    APP_VERSION: str = "0.2.0"
    API_BASE_URL: str = "http://localhost:8000"
    ANTHROPIC_API_KEY: Optional[str] = None

    # CORS — lista separada por comas; "*" permite todo (solo para dev)
    ALLOWED_ORIGINS: str = "*"

    # Admin credentials — sobreescribir en produccion con variables de entorno
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme123"
    ADMIN_SECRET_KEY: str = "dev-secret-key-change-in-production"

    @field_validator("DATABASE_URL")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        """
        Railway genera URLs con prefijo 'postgres://' o 'postgresql://'.
        asyncpg requiere 'postgresql+asyncpg://'. Se convierte automaticamente.
        """
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def anthropic_api_key(self) -> Optional[str]:
        return self.ANTHROPIC_API_KEY

    @property
    def cors_origins(self) -> list[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
