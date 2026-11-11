import asyncio
import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp()
os.environ.update(ENV="test", DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/test.db", SOLVER_TIME_LIMIT_SECONDS="1",
                  JWT_SECRET="test-secret-0123456789abcdef0123456789")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apps.api.main import app  # noqa: E402
from apps.db.models import Base  # noqa: E402
from apps.db.session import engine  # noqa: E402
from apps.security.auth import issue_token  # noqa: E402


async def _reset():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
def client():
    asyncio.run(_reset())
    with TestClient(app) as c:
        yield c


def auth(tenant_id, *roles, sub=None):
    return {"Authorization": f"Bearer {issue_token(sub or f'user-{roles[0]}', tenant_id, list(roles))}"}


@pytest.fixture
def tenant(client):
    """Legt einen Mandanten an und liefert (tenant_id, header-fabrik)."""
    bootstrap = auth(uuid.uuid4(), "admin", sub="platform-admin")
    r = client.post("/api/v1/tenants", json={"name": "1./Wachbataillon", "datev_berater_nr": "12345",
                                               "datev_mandant_nr": "678"}, headers=bootstrap)
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    return tid, (lambda *roles, sub=None: auth(tid, *roles, sub=sub))
