"""Zentrale Konfiguration (12-Factor, via Umgebungsvariablen / .env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "prod"  # dev | test | prod  (Default fail-closed)
    DATABASE_URL: str = "sqlite+aiosqlite:///./dienstplan-dev.db"
    AUTO_CREATE_TABLES: bool | None = None  # None: only in dev/test; production uses `alembic upgrade head`

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

if not settings.dev_endpoints_enabled and (settings.JWT_SECRET == "dev-secret-change-me" or len(settings.JWT_SECRET) < 32):
    raise RuntimeError("JWT_SECRET (>= 32 Zeichen) muss ausserhalb von ENV=dev/test gesetzt werden")
