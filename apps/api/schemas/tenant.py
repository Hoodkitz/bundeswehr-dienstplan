"""Pydantic schemas for Tenant."""
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from ..core.models import Tenant


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    security_classification: str = "VS-NfD"


class TenantResponse(Tenant):
    pass
