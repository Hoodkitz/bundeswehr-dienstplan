"""Dienstplan router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime
from dateutil.relativedelta import relativedelta

from ..schemas.dienstplan import DienstplanCreate, DienstplanResponse, SchichtCreate, SchichtResponse
from ...db.session import get_session
from ...db.models import Dienstplan as DienstplanModel, Schicht as SchichtModel, Soldat as SoldatModel

router = APIRouter(prefix="/dienstplaene", tags=["dienstplaene"])


@router.post("", response_model=DienstplanResponse)
async def create_dienstplan(req: DienstplanCreate, session: AsyncSession = Depends(get_session)):
    # Validate tenant
    stmt = select(DienstplanModel).where(DienstplanModel.tenant_id == req.tenant_id)
    existing = (await session.execute(stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Dienstplan for this tenant already exists")
    
    db_plan = DienstplanModel(
        id=UUID(str(req.tenant_id) + "_plan_" + datetime.utcnow().strftime("%Y%m%d%H%M%S")),
        tenant_id=req.tenant_id,
        planungszeitraum_start=req.planungszeitraum_start.date(),
        planungszeitraum_ende=req.planungszeitraum_ende.date(),
        status="DRAFT",
    )
    session.add(db_plan)
    await session.commit()
    return db_plan


@router.get("/{plan_id}", response_model=DienstplanResponse)
async def get_dienstplan(plan_id: UUID, session: AsyncSession = Depends(get_session)):
    stmt = select(DienstplanModel).where(DienstplanModel.id == plan_id)
    plan = (await session.execute(stmt)).scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Dienstplan not found")
    return plan


@router.post("/{plan_id}/schichten")
async def add_schichten(plan_id: UUID, schichten: list[SchichtCreate], session: AsyncSession = Depends(get_session)):
    stmt = select(DienstplanModel).where(DienstplanModel.id == plan_id)
    plan = (await session.execute(stmt)).scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Dienstplan not found")
    for s in schichten:
        db_s = SchichtModel(
            id=UUID(str(s.soldat_id) + "_schicht_" + str(s.start_zeit.timestamp())),
            tenant_id=plan.tenant_id,
            soldat_id=s.soldat_id,
            schicht_type=s.schicht_type,
            start_zeit=s.start_zeit,
            end_zeit=s.end_zeit,
            dienstplan_id=plan.id,
            haushaltsnummer=s.haushaltsnummer,
            ort=s.ort,
            beschreibung=s.beschreibung,
        )
        session.add(db_s)
    plan.schichten = list(plan.schichten) + schichten
    await session.commit()
    return {"status": "schichten_added", "count": len(schichten)}


@router.post("/{plan_id}/publish")
async def publish_dienstplan(plan_id: UUID, session: AsyncSession = Depends(get_session)):
    stmt = select(DienstplanModel).where(DienstplanModel.id == plan_id)
    plan = (await session.execute(stmt)).scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Dienstplan not found")
    plan.status = "PUBLISHED"
    plan.published_at = datetime.utcnow()
    await session.commit()
    return {"status": "published", "id": plan_id}
