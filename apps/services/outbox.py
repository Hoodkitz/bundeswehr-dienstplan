"""Outbox-Worker: verarbeitet PENDING-Exporte idempotent."""
import logging
import uuid
from datetime import date

from sqlalchemy import select

from apps.core.enums import DatevFormat
from apps.db.models import DatevOutbox, Tenant, utcnow
from apps.db.session import SessionLocal, set_tenant_context
from apps.domain.datev import Zeile, render

log = logging.getLogger(__name__)


async def process_pending(tenant_id: uuid.UUID) -> int:
    done = 0
    async with SessionLocal() as db:
        await set_tenant_context(db, str(tenant_id))
        tenant = await db.get(Tenant, tenant_id)
        rows = (await db.execute(select(DatevOutbox).where(
            DatevOutbox.tenant_id == tenant_id, DatevOutbox.status == "PENDING"))).scalars().all()
        for e in rows:
            try:
                zeilen = [Zeile(p["personalnummer"], date.fromisoformat(p["datum"]), p["stunden"], p["lohnart"])
                          for p in e.payload]
                e.result = render(DatevFormat(e.format), zeilen, tenant.datev_berater_nr or "0",
                                  tenant.datev_mandant_nr or "0")
                e.status = "DONE"
                done += 1
            except Exception as ex:  # einzelner Fehler blockiert nicht die ganze Queue
                log.exception("Outbox-Eintrag %s fehlgeschlagen", e.id)
                e.status, e.error = "ERROR", str(ex)[:500]
            e.processed_at = utcnow()
        await db.commit()
    return done
