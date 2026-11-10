"""Base models and enums."""
from enum import Enum
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Tenant(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    security_classification: str = "VS-NfD"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Dienstgrad(str, Enum):
    REKRUT = "Rekrut"
    SOLDAT = "Soldat"
    GEFR = "Gefreiter"
    UNTEROFFIZIER = "Unteroffizier"
    STABSOFFIZIER = "Stabsoffizier"
    FELDWEBEL = "Feldwebel"
    HAUPTOFFIZIER = "Hauptoffizier"
    GENERAL = "General"


class SoldatBase(BaseModel):
    personalnummer: str = Field(..., min_length=5, max_length=50)
    dienstgrad: Dienstgrad
    vorname: str
    nachname: str
    qualifikationen: list[str] = Field(default_factory=list)
    arbeitszeitkonto_id: str | None = None
    eingestellt: bool = False


class Soldat(SoldatBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
