"""Deterministischer Schichtplan-Solver (Konstruktionsheuristik + lokale Suche).

Stellvertreter fuer den Timefold-Service (ADR-01/02): gleiche Score-Semantik,
austauschbar ueber die Funktion `solve`.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, replace

from apps.core.enums import AusnahmeModus
from apps.domain.constraints import RULESETS, Score, Shift, Soldier, Violation, can_take, evaluate


@dataclass
class SolveResult:
    shifts: list[Shift]
    score: Score
    violations: list[Violation]
    iterations: int


def solve(shifts: list[Shift], soldiers: list[Soldier], modus: AusnahmeModus = AusnahmeModus.KEINE,
          time_limit: float = 5.0, max_iterations: int = 20000, seed: int = 42) -> SolveResult:
    rules = RULESETS[modus]
    by_id = {s.id: s for s in soldiers}
    work = [replace(s) if s.pinned else replace(s, soldat_id=None) for s in shifts]
    work.sort(key=lambda s: (s.start, s.id))

    # 1) Konstruktion: knappste Schichten zuerst, Kandidat mit wenigsten Stunden
    assigned: dict[str, list[Shift]] = {s.id: [] for s in soldiers}
    hours: dict[str, float] = {s.id: 0.0 for s in soldiers}
    for s in work:
        if s.soldat_id and s.soldat_id in assigned:
            assigned[s.soldat_id].append(s)
            hours[s.soldat_id] += s.hours

    def candidates(shift: Shift) -> list[Soldier]:
        return [so for so in soldiers if can_take(shift, so, assigned[so.id], rules)]

    open_shifts = [s for s in work if s.soldat_id is None]
    open_shifts.sort(key=lambda s: (len(candidates(s)), s.start))
    for s in open_shifts:
        cands = candidates(s)
        if not cands:
            continue
        wish_ok = [c for c in cands if not any(not a.is_hard and s.overlaps(a.start, a.end) for a in c.absences)]
        pool = wish_ok or cands
        best = min(pool, key=lambda c: (hours[c.id], c.id))
        s.soldat_id = best.id
        assigned[best.id].append(s)
        hours[best.id] += s.hours

    # 2) Lokale Suche (Hill Climbing): Reassign- und Swap-Zuege
    score, violations = evaluate(work, by_id, modus)
    rng = random.Random(seed)
    movable = [s for s in work if not s.pinned]
    deadline = time.monotonic() + time_limit
    it = 0
    if movable and soldiers:
        while it < max_iterations and time.monotonic() < deadline:
            it += 1
            if rng.random() < 0.5 or len(movable) < 2:
                s = rng.choice(movable)
                old = s.soldat_id
                s.soldat_id = rng.choice(soldiers).id
                new_score, new_v = evaluate(work, by_id, modus)
                if new_score > score:
                    score, violations = new_score, new_v
                else:
                    s.soldat_id = old
            else:
                a, b = rng.sample(movable, 2)
                if a.soldat_id == b.soldat_id:
                    continue
                a.soldat_id, b.soldat_id = b.soldat_id, a.soldat_id
                new_score, new_v = evaluate(work, by_id, modus)
                if new_score > score:
                    score, violations = new_score, new_v
                else:
                    a.soldat_id, b.soldat_id = b.soldat_id, a.soldat_id
            if score.hard == 0 and score.medium == 0 and score.soft == 0:
                break

    return SolveResult(work, score, violations, it)


def workload_stats(shifts: list[Shift], soldiers: list[Soldier]) -> dict:
    """Simulation & Belastungspruefung (SIMULATION_REVIEW)."""
    per = {s.id: {"stunden": 0.0, "schichten": 0, "nachtdienste": 0} for s in soldiers}
    for sh in shifts:
        if sh.soldat_id in per:
            p = per[sh.soldat_id]
            p["stunden"] += round(sh.hours, 2)
            p["schichten"] += 1
            p["nachtdienste"] += int(sh.is_night)
    hrs = [p["stunden"] for p in per.values()] or [0]
    return {
        "pro_soldat": per,
        "stunden_min": min(hrs),
        "stunden_max": max(hrs),
        "stunden_schnitt": round(sum(hrs) / len(hrs), 2),
        "unbesetzt": sum(1 for s in shifts if s.soldat_id is None),
    }
