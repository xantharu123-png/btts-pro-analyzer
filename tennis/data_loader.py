"""Tennis historical data loaders with a strict odds-blind boundary.

Two data planes, mirroring the football pipeline architecture:

1. STATS plane (odds-blind) — ManTennisData ATP match statistics
   (github.com/msolonskyi/ManTennisData, MIT-licensed scrape of
   atptour.com): per-match serve/return points, aces, double faults,
   break points, games, plus tournament surface/indoor metadata.
   Models may ONLY consume this plane.  An explicit allowlist makes
   sure no bookmaker column can cross the boundary (there are none in
   this source, the allowlist also guards future schema changes).

2. ODDS plane (evaluation only) — tennis-data.co.uk season files
   (ATP ``{year}.xlsx`` / WTA ``{year}w.xlsx`` over plain http):
   results plus Pinnacle (PSW/PSL) and Bet365 (B365W/B365L) closing
   prices.  Only the walk-forward backtest may read this plane to
   score model probabilities against the market.  Nothing from this
   plane may become a model feature.

Author: Miroslav
Date: July 2026
"""

from __future__ import annotations

import ast
import re
import unicodedata
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Callable, Collection, Iterable, Optional

import pandas as pd
import requests

from runtime_paths import (
    PACKAGED_TENNIS_TRAINING_DATA_DIR,
    TENNIS_TRAINING_DATA_DIR,
    _assert_no_symlink_components,
    atomic_write_bytes,
)

MAN_TENNIS_BASE = (
    "https://raw.githubusercontent.com/msolonskyi/ManTennisData/master"
)
TENNIS_DATA_BASE = "http://www.tennis-data.co.uk"

DEFAULT_CACHE_DIR = TENNIS_TRAINING_DATA_DIR

# ---------------------------------------------------------------------------
# STATS plane allowlist (odds-blind)
# ---------------------------------------------------------------------------

_STATS_MATCH_COLUMNS = (
    "id",
    "tournament_id",
    "stadie_id",  # round code: F, SF, QF, R16, ..., Q1
    "match_order",
    "match_ret",  # retirement flag, e.g. "(RET)"
    "winner_name",
    "loser_name",
    "winner_code",   # joins players.csv -> handedness
    "loser_code",
    "winner_age",
    "loser_age",
    "winner_seed",
    "loser_seed",
    "match_score",
    "winner_sets_won",
    "loser_sets_won",
    "winner_games_won",
    "loser_games_won",
    "match_duration",
    # winner serve/return box score
    "win_aces",
    "win_double_faults",
    "win_first_serves_in",
    "win_first_serves_total",
    "win_first_serve_points_won",
    "win_first_serve_points_total",
    "win_second_serve_points_won",
    "win_second_serve_points_total",
    "win_break_points_saved",
    "win_break_points_serve_total",
    "win_service_points_won",
    "win_service_points_total",
    "win_break_points_converted",
    "win_break_points_return_total",
    "win_service_games_played",
    "win_return_games_played",
    "win_return_points_won",
    "win_return_points_total",
    "win_total_points_won",
    "win_total_points_total",
    "win_net_points_won",     # sparse pre-2020, but the only style marker
    "win_net_points_total",   # the feed has: net-approach frequency
    # loser serve/return box score
    "los_aces",
    "los_double_faults",
    "los_first_serves_in",
    "los_first_serves_total",
    "los_first_serve_points_won",
    "los_first_serve_points_total",
    "los_second_serve_points_won",
    "los_second_serve_points_total",
    "los_break_points_saved",
    "los_break_points_serve_total",
    "los_service_points_won",
    "los_service_points_total",
    "los_break_points_converted",
    "los_break_points_return_total",
    "los_service_games_played",
    "los_return_games_played",
    "los_return_points_won",
    "los_return_points_total",
    "los_total_points_won",
    "los_total_points_total",
    "los_net_points_won",
    "los_net_points_total",
)

_STATS_TOURNAMENT_COLUMNS = (
    "id",
    "name",
    "year",
    "indoor_outdoor",
    "surface",
    "series_category_id",
    "start_dtm",
)

