"""Hard constraints for roster optimization (§ 3, 5, 14 SG)."""
from datetime import datetime, timedelta
from typing import List, Dict


class ConstraintViolation(Exception):
    pass


def check_max_duty_hours(shifts: List[Dict], max_hours: float = 8.0) -> bool:
    """Max 8 hours daily duty time per soldat."""
    from collections import defaultdict
    daily_hours = defaultdict(float)
    for shift in shifts:
        soldat_id = shift.get("soldat_id")
        start = datetime.fromisoformat(shift["start"])
        end = datetime.fromisoformat(shift["end"])
        hours = (end - start).total_seconds() / 3600
        day_key = (soldat_id, start.date().isoformat())
        daily_hours[day_key] += hours
        if daily_hours[day_key] > max_hours:
            return False
    return True


def check_min_rest(shifts: List[Dict], min_hours: float = 11.0) -> bool:
    """Min 11 hours rest between consecutive shifts."""
    sorted_shifts = sorted(shifts, key=lambda s: s["start"])
    by_soldat = {}
    for shift in sorted_shifts:
        sid = shift["soldat_id"]
        by_soldat.setdefault(sid, []).append(shift)
    for sid, slist in by_soldat.items():
        slist.sort(key=lambda s: s["start"])
        for i in range(1, len(slist)):
            prev_end = datetime.fromisoformat(slist[i-1]["end"])
            curr_start = datetime.fromisoformat(slist[i]["start"])
            rest = (curr_start - prev_end).total_seconds() / 3600
            if rest < min_hours:
                return False
    return True


def check_weekly_hours(shifts: List[Dict], max_weekly: float = 48.0) -> bool:
    """Max 48 hours per week average."""
    from collections import defaultdict
    weekly_hours = defaultdict(float)
    for shift in shifts:
        sid = shift["soldat_id"]
        start = datetime.fromisoformat(shift["start"])
        end = datetime.fromisoformat(shift["end"])
        hours = (end - start).total_seconds() / 3600
        week_key = (sid, start.isocalendar()[1])
        weekly_hours[week_key] += hours
        if weekly_hours[week_key] > max_weekly:
            return False
    return True


def check_rest_days(shifts: List[Dict], min_days: int = 2) -> bool:
    """Min 2 rest days per 7-day period."""
    from collections import defaultdict
    work_days = defaultdict(set)
    for shift in shifts:
        sid = shift["soldat_id"]
        start = datetime.fromisoformat(shift["start"])
        work_days[sid].add(start.date().isoformat())
    # Check each 7-day window
    for sid, days in work_days.items():
        sorted_days = sorted(days)
        for i in range(len(sorted_days)):
            window_start = datetime.fromisoformat(sorted_days[i]).date()
            window_end = window_start + timedelta(days=7)
            work_in_window = sum(1 for d in sorted_days if window_start <= datetime.fromisoformat(d).date() < window_end)
            rest_days = 7 - work_in_window
            if rest_days < min_days:
                return False
    return True


HARD_CONSTRAINTS = [check_max_duty_hours, check_min_rest, check_weekly_hours, check_rest_days]
