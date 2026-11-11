from datetime import datetime as dt, timedelta

from apps.core.enums import AbwesenheitTyp, AusnahmeModus
from apps.domain import constraints as c
from apps.domain.solver import solve, workload_stats


def wache(days=7, per_day=3, start=dt(2026, 4, 6)):
    """24/7 Wachdienst in 8h-Schichten."""
    shifts = []
    for d in range(days):
        for k in range(per_day):
            s = start + timedelta(days=d, hours=8 * k)
            shifts.append(c.Shift(f"{d}-{k}", s, s + timedelta(hours=8), required_qualification="Wache"))
    return shifts


def test_solver_findet_zulaessigen_plan():
    soldiers = [c.Soldier(f"S{i}", {"Wache"}) for i in range(6)]
    res = solve(wache(), soldiers, time_limit=2)
    assert res.score.hard == 0 and res.score.medium == 0
    assert all(s.soldat_id for s in res.shifts)


def test_solver_beachtet_qualifikation_und_abwesenheit():
    soldiers = [c.Soldier("Q1", {"Wache"}), c.Soldier("Q2", {"Wache"}), c.Soldier("Q3", {"Wache"}),
                c.Soldier("Q4", {"Wache"}, [c.Absence(dt(2026, 4, 6), dt(2026, 4, 20), AbwesenheitTyp.URLAUB)]),
                c.Soldier("OHNE")]
    res = solve(wache(days=2), soldiers, time_limit=1)
    used = {s.soldat_id for s in res.shifts}
    assert "OHNE" not in used and "Q4" not in used
    assert res.score.hard == 0


def test_solver_unloesbar_meldet_hard_oder_unbesetzt():
    res = solve(wache(days=1), [c.Soldier("A", {"Wache"})], time_limit=0.5)
    assert res.score.hard < 0 or res.score.medium < 0


def test_pinned_schichten_bleiben_fix():
    shifts = wache(days=2)
    shifts[0].soldat_id, shifts[0].pinned = "S5", True
    soldiers = [c.Soldier(f"S{i}", {"Wache"}) for i in range(6)]
    res = solve(shifts, soldiers, time_limit=1)
    assert next(s for s in res.shifts if s.id == shifts[0].id).soldat_id == "S5"


def test_solver_deterministisch():
    soldiers = [c.Soldier(f"S{i}", {"Wache"}) for i in range(5)]
    a = solve(wache(days=3), soldiers, time_limit=5, max_iterations=300)
    b = solve(wache(days=3), soldiers, time_limit=5, max_iterations=300)
    assert [s.soldat_id for s in a.shifts] == [s.soldat_id for s in b.shifts]


def test_workload_stats():
    soldiers = [c.Soldier(f"S{i}", {"Wache"}) for i in range(6)]
    res = solve(wache(days=2), soldiers, time_limit=1)
    st = workload_stats(res.shifts, soldiers)
    assert st["unbesetzt"] == 0 and sum(p["schichten"] for p in st["pro_soldat"].values()) == 6


def test_einsatzmodus_erlaubt_dichtere_plaene():
    soldiers = [c.Soldier("A", {"Wache"}), c.Soldier("B", {"Wache"})]
    normal = solve(wache(days=2), soldiers, AusnahmeModus.KEINE, time_limit=0.5)
    einsatz = solve(wache(days=2), soldiers, AusnahmeModus.EINSATZ, time_limit=0.5)
    assert einsatz.score > normal.score
