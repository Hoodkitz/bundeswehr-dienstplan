"""Token-Validierung, Benutzerkontext und RBAC-Dependencies.

Die Authentifizierung selbst (OIDC Authorization Code + PKCE, Spec Kap. 8) findet beim
Identity Provider statt. Diese API validiert nur Bearer-Tokens und wertet die Claims
`sub`, `tenant_id` und `roles` aus. Ein Password-Grant existiert bewusst nicht.
"""
import json
import threading
import time
import urllib.request
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
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


class _JWKSCache:
    """IdP signing keys, cached. An unknown kid triggers at most one refetch per REFRESH_MIN seconds, so forged
    tokens with random kids cannot make the API hammer the IdP or block on network I/O."""
    REFRESH_MIN = 60
    TIMEOUT = 5

    def __init__(self, url: str):
        self.url, self.keys, self.fetched = url, {}, float("-inf")  # first fetch always allowed (monotonic may be < 60s after boot)
        self._lock = threading.Lock()

    def _fetch(self) -> None:
        with urllib.request.urlopen(self.url, timeout=self.TIMEOUT) as r:  # noqa: S310 - fixed admin-configured URL
            data = json.loads(r.read(1_000_000))
        self.fetched = time.monotonic()  # also on partial failure: back-off always applies
        keys = {}
        for k in data.get("keys", []):
            if not k.get("kid") or k.get("use", "sig") != "sig":
                continue
            try:
                keys[k["kid"]] = jwt.PyJWK(k)
            except jwt.PyJWTError:
                continue  # unsupported key type: skip it, keep the others
        self.keys = keys

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        kid = jwt.get_unverified_header(token).get("kid")
        if kid not in self.keys:
            with self._lock:
                if kid not in self.keys and time.monotonic() - self.fetched >= self.REFRESH_MIN:
                    try:
                        self._fetch()
                    except (OSError, ValueError) as e:
                        self.fetched = time.monotonic()  # back off on IdP outage as well
                        raise jwt.PyJWKClientError(f"JWKS fetch failed: {e.__class__.__name__}") from e
        if kid not in self.keys:
            raise jwt.PyJWKClientError("unknown signing key")
        return self.keys[kid]


_jwks: _JWKSCache | None = None


def _claim(c: dict, path: str):
    for part in path.split("."):
        if not isinstance(c, dict):
            return None
        c = c.get(part)
    return c


def _verify(token: str) -> dict:
    opts = {"require": ["exp", "sub", "aud", "iss"]}
    if settings.OIDC_JWKS_URL:
        global _jwks
        if _jwks is None:
            _jwks = _JWKSCache(settings.OIDC_JWKS_URL)
        key = _jwks.get_signing_key_from_jwt(token).key
        algs = [a.strip() for a in settings.OIDC_ALGORITHMS.split(",") if a.strip()]
        return jwt.decode(token, key, algorithms=algs, audience=settings.JWT_AUDIENCE, issuer=settings.OIDC_ISSUER,
                          options=opts)
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM], audience=settings.JWT_AUDIENCE,
                      issuer=settings.OIDC_ISSUER, options=opts)


def decode_token(token: str) -> CurrentUser:
    try:
        c = _verify(token)
        tenant = uuid.UUID(str(_claim(c, settings.OIDC_TENANT_CLAIM)))
    except (jwt.PyJWTError, KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungueltiges Token",
                            headers={"WWW-Authenticate": "Bearer"}) from e
    roles = []
    raw_roles = _claim(c, settings.OIDC_ROLES_CLAIM) or []
    for r in raw_roles if isinstance(raw_roles, list) else []:
        try:
            roles.append(Role(r))
        except ValueError:
            pass
    return CurrentUser(c["sub"], tenant, roles, permissions_for(roles))


async def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht authentifiziert",
                            headers={"WWW-Authenticate": "Bearer"})
    if settings.OIDC_JWKS_URL:  # may touch the network (key refresh): keep the event loop free
        return await run_in_threadpool(decode_token, cred.credentials)
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
