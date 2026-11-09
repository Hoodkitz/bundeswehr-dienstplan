"""Tenant management endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel
from uuid import UUID

router = APIRouter(prefix="/api/v1", tags=["tenant"])


class TenantCreate(BaseModel):
    name: str
    security_classification: str = "VS-NfD"


@router.post("/tenants")
async def create_tenant(req: TenantCreate):
    return {"id": str(UUID(int=1)), "name": req.name, "status": "created"}


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: UUID):
    return {"id": str(tenant_id), "name": "Default", "security_classification": "VS-NfD"}
