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
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests

MAN_TENNIS_BASE = (
    "https://raw.githubusercontent.com/msolonskyi/ManTennisData/master"
)
TENNIS_DATA_BASE = "http://www.tennis-data.co.uk"

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "data"

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


def _download(url: str, cache_path: Path, timeout: int = 60) -> Path:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    cache_path.write_bytes(response.content)
    return cache_path


def available_man_tennis_years(cache_dir: Path = DEFAULT_CACHE_DIR) -> range:
    """ATP stats coverage published by ManTennisData."""
    return range(1999, 2027)


# ---------------------------------------------------------------------------
# STATS plane loader (odds-blind)
# ---------------------------------------------------------------------------


def load_atp_stats(
    years: Optional[Iterable[int]] = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> pd.DataFrame:
    """Load ATP match statistics joined with tournament surface metadata.

    Returns one row per match with the allowlisted stats columns plus
    ``surface``, ``indoor_outdoor``, ``series_category_id`` and
    ``tourney_date`` (tournament start date, used as the conservative
    walk-forward cutoff key).  Guaranteed odds-blind.
    """
    if years is None:
        years = available_man_tennis_years()

    tournaments_path = _download(
        f"{MAN_TENNIS_BASE}/atp/tournaments.csv", cache_dir / "atp_tournaments.csv"
    )
    tournaments = pd.read_csv(tournaments_path, usecols=list(_STATS_TOURNAMENT_COLUMNS))
    tournaments = tournaments.rename(columns={"id": "tournament_id"})
    tournaments["tourney_date"] = pd.to_datetime(
        tournaments["start_dtm"].astype(str), format="%Y%m%d", errors="coerce"
    )

    frames = []
    for year in years:
        try:
            path = _download(
                f"{MAN_TENNIS_BASE}/atp/matches_{year}.csv",
                cache_dir / f"atp_matches_{year}.csv",
            )
        except requests.HTTPError:
            continue  # season not published yet
        frame = pd.read_csv(path, low_memory=False)
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
) -> pd.DataFrame:
    """Load tennis-data.co.uk season files with closing prices.

    EVALUATION ONLY: the returned frame carries bookmaker columns and
    must never be used to build model features.
    """
    wta = tour.lower() == "wta"
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
        try:
            path = _download(url, cache_dir / f"{tour.lower()}_odds_{year}.xlsx")
        except requests.HTTPError:
            continue
        frame = pd.read_excel(path)
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
