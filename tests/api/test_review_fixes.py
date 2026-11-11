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
    sol = c.Soldier("s1")
    shifts = [c.Shift(f"x{i}", START + timedelta(days=i), START + timedelta(days=i, hours=12), soldat_id="s1")
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
