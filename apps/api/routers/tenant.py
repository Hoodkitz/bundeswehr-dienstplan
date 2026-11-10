"""Tenant router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime

from ..schemas.tenant import TenantCreate, TenantResponse
from ...db.session import get_session
from ...db.models import Tenant as TenantModel

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse)
async def create_tenant(req: TenantCreate, session: AsyncSession = Depends(get_session)):
    db_tenant = TenantModel(
        id=UUID(str(uuid.uuid4())),
        name=req.name,
        security_classification=req.security_classification,
    )
    session.add(db_tenant)
    await session.commit()
    return db_tenant


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: UUID, session: AsyncSession = Depends(get_session)):
    stmt = select(TenantModel).where(TenantModel.id == tenant_id)
    tenant = (await session.execute(stmt)).scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("", response_model=list[TenantResponse])
async def list_tenants(session: AsyncSession = Depends(get_session)):
    stmt = select(TenantModel)
    result = await session.execute(stmt)
    return result.scalars().all()
