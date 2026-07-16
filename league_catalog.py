"""Canonical API-Football competition identifiers used by BetBoy.

Names and countries were verified against the provider's ``/leagues``
endpoint on 2026-07-11. Legacy short codes are retained for database and UI
compatibility, even where the old code itself is not descriptive.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LeagueDefinition:
    league_id: int
    name: str
    country: str
    code: Optional[str] = None
    calendar_year: bool = False
    rollover_month: int = 7


LEAGUES = (
    LeagueDefinition(78, "Bundesliga", "Germany", "BL1"),
    LeagueDefinition(39, "Premier League", "England", "PL"),
    LeagueDefinition(140, "La Liga", "Spain", "PD"),
    LeagueDefinition(135, "Serie A", "Italy", "SA"),
    LeagueDefinition(61, "Ligue 1", "France", "FL1"),
    LeagueDefinition(88, "Eredivisie", "Netherlands", "DED"),
    LeagueDefinition(94, "Primeira Liga", "Portugal", "PPL"),
    LeagueDefinition(203, "Super Lig", "Turkey", "TSL"),
    LeagueDefinition(40, "Championship", "England", "ELC"),
    LeagueDefinition(79, "2. Bundesliga", "Germany", "BL2"),
    LeagueDefinition(262, "Liga MX", "Mexico", "MX1"),
    LeagueDefinition(71, "Serie A", "Brazil", "BSA", calendar_year=True),
    LeagueDefinition(2, "UEFA Champions League", "World", "CL"),
    LeagueDefinition(3, "UEFA Europa League", "World", "EL"),
    LeagueDefinition(848, "UEFA Europa Conference League", "World", "ECL"),
    LeagueDefinition(179, "Premiership", "Scotland", "SC1"),
    LeagueDefinition(144, "Jupiler Pro League", "Belgium", "BE1"),
    LeagueDefinition(207, "Super League", "Switzerland", "SL1"),
    LeagueDefinition(218, "Bundesliga", "Austria", "AL1"),
    LeagueDefinition(265, "Primera Division", "Chile", "SPL", calendar_year=True),
    LeagueDefinition(330, "Premier League", "Kuwait", "ESI", rollover_month=8),
    LeagueDefinition(165, "1. Deild", "Iceland", "IS2", calendar_year=True),
    LeagueDefinition(188, "A-League", "Australia", "ALE", rollover_month=10),
    LeagueDefinition(89, "Eerste Divisie", "Netherlands", "ED1"),
    LeagueDefinition(209, "Schweizer Cup", "Switzerland", "CHL"),
    LeagueDefinition(113, "Allsvenskan", "Sweden", "ALL", calendar_year=True),
    LeagueDefinition(292, "K League 1", "South Korea", "QSL", calendar_year=True),
    LeagueDefinition(301, "Pro League", "United Arab Emirates", "UAE"),
    LeagueDefinition(41, "League One", "England"),
    LeagueDefinition(42, "League Two", "England"),
    LeagueDefinition(119, "Superliga", "Denmark"),
    LeagueDefinition(103, "Eliteserien", "Norway", calendar_year=True),
    LeagueDefinition(197, "Super League 1", "Greece", rollover_month=8),
    LeagueDefinition(345, "Czech Liga", "Czech Republic"),
    LeagueDefinition(283, "Liga I", "Romania"),
    LeagueDefinition(286, "Super Liga", "Serbia"),
    LeagueDefinition(210, "HNL", "Croatia"),
    LeagueDefinition(333, "Premier League", "Ukraine"),
    LeagueDefinition(106, "Ekstraklasa", "Poland"),
    LeagueDefinition(332, "Super Liga", "Slovakia"),
    LeagueDefinition(128, "Liga Profesional Argentina", "Argentina", calendar_year=True),
    LeagueDefinition(239, "Primera A", "Colombia", calendar_year=True),
    LeagueDefinition(274, "Liga 1", "Indonesia", rollover_month=8),
    LeagueDefinition(242, "Liga Pro", "Ecuador", calendar_year=True),
)


LEAGUE_BY_ID = {league.league_id: league for league in LEAGUES}
LEAGUE_BY_CODE = {
    league.code: league for league in LEAGUES if league.code is not None
}
ANALYZER_LEAGUE_IDS = {
    code: league.league_id for code, league in LEAGUE_BY_CODE.items()
}
ALTERNATIVE_MARKET_LEAGUES = {
    league.league_id: f"{league.country}: {league.name}" for league in LEAGUES
}


def league_code_for_id(league_id: int) -> Optional[str]:
    league = LEAGUE_BY_ID.get(league_id)
    return league.code if league else None
