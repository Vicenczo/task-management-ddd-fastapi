from functools import lru_cache
from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi.security import OAuth2PasswordBearer


class Settings(BaseSettings):
    """
    Centralna konfiguracija aplikacije.
    Čita vrednosti iz .env fajla ili environment varijabli.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Task & Project Management API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    DB_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://taskapi:taskapi_secret@localhost:5432/taskapi_db",
        description="Async PostgreSQL connection string (asyncpg driver).",
    )

    # --- Redis ---
    REDIS_URL: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string.",
    )

    # --- Security / JWT ---
    JWT_SECRET: str = Field(
        default="CHANGE_ME_IN_PRODUCTION",
        min_length=32,
        description="Tajni ključ za potpisivanje JWT tokena. Mora biti dug i nasumičan.",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Ovo omogućava tvom dependencies.py da pristupi settings.SECRET_KEY
    @property
    def SECRET_KEY(self) -> str:
        return self.JWT_SECRET

    # --- Auth Scheme ---
    # Ovo popravlja AttributeError: 'Settings' object has no attribute 'OAUTH2_SCHEME'
    @property
    def OAUTH2_SCHEME(self) -> OAuth2PasswordBearer:
        return OAuth2PasswordBearer(tokenUrl=f"{self.API_V1_PREFIX}/auth/login")

    # --- CORS ---
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_must_be_strong(cls, value: str) -> str:
        if value == "CHANGE_ME_IN_PRODUCTION" and not __debug__:
            raise ValueError("JWT_SECRET mora biti promenjen u produkciji!")
        return value


@lru_cache
def get_settings() -> Settings:
    """
    Vraća singleton instancu Settings objekta.
    lru_cache osigurava da se .env čita samo jednom.
    """
    return Settings()


# Globalni settings objekat za direktan import
settings: Settings = get_settings()