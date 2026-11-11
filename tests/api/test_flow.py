"""E2E: Anlegen -> Planungslauf -> Freigabe -> eigene Schichten -> Tausch -> DATEV -> DSGVO."""
import uuid
from datetime import UTC, datetime, timedelta

from tests.conftest import auth

START = (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)


def wache(days=3):
    out = []
    for d in range(days):
        for k in range(3):
            s = START + timedelta(days=d, hours=8 * k)
            out.append({"typ": "WACHDIENST", "start": s.isoformat(), "ende": (s + timedelta(hours=8)).isoformat(),
                        "erforderliche_qualifikation": "Wache", "ort": "Haupttor"})
    return out


def setup_soldaten(client, H, n=6):
    ids = []
    for i in range(n):
        r = client.post("/api/v1/soldaten", headers=H("planer"), json={
            "personalnummer": f"PN-{1000 + i}", "dienstgrad": "Gefreiter", "vorname": f"Max{i}",
            "nachname": f"Muster{i}", "qualifikationen": ["Wache"], "user_sub": f"soldat-{i}"})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


def create_job(client, H, key="job-key-0001", days=3, modus="keine"):
    body = {"zeitraum_start": START.date().isoformat(),
            "zeitraum_ende": (START + timedelta(days=days)).date().isoformat(),
            "ausnahme_modus": modus, "schichten": wache(days)}
    return client.post("/api/v1/jobs/roster", json=body, headers={**H("planer"), "Idempotency-Key": key})


def test_health(client):
    assert client.get("/healthz").json()["status"] == "ok"


def test_ohne_token_401_und_falsche_rolle_403(client, tenant):
    tid, H = tenant
    assert client.get("/api/v1/soldaten").status_code == 401
    assert client.get("/api/v1/soldaten", headers={"Authorization": "Bearer kaputt"}).status_code == 401
    assert client.post("/api/v1/soldaten", headers=H("soldat"), json={}).status_code == 403


def test_kompletter_workflow(client, tenant):
    tid, H = tenant
    ids = setup_soldaten(client, H)
    r = create_job(client, H)
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]

    job = client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()
    assert job["status"] == "COMMAND_APPROVAL_INTERRUPT", job
    assert job["score"].startswith("0hard/0medium")
    assert all(s["soldat_id"] for s in job["schichten"])
    assert job["stats"]["unbesetzt"] == 0

    # Idempotenz: gleicher Key -> gleicher Job, kein zweiter Lauf
    again = create_job(client, H)
    assert again.status_code == 200 and again.json()["id"] == job_id

    # Planer darf nicht freigeben, Vorgesetzter schon
    assert client.post(f"/api/v1/jobs/roster/{job_id}/approve", headers=H("planer")).status_code == 403
    r = client.post(f"/api/v1/jobs/roster/{job_id}/approve", headers=H("vorgesetzter", sub="kp-chef"))
    assert r.status_code == 200 and r.json()["status"] == "PUBLISHED" and r.json()["approved_by"] == "kp-chef"
    assert client.post(f"/api/v1/jobs/roster/{job_id}/approve", headers=H("vorgesetzter")).status_code == 409

    # Soldat sieht eigene Schichten inkl. Ruhezeit
    mine = {}
    for i in range(6):
        mine[i] = client.get("/api/v1/roster/my-shifts", headers=H("soldat", sub=f"soldat-{i}")).json()
    assert sum(len(v) for v in mine.values()) == 9
    owner = next(i for i, v in mine.items() if v)

    # Diensttausch: Anfrage -> Annahme -> Genehmigung
    target = next(i for i in range(6) if i != owner and not mine[i]) if any(not v for v in mine.values()) else None
    schicht = mine[owner][0]
    tgt_idx = target if target is not None else next(i for i in range(6) if i != owner)
    r = client.post("/api/v1/roster/trades", headers=H("soldat", sub=f"soldat-{owner}"),
                    json={"schicht_id": schicht["schicht_id"], "an_soldat_id": ids[tgt_idx]})
    assert r.status_code == 201, r.text
    trade = r.json()["id"]
    assert client.post(f"/api/v1/roster/trades/{trade}/decide", headers=H("planer"),
                       json={"genehmigt": True}).status_code == 409  # noch nicht angenommen
    assert client.post(f"/api/v1/roster/trades/{trade}/accept",
                       headers=H("soldat", sub=f"soldat-{owner}")).status_code == 403
    assert client.post(f"/api/v1/roster/trades/{trade}/accept",
                       headers=H("soldat", sub=f"soldat-{tgt_idx}")).status_code == 200
    r = client.post(f"/api/v1/roster/trades/{trade}/decide", headers=H("vorgesetzter"), json={"genehmigt": True})
    assert r.status_code in (200, 409), r.text  # 409 nur wenn Tausch Ruhezeit verletzen wuerde
    if r.status_code == 200:
        assert r.json()["status"] == "GENEHMIGT"

    # DATEV-Export ueber Outbox
    r = client.post("/api/v1/exports/datev", headers=H("admin"), json={"job_id": job_id, "format": "lodas"})
    assert r.status_code == 202, r.text
    exp = r.json()["id"]
    assert client.get(f"/api/v1/exports/datev/{exp}", headers=H("admin")).json()["status"] == "DONE"
    txt = client.get(f"/api/v1/exports/datev/{exp}/download", headers=H("admin")).content.decode("cp1252")
    assert "Ziel=LODAS" in txt and "BeraterNr=12345" in txt and ";8,00;210;0" in txt

    # Audit-Kette intakt
    v = client.get("/api/v1/audit/verify", headers=H("audit")).json()
    assert v["intakt"] and v["eintraege"] >= 10


