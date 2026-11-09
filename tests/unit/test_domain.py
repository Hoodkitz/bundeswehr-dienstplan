"""Tests for domain models."""
from packages.domain.models import Soldat, Dienstplan, Schicht, Dienstgrad, DienstplanStatus
from uuid import uuid4


def test_soldat_creation():
    s = Soldat(tenant_id=uuid4(), personalnummer="12345", dienstgrad=Dienstgrad.GEFR, vorname="Max", nachname="Mustermann")
    assert s.vorname == "Max"
    assert s.dienstgrad == Dienstgrad.GEFR


def test_dienstplan_creation():
    d = Dienstplan(tenant_id=uuid4(), planungszeitraum_start=__import__("datetime").date(2026,1,1), planungszeitraum_ende=__import__("datetime").date(2026,1,31))
    assert d.status == DienstplanStatus.DRAFT_INIT
