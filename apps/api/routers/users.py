"""Betroffenenrechte: Art. 15 (Export) und Art. 17 DSGVO (Loeschkaskade, ADR-08)."""
import hashlib

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.routers.deps import soldat_of_user
from apps.core.permissions import Permission as P
from apps.db.models import Abwesenheit, DeletionRegistry, Schicht, Soldat, TradeRequest, utcnow
from apps.security.auth import CurrentUser, get_db, require
from apps.services import audit

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me/export")
async def export_me(user: CurrentUser = Depends(require(P.SELF_SERVICE)), db: AsyncSession = Depends(get_db)):
    me = await soldat_of_user(db, user)
    abw = (await db.execute(select(Abwesenheit).where(Abwesenheit.soldat_id == me.id))).scalars().all()
    sch = (await db.execute(select(Schicht).where(Schicht.soldat_id == me.id).order_by(Schicht.start))).scalars().all()
    return {
        "soldat": {"personalnummer": me.personalnummer, "dienstgrad": me.dienstgrad, "vorname": me.vorname,
                   "nachname": me.nachname, "qualifikationen": me.qualifikationen},
        "abwesenheiten": [{"typ": a.typ, "start": a.start, "ende": a.ende} for a in abw],
        "schichten": [{"typ": s.typ, "start": s.start, "ende": s.ende, "ort": s.ort} for s in sch],
        "erstellt": utcnow(),
    }


@router.delete("/me", status_code=202)
async def delete_me(user: CurrentUser = Depends(require(P.SELF_SERVICE)), db: AsyncSession = Depends(get_db)):
    me = await soldat_of_user(db, user)
    hours = sum((s.ende - s.start).total_seconds() / 3600 for s in
                (await db.execute(select(Schicht).where(Schicht.soldat_id == me.id))).scalars().all())
    subject = hashlib.sha256(f"{user.tenant_id}:{me.personalnummer}".encode()).hexdigest()
    # Kaskade: personenbezogene Daten entfernen, Schichten anonymisieren (Plan bleibt als Befehl erhalten)
    await db.execute(update(Schicht).where(Schicht.soldat_id == me.id).values(soldat_id=None))
    await db.execute(delete(TradeRequest).where((TradeRequest.von_soldat_id == me.id) | (TradeRequest.an_soldat_id == me.id)))
    await db.execute(delete(Abwesenheit).where(Abwesenheit.soldat_id == me.id))
    await db.execute(delete(Soldat).where(Soldat.id == me.id))
    db.add(DeletionRegistry(tenant_id=user.tenant_id, subject_hash=subject, executed_at=utcnow(), hours_retained=hours))
    await audit.append(db, user.tenant_id, "dsgvo.deleted", "self", {"subject_hash": subject})
    await db.commit()
    return {"status": "geloescht", "subject_hash": subject}