def test_unloesbarer_plan_geht_in_manual_review(client, tenant):
    tid, H = tenant
    setup_soldaten(client, H, n=1)
    job_id = create_job(client, H, key="job-key-small", days=1).json()["id"]
    job = client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()
    assert job["status"] == "MANUAL_REVIEW"
    assert client.post(f"/api/v1/jobs/roster/{job_id}/approve", headers=H("vorgesetzter")).status_code == 409
    assert any("nicht besetzt" in w for w in job["warnings"]) or job["violations"]


def test_fehlende_qualifikation_erzeugt_warnung(client, tenant):
    tid, H = tenant
    client.post("/api/v1/soldaten", headers=H("planer"), json={
        "personalnummer": "PN-9999", "dienstgrad": "Soldat", "vorname": "A", "nachname": "B"})
    job_id = create_job(client, H, key="job-key-qual", days=1).json()["id"]
    job = client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()
    assert any("Wache" in w for w in job["warnings"])
    assert job["status"] == "MANUAL_REVIEW"


def test_cancel(client, tenant):
    tid, H = tenant
    setup_soldaten(client, H)
    job_id = create_job(client, H, key="job-key-cancel").json()["id"]
    r = client.post(f"/api/v1/jobs/roster/{job_id}/cancel", headers=H("planer"))
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert client.post(f"/api/v1/jobs/roster/{job_id}/cancel", headers=H("planer")).status_code == 409


