"""Permissions."""
from enum import Enum
from typing import Set


class Permission(str, Enum):
    READ_TENANT = "read:tenant"
    READ_SOLDAT = "read:soldat"
    CREATE_SOLDAT = "create:soldat"
    UPDATE_SOLDAT = "update:soldat"
    DELETE_SOLDAT = "delete:soldat"
    READ_SCHICHT = "read:schicht"
    CREATE_SCHICHT = "create:schicht"
    UPDATE_SCHICHT = "update:schicht"
    DELETE_SCHICHT = "delete:schicht"
    READ_DIENSTPLAN = "read:dienstplan"
    CREATE_DIENSTPLAN = "create:dienstplan"
    UPDATE_DIENSTPLAN = "update:dienstplan"
    PUBLISH_DIENSTPLAN = "publish:dienstplan"
    EXPORT = "export"
    EXPORT_PDF = "export:pdf"
    EXPORT_XLSX = "export:xlsx"
    EXPORT_ICS = "export:ics"
    IMPORT = "import"
    AUDIT = "audit"


class Role(str, Enum):
    SOLDAT = "soldat"
    PLANER = "planer"
    TRUPPENARZT = "truppenarzt"
    VORGESETZTER = "vorgesetzter"
    ADMIN = "admin"
    AUDIT = "audit"


PERMISSIONS: dict[Role, set[str]] = {
    Role.SOLDAT: {
        Permission.READ_SOLDAT,
        Permission.READ_SCHICHT,
        Permission.READ_DIENSTPLAN,
        Permission.EXPORT_PDF,
        Permission.EXPORT_ICS,
    },
    Role.PLANER: {
        Permission.READ_SOLDAT,
        Permission.CREATE_SOLDAT,
        Permission.UPDATE_SOLDAT,
        Permission.READ_SCHICHT,
        Permission.CREATE_SCHICHT,
        Permission.UPDATE_SCHICHT,
        Permission.READ_DIENSTPLAN,
        Permission.CREATE_DIENSTPLAN,
        Permission.UPDATE_DIENSTPLAN,
        Permission.EXPORT_PDF,
        Permission.EXPORT_XLSX,
        Permission.EXPORT_ICS,
    },
    Role.TRUPPENARZT: {
        Permission.READ_SOLDAT,
        Permission.READ_SCHICHT,
        Permission.READ_DIENSTPLAN,
        Permission.EXPORT,
    },
    Role.VORGESETZTER: {
        Permission.READ_SOLDAT,
        Permission.READ_SCHICHT,
        Permission.READ_DIENSTPLAN,
        Permission.PUBLISH_DIENSTPLAN,
        Permission.EXPORT_PDF,
        Permission.EXPORT_XLSX,
        Permission.EXPORT_ICS,
    },
    Role.ADMIN: {
        Permission.READ_TENANT,
        Permission.CREATE_SOLDAT,
        Permission.UPDATE_SOLDAT,
        Permission.DELETE_SOLDAT,
        Permission.READ_SCHICHT,
        Permission.CREATE_SCHICHT,
        Permission.UPDATE_SCHICHT,
        Permission.READ_DIENSTPLAN,
        Permission.CREATE_DIENSTPLAN,
        Permission.UPDATE_DIENSTPLAN,
        Permission.PUBLISH_DIENSTPLAN,
        Permission.EXPORT,
        Permission.IMPORT,
    },
    Role.AUDIT: {
        Permission.AUDIT,
        Permission.READ_SCHICHT,
        Permission.READ_DIENSTPLAN,
        Permission.EXPORT,
    },
}
