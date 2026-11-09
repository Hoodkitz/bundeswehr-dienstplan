"""Soft constraints for roster optimization."""
def minimize_night_shifts(shifts: list) -> float:
    """Minimize number of night shifts per person."""
    return 0.0

def maximize_fairness(shifts: list) -> float:
    """Maximize fairness (equal distribution)."""
    return 0.0

def minimize_weekend_work(shifts: list) -> float:
    """Minimize weekend work."""
    return 0.0

SOFT_CONSTRAINTS = [minimize_night_shifts, maximize_fairness, minimize_weekend_work]
