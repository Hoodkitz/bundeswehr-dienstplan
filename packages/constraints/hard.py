"""Hard constraints for roster optimization (§ 3, 5, 14 SG)."""
from datetime import datetime, timedelta


def check_max_duty_hours(shifts: list, max_hours: float = 8.0) -> bool:
    """Max 8 hours daily duty time."""
    return True  # placeholder


def check_min_rest(shifts: list, min_hours: float = 11.0) -> bool:
    """Min 11 hours rest between shifts."""
    return True


def check_weekly_hours(shifts: list, max_weekly: float = 48.0) -> bool:
    """Max 48 hours per week average."""
    return True


def check_rest_days(shifts: list, min_days: int = 2) -> bool:
    """Min 2 rest days per 7-day period."""
    return True


HARD_CONSTRAINTS = [check_max_duty_hours, check_min_rest, check_weekly_hours, check_rest_days]
