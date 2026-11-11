"""Orchestrierung des Planungslaufs (Spec Kap. 4).

Jeder Schritt wird persistiert (Checkpoint), sodass ein abgebrochener Worker den Lauf
anhand des gespeicherten Status fortsetzen kann. Seiteneffekte vor dem Freigabe-Interrupt
sind idempotent (Zuweisungen werden vollstaendig ueberschrieben).
"""
import logging
import uuid
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.core.config import settings
from apps.core.enums import AbwesenheitTyp, AusnahmeModus, RosterStatus as S, SchichtTyp
from apps.db.models import Abwesenheit, RosterJob, Schicht, Soldat, utcnow
from apps.db.session import SessionLocal, set_tenant_context
from apps.domain import constraints as c
from apps.domain.solver import solve, workload_stats
from apps.domain.workflow import check_transition
from apps.services import audit

log = logging.getLogger(__name__)


async def load_job(session: AsyncSession, tenant_id: uuid.UUID, job_id: uuid.UUID) -> RosterJob | None:
    return (await session.execute(
        select(RosterJob).options(selectinload(RosterJob.schichten))
        .where(RosterJob.id == job_id, RosterJob.tenant_id == tenant_id)
    )).scalar_one_or_none()


async def load_soldiers(session: AsyncSession, tenant_id: uuid.UUID, start: datetime, end: datetime) -> list[c.Soldier]:
    soldaten = (await session.execute(select(Soldat).where(Soldat.tenant_id == tenant_id))).scalars().all()
    absences = (await session.execute(
        select(Abwesenheit).where(Abwesenheit.tenant_id == tenant_id, Abwesenheit.start < end, Abwesenheit.ende > start)
    )).scalars().all()
    by_soldier: dict[uuid.UUID, list[c.Absence]] = {}
    for a in absences:
        by_soldier.setdefault(a.soldat_id, []).append(c.Absence(a.start, a.ende, AbwesenheitTyp(a.typ)))
    return [c.Soldier(str(s.id), set(s.qualifikationen or []), by_soldier.get(s.id, []), s.sanitaet_opt_out)
            for s in soldaten]


def to_domain(s: Schicht) -> c.Shift:
    return c.Shift(str(s.id), s.start, s.ende, SchichtTyp(s.typ), s.erforderliche_qualifikation,
                   str(s.soldat_id) if s.soldat_id else None, s.pinned)


class Aborted(Exception):
    """Der Lauf wurde waehrenddessen abgebrochen (z. B. vom Planer)."""


async def _step(session: AsyncSession, job: RosterJob, target: S) -> None:
    # Status frisch und gesperrt lesen: ein zwischenzeitliches CANCELLED darf nie ueberschrieben werden.
    await session.refresh(job, ["status"], with_for_update=True)
    if job.status == S.CANCELLED.value:
        raise Aborted()
    job.status = check_transition(job.status, target).value
    await session.commit()


async def load_context_shifts(session: AsyncSession, tenant_id, exclude_job_id, start: datetime,
                              end: datetime) -> list[c.Shift]:
    """Bereits veroeffentlichte Schichten anderer Plaene im (um einen Tag erweiterten) Zeitraum – als fixierter
    Kontext, damit Ruhezeit, Tages-/Wochenstunden und Doppelbelegung planuebergreifend gelten."""
    rows = (await session.execute(
        select(Schicht).join(RosterJob, Schicht.job_id == RosterJob.id).where(
            Schicht.tenant_id == tenant_id, RosterJob.id != exclude_job_id, RosterJob.status == S.PUBLISHED.value,
            Schicht.soldat_id.is_not(None), Schicht.ende > start - timedelta(days=7), Schicht.start < end + timedelta(days=7))
    )).scalars().all()
    out = []
    for r in rows:
        sh = to_domain(r)
        sh.id = "ctx:" + sh.id
        sh.pinned = True
        out.append(sh)
    return out


async def run_pipeline(tenant_id: uuid.UUID, job_id: uuid.UUID, start_at: S = S.DATA_FETCHING) -> None:
    """Fuehrt den Lauf bis zum Freigabe-Interrupt (oder MANUAL_REVIEW/FAILED) aus."""
    async with SessionLocal() as session:
        await set_tenant_context(session, str(tenant_id))
        job = await load_job(session, tenant_id, job_id)
        if job is None:
            return
        try:
            await _run(session, job, start_at)
        except Aborted:
            await session.rollback()
        except Exception as e:  # Worker darf nie haengen bleiben; Fehler im Job sichtbar machen
            log.exception("Planungslauf %s fehlgeschlagen", job_id)
            await session.rollback()
            job = await load_job(session, tenant_id, job_id)
            job.status = S.FAILED.value
            job.warnings = list(job.warnings or []) + [f"Interner Fehler: {type(e).__name__}"]
            await session.commit()


