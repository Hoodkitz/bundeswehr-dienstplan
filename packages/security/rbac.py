"""RBAC for Bundeswehr Dienstplan."""
from enum import Enum
from typing import Set


class Role(str, Enum):
    SOLDAT = "soldat"
    PLANER = "planer"
    TRUPPENARZT = "truppenarzt"
    VORGESETZTER = "vorgesetzter"
    ADMIN = "admin"
    AUDIT = "audit"


PERMISSIONS: dict[Role, Set[str]] = {
    Role.SOLDAT: {"read:own_shifts", "request:trade", "read:rest_times"},
    Role.PLANER: {"read:all_shifts", "create:roster", "update:roster", "read:accounts", "read:availability"},
    Role.TRUPPENARZT: {"read:health_data", "read:absences", "update:absences"},
    Role.VORGESETZTER: {"approve:roster", "read:all_shifts", "read:accounts", "command:issue"},
    Role.ADMIN: {"*"},
    Role.AUDIT: {"read:audit_log", "read:all_shifts", "read:accounts", "export:datev"},
}


def has_permission(role: Role, permission: str) -> bool:
    perms = PERMISSIONS.get(role, set())
    return "*" in perms or permission in perms
