"""Core configuration."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/bundeswehr")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    OIDC_ISSUER: str = os.getenv("OIDC_ISSUER", "https://auth.bundeswehr.de")
    OIDC_CLIENT_ID: str = os.getenv("OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET: str = os.getenv("OIDC_CLIENT_SECRET", "")
    OIDC_REDIRECT_URI: str = os.getenv("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    class Config:
        env_file = ".env"


settings = Settings()
