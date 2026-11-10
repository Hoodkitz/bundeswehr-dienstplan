"""Domain models and enums."""
from enum import Enum
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


class Tenant(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=2, max_length=255)
    security_classification: str = "VS-NfD"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    timezone: str = "Europe/Berlin"


class Dienstgrad(str, Enum):
    REKRUT = "Rekrut"
    SOLDAT = "Soldat"
    GEFR = "Gefreiter"
    UNTEROFFIZIER = "Unteroffizier"
    STABSOFFIZIER = "Stabsoffizier"
    FELDWEBEL = "Feldwebel"
    HAUPTOFFIZIER = "Hauptoffizier"
    GENERAL = "General"


class DienstplanStatus(str, Enum):
    DRAFT = "DRAFT"
    DATA_FETCHING = "DATA_FETCHING"
    CONSTRAINT_VALIDATION = "CONSTRAINT_VALIDATION"
    SOLVER_OPTIMIZING = "SOLVER_OPTIMIZING"
    HARDFEASIBILITY_CHECK = "HARDFEASIBILITY_CHECK"
    SIMULATION_REVIEW = "SIMULATION_REVIEW"
    APPROVAL_INTERRUPT = "APPROVAL_INTERRUPT"
    PUBLISHED = "PUBLISHED"
    REALTIME_REPLANNING = "REALTIME_REPLANNING"


class SoldatBase(BaseModel):
    personalnummer: str = Field(..., min_length=5, max_length=50)
    dienstgrad: Dienstgrad
    vorname: str = Field(..., min_length=2, max_length=100)
    nachname: str = Field(..., min_length=2, max_length=100)
    qualifikationen: list[str] = Field(default_factory=list)
    arbeitszeitkonto_id: str | None = None
    eingestellt: bool = False
    eigene_oeffentliche_zustaendigkeit: bool = False
    grenzbeschraenkung: str | None = None


class Soldat(SoldatBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SchichtType(str, Enum):
    WACH = "WACH"
    EINWAHL = "EINWAHL"
    FREISTUNDE = "FREISTUNDE"
    VERANSTALTUNG = "VERANSTALTUNG"
    UEBUNG = "UEBUNG"
    RAST = "RAST"
    TOF = "TOF"
    LEHRTUECKE = "LEHRTUECKE"
    DIENSTAGENTUR = "DIENSTAGENTUR"


class Schicht(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    soldat_id: UUID
    schicht_type: SchichtType
    start_zeit: datetime
    end_zeit: datetime
    dienstplan_id: UUID | None = None
    haushaltsnummer: str | None = None
    ort: str | None = None
    beschreibung: str | None = None


class Dienstplan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    planungszeitraum_start: datetime
    planungszeitraum_ende: datetime
    status: DienstplanStatus = DienstplanStatus.DRAFT
    approver_id: UUID | None = None
    schichten: list[Schicht] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: datetime | None = None
    export_pdf_url: str | None = None
    export_xlsx_url: str | None = None
    export_ics_url: str | None = None
    audit_trail: list[dict] = Field(default_factory=list)