def test_replanning_nach_krankmeldung_mit_pinning(client, tenant):
    tid, H = tenant
    ids = setup_soldaten(client, H)
    job_id = create_job(client, H, key="job-key-replan").json()["id"]
    client.post(f"/api/v1/jobs/roster/{job_id}/approve", headers=H("vorgesetzter"))
    job = client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()
    first = min(job["schichten"], key=lambda s: s["start"])
    later = [s for s in job["schichten"] if s["start"] >= (START + timedelta(days=1)).isoformat()]
    sick = later[0]["soldat_id"]

    # Truppenarzt meldet krank ab Tag 2
    r = client.post("/api/v1/abwesenheiten", headers=H("truppenarzt"), json={
        "soldat_id": sick, "typ": "KRANK", "start": (START + timedelta(days=1)).isoformat(),
        "ende": (START + timedelta(days=5)).isoformat()})
    assert r.status_code == 201

    ref = (START + timedelta(hours=1)).isoformat()  # Lauf "jetzt" am ersten Tag
    r = client.post(f"/api/v1/jobs/roster/{job_id}/replan", headers=H("planer"), json={"referenzzeit": ref})
    assert r.status_code == 202, r.text
    job2 = client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()
    assert job2["status"] == "COMMAND_APPROVAL_INTERRUPT"
    by_id = {s["id"]: s for s in job2["schichten"]}
    assert by_id[first["id"]]["pinned"] and by_id[first["id"]]["soldat_id"] == first["soldat_id"]
    assert all(s["soldat_id"] != sick for s in job2["schichten"] if s["start"] >= (START + timedelta(days=1)).isoformat())


def test_mandantentrennung_bola(client, tenant):
    tid, H = tenant
    ids = setup_soldaten(client, H, n=2)
    job_id = create_job(client, H, key="job-key-bola", days=1).json()["id"]
    other = lambda *r, sub=None: auth(uuid.uuid4(), *r, sub=sub)  # fremder Mandant
    assert client.get(f"/api/v1/soldaten/{ids[0]}", headers=other("planer")).status_code == 404
    assert client.get("/api/v1/soldaten", headers=other("planer")).json() == []
    assert client.get(f"/api/v1/jobs/roster/{job_id}", headers=other("planer")).status_code == 404
    assert client.post(f"/api/v1/jobs/roster/{job_id}/approve", headers=other("vorgesetzter")).status_code == 404
    assert client.post("/api/v1/abwesenheiten", headers=other("truppenarzt"), json={
        "soldat_id": ids[0], "typ": "KRANK", "start": START.isoformat(),
        "ende": (START + timedelta(days=1)).isoformat()}).status_code == 404


def test_validierung(client, tenant):
    tid, H = tenant
    body = {"zeitraum_start": "2026-04-10", "zeitraum_ende": "2026-04-01", "schichten": wache(1)}
    r = client.post("/api/v1/jobs/roster", json=body, headers={**H("planer"), "Idempotency-Key": "abcdefgh"})
    assert r.status_code == 422
    r = client.post("/api/v1/jobs/roster", json=body, headers=H("planer"))
    assert r.status_code == 422  # Idempotency-Key fehlt
    r = client.post("/api/v1/soldaten", headers=H("planer"), json={
        "personalnummer": "PN-1", "dienstgrad": "General", "vorname": "A", "nachname": "B"})
    assert r.status_code == 422


def test_doppelte_personalnummer(client, tenant):
    tid, H = tenant
    setup_soldaten(client, H, n=1)
    r = client.post("/api/v1/soldaten", headers=H("planer"), json={
        "personalnummer": "PN-1000", "dienstgrad": "Soldat", "vorname": "A", "nachname": "B"})
    assert r.status_code == 409


def test_dsgvo_export_und_loeschung(client, tenant):
    tid, H = tenant
    setup_soldaten(client, H, n=1)
    me = H("soldat", sub="soldat-0")
    exp = client.get("/api/v1/users/me/export", headers=me).json()
    assert exp["soldat"]["personalnummer"] == "PN-1000"
    r = client.delete("/api/v1/users/me", headers=me)
    assert r.status_code == 202 and len(r.json()["subject_hash"]) == 64
    assert client.get("/api/v1/soldaten", headers=H("planer")).json() == []
    assert client.get("/api/v1/users/me/export", headers=me).status_code == 404


def test_token_abgelaufen(client, tenant):
    from apps.security.auth import issue_token
    tid, _ = tenant
    tok = issue_token("x", tid, ["planer"], minutes=-1)
    assert client.get("/api/v1/soldaten", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
