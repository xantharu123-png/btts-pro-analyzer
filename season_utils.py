"""Season selection helpers for API-Football requests."""

from datetime import date, datetime
from typing import Optional, Union

from league_catalog import LEAGUE_BY_CODE, LEAGUE_BY_ID


DateLike = Union[date, datetime]

def current_season_start_year(
    league_code: Optional[str] = None,
    when: Optional[DateLike] = None,
) -> int:
    """Return the API-Football season year for the supplied competition/date."""
    reference = when or datetime.now()
    code = (league_code or "").upper()

    league = LEAGUE_BY_CODE.get(code)
    if league and league.calendar_year:
        return reference.year

    rollover_month = league.rollover_month if league else 7
    return reference.year if reference.month >= rollover_month else reference.year - 1


def current_season_start_year_for_id(
    league_id: int,
    when: Optional[DateLike] = None,
) -> int:
    """Return the provider season year for a canonical competition id."""
    reference = when or datetime.now()
    league = LEAGUE_BY_ID.get(league_id)
    if league and league.calendar_year:
        return reference.year
    rollover_month = league.rollover_month if league else 7
    return reference.year if reference.month >= rollover_month else reference.year - 1
