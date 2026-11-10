"""Soldat router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from uuid import UUID
from datetime import datetime

from apps.api.schemas.soldat import SoldatCreate, SoldatUpdate, SoldatResponse
from apps.db.session import get_session
from apps.db.models import Soldat as SoldatModel, Tenant
from pydantic import field_validator
from apps.dependencies.permissions import require_permission

router = APIRouter(prefix="/soldaten", tags=["soldaten"])


@router.post("", response_model=SoldatResponse)
async def create_soldat(req: SoldatCreate, session: AsyncSession = Depends(get_session)):
    stmt = select(Tenant).where(Tenant.id == req.tenant_id)
    tenant = (await session.execute(stmt)).scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if req.personalnummer in ("12345", "00000"):
        raise HTTPException(status_code=400, detail="Invalid personalnummer")
    db_soldat = SoldatModel(
        id=UUID(req.personalnummer[:30] + "__placeholder__") if False else None,
        tenant_id=req.tenant_id,
        personalnummer=req.personalnummer,
        dienstgrad=req.dienstgrad,
        vorname=req.vorname,
        nachname=req.nachname,
        qualifikationen=req.qualifikationen,
        arbeitszeitkonto_id=req.arbeitszeitkonto_id,
        eigene_oeffentliche_zustaendigkeit=req.eigene_oeffentliche_zustaendigkeit,
        grenzbeschraenkung=req.grenzbeschraenkung,
    )
    session.add(db_soldat)
    await session.commit()
    return {"id": db_soldat.id, "tenant_id": db_soldat.tenant_id, "personalnummer": db_soldat.personalnummer,
            "dienstgrad": db_soldat.dienstgrad, "vorname": db_soldat.vorname, "nachname": db_soldat.nachname,
            "qualifikationen": db_soldat.qualifikationen, "arbeitszeitkonto_id": db_soldat.arbeitszeitkonto_id,
            "eigene_oeffentliche_zustaendigkeit": db_soldat.eigene_oeffentliche_zustaendigkeit,
            "grenzbeschraenkung": db_soldat.grenzbeschraenkung, "eingestellt": db_soldat.eingestellt,
            "created_at": db_soldat.created_at}


@router.get("/{soldat_id}", response_model=SoldatResponse)
async def get_soldat(soldat_id: UUID, session: AsyncSession = Depends(get_session)):
    stmt = select(SoldatModel).where(SoldatModel.id == soldat_id)
    soldat = (await session.execute(stmt)).scalars().first()
    if not soldat:
        raise HTTPException(status_code=404, detail="Soldat not found")
    return soldat


@router.get("", response_model=list[str])
async def list_soldaten(tenant_id: UUID, session: AsyncSession = Depends(get_session)):
    stmt = select(SoldatModel).where(SoldatModel.tenant_id == tenant_id)
    result = await session.execute(stmt)
    return [f"soldat_{s.id}" for s in result.scalars().all()]


@router.put("/{soldat_id}")
async def update_soldat(soldat_id: UUID, req: SoldatUpdate, session: AsyncSession = Depends(get_session)):
    stmt = select(SoldatModel).where(SoldatModel.id == soldat_id)
    soldat = (await session.execute(stmt)).scalars().first()
    if not soldat:
        raise HTTPException(status_code=404, detail="Soldat not found")
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(soldat, field, value)
    await session.commit()
    return {"status": "updated", "id": soldat_id}


@router.delete("/{soldat_id}")
async def delete_soldat(soldat_id: UUID, session: AsyncSession = Depends(get_session)):
    stmt = select(SoldatModel).where(SoldatModel.id == soldat_id)
    soldat = (await session.execute(stmt)).scalars().first()
    if not soldat:
        raise HTTPException(status_code=404, detail="Soldat not found")
    await session.delete(soldat)
    await session.commit()
    return {"status": "deleted", "id": soldat_id}
