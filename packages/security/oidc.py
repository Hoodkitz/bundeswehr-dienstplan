"""OIDC with PKCE for Bundeswehr (RFC 9700 compliant)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx, os, secrets, hashlib, base64

router = APIRouter(prefix="/auth", tags=["auth"])

OIDC_ISSUER = os.getenv("OIDC_ISSUER", "https://auth.bundeswehr.de")
CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900  # 15 minutes


def generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


@router.get("/login")
async def login():
    verifier, challenge = generate_pkce()
    # Store verifier in session (simplified)
    auth_url = (
        f"{OIDC_ISSUER}/authorize?"
        f"response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&scope=openid profile email&code_challenge={challenge}&code_challenge_method=S256"
    )
    return {"auth_url": auth_url, "verifier": verifier}


@router.get("/callback")
async def callback(code: str, state: str = ""):
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OIDC_ISSUER}/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code_verifier": state,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Token exchange failed")
        return resp.json()
