"""Zustandsautomat des Erstellungs- und Freigabeprozesses (Spec Kap. 4).

Ein Dienstplan ist ein Befehl nach § 10 SG. Uebergaenge sind deshalb strikt;
Freigabe ist nur aus COMMAND_APPROVAL_INTERRUPT und nur fuer zulaessige Plaene moeglich.
"""
from apps.core.enums import RosterStatus as S

TRANSITIONS: dict[S, set[S]] = {
    S.DRAFT_INIT: {S.DATA_FETCHING, S.CANCELLED},
    S.DATA_FETCHING: {S.CONSTRAINT_VALIDATION, S.FAILED, S.CANCELLED},
    S.CONSTRAINT_VALIDATION: {S.SOLVER_OPTIMIZING, S.FAILED, S.CANCELLED},
    S.SOLVER_OPTIMIZING: {S.HARDFEASIBILITY_CHECK, S.FAILED, S.CANCELLED},
    S.HARDFEASIBILITY_CHECK: {S.SIMULATION_REVIEW, S.MANUAL_REVIEW, S.CANCELLED},
    S.SIMULATION_REVIEW: {S.COMMAND_APPROVAL_INTERRUPT, S.CANCELLED},
    S.COMMAND_APPROVAL_INTERRUPT: {S.PUBLISHED, S.CANCELLED, S.DATA_FETCHING},
    S.MANUAL_REVIEW: {S.DATA_FETCHING, S.CANCELLED},
    S.PUBLISHED: {S.REALTIME_REPLANNING},
    S.REALTIME_REPLANNING: {S.SOLVER_OPTIMIZING, S.FAILED},
    S.CANCELLED: set(),
    S.FAILED: {S.DATA_FETCHING},
}

CANCELLABLE = {s for s, nxt in TRANSITIONS.items() if S.CANCELLED in nxt}


class InvalidTransition(Exception):
    pass


def check_transition(current: S | str, target: S | str) -> S:
    cur, tgt = S(current), S(target)
    if tgt not in TRANSITIONS[cur]:
        raise InvalidTransition(f"Uebergang {cur.value} -> {tgt.value} nicht erlaubt")
    return tgt
