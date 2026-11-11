"""Schreiben ins Hash-verkettete Audit-Log."""
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.db.models import AuditLog, utcnow
from apps.domain.audit import GENESIS, entry_hash


async def append(session: AsyncSession, tenant_id: uuid.UUID, action: str, actor: str, payload: dict) -> AuditLog:
    if session.bind.dialect.name == "postgresql":
        # Serialisiert parallele Schreiber je Mandant (API + Worker): sonst kollidiert MAX(seq)+1 auf UNIQUE.
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:t))"), {"t": "audit:" + str(tenant_id)})
    last = (await session.execute(
        select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(AuditLog.seq.desc()).limit(1)
    )).scalar_one_or_none()
    seq = (last.seq + 1) if last else 1
    prev = last.hash if last else GENESIS
    ts = utcnow().replace(microsecond=0)
    payload = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in payload.items()}
    entry = AuditLog(tenant_id=tenant_id, seq=seq, action=action, actor=actor, payload=payload, ts=ts,
                     prev_hash=prev, hash=entry_hash(prev, seq, action, actor, payload, ts))
    session.add(entry)
    return entry
