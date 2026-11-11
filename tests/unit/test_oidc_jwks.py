"""Production path: tokens signed by the customer's IdP (RS256) are verified against its JWKS."""
import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from apps.core.config import settings
from apps.security import auth


@pytest.fixture
def idp(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="k1", use="sig", alg="RS256")

    class FakeJWKS:
        def get_signing_key_from_jwt(self, token):
            if jwt.get_unverified_header(token).get("kid") != "k1":
                raise jwt.PyJWKClientError("unknown kid")
            return jwt.PyJWK(jwk)

    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "https://idp.example/certs")
    monkeypatch.setattr(settings, "OIDC_ROLES_CLAIM", "realm_access.roles")
    monkeypatch.setattr(auth, "_jwks", FakeJWKS())

    def sign(claims, kid="k1", k=key):
        now = datetime.now(timezone.utc)
        base = {"iss": settings.OIDC_ISSUER, "aud": settings.JWT_AUDIENCE, "iat": now, "exp": now + timedelta(minutes=5),
                "sub": "kc-user-1"}
        return jwt.encode({**base, **claims}, k, algorithm="RS256", headers={"kid": kid})
    return sign


def test_idp_token_accepted_with_nested_roles(idp):
    tid = uuid.uuid4()
    u = auth.decode_token(idp({"tenant_id": str(tid), "realm_access": {"roles": ["planer", "unknown-role"]}}))
    assert u.tenant_id == tid and [r.value for r in u.roles] == ["planer"]


def test_foreign_key_and_hs256_rejected_when_jwks_configured(idp):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tid = str(uuid.uuid4())
    with pytest.raises(HTTPException):
        auth.decode_token(idp({"tenant_id": tid}, k=other))
    with pytest.raises(HTTPException):  # locally signed HS256 tokens must not pass in IdP mode
        auth.decode_token(auth.issue_token("x", tid, ["admin"]))
    with pytest.raises(HTTPException):
        auth.decode_token(idp({"tenant_id": tid, "aud": "someone-else"}))
