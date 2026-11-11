"""Pydantic-v2-Schemas der API."""
import uuid
from datetime import date, datetime
from typing import Self

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def _naive_local(v: datetime) -> datetime:
    if v.tzinfo is not None:
        raise ValueError("Zeit ohne Zeitzone angeben (Ortszeit der Einheit, z. B. 2026-11-16T07:00:00)")
    return v


LocalDateTime = Annotated[datetime, AfterValidator(_naive_local)]

from apps.core.enums import AbwesenheitTyp, AusnahmeModus, DatevFormat, Dienstgrad, SchichtTyp


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    security_classification: str = "VS-NfD"
    datev_berater_nr: str | None = Field(default=None, pattern=r"^\d{4,7}$")
    datev_mandant_nr: str | None = Field(default=None, pattern=r"^\d{1,5}$")


class TenantOut(ORM):
    id: uuid.UUID
    name: str
    security_classification: str
    timezone: str
    created_at: datetime


class SoldatCreate(BaseModel):
    personalnummer: str = Field(min_length=5, max_length=50, pattern=r"^[A-Za-z0-9-]+$")
    dienstgrad: Dienstgrad
    vorname: str = Field(min_length=1, max_length=100)
    nachname: str = Field(min_length=1, max_length=100)
    qualifikationen: list[str] = Field(default_factory=list)
    sanitaet_opt_out: bool = False
    user_sub: str | None = None


class SoldatUpdate(BaseModel):
    dienstgrad: Dienstgrad | None = None
    vorname: str | None = Field(default=None, min_length=1, max_length=100)
    nachname: str | None = Field(default=None, min_length=1, max_length=100)
    qualifikationen: list[str] | None = None
    sanitaet_opt_out: bool | None = None
    user_sub: str | None = None


class SoldatOut(ORM):
    id: uuid.UUID
    user_sub: str | None = None
    personalnummer: str
    dienstgrad: str
    vorname: str
    nachname: str
    qualifikationen: list[str]
    sanitaet_opt_out: bool
    created_at: datetime


class AbwesenheitCreate(BaseModel):
    soldat_id: uuid.UUID
    typ: AbwesenheitTyp
    start: LocalDateTime
    ende: LocalDateTime

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.ende <= self.start:
            raise ValueError("ende muss nach start liegen")
        return self


class AbwesenheitOut(ORM):
    id: uuid.UUID
    soldat_id: uuid.UUID
    typ: str
    start: datetime
    ende: datetime


class SchichtIn(BaseModel):
    typ: SchichtTyp = SchichtTyp.GRUNDDIENST
    start: LocalDateTime
    ende: LocalDateTime
    erforderliche_qualifikation: str | None = None
    ort: str | None = None
    anzahl: int = Field(default=1, ge=1, le=50, description="Soll-Personal fuer diesen Dienstposten")

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.ende <= self.start:
            raise ValueError("ende muss nach start liegen")
        if (self.ende - self.start).total_seconds() > 24 * 3600:
            raise ValueError("Schicht darf hoechstens 24h dauern")
        return self


class RosterJobCreate(BaseModel):
    zeitraum_start: date
    zeitraum_ende: date
    ausnahme_modus: AusnahmeModus = AusnahmeModus.KEINE
    schichten: list[SchichtIn] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.zeitraum_ende < self.zeitraum_start:
            raise ValueError("zeitraum_ende vor zeitraum_start")
        if (self.zeitraum_ende - self.zeitraum_start).days > 62:
            raise ValueError("Planungszeitraum max. 62 Tage")
        for s in self.schichten:
            if not (self.zeitraum_start <= s.start.date() <= self.zeitraum_ende):
                raise ValueError(f"Schicht {s.start} liegt ausserhalb des Planungszeitraums")
        return self


class SchichtOut(ORM):
    id: uuid.UUID
    typ: str
    start: datetime
    ende: datetime
    erforderliche_qualifikation: str | None
    ort: str | None
    soldat_id: uuid.UUID | None
    pinned: bool


class RosterJobOut(ORM):
    id: uuid.UUID
    status: str
    zeitraum_start: date
    zeitraum_ende: date
    ausnahme_modus: str
    score: str | None
    violations: list[dict]
    warnings: list[str]
    stats: dict
    created_by: str
    approved_by: str | None
    approved_at: datetime | None
    version: int
    schichten: list[SchichtOut] = []


class ReplanRequest(BaseModel):
    referenzzeit: LocalDateTime | None = None


class MyShift(BaseModel):
    schicht_id: uuid.UUID
    job_id: uuid.UUID
    typ: str
    start: datetime
    ende: datetime
    ort: str | None
    ruhezeit_bis_naechste_h: float | None


class TradeCreate(BaseModel):
    schicht_id: uuid.UUID
    an_soldat_id: uuid.UUID | None = None
    an_personalnummer: str | None = Field(default=None, max_length=50)  # Soldaten kennen keine internen IDs
    begruendung: str | None = Field(default=None, max_length=500)


class TradeDecision(BaseModel):
    genehmigt: bool


class TradeOut(ORM):
    id: uuid.UUID
    schicht_id: uuid.UUID
    von_soldat_id: uuid.UUID
    an_soldat_id: uuid.UUID
    status: str
    begruendung: str | None


class DatevExportCreate(BaseModel):
    job_id: uuid.UUID
    format: DatevFormat = DatevFormat.LODAS


class DatevExportOut(ORM):
    id: uuid.UUID
    job_id: uuid.UUID
    format: str
    status: str
    error: str | None
    created_at: datetime
    processed_at: datetime | None


class DevTokenRequest(BaseModel):
    sub: str
    tenant_id: uuid.UUID
    roles: list[str]
