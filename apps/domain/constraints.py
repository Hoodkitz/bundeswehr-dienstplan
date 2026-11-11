"""SAZV / SG Constraint-Matrix (Spec Kap. 5).

Reine Python-Implementierung der ConstraintStreams-Logik, damit Regeln ohne
JVM testbar sind (analog Timefold ConstraintVerifier). Score ist lexikografisch
(hard, medium, soft); ein Plan ist zulaessig, wenn hard == 0.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from apps.core.enums import AbwesenheitTyp, AusnahmeModus, SchichtTyp


@dataclass
class Shift:
    id: str
    start: datetime
    end: datetime
    typ: SchichtTyp = SchichtTyp.GRUNDDIENST
    required_qualification: str | None = None
    soldat_id: str | None = None
    pinned: bool = False

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600

    @property
    def is_night(self) -> bool:
        """Nachtdienst: beruehrt das Fenster 23:00-05:00."""
        t = self.start
        while t < self.end:
            if t.hour >= 23 or t.hour < 5:
                return True
            t += timedelta(hours=1)
        return False

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.start < end and start < self.end


@dataclass
class Absence:
    start: datetime
    end: datetime
    typ: AbwesenheitTyp

    @property
    def is_hard(self) -> bool:
        return self.typ != AbwesenheitTyp.FREIWUNSCH


@dataclass
class Soldier:
    id: str
    qualifications: set[str] = field(default_factory=set)
    absences: list[Absence] = field(default_factory=list)
    sanitaet_opt_out: bool = False  # § 13 SAZV: bis 54h/Woche


@dataclass(frozen=True)
class RuleSet:
    min_rest_hours: float | None
    max_daily_hours: float | None
    weekly_cap_hours: float | None
    weekly_cap_sanitaet_opt_out: float | None


RULESETS: dict[AusnahmeModus, RuleSet] = {
    # Grundbetrieb: § 5 SAZV (11h Ruhe), § 7 SAZV (13h/Tag), § 12/13 SAZV (48h bzw. 54h/Woche)
    AusnahmeModus.KEINE: RuleSet(11, 13, 48, 54),
    # § 30c Abs. 4 SG: Sonderregeln. Werte sind konfigurierbare Defaults der Einheit.
    AusnahmeModus.UEBUNG: RuleSet(6, 16, None, None),
    AusnahmeModus.EINSATZ: RuleSet(None, None, None, None),
    AusnahmeModus.LANDESVERTEIDIGUNG: RuleSet(None, None, None, None),
}

HARD, MEDIUM, SOFT = "hard", "medium", "soft"


@dataclass(order=True)
class Score:
    hard: int = 0
    medium: int = 0
    soft: int = 0

    @property
    def feasible(self) -> bool:
        return self.hard == 0

    def __str__(self) -> str:
        return f"{self.hard}hard/{self.medium}medium/{self.soft}soft"


@dataclass
class Violation:
    constraint: str
    level: str
    penalty: int
    soldat_id: str | None
    shift_ids: list[str]
    detail: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


# --------------------------------------------------------------------------- Constraints

def ruhezeit_einhaltung(shifts: list[Shift], rules: RuleSet) -> list[Violation]:
    if rules.min_rest_hours is None:
        return []
    out = []
    for sid, own in _by_soldier(shifts).items():
        own = sorted(own, key=lambda s: s.start)
        for a, b in zip(own, own[1:]):
            gap = (b.start - a.end).total_seconds() / 3600
            if 0 <= gap < rules.min_rest_hours:
                out.append(Violation("ruhezeitEinhaltung", HARD, 1, sid, [a.id, b.id],
                                     f"Ruhezeit {gap:.1f}h < {rules.min_rest_hours}h"))
    return out


def max_tagesarbeitszeit(shifts: list[Shift], rules: RuleSet) -> list[Violation]:
    if rules.max_daily_hours is None:
        return []
    out = []
    for sid, own in _by_soldier(shifts).items():
        per_day: dict = defaultdict(list)
        for s in own:
            per_day[s.start.date()].append(s)
        for day, day_shifts in per_day.items():
            total = sum(s.hours for s in day_shifts)
            if total > rules.max_daily_hours:
                out.append(Violation("maxTagesarbeitszeit", HARD, 1, sid, [s.id for s in day_shifts],
                                     f"{day}: {total:.1f}h > {rules.max_daily_hours}h"))
    return out


def erforderliche_qualifikation(shifts: list[Shift], soldiers: dict[str, Soldier]) -> list[Violation]:
    out = []
    for s in shifts:
        if s.soldat_id and s.required_qualification:
            sol = soldiers.get(s.soldat_id)
            if sol is None or s.required_qualification not in sol.qualifications:
                out.append(Violation("erforderlicheQualifikation", HARD, 1, s.soldat_id, [s.id],
                                     f"Qualifikation '{s.required_qualification}' fehlt"))
    return out


def keine_doppelbelegung(shifts: list[Shift]) -> list[Violation]:
    out = []
    for sid, own in _by_soldier(shifts).items():
        own = sorted(own, key=lambda s: s.start)
        for i, a in enumerate(own):
            for b in own[i + 1:]:
                if b.start >= a.end:
                    break
                out.append(Violation("keineDoppelbelegung", HARD, 1, sid, [a.id, b.id],
                                     "Schichten ueberschneiden sich"))
    return out


def abwesenheit_beachten(shifts: list[Shift], soldiers: dict[str, Soldier]) -> list[Violation]:
    out = []
    for s in shifts:
        sol = soldiers.get(s.soldat_id) if s.soldat_id else None
        if not sol:
            continue
        for a in sol.absences:
            if a.is_hard and s.overlaps(a.start, a.end):
                out.append(Violation("abwesenheitBeachten", HARD, 1, sol.id, [s.id],
                                     f"Soldat abwesenheitsgemeldet ({a.typ.value})"))
    return out


def unbesetzte_schicht(shifts: list[Shift]) -> list[Violation]:
    return [Violation("unbesetzteSchicht", MEDIUM, 1, None, [s.id], "Schicht nicht besetzt")
            for s in shifts if s.soldat_id is None]


def bereitschafts_deckelung(shifts: list[Shift], soldiers: dict[str, Soldier], rules: RuleSet) -> list[Violation]:
    """§ 12/13 SAZV – Wochenhoechstarbeitszeit (Medium)."""
    if rules.weekly_cap_hours is None:
        return []
    out = []
    for sid, own in _by_soldier(shifts).items():
        sol = soldiers.get(sid)
        cap = rules.weekly_cap_hours
        if sol and sol.sanitaet_opt_out and rules.weekly_cap_sanitaet_opt_out:
            cap = rules.weekly_cap_sanitaet_opt_out
        per_week: dict = defaultdict(float)
        for s in own:
            per_week[tuple(s.start.isocalendar())[:2]] += s.hours
        for week, total in per_week.items():
            if total > cap:
                out.append(Violation("bereitschaftsDeckelung", MEDIUM, math.ceil(total - cap), sid, [],
                                     f"KW {week[1]}/{week[0]}: {total:.1f}h > {cap}h"))
    return out


def faire_belastungsverteilung(shifts: list[Shift], soldiers: dict[str, Soldier]) -> list[Violation]:
    """Soft: minimiert Varianz von Stunden und Nachtdiensten."""
    if not soldiers:
        return []
    hours = {sid: 0.0 for sid in soldiers}
    nights = {sid: 0 for sid in soldiers}
    for s in shifts:
        if s.soldat_id in hours:
            hours[s.soldat_id] += s.hours
            nights[s.soldat_id] += int(s.is_night)
    n = len(hours)
    mh = sum(hours.values()) / n
    mn = sum(nights.values()) / n
    var_h = sum((h - mh) ** 2 for h in hours.values()) / n
    var_n = sum((x - mn) ** 2 for x in nights.values()) / n
    penalty = int(round(var_h + 10 * var_n))
    if penalty == 0:
        return []
    return [Violation("faireBelastungsverteilung", SOFT, penalty, None, [],
                      f"Varianz Stunden {var_h:.1f}, Nachtdienste {var_n:.2f}")]


def soldaten_wunsch(shifts: list[Shift], soldiers: dict[str, Soldier]) -> list[Violation]:
    out = []
    for s in shifts:
        sol = soldiers.get(s.soldat_id) if s.soldat_id else None
        if not sol:
            continue
        for a in sol.absences:
            if not a.is_hard and s.overlaps(a.start, a.end):
                out.append(Violation("soldatenWunsch", SOFT, 10, sol.id, [s.id], "Freiwunsch nicht erfuellt"))
    return out


# --------------------------------------------------------------------------- Bewertung

def evaluate(shifts: list[Shift], soldiers: dict[str, Soldier],
             modus: AusnahmeModus = AusnahmeModus.KEINE) -> tuple[Score, list[Violation]]:
    rules = RULESETS[modus]
    violations = (
        ruhezeit_einhaltung(shifts, rules)
        + max_tagesarbeitszeit(shifts, rules)
        + erforderliche_qualifikation(shifts, soldiers)
        + keine_doppelbelegung(shifts)
        + abwesenheit_beachten(shifts, soldiers)
        + unbesetzte_schicht(shifts)
        + bereitschafts_deckelung(shifts, soldiers, rules)
        + faire_belastungsverteilung(shifts, soldiers)
        + soldaten_wunsch(shifts, soldiers)
    )
    score = Score()
    for v in violations:
        setattr(score, v.level, getattr(score, v.level) - v.penalty)
    return score, violations


def can_take(shift: Shift, soldier: Soldier, assigned: list[Shift], rules: RuleSet) -> bool:
    """Schnelle Hard-Pruefung fuer einen einzelnen Kandidaten (Konstruktionsheuristik)."""
    if shift.required_qualification and shift.required_qualification not in soldier.qualifications:
        return False
    if any(a.is_hard and shift.overlaps(a.start, a.end) for a in soldier.absences):
        return False
    day_hours = shift.hours
    for o in assigned:
        if o.overlaps(shift.start, shift.end):
            return False
        if rules.min_rest_hours is not None:
            gap = min(abs((shift.start - o.end).total_seconds()), abs((o.start - shift.end).total_seconds())) / 3600
            if gap < rules.min_rest_hours:
                return False
        if o.start.date() == shift.start.date():
            day_hours += o.hours
    if rules.max_daily_hours is not None and day_hours > rules.max_daily_hours:
        return False
    return True


def _by_soldier(shifts: list[Shift]) -> dict[str, list[Shift]]:
    res: dict[str, list[Shift]] = defaultdict(list)
    for s in shifts:
        if s.soldat_id:
            res[s.soldat_id].append(s)
    return res
