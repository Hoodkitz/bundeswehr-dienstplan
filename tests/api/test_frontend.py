"""Web app delivery, login config and the endpoints the app relies on."""
import uuid

from tests.conftest import auth


def test_web_app_served_with_csp(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/app/"
    r = client.get("/app/")
    assert r.status_code == 200 and "Bundeswehr Dienstplan" in r.text
    assert "script-src" not in r.headers["content-security-policy"] or "'unsafe-inline'" not in r.headers["content-security-policy"]
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/app/app.js").status_code == 200 and client.get("/app/style.css").status_code == 200
    assert "default-src 'none'" in client.get("/healthz").headers["content-security-policy"]


def test_login_config(client):
    c = client.get("/api/v1/auth/config").json()
    assert c["dev_login"] is True and c["oidc"] is None


def test_pending_trades_and_export_list_permissions(client, tenant):
    tid, H = tenant
    assert client.get("/api/v1/roster/trades/pending", headers=H("planer")).json() == []
    assert client.get("/api/v1/roster/trades/pending", headers=H("soldat")).status_code == 403
    assert client.get("/api/v1/exports/datev", headers=H("admin")).json() == []
    assert client.get("/api/v1/exports/datev", headers=H("soldat")).status_code == 403
    assert client.get("/api/v1/exports/datev", headers=auth(str(uuid.uuid4()), "admin")).json() == []