async def _run(session: AsyncSession, job: RosterJob, start_at: S) -> None:
    if start_at == S.DATA_FETCHING:
        await _step(session, job, S.DATA_FETCHING)
    period_start = datetime.combine(job.zeitraum_start, time.min)
    period_end = datetime.combine(job.zeitraum_ende, time.max)
    soldiers = await load_soldiers(session, job.tenant_id, period_start, period_end)
    own_shifts = [to_domain(s) for s in job.schichten]
    context = await load_context_shifts(session, job.tenant_id, job.id, period_start, period_end)
    shifts = own_shifts + context

    if start_at == S.DATA_FETCHING:
        await _step(session, job, S.CONSTRAINT_VALIDATION)
        warnings = []
        if not soldiers:
            warnings.append("Keine Soldaten im Mandanten erfasst")
        for sh in own_shifts:
            if sh.required_qualification and not any(
                sh.required_qualification in so.qualifications
                and not any(a.is_hard and sh.overlaps(a.start, a.end) for a in so.absences)
                for so in soldiers
            ):
                warnings.append(f"Schicht {sh.start:%d.%m. %H:%M}: niemand mit '{sh.required_qualification}' verfuegbar")
        job.warnings = warnings
        if not own_shifts or not soldiers:
            job.status = check_transition(job.status, S.FAILED).value
            job.warnings = warnings or ["Keine Schichten definiert"]
            await session.commit()
            return

    await _step(session, job, S.SOLVER_OPTIMIZING)
    modus = AusnahmeModus(job.ausnahme_modus)
    result = solve(shifts, soldiers, modus, time_limit=settings.SOLVER_TIME_LIMIT_SECONDS)
    assignment = {s.id: s.soldat_id for s in result.shifts}
    for row in job.schichten:
        sid = assignment.get(str(row.id))
        row.soldat_id = uuid.UUID(sid) if sid else None
    job.score = str(result.score)
    job.violations = [v.as_dict() for v in result.violations if v.level != c.SOFT]
    await _step(session, job, S.HARDFEASIBILITY_CHECK)

    own_result = [s for s in result.shifts if not s.id.startswith("ctx:")]
    unbesetzt = sum(1 for s in own_result if s.soldat_id is None)
    if not result.score.feasible or unbesetzt:
        # Unzulaessig oder unvollstaendig -> manuelle Nachbearbeitung durch den Planer
        if unbesetzt:
            job.warnings = list(job.warnings or []) + [f"{unbesetzt} Schicht(en) konnten nicht besetzt werden"]
        await _step(session, job, S.MANUAL_REVIEW)
        return
    await _step(session, job, S.SIMULATION_REVIEW)
    job.stats = workload_stats(own_result, soldiers)
    await _step(session, job, S.COMMAND_APPROVAL_INTERRUPT)


async def approve(session: AsyncSession, job: RosterJob, actor: str) -> None:
    score_hard = int(job.score.split("hard")[0]) if job.score else -1
    if score_hard != 0:
        raise ValueError("Plan verletzt Hard-Constraints und kann nicht freigegeben werden")
    if any(s.soldat_id is None for s in job.schichten):
        raise ValueError("Plan enthaelt unbesetzte Schichten")
    job.status = check_transition(job.status, S.PUBLISHED).value
    job.approved_by = actor
    job.approved_at = utcnow()
    job.version += 1
    await audit.append(session, job.tenant_id, "roster.approved", actor,
                       {"job_id": job.id, "score": job.score, "version": job.version})


def pin_for_replanning(job: RosterJob, now: datetime) -> int:
    """Pinning: begonnene oder kurz bevorstehende Schichten bleiben unveraenderlich."""
    horizon = now + timedelta(hours=settings.REPLAN_PIN_HOURS)
    pinned = 0
    for s in job.schichten:
        s.pinned = s.start < horizon and s.soldat_id is not None
        pinned += int(s.pinned)
    return pinned
