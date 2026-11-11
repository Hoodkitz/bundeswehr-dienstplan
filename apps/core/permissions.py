"""RBAC: Rollen -> Berechtigungen (Spec Kap. 8)."""
from enum import Enum

from apps.core.enums import Role


class Permission(str, Enum):
    TENANT_MANAGE = "tenant:manage"
    SOLDAT_READ = "soldat:read"
    SOLDAT_WRITE = "soldat:write"
    ABWESENHEIT_READ = "abwesenheit:read"
    ABWESENHEIT_WRITE = "abwesenheit:write"
    ROSTER_CREATE = "roster:create"
    ROSTER_READ = "roster:read"
    ROSTER_APPROVE = "roster:approve"
    ROSTER_CANCEL = "roster:cancel"
    ROSTER_REPLAN = "roster:replan"
    MY_SHIFTS = "roster:my-shifts"
    TRADE_REQUEST = "trade:request"
    TRADE_DECIDE = "trade:decide"
    EXPORT_DATEV = "export:datev"
    AUDIT_READ = "audit:read"
    SELF_SERVICE = "self:service"


P = Permission

PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SOLDAT: frozenset({P.MY_SHIFTS, P.TRADE_REQUEST, P.SELF_SERVICE}),
    Role.PLANER: frozenset({
        P.SOLDAT_READ, P.SOLDAT_WRITE, P.ABWESENHEIT_READ, P.ABWESENHEIT_WRITE,
        P.ROSTER_CREATE, P.ROSTER_READ, P.ROSTER_CANCEL, P.ROSTER_REPLAN, P.TRADE_DECIDE,
    }),
    # Truppenarzt pflegt Krankmeldungen, sieht aber keine Plaene im Detail
    Role.TRUPPENARZT: frozenset({P.SOLDAT_READ, P.ABWESENHEIT_READ, P.ABWESENHEIT_WRITE}),
    Role.VORGESETZTER: frozenset({P.SOLDAT_READ, P.ROSTER_READ, P.ROSTER_APPROVE, P.TRADE_DECIDE}),
    Role.ADMIN: frozenset({
        P.TENANT_MANAGE, P.SOLDAT_READ, P.SOLDAT_WRITE, P.ABWESENHEIT_READ,
        P.ROSTER_CREATE, P.ROSTER_CANCEL, P.EXPORT_DATEV,
    }),
    Role.AUDIT: frozenset({P.ROSTER_READ, P.AUDIT_READ, P.EXPORT_DATEV}),
}


def permissions_for(roles: list[Role] | list[str]) -> set[Permission]:
    result: set[Permission] = set()
    for r in roles:
        try:
            result |= PERMISSIONS[Role(r)]
        except ValueError:
            continue  # unbekannte Rolle -> keine Rechte
    return result
