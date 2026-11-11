"""Token-Validierung, Benutzerkontext und RBAC-Dependencies.

Die Authentifizierung selbst (OIDC Authorization Code + PKCE, Spec Kap. 8) findet beim
Identity Provider statt. Diese API validiert nur Bearer-Tokens und wertet die Claims
`sub`, `tenant_id` und `roles` aus. Ein Password-Grant existiert bewusst nicht.
"""
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from apps.core.config import settings
from apps.core.enums import Role
from apps.core.permissions import Permission, permissions_for
from apps.db.session import SessionLocal, set_tenant_context

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    sub: str
    tenant_id: uuid.UUID
    roles: list[Role]
    permissions: set[Permission] = field(default_factory=set)

    def has(self, perm: Permission) -> bool:
        return perm in self.permissions


def issue_token(sub: str, tenant_id: str | uuid.UUID, roles: list[str], minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub, "tenant_id": str(tenant_id), "roles": roles,
        "iss": settings.OIDC_ISSUER, "aud": settings.JWT_AUDIENCE,
        "iat": now, "exp": now + timedelta(minutes=minutes or settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> CurrentUser:
    try:
        c = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM],
                       audience=settings.JWT_AUDIENCE, issuer=settings.OIDC_ISSUER,
                       options={"require": ["exp", "sub", "aud", "iss"]})
        tenant = uuid.UUID(c["tenant_id"])
    except (jwt.PyJWTError, KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungueltiges Token",
                            headers={"WWW-Authenticate": "Bearer"}) from e
    roles = []
    for r in c.get("roles", []):
        try:
            roles.append(Role(r))
        except ValueError:
            pass
    return CurrentUser(c["sub"], tenant, roles, permissions_for(roles))


async def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht authentifiziert",
                            headers={"WWW-Authenticate": "Bearer"})
    return decode_token(cred.credentials)


def require(perm: Permission):
    async def dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has(perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Berechtigung fehlt: {perm.value}")
        return user
    return dep


async def get_db(user: CurrentUser = Depends(get_current_user)) -> AsyncIterator[AsyncSession]:
    """Tenant-scoped Session: setzt den RLS-Kontext transaktionslokal."""
    async with SessionLocal() as session:
        await set_tenant_context(session, str(user.tenant_id))
        yield session
