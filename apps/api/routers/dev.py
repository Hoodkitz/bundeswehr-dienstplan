"""Nur in ENV=dev/test: Token-Ausgabe fuer lokale Entwicklung (ersetzt den OIDC-Provider)."""
from fastapi import APIRouter

from apps.api.schemas import DevTokenRequest
from apps.security.auth import issue_token

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/token")
async def dev_token(req: DevTokenRequest):
    return {"access_token": issue_token(req.sub, req.tenant_id, req.roles), "token_type": "bearer"}
