"""Regression tests for review findings: cross-plan rules, weekly cap, cancellation race, tz input, unique login."""
import asyncio
import uuid
from datetime import timedelta

from apps.core.enums import RosterStatus as S
from apps.db.models import RosterJob
from apps.db.session import SessionLocal, set_tenant_context
from apps.domain import constraints as c
from apps.services import roster as svc
from tests.api.test_flow import START, create_job, setup_soldaten


def _approve(client, H, job_id):
    r = client.post(f"/api/v1/jobs/roster/{job_id}/approve", headers=H("vorgesetzter"))
    assert r.status_code == 200, r.text


def test_second_plan_respects_first_published_plan(client, tenant):
    tid, H = tenant
    setup_soldaten(client, H, n=6)
    first = create_job(client, H, key="first-plan-0001").json()["id"]
    _approve(client, H, first)
    # overlapping period: the solver must see the published shifts as fixed context
    second = create_job(client, H, key="second-plan-001").json()["id"]
    job = client.get(f"/api/v1/jobs/roster/{second}", headers=H("planer")).json()
    pub = client.get(f"/api/v1/jobs/roster/{first}", headers=H("planer")).json()
    busy = {(s["soldat_id"], s["start"]) for s in pub["schichten"]}
    if job["status"] == "COMMAND_APPROVAL_INTERRUPT":
        assert not any((s["soldat_id"], s["start"]) in busy for s in job["schichten"])
    else:  # 6 soldiers cannot cover two full 24h guard plans within the rules -> must not be approvable
        assert job["status"] == "MANUAL_REVIEW"


def test_weekly_cap_is_hard_and_respected_by_can_take():
    from datetime import datetime
    sol = c.Soldier("s1")
    monday = datetime(2026, 11, 16)  # fixed ISO week: the test must not depend on today's weekday
    shifts = [c.Shift(f"x{i}", monday + timedelta(days=i), monday + timedelta(days=i, hours=12), soldat_id="s1")
              for i in range(5)]
    score, v = c.evaluate(shifts, {"s1": sol})
    assert not score.feasible and any(x.constraint == "bereitschaftsDeckelung" for x in v)
    rules = c.RULESETS[c.AusnahmeModus.KEINE]
    assert c.can_take(shifts[4], sol, shifts[:4], rules) is False  # 48h already planned this week


def test_cancel_during_run_is_never_overwritten(client, tenant):
    tid, H = tenant
    setup_soldaten(client, H)
    job_id = create_job(client, H, key="cancel-race-01").json()["id"]

    async def scenario():
        async with SessionLocal() as s:
            await set_tenant_context(s, tid)
            job = await s.get(RosterJob, uuid.UUID(job_id))
            job.status = S.DATA_FETCHING.value
            await s.commit()
        async with SessionLocal() as worker, SessionLocal() as api:
            await set_tenant_context(worker, tid)
            await set_tenant_context(api, tid)
            wjob = await svc.load_job(worker, uuid.UUID(tid), uuid.UUID(job_id))  # worker holds a stale copy
            ajob = await api.get(RosterJob, uuid.UUID(job_id))
            ajob.status = S.CANCELLED.value
            await api.commit()
            try:
                await svc._step(worker, wjob, S.CONSTRAINT_VALIDATION)
                return "advanced"
            except svc.Aborted:
                return "aborted"
    assert asyncio.run(scenario()) == "aborted"
    assert client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()["status"] == "CANCELLED"


def test_timezone_aware_times_rejected(client, tenant):
    tid, H = tenant
    body = {"zeitraum_start": START.date().isoformat(), "zeitraum_ende": START.date().isoformat(),
            "schichten": [{"typ": "GRUNDDIENST", "start": START.isoformat() + "Z",
                           "ende": (START + timedelta(hours=8)).isoformat() + "Z"}]}
    r = client.post("/api/v1/jobs/roster", json=body, headers={**H("planer"), "Idempotency-Key": "tz-check-001"})
    assert r.status_code == 422


def test_login_id_unique_per_tenant(client, tenant):
    tid, H = tenant
    setup_soldaten(client, H, n=1)
    r = client.post("/api/v1/soldaten", headers=H("planer"), json={
        "personalnummer": "PN-9999", "dienstgrad": "Gefreiter", "vorname": "A", "nachname": "B", "user_sub": "soldat-0"})
    assert r.status_code == 409
    lst = client.get("/api/v1/soldaten", headers=H("planer")).json()
    assert lst[0]["user_sub"] == "soldat-0"


def test_failed_replan_keeps_published_plan(client, tenant):
    tid, H = tenant
    ids = setup_soldaten(client, H, n=6)
    job_id = create_job(client, H, key="replan-keep-01").json()["id"]
    _approve(client, H, job_id)
    before = {s["id"]: s["soldat_id"] for s in client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()["schichten"]}
    # everybody falls ill -> no feasible re-plan exists
    for sid in ids:
        client.post("/api/v1/abwesenheiten", headers=H("planer"), json={
            "soldat_id": sid, "typ": "KRANK", "start": START.isoformat(), "ende": (START + timedelta(days=5)).isoformat()})
    r = client.post(f"/api/v1/jobs/roster/{job_id}/replan", headers=H("planer"), json={"referenzzeit": (START - timedelta(days=2)).isoformat()})
    assert r.status_code == 202, r.text
    job = client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()
    assert job["status"] == "PUBLISHED"
    assert {s["id"]: s["soldat_id"] for s in job["schichten"]} == before
    assert any("Umplanung" in w for w in job["warnings"])


def test_approve_rechecks_against_new_absences(client, tenant):
    tid, H = tenant
    ids = setup_soldaten(client, H, n=6)
    job_id = create_job(client, H, key="approve-recheck").json()["id"]
    job = client.get(f"/api/v1/jobs/roster/{job_id}", headers=H("planer")).json()
    victim = job["schichten"][0]["soldat_id"]
    client.post("/api/v1/abwesenheiten", headers=H("planer"), json={
        "soldat_id": victim, "typ": "KRANK", "start": START.isoformat(), "ende": (START + timedelta(days=5)).isoformat()})
    r = client.post(f"/api/v1/jobs/roster/{job_id}/approve", headers=H("vorgesetzter"))
    assert r.status_code == 409 and "nicht mehr zulaessig" in r.text


def test_patch_rejects_nulls_and_datev_job_list(client, tenant):
    tid, H = tenant
    ids = setup_soldaten(client, H, n=1)
    assert client.patch(f"/api/v1/soldaten/{ids[0]}", headers=H("planer"), json={"qualifikationen": None}).status_code == 422
    assert client.patch(f"/api/v1/soldaten/{ids[0]}", headers=H("planer"), json={"user_sub": None}).status_code == 200
    assert client.get("/api/v1/exports/datev/jobs", headers=H("admin")).json() == []
