"""Daytime planning, never proof of match finality or spendable returns.

The allowances include time for play and bookmaker settlement. They are a
conservative product rule, not measured duration forecasts. Only confirmed
settlement unlocks the next reservation; a delay can invalidate this plan.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

_TZ = ZoneInfo('Europe/Zurich')
_ALLOWANCES = {'football': 3, 'basketball': 3, 'hockey': 3,
               'tennis': 4, 'esports': 4}
_MIN_NEXT_LEG = timedelta(hours=min(_ALLOWANCES.values()))


def planning_allowance(sport):
    return timedelta(hours=_ALLOWANCES[sport])


def planned_ready_at(start, sport):
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError('Daily3 planning requires an aware kickoff')
    return start.astimezone(timezone.utc) + planning_allowance(sport)


def fits_daily3_window(start, sport, used_slots):
    """Keep daytime capacity for every remaining slot, without inventing tips."""
    if type(used_slots) is not int or not 0 <= used_slots < 3:
        return False
    if sport not in _ALLOWANCES or start.tzinfo is None or start.utcoffset() is None:
        return False
    tomorrow = start.astimezone(_TZ).date() + timedelta(days=1)
    deadline = datetime.combine(tomorrow, time.min, _TZ).astimezone(timezone.utc)
    return planned_ready_at(start, sport) + (2-used_slots)*_MIN_NEXT_LEG <= deadline


def pending_ready_at(bets, *, now):
    """Earliest *planned* follow-up; does not grant permission to reserve."""
    ready = now
    for bet in bets:
        if bet['status'] not in ('reserved', 'open'):
            continue
        snap = bet['snapshot']
        start = datetime.fromisoformat(snap['scheduled_start'])
        ready = max(ready, planned_ready_at(start, snap['sport']))
    return ready
