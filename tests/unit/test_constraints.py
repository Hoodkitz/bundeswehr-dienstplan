"""ConstraintVerifier-artige Tests (Spec Kap. 13)."""
from datetime import datetime as dt

from apps.core.enums import AbwesenheitTyp, AusnahmeModus
from apps.domain import constraints as c

RULES = c.RULESETS[AusnahmeModus.KEINE]


def sh(i, start, end, sid="A", qual=None):
    return c.Shift(str(i), start, end, required_qualification=qual, soldat_id=sid)


def test_ruhezeit_unterschritten_penalisiert_hard():
    # Spec-Beispiel: Ende 22 Uhr, Beginn 06 Uhr Folgetag -> 8h Ruhe
    v = c.ruhezeit_einhaltung([sh(1, dt(2026, 4, 1, 14), dt(2026, 4, 1, 22)),
                               sh(2, dt(2026, 4, 2, 6), dt(2026, 4, 2, 14))], RULES)
    assert len(v) == 1 and v[0].level == c.HARD and v[0].penalty == 1


def test_ruhezeit_11h_genau_ok():
    assert c.ruhezeit_einhaltung([sh(1, dt(2026, 4, 1, 8), dt(2026, 4, 1, 19)),
                                  sh(2, dt(2026, 4, 2, 6), dt(2026, 4, 2, 14))], RULES) == []


def test_ruhezeit_verschiedene_soldaten_ok():
    assert c.ruhezeit_einhaltung([sh(1, dt(2026, 4, 1, 14), dt(2026, 4, 1, 22), "A"),
                                  sh(2, dt(2026, 4, 2, 6), dt(2026, 4, 2, 14), "B")], RULES) == []


def test_max_tagesarbeitszeit():
    v = c.max_tagesarbeitszeit([sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14)),
                                sh(2, dt(2026, 4, 1, 15), dt(2026, 4, 1, 21))], RULES)
    assert len(v) == 1 and "14.0h" in v[0].detail
    assert c.max_tagesarbeitszeit([sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 19))], RULES) == []


def test_qualifikation_fehlt():
    soldiers = {"A": c.Soldier("A", {"Wachhabender"}), "B": c.Soldier("B")}
    shifts = [sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14), "A", "Wachhabender"),
              sh(2, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14), "B", "Wachhabender")]
    v = c.erforderliche_qualifikation(shifts, soldiers)
    assert [x.soldat_id for x in v] == ["B"]


def test_doppelbelegung():
    v = c.keine_doppelbelegung([sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14)),
                                sh(2, dt(2026, 4, 1, 13), dt(2026, 4, 1, 18))])
    assert len(v) == 1


def test_abwesenheit_hart_und_wunsch_weich():
    sol = c.Soldier("A", absences=[c.Absence(dt(2026, 4, 1), dt(2026, 4, 2), AbwesenheitTyp.KRANK),
                                   c.Absence(dt(2026, 4, 3), dt(2026, 4, 4), AbwesenheitTyp.FREIWUNSCH)])
    shifts = [sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14)), sh(2, dt(2026, 4, 3, 6), dt(2026, 4, 3, 14))]
    score, v = c.evaluate(shifts, {"A": sol})
    names = {x.constraint for x in v}
    assert "abwesenheitBeachten" in names and "soldatenWunsch" in names
    assert score.hard == -1 and score.soft <= -10


def test_wochendeckel_48h_und_sanitaet_opt_out():
    shifts = [sh(i, dt(2026, 4, 6 + i, 6), dt(2026, 4, 6 + i, 16)) for i in range(5)]  # 50h, KW 15
    v = c.bereitschafts_deckelung(shifts, {"A": c.Soldier("A")}, RULES)
    assert len(v) == 1 and v[0].level == c.HARD and v[0].penalty == 2
    assert c.bereitschafts_deckelung(shifts, {"A": c.Soldier("A", sanitaet_opt_out=True)}, RULES) == []


def test_ausnahme_30c_einsatz_hebt_zeitgrenzen_auf():
    shifts = [sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 22)), sh(2, dt(2026, 4, 2, 2), dt(2026, 4, 2, 10))]
    soldiers = {"A": c.Soldier("A")}
    normal, _ = c.evaluate(shifts, soldiers, AusnahmeModus.KEINE)
    einsatz, _ = c.evaluate(shifts, soldiers, AusnahmeModus.EINSATZ)
    assert normal.hard < 0 and einsatz.hard == 0


def test_uebung_sonderregeln():
    shifts = [sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 21)), sh(2, dt(2026, 4, 2, 4), dt(2026, 4, 2, 12))]
    score, v = c.evaluate(shifts, {"A": c.Soldier("A")}, AusnahmeModus.UEBUNG)
    assert score.hard == 0  # 15h <= 16h, 7h Ruhe >= 6h


def test_unbesetzt_ist_medium():
    score, _ = c.evaluate([sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14), None)], {})
    assert score.hard == 0 and score.medium == -1


def test_fairness_bevorzugt_gleichverteilung():
    soldiers = {"A": c.Soldier("A"), "B": c.Soldier("B")}
    unfair = [sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14), "A"), sh(2, dt(2026, 4, 2, 6), dt(2026, 4, 2, 14), "A")]
    fair = [sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14), "A"), sh(2, dt(2026, 4, 2, 6), dt(2026, 4, 2, 14), "B")]
    assert c.evaluate(fair, soldiers)[0] > c.evaluate(unfair, soldiers)[0]


def test_nachtdienst_erkennung():
    assert sh(1, dt(2026, 4, 1, 22), dt(2026, 4, 2, 6)).is_night
    assert not sh(1, dt(2026, 4, 1, 6), dt(2026, 4, 1, 14)).is_night