# Any column matching this pattern must never survive the stats allowlist.
_BOOKMAKER_PATTERN = re.compile(
    r"(B365|PS|PSW|PSL|SJW|SJL|LBW|LBL|EXW|EXL|MaxW|MaxL|AvgW|AvgL|odds)", re.I
)


def _assert_odds_blind(columns: Iterable[str]) -> None:
    leaked = [c for c in columns if _BOOKMAKER_PATTERN.search(c)]
    if leaked:
        raise AssertionError(f"Bookmaker columns crossed the stats plane: {leaked}")


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def cached_training_file(name: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    """Seed a missing canonical runtime file without changing packaged inputs.

    Explicit independent cache directories never inherit repository fixtures.
    This also provides offline tournament metadata to the daily fixture scan.
    """
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("training cache filename must be a single path component")
    target = Path(cache_dir) / name
    if Path(cache_dir) != DEFAULT_CACHE_DIR:
        return target
    _assert_no_symlink_components(target)
    if target.exists():
        return target
    seed = _assert_no_symlink_components(PACKAGED_TENNIS_TRAINING_DATA_DIR / name)
    if seed.is_file() and seed.stat().st_size > 0:
        atomic_write_bytes(target, seed.read_bytes(), replace_existing=False)
    return target


def _download(
    url: str, cache_path: Path, timeout: int = 60, *,
    refresh: bool = False, validate: Callable[[bytes], None] | None = None,
) -> Path:
    cache_path = cached_training_file(cache_path.name, cache_path.parent)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not refresh and cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.content
    if not payload:
        raise ValueError("training source returned an empty response")
    if validate is not None:
        validate(payload)
    return atomic_write_bytes(cache_path, payload)


def _training_table(payload: bytes, required: tuple[str, ...], *, excel: bool = False) -> pd.DataFrame:
    try:
        frame = pd.read_excel(BytesIO(payload)) if excel else pd.read_csv(BytesIO(payload), low_memory=False)
    except Exception as exc:
        raise ValueError("training source is not a valid table") from exc
    if frame.empty or not set(required).issubset(frame.columns):
        raise ValueError("training source is empty or lacks required result columns")
    return frame


def _require_values(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"training source has missing {column}")


def _validate_tournaments(payload: bytes) -> pd.DataFrame:
    frame = _training_table(payload, _STATS_TOURNAMENT_COLUMNS)
    _require_values(frame, ("id", "start_dtm"))
    if pd.to_datetime(frame["start_dtm"].astype(str), format="%Y%m%d", errors="coerce").isna().any():
        raise ValueError("training source has invalid tournament start dates")
    return frame


def _validate_atp_matches(payload: bytes) -> pd.DataFrame:
    required = ("id", "tournament_id", "winner_name", "loser_name")
    frame = _training_table(payload, required)
    _require_values(frame, ("id", "tournament_id"))
    frame = _completed_atp_rows(frame)
    if frame.empty:
        raise ValueError("training source has no complete player result rows")
    return frame


def _completed_atp_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Ignore source placeholders; both named participants are indispensable."""
    complete = frame["winner_name"].notna() & frame["loser_name"].notna()
    for column in ("winner_name", "loser_name"):
        complete &= frame[column].astype("string").str.strip().ne("").fillna(False)
    return frame[complete].copy()


def _validate_market_results(payload: bytes) -> pd.DataFrame:
    # WTA ratings consume these result fields, never bookmaker prices.
    required = ("Date", "Winner", "Loser", "Surface")
    frame = _training_table(payload, required, excel=True)
    _require_values(frame, required)
    if pd.to_datetime(frame["Date"], errors="coerce").isna().any():
        raise ValueError("training source has invalid result dates")
    return frame


def _assert_coverage_not_regressed(
    current: tuple[int, pd.Timestamp],
    previous: tuple[int, pd.Timestamp] | None,
    *,
    source: str,
) -> None:
    if previous is not None and (
        current[0] < previous[0] or current[1] < previous[1]
    ):
        raise ValueError(f"{source} active-year coverage regressed")


def _tournament_dates_for_year(
    frame: pd.DataFrame,
    year: int,
) -> dict[str, pd.Timestamp]:
    # Provider identities are opaque keys such as "2026-2801", not integers.
    ids = frame["id"].astype("string")
    years = pd.to_numeric(frame["year"], errors="coerce")
    dates = pd.to_datetime(
        frame["start_dtm"].astype(str),
        format="%Y%m%d",
        errors="coerce",
        utc=True,
    )
    mask = ids.notna() & years.eq(year) & dates.notna() & dates.dt.year.eq(year)
    return {
        str(tournament_id): tournament_date
        for tournament_id, tournament_date in zip(ids[mask], dates[mask])
    }


def _tournament_coverage(
    payload: bytes,
    *,
    year: int,
    as_of: pd.Timestamp,
) -> tuple[int, pd.Timestamp]:
    dates = _tournament_dates_for_year(_validate_tournaments(payload), year)
    causal = [value for value in dates.values() if value <= as_of]
    if not causal:
        raise ValueError(f"tournament source has no causal {year} coverage")
    return len(causal), max(causal)


def _atp_match_coverage(
    payload: bytes,
    *,
    tournament_dates: dict[str, pd.Timestamp],
    year: int,
    as_of: pd.Timestamp,
) -> tuple[int, pd.Timestamp]:
    frame = _validate_atp_matches(payload)
    tournament_ids = frame["tournament_id"].astype("string")
    dates = tournament_ids.map(tournament_dates)
    causal = dates.notna() & dates.le(as_of)
    if not causal.any():
        raise ValueError(f"ATP match source has no causal {year} coverage")
    return int(causal.sum()), dates[causal].max()


def _market_result_coverage(
    payload: bytes,
    *,
    year: int,
    as_of: pd.Timestamp,
) -> tuple[int, pd.Timestamp]:
    frame = _validate_market_results(payload)
    dates = pd.to_datetime(frame["Date"], errors="coerce", utc=True)
    causal = dates.notna() & dates.dt.year.eq(year) & dates.le(as_of)
    if not causal.any():
        raise ValueError(f"market result source has no causal {year} coverage")
    return int(causal.sum()), dates[causal].max()


def _previous_coverage(payload: bytes | None, loader) -> tuple[int, pd.Timestamp] | None:
    if payload is None:
        return None
    try:
        return loader(payload)
    except (TypeError, ValueError):
        return None


def available_man_tennis_years(cache_dir: Path = DEFAULT_CACHE_DIR) -> range:
    """ATP stats coverage published by ManTennisData."""
    return range(1999, 2027)


# ---------------------------------------------------------------------------
# STATS plane loader (odds-blind)
# ---------------------------------------------------------------------------


def load_atp_stats(
    years: Optional[Iterable[int]] = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    refresh_current: bool = False,
    current_year: int | None = None,
) -> pd.DataFrame:
    """Load ATP match statistics joined with tournament surface metadata.

    Returns one row per match with the allowlisted stats columns plus
    ``surface``, ``indoor_outdoor``, ``series_category_id`` and
    ``tourney_date`` (tournament start date, used as the conservative
    walk-forward cutoff key).  Guaranteed odds-blind.
    """
    if years is None:
        years = available_man_tennis_years()
    years = tuple(years)
    active_year = datetime.now(timezone.utc).year if current_year is None else current_year
    if refresh_current and active_year not in years:
        raise ValueError("active ATP year must be included in refreshed years")
    refresh_cutoff = pd.Timestamp(datetime.now(timezone.utc))

    # All seed baselines must exist before the refreshed metadata is validated:
    # a provider response may not silently remove previously consumed results.
    tournaments_cache = cached_training_file("atp_tournaments.csv", cache_dir)
    for year in years:
        cached_training_file(f"atp_matches_{year}.csv", cache_dir)
    previous_tournaments = (
        tournaments_cache.read_bytes()
        if refresh_current and tournaments_cache.exists()
        else None
    )
    if refresh_current:
        def validate_tournaments(payload: bytes) -> None:
            _tournament_coverage(
                payload, year=active_year, as_of=refresh_cutoff,
            )
            # Calendar entries without results may be cancelled or corrected.
            # Protect actual completed history, not the number of empty events.
            prior_matches_path = cache_dir / f"atp_matches_{active_year}.csv"
            if previous_tournaments is not None and prior_matches_path.exists():
                prior_matches = prior_matches_path.read_bytes()
                def coverage_with_metadata(metadata: bytes) -> tuple[int, pd.Timestamp]:
                    return _atp_match_coverage(
                        prior_matches,
                        tournament_dates=_tournament_dates_for_year(_validate_tournaments(metadata), active_year),
                        year=active_year, as_of=refresh_cutoff,
                    )
                previous = _previous_coverage(previous_tournaments, coverage_with_metadata)
                if previous is not None:
                    old_dates = _tournament_dates_for_year(_validate_tournaments(previous_tournaments), active_year)
                    new_dates = _tournament_dates_for_year(_validate_tournaments(payload), active_year)
                    completed_ids = set(_validate_atp_matches(prior_matches)["tournament_id"].astype("string"))
                    consumed_ids = {key for key in completed_ids if key in old_dates and old_dates[key] <= refresh_cutoff}
                    new_causal_ids = {key for key, value in new_dates.items() if value <= refresh_cutoff}
                    if not consumed_ids.issubset(new_causal_ids):
                        raise ValueError("ATP completed tournament history lost source identities")
                    _assert_coverage_not_regressed(
                        coverage_with_metadata(payload), previous,
                        source="ATP completed tournament history",
                    )
        tournament_validator = validate_tournaments
    else:
        tournament_validator = _validate_tournaments
    tournaments_path = _download(
        f"{MAN_TENNIS_BASE}/atp/tournaments.csv",
        tournaments_cache,
        refresh=refresh_current,
        validate=tournament_validator,
    )
    tournaments = pd.read_csv(tournaments_path, usecols=list(_STATS_TOURNAMENT_COLUMNS))
    tournaments = tournaments.rename(columns={"id": "tournament_id"})
    tournaments["tourney_date"] = pd.to_datetime(
        tournaments["start_dtm"].astype(str), format="%Y%m%d", errors="coerce"
    )

    frames = []
    for year in years:
        refresh_year = refresh_current and year == active_year
        match_cache = cache_dir / f"atp_matches_{year}.csv"
        tournament_dates = _tournament_dates_for_year(
            tournaments.rename(columns={"tournament_id": "id"}), year,
        )
        previous_matches = (
            match_cache.read_bytes()
            if refresh_year and match_cache.exists()
            else None
        )
        if refresh_year:
            def validate_matches(payload: bytes) -> None:
                coverage = _atp_match_coverage(
                    payload,
                    tournament_dates=tournament_dates,
                    year=year,
                    as_of=refresh_cutoff,
                )
                previous = _previous_coverage(
                    previous_matches,
                    lambda value: _atp_match_coverage(
                        value,
                        tournament_dates=tournament_dates,
                        year=year,
                        as_of=refresh_cutoff,
                    ),
                )
                _assert_coverage_not_regressed(
                    coverage, previous, source="ATP match",
                )
            match_validator = validate_matches
        else:
            match_validator = _validate_atp_matches
        try:
            path = _download(
                f"{MAN_TENNIS_BASE}/atp/matches_{year}.csv",
                match_cache,
                refresh=refresh_year,
                validate=match_validator,
            )
        except requests.HTTPError:
            if refresh_year:
                raise  # Never present an old/omitted active season as refreshed.
            continue  # season not published yet
        frame = pd.read_csv(path, low_memory=False)
        frame = _completed_atp_rows(frame)
        frame_ids = frame["tournament_id"].astype("string")
        frame = frame[frame_ids.isin(tournament_dates)].copy()
        keep = [c for c in _STATS_MATCH_COLUMNS if c in frame.columns]
        frames.append(frame[keep])
    if not frames:
        raise RuntimeError("No ATP stats files could be loaded")

    matches = pd.concat(frames, ignore_index=True)
    merged = matches.merge(
        tournaments[
            [
                "tournament_id",
                "surface",
                "indoor_outdoor",
                "series_category_id",
                "tourney_date",
            ]
        ],
        on="tournament_id",
        how="left",
    )
    merged["tour"] = "ATP"
    _assert_odds_blind(merged.columns)
    return merged


# ---------------------------------------------------------------------------
# ODDS plane loader (evaluation only — never feed into models)
# ---------------------------------------------------------------------------

_ODDS_COLUMNS = (
    "Date",
    "Tournament",
    "Surface",
    "Court",
    "Round",
    "Best of",
    "Winner",
    "Loser",
    "WRank",
    "LRank",
    "Wsets",
    "Lsets",
    "W1", "L1", "W2", "L2", "W3", "L3", "W4", "L4", "W5", "L5",
    "Comment",
    "B365W", "B365L",
    "PSW", "PSL",
    "AvgW", "AvgL",
)


def load_market_odds(
    years: Iterable[int],
    tour: str = "atp",
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    refresh_current: bool = False,
    current_year: int | None = None,
) -> pd.DataFrame:
    """Load tennis-data.co.uk season files with closing prices.

    EVALUATION ONLY: the returned frame carries bookmaker columns and
    must never be used to build model features.
    """
    wta = tour.lower() == "wta"
    years = tuple(years)
    active_year = datetime.now(timezone.utc).year if current_year is None else current_year
    if refresh_current and active_year not in years:
        raise ValueError("active market year must be included in refreshed years")
    refresh_cutoff = pd.Timestamp(datetime.now(timezone.utc))
    frames = []
    for year in years:
        # WTA lives in a suffixed DIRECTORY (2024w/2024.xlsx); the old
        # file-suffix scheme (2024/2024w.xlsx) now 301-redirects to the ATP
        # file, which would silently poison WTA ratings with men's matches.
        url = (
            f"{TENNIS_DATA_BASE}/{year}w/{year}.xlsx"
            if wta
            else f"{TENNIS_DATA_BASE}/{year}/{year}.xlsx"
        )
        refresh_year = refresh_current and year == active_year
        market_cache = cached_training_file(f"{tour.lower()}_odds_{year}.xlsx", cache_dir)
        previous_market = (
            market_cache.read_bytes()
            if refresh_year and market_cache.exists()
            else None
        )
        if refresh_year:
            def validate_market(payload: bytes) -> None:
                coverage = _market_result_coverage(
                    payload, year=year, as_of=refresh_cutoff,
                )
                previous = _previous_coverage(
                    previous_market,
                    lambda value: _market_result_coverage(
                        value, year=year, as_of=refresh_cutoff,
                    ),
                )
                _assert_coverage_not_regressed(
                    coverage, previous, source=f"{tour.upper()} result",
                )
            market_validator = validate_market
        else:
            market_validator = _validate_market_results
        try:
            path = _download(
                url,
                market_cache,
                refresh=refresh_year,
                validate=market_validator,
            )
        except requests.HTTPError:
            if refresh_year:
                raise
            continue
        frame = pd.read_excel(path)
        frame_dates = pd.to_datetime(frame["Date"], errors="coerce", utc=True)
        frame = frame[frame_dates.dt.year.eq(year)].copy()
        keep = [c for c in _ODDS_COLUMNS if c in frame.columns]
        frames.append(frame[keep])
    if not frames:
        raise RuntimeError(f"No {tour.upper()} odds files could be loaded")
    odds = pd.concat(frames, ignore_index=True)
    odds["tour"] = tour.upper()
    odds["Date"] = pd.to_datetime(odds["Date"], errors="coerce")
    return odds


# ---------------------------------------------------------------------------
# Name normalisation (joins stats plane <-> odds plane)
# ---------------------------------------------------------------------------


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


_SURNAME_PARTICLES = {
    "de", "del", "der", "den", "di", "da", "dos", "du", "van", "von",
    "la", "le", "el", "o",
}
_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

# manual fixes for compound surnames neither source spells consistently
_NAME_KEY_ALIASES = {
    "perricard g": "mpetshi perricard g",
}


def normalize_player_name(value: object) -> str:
    """Normalise to ``'surname f'`` so both sources agree.

    Handles the hard cases that break naive normalisation:

    - 'Roman Andres Burruchaga'  -> 'burruchaga r'   (middle names dropped)
    - 'Alex de Minaur'           -> 'de minaur a'    (surname particles kept)
    - 'Botic van de Zandschulp'  -> 'van de zandschulp b'
    - \"Christopher O'Connell\"   -> 'oconnell c'      (apostrophe stripped)
    - 'O Connell C.'             -> 'oconnell c'     (both sources agree)
    - 'Andre J.B.'               -> 'andre j'        (first initial wins)
    """
    text = _strip_accents(str(value or "")).casefold().strip()
    text = text.replace("'", "").replace("`", "")
    text = re.sub(r"[^a-z\s]", " ", text)
    parts = [p for p in text.split() if p and p not in _NAME_SUFFIXES]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]

    # trailing single letters are initials ('Federer R.', 'Andre J B')
    initials = []
    while parts and len(parts[-1]) == 1:
        initials.append(parts.pop())
    if initials:
        initial = initials[-1]  # first given initial (last appended)
        surname_tokens = parts
    else:
        initial = parts[0][0]
        surname_tokens = parts[1:]
    if not surname_tokens:
        return ""

    # pull surname particles toward the end ('... van de zandschulp')
    start = len(surname_tokens) - 1
    while start > 0 and surname_tokens[start - 1] in _SURNAME_PARTICLES:
        start -= 1
    surname = " ".join(surname_tokens[start:])
    if surname.startswith("o "):  # Irish 'O Connor' -> 'oconnor'
        surname = "o" + surname[2:]
    key = f"{surname} {initial}"
    return _NAME_KEY_ALIASES.get(key, key)


def resolve_player_name_key(
    value: object,
    known_player_keys: Collection[str],
) -> str:
    """Resolve provider name order only when history proves the alternative.

    Some scoreboards emit East Asian names surname-first (for example
    ``Shang Juncheng``), while the historical feed stores ``Juncheng Shang``.
    A global reversal would corrupt ordinary names. The fallback therefore
    applies only to two-token names when the direct key is unknown and the
    reversed key already exists in the model roster.
    """
    direct = normalize_player_name(value)
    if not direct or direct in known_player_keys:
        return direct

    text = _strip_accents(str(value or "")).casefold().strip()
    text = text.replace("'", "").replace("`", "")
    parts = [
        part
        for part in re.sub(r"[^a-z\s]", " ", text).split()
        if part and part not in _NAME_SUFFIXES
    ]
    if len(parts) != 2:
        return direct
    reversed_key = normalize_player_name(" ".join(reversed(parts)))
    return reversed_key if reversed_key in known_player_keys else direct


def add_normalized_names(frame: pd.DataFrame, winner_col: str, loser_col: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["winner_key"] = frame[winner_col].map(normalize_player_name)
    frame["loser_key"] = frame[loser_col].map(normalize_player_name)
    return frame


# ---------------------------------------------------------------------------
# Tennis Abstract WTA leaderboard box scores (top 100), 2024 -> today
# ---------------------------------------------------------------------------
#
# Jeff Sackmann's original GitHub repos (tennis_wta) are offline and the
# surviving forks stop in 2023, but Tennis Abstract keeps publishing full
# per-match box scores for the leaderboard pool (ranks 1-50 and 51-100)
# as JS match matrices.  This is the same data family that feeds our ATP
# stats plane (ManTennisData is derived from Sackmann), so WTA serve/return
# ratings can finally be built on box scores instead of Elo alone.
#
# License note: CC BY-NC-SA 4.0 (Jeff Sackmann / Tennis Abstract) — fine
# for private use; requires a licensing conversation before any commercial
# distribution of the app.

TA_LEADERSOURCE_URLS = (
    ("wta_top50", "https://www.tennisabstract.com/jsmatches/leadersource_wta.js"),
    ("wta_51_100", "https://www.tennisabstract.com/jsmatches/leadersource51_wta.js"),
)

# matchmx row layout (45 columns, 'matchhead' on the leaderboard page)
_TA = {
    "date": 0, "tourn": 1, "surf": 2, "level": 3, "wl": 4, "player": 5,
    "round": 9, "opp": 12,
    "aces": 27, "dfs": 28, "pts": 29, "firsts": 30, "fwon": 31, "swon": 32,
    "games": 33, "saved": 34, "chances": 35,
    "ogames": 42, "osaved": 43, "ochances": 44,
}

# Tour-level categories only: G=Slam, PM=1000, P=500/700, I=250,
# F=Finals, O=Olympics.  Dropped: D=BJK Cup (team event), W=WTA 125
# (challenger level — same purity rule as ATP challengers).
TA_TOUR_LEVELS = frozenset({"G", "PM", "P", "I", "F", "O"})


def _ta_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_wta_ta_stats(cache_dir: Path = DEFAULT_CACHE_DIR) -> pd.DataFrame:
    """Load Tennis Abstract WTA box scores, one row per match (winner view).

    Returns the SAME schema as the ATP stats plane so ServeReturnModel,
    the walk-forward backtest and build_state can consume it unchanged:
    tourney_date, winner_name, loser_name, surface, win_/los_ box-score
    columns, series_category_id ('wta_tour' for tour-level filtering).

    A match appears once per leaderboard participant (winner view when the
    winner is in the pool, loser view when only the loser is); we
    normalise every row to the winner's perspective and de-duplicate,
    preferring the winner view.
    """
    rows = {}
    for tag, url in TA_LEADERSOURCE_URLS:
        try:
            path = _download(url, cache_dir / f"{tag}_leadersource.js")
        except requests.HTTPError:
            continue
        text = path.read_text(encoding="utf-8")
        start = text.find("var matchmx = ")
        if start < 0:
            continue
        end = text.find("];", start)
        matrix = ast.literal_eval(text[start + len("var matchmx = "):end + 1].strip())
        for r in matrix:
            level = r[_TA["level"]]
            if level not in TA_TOUR_LEVELS:
                continue
            date = str(r[_TA["date"]])
            won = r[_TA["wl"]] == "W"
            winner = r[_TA["player"]] if won else r[_TA["opp"]]
            loser = r[_TA["opp"]] if won else r[_TA["player"]]
            # box-score columns from the winner's perspective
            w_games = _ta_int(r[_TA["games"] if won else _TA["ogames"]])
            l_games = _ta_int(r[_TA["ogames"] if won else _TA["games"]])
            w_saved = _ta_int(r[_TA["saved"] if won else _TA["osaved"]])
            w_chances = _ta_int(r[_TA["chances"] if won else _TA["ochances"]])
            l_saved = _ta_int(r[_TA["osaved"] if won else _TA["saved"]])
            l_chances = _ta_int(r[_TA["ochances"] if won else _TA["chances"]])
            if None in (w_games, l_games, w_saved, w_chances, l_saved, l_chances):
                continue
            key = (date, winner, loser)
            if won or key not in rows:  # winner view wins the de-dup
                rows[key] = {
                    "tourney_date": pd.to_datetime(date, format="%Y%m%d", errors="coerce"),
                    "tourney_name": r[_TA["tourn"]],
                    "winner_name": winner,
                    "loser_name": loser,
                    "surface": r[_TA["surf"]] or None,
                    "win_service_games_played": w_games,
                    "los_service_games_played": l_games,
                    "win_return_games_played": l_games,
                    "los_return_games_played": w_games,
                    # winner's breaks = break chances the loser failed to save
                    "win_break_points_converted": l_chances - l_saved,
                    "los_break_points_converted": w_chances - w_saved,
                    "win_break_points_saved": w_saved,
                    "los_break_points_saved": l_saved,
                    "series_category_id": "wta_tour",
                    "tour": "WTA",
                }
    frame = pd.DataFrame(rows.values())
    if len(frame):
        frame = frame.dropna(subset=["tourney_date"]).sort_values(
            "tourney_date", kind="mergesort"
        ).reset_index(drop=True)
    return frame
