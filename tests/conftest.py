import asyncio
import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp()
# Optional: run the whole API suite against Postgres as the RLS-restricted app role.
#   PG_TEST_APP_URL=postgresql+asyncpg://application_user:...@host/db   (app, subject to RLS)
#   PG_TEST_OWNER_URL=postgresql+asyncpg://owner:...@host/db            (only used to truncate between tests)
PG_APP = os.environ.get("PG_TEST_APP_URL")
PG_OWNER = os.environ.get("PG_TEST_OWNER_URL")
os.environ.update(ENV="test", DATABASE_URL=PG_APP or f"sqlite+aiosqlite:///{_tmp}/test.db",
                  SOLVER_TIME_LIMIT_SECONDS="1", JWT_SECRET="test-secret-0123456789abcdef0123456789",
                  AUTO_CREATE_TABLES="false" if PG_APP else "true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apps.api.main import app  # noqa: E402
from apps.db.models import Base  # noqa: E402
from apps.db.session import engine  # noqa: E402
from apps.security.auth import issue_token  # noqa: E402


async def _reset():
    if PG_APP:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        owner = create_async_engine(PG_OWNER)
        async with owner.begin() as conn:
            names = ", ".join(t.name for t in Base.metadata.sorted_tables)
            await conn.execute(text(f"TRUNCATE {names} CASCADE"))
        await owner.dispose()
        return
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
