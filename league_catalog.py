"""Canonical API-Football competition identifiers used by BetBoy.

Names and countries were verified against the provider's ``/leagues``
endpoint on 2026-07-11. Legacy short codes are retained for database and UI
compatibility, even where the old code itself is not descriptive.
"""

from dataclasses import dataclass
from typing import Optional


CATALOG_VERSION = 4


@dataclass(frozen=True)
class LeagueDefinition:
    league_id: int
    name: str
    country: str
    code: str
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
    LeagueDefinition(41, "League One", "England", "ENG3"),
    LeagueDefinition(42, "League Two", "England", "ENG4"),
    LeagueDefinition(119, "Superliga", "Denmark", "DEN1"),
    LeagueDefinition(103, "Eliteserien", "Norway", "NOR1", calendar_year=True),
    LeagueDefinition(197, "Super League 1", "Greece", "GRE1", rollover_month=8),
    LeagueDefinition(345, "Czech Liga", "Czech Republic", "CZE1"),
    LeagueDefinition(283, "Liga I", "Romania", "ROU1"),
    LeagueDefinition(286, "Super Liga", "Serbia", "SRB1"),
    LeagueDefinition(210, "HNL", "Croatia", "CRO1"),
    LeagueDefinition(333, "Premier League", "Ukraine", "UKR1"),
    LeagueDefinition(106, "Ekstraklasa", "Poland", "POL1"),
    LeagueDefinition(332, "Super Liga", "Slovakia", "SVK1"),
    LeagueDefinition(
        128,
        "Liga Profesional Argentina",
        "Argentina",
        "ARG1",
        calendar_year=True,
    ),
    LeagueDefinition(239, "Primera A", "Colombia", "COL1", calendar_year=True),
    LeagueDefinition(274, "Liga 1", "Indonesia", "IDN1", rollover_month=8),
    LeagueDefinition(242, "Liga Pro", "Ecuador", "ECU1", calendar_year=True),
    # Nordic additions 2026-07-30 (ids verified against /leagues on 2026-07-30):
    # complete the 1st+2nd tier pairs for the Scandinavian summer leagues.
    LeagueDefinition(114, "Superettan", "Sweden", "SWE2", calendar_year=True),
    LeagueDefinition(120, "1. Division", "Denmark", "DEN2"),
    LeagueDefinition(104, "1. Division", "Norway", "NOR2", calendar_year=True),
    LeagueDefinition(164, "Úrvalsdeild", "Iceland", "IS1", calendar_year=True),
    # Finland (Nordic, user request 2026-07-30; ids verified against /leagues):
    LeagueDefinition(244, "Veikkausliiga", "Finland", "FIN1", calendar_year=True),
    LeagueDefinition(245, "Ykkönen", "Finland", "FIN2", calendar_year=True),
)


def _sync_mapping(name: str, values: dict) -> dict:
    """Preserve imported mapping references across Streamlit module reloads."""
    existing = globals().get(name)
    if isinstance(existing, dict):
        existing.clear()
        existing.update(values)
        return existing
    return values


LEAGUE_BY_ID = _sync_mapping(
    "LEAGUE_BY_ID",
    {league.league_id: league for league in LEAGUES},
)
LEAGUE_BY_CODE = _sync_mapping(
    "LEAGUE_BY_CODE",
    {league.code: league for league in LEAGUES},
)
ANALYZER_LEAGUE_IDS = _sync_mapping(
    "ANALYZER_LEAGUE_IDS",
    {league.code: league.league_id for league in LEAGUES},
)
ALTERNATIVE_MARKET_LEAGUES = _sync_mapping(
    "ALTERNATIVE_MARKET_LEAGUES",
    {
        league.league_id: f"{league.country}: {league.name}"
        for league in LEAGUES
    },
)


def league_code_for_id(league_id: int) -> Optional[str]:
    league = LEAGUE_BY_ID.get(league_id)
    return league.code if league else None


def league_label_for_code(league_code: str) -> str:
    """Return a stable user-facing label while keeping codes as internal keys."""
    league = LEAGUE_BY_CODE.get(str(league_code).upper())
    if league is None:
        return str(league_code)
    return f"{league.country}: {league.name}"
