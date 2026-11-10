"""Pydantic schemas for Soldat."""
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from apps.core.models import SoldatBase, Dienstgrad


class SoldatCreate(BaseModel):
    tenant_id: UUID
    personalnummer: str = Field(..., min_length=5, max_length=50)
    dienstgrad: Dienstgrad
    vorname: str = Field(..., min_length=2, max_length=100)
    nachname: str = Field(..., min_length=2, max_length=100)
    qualifikationen: list[str] = Field(default_factory=list)
    arbeitszeitkonto_id: str | None = None
    eigene_oeffentliche_zustaendigkeit: bool = False
    grenzbeschraenkung: str | None = None

    @field_validator("personalnummer")
    @classmethod
    def validate_personalnummer(cls, v):
        if not v.strip():
            raise ValueError("Personalnummer darf nicht leer sein")
        return v


class SoldatResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    personalnummer: str
    dienstgrad: Dienstgrad
    vorname: str
    nachname: str
    qualifikationen: list[str]
    arbeitszeitkonto_id: str | None
    eigene_oeffentliche_zustaendigkeit: bool
    grenzbeschraenkung: str | None
    eingestellt: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SoldatUpdate(BaseModel):
    personalnummer: str | None = None
    dienstgrad: Dienstgrad | None = None
    vorname: str | None = None
    nachname: str | None = None
    qualifikationen: list[str] | None = None
    arbeitszeitkonto_id: str | None = None
    eigene_oeffentliche_zustaendigkeit: bool | None = None
    grenzbeschraenkung: str | None = None
    eingestellt: bool | None = None
