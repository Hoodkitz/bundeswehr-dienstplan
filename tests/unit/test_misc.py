from datetime import date, datetime

import pytest

from apps.core.enums import DatevFormat, Role, RosterStatus as S
from apps.core.permissions import Permission as P, permissions_for
from apps.domain.audit import GENESIS, entry_hash, verify_chain
from apps.domain.datev import Zeile, render
from apps.domain.workflow import InvalidTransition, check_transition


def test_workflow_happy_path():
    path = [S.DRAFT_INIT, S.DATA_FETCHING, S.CONSTRAINT_VALIDATION, S.SOLVER_OPTIMIZING, S.HARDFEASIBILITY_CHECK,
            S.SIMULATION_REVIEW, S.COMMAND_APPROVAL_INTERRUPT, S.PUBLISHED, S.REALTIME_REPLANNING, S.SOLVER_OPTIMIZING]
    for a, b in zip(path, path[1:]):
        assert check_transition(a, b) == b


@pytest.mark.parametrize("a,b", [(S.DRAFT_INIT, S.PUBLISHED), (S.MANUAL_REVIEW, S.PUBLISHED),
                                 (S.PUBLISHED, S.CANCELLED), (S.CANCELLED, S.DATA_FETCHING)])
def test_workflow_verbotene_uebergaenge(a, b):
    with pytest.raises(InvalidTransition):
        check_transition(a, b)


def test_rbac():
    assert P.ROSTER_APPROVE in permissions_for([Role.VORGESETZTER])
    assert P.ROSTER_APPROVE not in permissions_for([Role.PLANER])
    assert P.EXPORT_DATEV not in permissions_for([Role.SOLDAT])
    assert permissions_for(["unbekannt"]) == set()


def _chain(n):
    prev, out = GENESIS, []
    for i in range(1, n + 1):
        ts = datetime(2026, 1, 1, 12, 0, i)
        h = entry_hash(prev, i, "x", "a", {"i": i}, ts)
        out.append({"seq": i, "action": "x", "actor": "a", "payload": {"i": i}, "ts": ts, "prev_hash": prev, "hash": h})
        prev = h
    return out


def test_audit_chain_ok_und_manipulation():
    chain = _chain(4)
    assert verify_chain(chain) == (True, None)
    chain[2]["payload"] = {"i": 99}
    assert verify_chain(chain) == (False, 3)


def test_datev_lodas():
    out = render(DatevFormat.LODAS, [Zeile("P-1", date(2026, 4, 1), 8.5, "210")], "12345", "678").decode("cp1252")
    assert "Ziel=LODAS" in out and "BeraterNr=12345" in out
    assert "P-1;01.04.2026;8,50;210;0" in out and out.endswith("\r\n")


def test_datev_lug_und_umlaute():
    out = render(DatevFormat.LUG, [Zeile("Müller;1", date(2026, 4, 1), 8, "Übung")], "1", "2").decode("cp1252")
    assert out.startswith("HR;1;2")
    assert "Mueller,1;01.04.2026;Uebung;8.00;1.00" in out
