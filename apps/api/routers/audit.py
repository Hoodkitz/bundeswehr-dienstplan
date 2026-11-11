from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.core.permissions import Permission as P
from apps.db.models import AuditLog
from apps.domain.audit import verify_chain
from apps.security.auth import CurrentUser, get_db, require

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


async def _entries(db, user):
    return (await db.execute(select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
                             .order_by(AuditLog.seq))).scalars().all()


@router.get("")
async def list_audit(limit: int = 200, user: CurrentUser = Depends(require(P.AUDIT_READ)), db: AsyncSession = Depends(get_db)):
    rows = await _entries(db, user)
    return [{"seq": e.seq, "action": e.action, "actor": e.actor, "payload": e.payload, "ts": e.ts, "hash": e.hash}
            for e in rows[-limit:]]


@router.get("/verify")
async def verify_audit(user: CurrentUser = Depends(require(P.AUDIT_READ)), db: AsyncSession = Depends(get_db)):
    rows = await _entries(db, user)
    ok, broken = verify_chain([{"seq": e.seq, "action": e.action, "actor": e.actor, "payload": e.payload,
                                "ts": e.ts, "prev_hash": e.prev_hash, "hash": e.hash} for e in rows])
    return {"intakt": ok, "eintraege": len(rows), "erste_defekte_seq": broken}
