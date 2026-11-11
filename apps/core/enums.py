"""Fachliche Aufzaehlungen."""
from enum import Enum


class Role(str, Enum):
    SOLDAT = "soldat"
    PLANER = "planer"
    TRUPPENARZT = "truppenarzt"
    VORGESETZTER = "vorgesetzter"  # Einheitsfuehrer / Kommandeur, gibt nach § 10 SG frei
    ADMIN = "admin"
    AUDIT = "audit"


class AusnahmeModus(str, Enum):
    """§ 30c Abs. 4 SG – Ausnahmen vom Grundbetrieb."""
    KEINE = "keine"
    UEBUNG = "uebung"
    EINSATZ = "einsatz"
    LANDESVERTEIDIGUNG = "landesverteidigung"


class RosterStatus(str, Enum):
    DRAFT_INIT = "DRAFT_INIT"
    DATA_FETCHING = "DATA_FETCHING"
    CONSTRAINT_VALIDATION = "CONSTRAINT_VALIDATION"
    SOLVER_OPTIMIZING = "SOLVER_OPTIMIZING"
    HARDFEASIBILITY_CHECK = "HARDFEASIBILITY_CHECK"
    SIMULATION_REVIEW = "SIMULATION_REVIEW"
    COMMAND_APPROVAL_INTERRUPT = "COMMAND_APPROVAL_INTERRUPT"
    PUBLISHED = "PUBLISHED"
    REALTIME_REPLANNING = "REALTIME_REPLANNING"
    MANUAL_REVIEW = "MANUAL_REVIEW"  # Hard-Constraints verletzt -> Planer muss nacharbeiten
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class SchichtTyp(str, Enum):
    GRUNDDIENST = "GRUNDDIENST"
    WACHDIENST = "WACHDIENST"
    BEREITSCHAFT = "BEREITSCHAFT"
    SANITAETSDIENST = "SANITAETSDIENST"
    UEBUNG = "UEBUNG"
    LEHRGANG = "LEHRGANG"


class AbwesenheitTyp(str, Enum):
    URLAUB = "URLAUB"
    KRANK = "KRANK"
    LEHRGANG = "LEHRGANG"
    FREIWUNSCH = "FREIWUNSCH"  # weich: soldatenWunsch


class TradeStatus(str, Enum):
    OFFEN = "OFFEN"
    ANGENOMMEN = "ANGENOMMEN"  # Kamerad hat zugestimmt, wartet auf Planer
    GENEHMIGT = "GENEHMIGT"
    ABGELEHNT = "ABGELEHNT"


class DatevFormat(str, Enum):
    LODAS = "lodas"
    LUG = "lug"  # Lohn und Gehalt


class Dienstgrad(str, Enum):
    SOLDAT = "Soldat"
    GEFREITER = "Gefreiter"
    OBERGEFREITER = "Obergefreiter"
    HAUPTGEFREITER = "Hauptgefreiter"
    STABSGEFREITER = "Stabsgefreiter"
    UNTEROFFIZIER = "Unteroffizier"
    STABSUNTEROFFIZIER = "Stabsunteroffizier"
    FELDWEBEL = "Feldwebel"
    OBERFELDWEBEL = "Oberfeldwebel"
    HAUPTFELDWEBEL = "Hauptfeldwebel"
    LEUTNANT = "Leutnant"
    OBERLEUTNANT = "Oberleutnant"
    HAUPTMANN = "Hauptmann"
    MAJOR = "Major"
    OBERSTLEUTNANT = "Oberstleutnant"
    OBERST = "Oberst"
