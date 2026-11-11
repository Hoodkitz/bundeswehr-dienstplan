"""Planungslaeufe, eigene Schichten und Diensttausch (Spec Kap. 8)."""
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.routers.deps import get_owned, soldat_of_user
from apps.api.schemas import (MyShift, ReplanRequest, RosterJobCreate, RosterJobOut, TradeCreate, TradeDecision,
                              TradeOut)
from apps.core.enums import AusnahmeModus, RosterStatus as S, TradeStatus
from apps.core.permissions import Permission as P
from apps.db.models import RosterJob, Schicht, Soldat, TradeRequest, utcnow
from apps.domain import constraints as c
from apps.domain.workflow import CANCELLABLE, InvalidTransition, check_transition
from apps.security.auth import CurrentUser, get_db, require
from apps.services import audit, roster as svc

router = APIRouter(prefix="/api/v1", tags=["roster"])


async def _job(db: AsyncSession, user: CurrentUser, job_id: uuid.UUID) -> RosterJob:
    job = await svc.load_job(db, user.tenant_id, job_id)
    if job is None:
        raise HTTPException(404, "Planungslauf nicht gefunden")
    return job


@router.post("/jobs/roster", response_model=RosterJobOut, status_code=202)
async def create_roster_job(req: RosterJobCreate, background: BackgroundTasks, response: Response,
                            idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
                            user: CurrentUser = Depends(require(P.ROSTER_CREATE)), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(RosterJob).where(
        RosterJob.tenant_id == user.tenant_id, RosterJob.idempotency_key == idempotency_key))).scalar_one_or_none()
    if existing:
        response.status_code = 200
        return await _job(db, user, existing.id)

    job = RosterJob(tenant_id=user.tenant_id, idempotency_key=idempotency_key, status=S.DRAFT_INIT.value,
                    zeitraum_start=req.zeitraum_start, zeitraum_ende=req.zeitraum_ende,
                    ausnahme_modus=req.ausnahme_modus.value, created_by=user.sub, violations=[], warnings=[], stats={})
    db.add(job)
    await db.flush()
    for s in req.schichten:
        for _ in range(s.anzahl):
            db.add(Schicht(tenant_id=user.tenant_id, job_id=job.id, typ=s.typ.value, start=s.start, ende=s.ende,
                           erforderliche_qualifikation=s.erforderliche_qualifikation, ort=s.ort))
    await audit.append(db, user.tenant_id, "roster.created", user.sub,
                       {"job_id": job.id, "modus": job.ausnahme_modus, "schichten": sum(s.anzahl for s in req.schichten)})
    if req.ausnahme_modus != AusnahmeModus.KEINE:
        await audit.append(db, user.tenant_id, "roster.ausnahme_30c", user.sub, {"job_id": job.id, "modus": job.ausnahme_modus})
    await db.commit()
    background.add_task(svc.run_pipeline, user.tenant_id, job.id)
    return await _job(db, user, job.id)


@router.get("/jobs/roster", response_model=list[RosterJobOut])
async def list_jobs(user: CurrentUser = Depends(require(P.ROSTER_READ)), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(RosterJob.id).where(RosterJob.tenant_id == user.tenant_id)
                             .order_by(RosterJob.created_at.desc()))).scalars().all()
    return [await _job(db, user, i) for i in rows]


@router.get("/jobs/roster/{job_id}", response_model=RosterJobOut)
async def get_job(job_id: uuid.UUID, user: CurrentUser = Depends(require(P.ROSTER_READ)), db: AsyncSession = Depends(get_db)):
    return await _job(db, user, job_id)


@router.post("/jobs/roster/{job_id}/approve", response_model=RosterJobOut)
async def approve_job(job_id: uuid.UUID, user: CurrentUser = Depends(require(P.ROSTER_APPROVE)),
                      db: AsyncSession = Depends(get_db)):
    job = await _job(db, user, job_id)
    try:
        await svc.approve(db, job, user.sub)
    except (InvalidTransition, ValueError) as e:
        raise HTTPException(409, str(e))
    await db.commit()
    return await _job(db, user, job_id)


