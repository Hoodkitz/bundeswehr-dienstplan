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
    # Production: tokens from the customer's IdP (Keycloak, Entra ID, ...) are verified against its JWKS.
    OIDC_JWKS_URL: str = ""              # e.g. https://idp.example/realms/bw/protocol/openid-connect/certs
    OIDC_ALGORITHMS: str = "RS256,ES256"
    OIDC_TENANT_CLAIM: str = "tenant_id"  # claim carrying the tenant UUID (IdP mapper)
    OIDC_ROLES_CLAIM: str = "roles"       # dotted path allowed, e.g. realm_access.roles

    CORS_ORIGINS: str = "http://localhost:3000"
    SOLVER_TIME_LIMIT_SECONDS: float = 5.0
    REPLAN_PIN_HOURS: int = 12  # Schichten, die innerhalb dieser Frist beginnen, werden fixiert

    @property
    def dev_endpoints_enabled(self) -> bool:
        return self.ENV in ("dev", "test")


settings = Settings()

if not settings.dev_endpoints_enabled and not settings.OIDC_JWKS_URL and (
        settings.JWT_SECRET == "dev-secret-change-me" or len(settings.JWT_SECRET) < 32):
    raise RuntimeError("Ausserhalb von ENV=dev/test: OIDC_JWKS_URL setzen oder JWT_SECRET (>= 32 Zeichen)")
