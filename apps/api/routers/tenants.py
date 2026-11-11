import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas import TenantCreate, TenantOut
from apps.core.permissions import Permission as P
from apps.db.models import Tenant
from apps.db.session import set_tenant_context
from apps.security.auth import CurrentUser, get_current_user, get_db, require
from apps.services import audit

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.post("", response_model=TenantOut, status_code=201)
async def create_tenant(req: TenantCreate, user: CurrentUser = Depends(require(P.TENANT_MANAGE)),
                        db: AsyncSession = Depends(get_db)):
    t = Tenant(id=uuid.uuid4(), **req.model_dump())
    await set_tenant_context(db, str(t.id))  # the audit entry belongs to the NEW tenant (RLS WITH CHECK)
    db.add(t)
    await db.flush()
    await audit.append(db, t.id, "tenant.created", user.sub, {"name": t.name})
    await db.commit()
    return t


@router.get("/current", response_model=TenantOut)
async def current_tenant(user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Name/Stammdaten der eigenen Einheit – fuer jede angemeldete Rolle (Kopfzeile der App)."""
    t = await db.get(Tenant, user.tenant_id)
    if t is None:
        raise HTTPException(404, "Mandant nicht gefunden")
    return t


auth_config = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@auth_config.get("/config")
async def login_config():
    """What the web app needs to log in: the customer's OIDC IdP (Authorization Code + PKCE) and, only in dev/test,
    the local development login."""
    from apps.core.config import settings
    return {"oidc": {"issuer": settings.OIDC_ISSUER, "client_id": settings.OIDC_CLIENT_ID,
                     "scope": settings.OIDC_SCOPE} if settings.OIDC_JWKS_URL and settings.OIDC_CLIENT_ID else None,
            "dev_login": settings.dev_endpoints_enabled}
