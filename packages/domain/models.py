"""Domain models for Bundeswehr Dienstplan SaaS."""
from enum import Enum
from datetime import datetime, date, time
from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Dienstgrad(str, Enum):
    REKRUT = "Rekrut"
    SOLDAT = "Soldat"
    GEFR = "Gefreiter"
    OBERGEFR = "Obergefreiter"
    HAUPTGEFR = "Hauptgefreiter"
    STABSGEFR = "Stabsgefreiter"
    UNTEROFFIZIER = "Unteroffizier"
    STABSUNTEROFFIZIER = "Stabsunteroffizier"
    FELDWEBEL = "Feldwebel"
    OBERFELDWEBEL = "Oberfeldwebel"
    HAUPTFELDWEBEL = "Hauptfeldwebel"
    STABSFELDWEBEL = "Stabsfeldwebel"
    OBERSTABSFE = "Oberstabsfeldwebel"
    LEUTNANT = "Leutnant"
    OBERLEUTNANT = "Oberleutnant"
    HAUPTMANN = "Hauptmann"
    STABSHAUPTMANN = "Stabshauptmann"
    MAJOR = "Major"
    OBERSTLEUTNANT = "Oberstleutnant"
    OBERST = "Oberst"


class Tenant(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    security_classification: str = "VS-NfD"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Soldat(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    personalnummer: str
    dienstgrad: Dienstgrad
    vorname: str
    nachname: str
    qualifikationen: List[str] = []
    arbeitszeitkonto_id: Optional[UUID] = None


class Schicht(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    bezeichnung: str
    start_zeit: datetime
    end_zeit: datetime
    erforderliche_qualifikationen: List[str] = []
    assigned_soldat_id: Optional[UUID] = None
    dienstplan_id: Optional[UUID] = None


class DienstplanStatus(str, Enum):
    DRAFT_INIT = "DRAFT_INIT"
    DATA_FETCHING = "DATA_FETCHING"
    CONSTRAINT_VALIDATION = "CONSTRAINT_VALIDATION"
    SOLVER_OPTIMIZING = "SOLVER_OPTIMIZING"
    HARDFEASIBILITY_CHECK = "HARDFEASIBILITY_CHECK"
    SIMULATION_REVIEW = "SIMULATION_REVIEW"
    COMMAND_APPROVAL_INTERRUPT = "COMMAND_APPROVAL_INTERRUPT"
    PUBLISHED = "PUBLISHED"
    REALTIME_REPLANNING = "REALTIME_REPLANNING"


class Dienstplan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    planungszeitraum_start: date
    planungszeitraum_ende: date
    status: DienstplanStatus = DienstplanStatus.DRAFT_INIT
    approver_id: Optional[UUID] = None
    schichten: List[Schicht] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
