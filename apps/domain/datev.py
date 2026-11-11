"""DATEV-ASCII-Export (Spec Kap. 9): LODAS vs. Lohn und Gehalt."""
from dataclasses import dataclass
from datetime import date

from apps.core.enums import DatevFormat

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


@dataclass
class Zeile:
    personalnummer: str
    datum: date
    stunden: float
    lohnart: str
    bearbeitungsschluessel: str = "0"
    tagesfaktor: float = 1.0


def _ascii(text: str) -> str:
    return text.translate(_UMLAUTE).replace(";", ",")


def render(fmt: DatevFormat, zeilen: list[Zeile], berater_nr: str, mandant_nr: str) -> bytes:
    if fmt == DatevFormat.LODAS:
        lines = [
            "[Allgemein]",
            "Ziel=LODAS",
            f"BeraterNr={berater_nr}",
            f"MandantenNr={mandant_nr}",
            "[Satzbeschreibung]",
            "Personalnummer;Datum;Stunden;Lohnart;Bearbeitungsschluessel",
            "[Bewegungsdaten]",
        ]
        for z in zeilen:
            lines.append(";".join([
                _ascii(z.personalnummer), z.datum.strftime("%d.%m.%Y"),
                f"{z.stunden:.2f}".replace(".", ","), _ascii(z.lohnart), _ascii(z.bearbeitungsschluessel),
            ]))
    else:
        lines = [f"HR;{berater_nr};{mandant_nr}", "SR;Personalnummer;Datum;Art;Stunden;Tagesfaktor"]
        for z in zeilen:
            lines.append(";".join([
                _ascii(z.personalnummer), z.datum.strftime("%d.%m.%Y"), _ascii(z.lohnart),
                f"{z.stunden:.2f}", f"{z.tagesfaktor:.2f}",
            ]))
    return ("\r\n".join(lines) + "\r\n").encode("cp1252", errors="replace")
