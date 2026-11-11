"""DATEV-Export ueber Transactional Outbox (ADR-07)."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.routers.deps import get_owned
from apps.api.schemas import DatevExportCreate, DatevExportOut
from apps.core.enums import RosterStatus as S
from apps.core.permissions import Permission as P
from apps.db.models import DatevOutbox, RosterJob, Schicht, Soldat
from apps.security.auth import CurrentUser, get_db, require
from apps.services import audit, outbox

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])

# Mapping Schichttyp -> Lohnart (von der Kanzlei vorgegeben, hier Defaults)
LOHNART = {"GRUNDDIENST": "100", "WACHDIENST": "210", "BEREITSCHAFT": "220", "SANITAETSDIENST": "230",
           "UEBUNG": "300", "LEHRGANG": "400"}


@router.post("/datev", response_model=DatevExportOut, status_code=202)
async def create_datev_export(req: DatevExportCreate, background: BackgroundTasks,
                              user: CurrentUser = Depends(require(P.EXPORT_DATEV)), db: AsyncSession = Depends(get_db)):
    job = await get_owned(db, RosterJob, req.job_id, user, "Planungslauf")
    if job.status != S.PUBLISHED.value:
        raise HTTPException(409, "Nur veroeffentlichte Dienstplaene koennen exportiert werden")
    rows = (await db.execute(
        select(Schicht, Soldat.personalnummer).join(Soldat, Schicht.soldat_id == Soldat.id)
        .where(Schicht.job_id == job.id, Schicht.tenant_id == user.tenant_id).order_by(Soldat.personalnummer, Schicht.start)
    )).all()
    payload = [{"personalnummer": pn, "datum": s.start.date().isoformat(),
                "stunden": round((s.ende - s.start).total_seconds() / 3600, 2), "lohnart": LOHNART.get(s.typ, "100")}
               for s, pn in rows]
    # Atomar: Outbox-Eintrag + Audit in derselben Transaktion
    entry = DatevOutbox(tenant_id=user.tenant_id, job_id=job.id, format=req.format.value, payload=payload)
    db.add(entry)
    await db.flush()
    await audit.append(db, user.tenant_id, "export.datev.requested", user.sub,
                       {"outbox_id": entry.id, "job_id": job.id, "zeilen": len(payload)})
    await db.commit()
    background.add_task(outbox.process_pending, user.tenant_id)
    return entry


@router.get("/datev", response_model=list[DatevExportOut])
async def list_datev_exports(user: CurrentUser = Depends(require(P.EXPORT_DATEV)), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(DatevOutbox).where(DatevOutbox.tenant_id == user.tenant_id)
                             .order_by(DatevOutbox.created_at.desc()).limit(100))).scalars().all()


@router.get("/datev/{export_id}", response_model=DatevExportOut)
async def get_datev_export(export_id: uuid.UUID, user: CurrentUser = Depends(require(P.EXPORT_DATEV)),
                           db: AsyncSession = Depends(get_db)):
    return await get_owned(db, DatevOutbox, export_id, user, "Export")


@router.get("/datev/{export_id}/download")
async def download_datev_export(export_id: uuid.UUID, user: CurrentUser = Depends(require(P.EXPORT_DATEV)),
                                db: AsyncSession = Depends(get_db)):
    e = await get_owned(db, DatevOutbox, export_id, user, "Export")
    if e.status != "DONE" or e.result is None:
        raise HTTPException(409, f"Export noch nicht fertig ({e.status})")
    return Response(e.result, media_type="text/plain; charset=windows-1252",
                    headers={"Content-Disposition": f'attachment; filename="datev_{e.format}_{e.id}.txt"'})
