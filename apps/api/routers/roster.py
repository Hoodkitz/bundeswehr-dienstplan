"""Roster API endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

router = APIRouter(prefix="/api/v1/jobs", tags=["roster"])


class RosterRequest(BaseModel):
    tenant_id: UUID
    planungszeitraum_start: str
    planungszeitraum_ende: str
    ausnahme_modus: Optional[str] = None


@router.post("/roster")
async def create_roster(req: RosterRequest):
    return {"job_id": str(UUID(int=0)), "status": "queued", "tenant_id": str(req.tenant_id)}


@router.get("/roster/{job_id}")
async def get_roster(job_id: UUID):
    return {"job_id": str(job_id), "status": "pending"}


@router.post("/roster/{job_id}/approve")
async def approve_roster(job_id: UUID):
    return {"job_id": str(job_id), "status": "approved", "audit_logged": True}


@router.post("/roster/{job_id}/cancel")
async def cancel_roster(job_id: UUID):
    return {"job_id": str(job_id), "status": "cancelled"}
