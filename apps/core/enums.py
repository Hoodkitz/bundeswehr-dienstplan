"""Enums."""
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    PLANER = "planer"
    TRUPPENARZT = "truppenarzt"
    VORGESETZTER = "vorgesetzter"
    SOLDAT = "soldat"
    AUDIT = "audit"


class AusnahmeModus(str, Enum):
    TRAINING = "training"
    DEPLOYMENT = "deployment"
    DEFENSE = "defense"
    KEINE = "keine"


class ExportFormat(str, Enum):
    PDF = "pdf"
    XLSX = "xlsx"
    ICS = "ics"
    ALL = "all"
