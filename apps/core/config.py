"""Zentrale Konfiguration (12-Factor, via Umgebungsvariablen / .env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "dev"  # dev | test | prod
    DATABASE_URL: str = "sqlite+aiosqlite:///./dienstplan-dev.db"
    AUTO_CREATE_TABLES: bool = True

    # Token-Validierung. In Produktion stellt der OIDC-Provider (Authorization Code + PKCE)
    # die Tokens aus; die API validiert sie nur. HS256 ist fuer dev/test gedacht.
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_AUDIENCE: str = "dienstplan-api"
    ACCESS_TOKEN_MINUTES: int = 15  # Spec Kap. 8: max. 15 Minuten
    OIDC_ISSUER: str = "https://auth.example.invalid"

    CORS_ORIGINS: str = "http://localhost:3000"
    SOLVER_TIME_LIMIT_SECONDS: float = 5.0
    REPLAN_PIN_HOURS: int = 12  # Schichten, die innerhalb dieser Frist beginnen, werden fixiert

    @property
    def dev_endpoints_enabled(self) -> bool:
        return self.ENV in ("dev", "test")


settings = Settings()

if settings.ENV == "prod" and settings.JWT_SECRET == "dev-secret-change-me":
    raise RuntimeError("JWT_SECRET muss in Produktion gesetzt werden")
