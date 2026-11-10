"""Pydantic schemas for Dienstplan."""
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from enum import Enum
from apps.core.models import DienstplanStatus, SchichtType


class SchichtBase(BaseModel):
    schicht_type: SchichtType
    start_zeit: datetime
    end_zeit: datetime
    haushaltsnummer: str | None = None
    ort: str | None = None
    beschreibung: str | None = None


class SchichtCreate(SchichtBase):
    soldat_id: UUID


class SchichtResponse(SchichtBase):
    id: UUID
    soldat_id: UUID
    dienstplan_id: UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


class DienstplanCreate(BaseModel):
    tenant_id: UUID
    planungszeitraum_start: datetime
    planungszeitraum_ende: datetime
    ausnahme_modus: str | None = None


class DienstplanResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    planungszeitraum_start: datetime
    planungszeitraum_ende: datetime
    status: DienstplanStatus
    approver_id: UUID | None
    schichten: list[SchichtResponse] = []
    created_at: datetime
    published_at: datetime | None
    export_pdf_url: str | None
    export_xlsx_url: str | None
    export_ics_url: str | None
    audit_trail: list[dict] = []

    class Config:
        from_attributes = True


class DienstplanUpdate(BaseModel):
    planungszeitraum_start: datetime | None = None
    planungszeitraum_ende: datetime | None = None
    status: DienstplanStatus | None = None
    approver_id: UUID | None = None
    schichten: list[SchichtCreate] | None = None
    export_format: str | None = None