@router.post("/jobs/roster/{job_id}/cancel", response_model=RosterJobOut)
async def cancel_job(job_id: uuid.UUID, user: CurrentUser = Depends(require(P.ROSTER_CANCEL)),
                     db: AsyncSession = Depends(get_db)):
    job = await _job(db, user, job_id)
    if S(job.status) not in CANCELLABLE:
        raise HTTPException(409, f"Lauf im Status {job.status} kann nicht abgebrochen werden")
    job.status = S.CANCELLED.value
    await audit.append(db, user.tenant_id, "roster.cancelled", user.sub, {"job_id": job.id})
    await db.commit()
    return await _job(db, user, job_id)


@router.post("/jobs/roster/{job_id}/replan", response_model=RosterJobOut, status_code=202)
async def replan_job(job_id: uuid.UUID, req: ReplanRequest, background: BackgroundTasks,
                     user: CurrentUser = Depends(require(P.ROSTER_REPLAN)), db: AsyncSession = Depends(get_db)):
    """Echtzeit-Re-Optimierung nach Spontanausfall; fixiert nahe Schichten (Pinning)."""
    job = await _job(db, user, job_id)
    try:
        job.status = check_transition(job.status, S.REALTIME_REPLANNING).value
    except InvalidTransition as e:
        raise HTTPException(409, str(e))
    now = req.referenzzeit or utcnow()
    svc.pin_for_replanning(job, now)
    # Schichten eines inzwischen abwesenden Soldaten nie fixieren
    soldiers = {s.id: s for s in await svc.load_soldiers(db, user.tenant_id, min(x.start for x in job.schichten),
                                                         max(x.ende for x in job.schichten))}
    for s in job.schichten:
        sol = soldiers.get(str(s.soldat_id)) if s.soldat_id else None
        if s.pinned and sol and any(a.is_hard and a.start < s.ende and s.start < a.end for a in sol.absences):
            s.pinned = False
    await audit.append(db, user.tenant_id, "roster.replanning", user.sub,
                       {"job_id": job.id, "fixiert": sum(s.pinned for s in job.schichten)})
    await db.commit()
    background.add_task(svc.run_pipeline, user.tenant_id, job.id, S.REALTIME_REPLANNING)
    return await _job(db, user, job_id)


@router.get("/roster/my-shifts", response_model=list[MyShift])
async def my_shifts(response: Response, user: CurrentUser = Depends(require(P.MY_SHIFTS)),
                    db: AsyncSession = Depends(get_db)):
    me = await soldat_of_user(db, user)
    rows = (await db.execute(
        select(Schicht).join(RosterJob).where(Schicht.tenant_id == user.tenant_id, Schicht.soldat_id == me.id,
                                              RosterJob.status == S.PUBLISHED.value).order_by(Schicht.start)
    )).scalars().all()
    out = []
    for i, s in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        out.append(MyShift(schicht_id=s.id, job_id=s.job_id, typ=s.typ, start=s.start, ende=s.ende, ort=s.ort,
                           ruhezeit_bis_naechste_h=round((nxt.start - s.ende).total_seconds() / 3600, 2) if nxt else None))
    response.headers["Cache-Control"] = "private, max-age=300"
    return out


# ------------------------------------------------------------------ Diensttausch

@router.post("/roster/trades", response_model=TradeOut, status_code=201)
async def create_trade(req: TradeCreate, user: CurrentUser = Depends(require(P.TRADE_REQUEST)),
                       db: AsyncSession = Depends(get_db)):
    me = await soldat_of_user(db, user)
    schicht = await get_owned(db, Schicht, req.schicht_id, user, "Schicht")
    if schicht.soldat_id != me.id:
        raise HTTPException(403, "Nur eigene Schichten koennen getauscht werden")
    job = await db.get(RosterJob, schicht.job_id)
    if job.status != S.PUBLISHED.value:
        raise HTTPException(409, "Nur Schichten veroeffentlichter Plaene sind tauschbar")
    if schicht.start <= utcnow():
        raise HTTPException(409, "Schicht hat bereits begonnen")
    await get_owned(db, Soldat, req.an_soldat_id, user, "Kamerad")
    if req.an_soldat_id == me.id:
        raise HTTPException(422, "Tausch mit sich selbst nicht moeglich")
    t = TradeRequest(tenant_id=user.tenant_id, schicht_id=schicht.id, von_soldat_id=me.id,
                     an_soldat_id=req.an_soldat_id, begruendung=req.begruendung)
    db.add(t)
    await db.flush()
    await audit.append(db, user.tenant_id, "trade.requested", user.sub, {"trade_id": t.id})
    await db.commit()
    return t


