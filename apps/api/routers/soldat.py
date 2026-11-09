"""Soldat management endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

router = APIRouter(prefix="/api/v1", tags=["soldat"])


class SoldatCreate(BaseModel):
    tenant_id: UUID
    personalnummer: str
    dienstgrad: str
    vorname: str
    nachname: str
    qualifikationen: List[str] = []


class SoldatResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    personalnummer: str
    dienstgrad: str
    vorname: str
    nachname: str
    qualifikationen: List[str]


@router.post("/soldat")
async def create_soldat(req: SoldatCreate):
    return {"id": str(UUID(int=2)), "personalnummer": req.personalnummer, "status": "created"}


@router.get("/soldat/{soldat_id}")
async def get_soldat(soldat_id: UUID):
    return {"id": str(soldat_id), "status": "active"}


@router.get("/soldat")
async def list_soldat(tenant_id: UUID, skip: int = 0, limit: int = 50):
    return {"soldaten": [], "total": 0}


@router.delete("/soldat/{soldat_id}")
async def delete_soldat(soldat_id: UUID):
    return {"id": str(soldat_id), "status": "deleted"}