@router.get("/roster/trades", response_model=list[TradeOut])
async def list_trades(user: CurrentUser = Depends(require(P.TRADE_REQUEST)),
                      db: AsyncSession = Depends(get_db)):
    me = await soldat_of_user(db, user)
    return (await db.execute(select(TradeRequest).where(
        TradeRequest.tenant_id == user.tenant_id,
        (TradeRequest.von_soldat_id == me.id) | (TradeRequest.an_soldat_id == me.id)))).scalars().all()


@router.post("/roster/trades/{trade_id}/accept", response_model=TradeOut)
async def accept_trade(trade_id: uuid.UUID, user: CurrentUser = Depends(require(P.TRADE_REQUEST)),
                       db: AsyncSession = Depends(get_db)):
    me = await soldat_of_user(db, user)
    t = await get_owned(db, TradeRequest, trade_id, user, "Tauschanfrage")
    if t.an_soldat_id != me.id:
        raise HTTPException(403, "Anfrage richtet sich an einen anderen Kameraden")
    if t.status != TradeStatus.OFFEN.value:
        raise HTTPException(409, f"Anfrage ist bereits {t.status}")
    t.status = TradeStatus.ANGENOMMEN.value
    await audit.append(db, user.tenant_id, "trade.accepted", user.sub, {"trade_id": t.id})
    await db.commit()
    return t


@router.post("/roster/trades/{trade_id}/decide", response_model=TradeOut)
async def decide_trade(trade_id: uuid.UUID, req: TradeDecision, user: CurrentUser = Depends(require(P.TRADE_DECIDE)),
                       db: AsyncSession = Depends(get_db)):
    """Planer/Vorgesetzter entscheidet (Vorrang nach § 10 SG). Tausch nur ohne Hard-Verletzung."""
    t = await get_owned(db, TradeRequest, trade_id, user, "Tauschanfrage")
    if t.status not in (TradeStatus.OFFEN.value, TradeStatus.ANGENOMMEN.value):
        raise HTTPException(409, f"Anfrage ist bereits {t.status}")
    if not req.genehmigt:
        t.status = TradeStatus.ABGELEHNT.value
    else:
        if t.status != TradeStatus.ANGENOMMEN.value:
            raise HTTPException(409, "Kamerad hat noch nicht zugestimmt")
        schicht = await get_owned(db, Schicht, t.schicht_id, user, "Schicht")
        if schicht.soldat_id != t.von_soldat_id:
            raise HTTPException(409, "Schicht wurde zwischenzeitlich umgeplant")
        job = await svc.load_job(db, user.tenant_id, schicht.job_id)
        shifts = [svc.to_domain(s) for s in job.schichten]
        soldiers = {s.id: s for s in await svc.load_soldiers(db, user.tenant_id, min(x.start for x in shifts),
                                                             max(x.end for x in shifts))}
        for s in shifts:
            if s.id == str(schicht.id):
                s.soldat_id = str(t.an_soldat_id)
        score, violations = c.evaluate(shifts, soldiers, AusnahmeModus(job.ausnahme_modus))
        if not score.feasible:
            raise HTTPException(409, {"detail": "Tausch verletzt Hard-Constraints",
                                      "violations": [v.as_dict() for v in violations if v.level == c.HARD]})
        schicht.soldat_id = t.an_soldat_id
        job.score = str(score)
        t.status = TradeStatus.GENEHMIGT.value
    await audit.append(db, user.tenant_id, "trade.decided", user.sub, {"trade_id": t.id, "status": t.status})
    await db.commit()
    return t
