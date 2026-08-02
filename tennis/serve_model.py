"""Rolling serve/return strength tracker built from match box scores.

For every player we keep cumulative sums (overall and per surface) of:

- service games played / held      -> hold percentage
- return games played / breaks     -> break percentage
- opponent quality faced           -> schedule adjustment

OPPONENT ADJUSTMENT (the part that separates a model from a toy):
a challenger regular can post a 0.84 grass hold% against weak
returners while a top-10 player posts 0.86 against elite ones.  Raw
percentages without schedule context are garbage.  For every service
game we therefore also accumulate the opponent's *current* shrunk
break%, and for every return game the opponent's *current* shrunk
hold%.  Raw rates are then deflated/inflated in odds form:

    adj_hold_odds = raw_hold_odds · (avg_opp_break_faced / TOUR_BREAK_AVG)
    adj_break_odds = raw_break_odds · (avg_opp_hold_faced / TOUR_HOLD_AVG)

Facing weak returners (avg_opp_break < tour avg) deflates an inflated
hold%, facing weak servers deflates an inflated break%.  The factor is
capped to [0.7, 1.4] so tiny samples cannot explode.

Matchup prediction for "A holds serve against B" combines the adjusted
abilities via a league-adjusted odds-ratio (log5 family):

    P(A holds) = hA·(1-bB)·(1-L) / (hA·(1-bB)·(1-L) + (1-hA)·bB·L)

with L = tour hold average.  It reduces EXACTLY to hA when B is a
league-average returner and moves in the right direction for
strong/weak returners.

Small samples are shrunk toward the tour average with a prior of
``PRIOR_GAMES`` games.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Dict, Optional, Tuple

from .data_loader import normalize_player_name

SURFACES = ("Hard", "Clay", "Grass", "Carpet")
OVERALL_KEY = "__overall__"

# F2: indoor/outdoor split.  Measured on tour-level box scores 2015-2026
# (ManTennisData): Hard Indoor hold 0.7996 (n=118'640 service games),
# Hard not-indoor 0.7924 (n=466'349 — Outdoor + missing flag).  Only
# Hard gets a compound bucket: grass has no indoor events at tour level
# and indoor clay is 54 matches in two seasons (n=2'988 — noise).
# The log5 league constant MUST come from the same environment as the
# ratings — two league-average players combined with the wrong L are off
# by 2.6 pp (checked numerically), so every environment carries its own
# average and sparse players are translated between scales in odds form.
HARD_INDOOR_KEY = "Hard@Indoor"
HARD_INDOOR_HOLD_AVG = 0.800
HARD_NOTINDOOR_HOLD_AVG = 0.792

# ATP tour averages (long-run): servers hold ~77%, returners break ~23%.
# WTA is a different universe (~70.6% hold, measured on Tennis Abstract
# top-100 box scores 2024-2026, n=56.6k service games): passing WTA rows
# through ATP constants would inflate every hold rating, so the averages
# are constructor parameters, not module constants.
TOUR_HOLD_AVG = 0.770
TOUR_BREAK_AVG = 0.230
WTA_TOUR_HOLD_AVG = 0.706
WTA_TOUR_BREAK_AVG = 1.0 - WTA_TOUR_HOLD_AVG
PRIOR_GAMES = 60.0
MIN_SURFACE_GAMES = 30.0
# opponent-adjustment factor is capped to this range
ADJUST_MIN, ADJUST_MAX = 0.70, 1.40

# Only tour-level events feed serve/return ratings.  Challenger box
# scores measure players against *challenger* opposition; mixing them
# in inflates journeymen (their "break%" comes against weak servers,
# so one opponent-adjustment pass cannot rescue them — circular
# reference).  Elo still consumes challengers (Elo is opponent-adjusted
# by construction); serve ratings must be level-pure.
TOUR_LEVEL_CATEGORIES = frozenset(
    {"gs", "1000", "atp500", "atp250", "og", "atpCup", "atpFinal", "wta_tour"}
)


def is_tour_level(row) -> bool:
    return row.get("series_category_id") in TOUR_LEVEL_CATEGORIES


class _Accum:
    __slots__ = ("sv_gms", "sv_held", "ret_gms", "ret_breaks",
                 "sv_opp_break_sum", "ret_opp_hold_sum", "last_date")

    def __init__(self) -> None:
        self.sv_gms = 0.0
        self.sv_held = 0.0
        self.ret_gms = 0.0
        self.ret_breaks = 0.0
        self.sv_opp_break_sum = 0.0   # sum(sv_gms * opponent break% at the time)
        self.ret_opp_hold_sum = 0.0   # sum(ret_gms * opponent hold% at the time)
        self.last_date = None         # date of the most recent contribution


def _to_naive_utc(value) -> Optional[datetime]:
    """Accept datetime/date/pandas Timestamp/ISO str -> naive UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, date):
        moment = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value[:19])
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _odds(p: float) -> float:
    p = min(max(p, 1e-4), 1.0 - 1e-4)
    return p / (1.0 - p)


def _from_odds(o: float) -> float:
    return o / (1.0 + o)


def _shift(p: float, from_avg: float, to_avg: float) -> float:
    """Translate a rate between environment scales in odds form.

    Identity at the source average: shifting the not-indoor average into
    the indoor world returns exactly the indoor average, so a player with
    no indoor data keeps his *relative* strength instead of his raw rate.
    """
    return _from_odds(_odds(p) * _odds(to_avg) / _odds(from_avg))


class ServeReturnModel:
    """Chronological tracker; state only moves when ``update`` is called.

    ``half_life_days``: exponential decay of every accumulator — a match
    counts half after one half-life, a quarter after two.  Ratings follow
    current form instead of career averages.  ``None`` keeps the old
    cumulative behaviour (used for the A/B backtest).
    """

    def __init__(self, hold_avg: float = TOUR_HOLD_AVG,
                 break_avg: float = TOUR_BREAK_AVG,
                 half_life_days: Optional[float] = 365.0,
                 split_indoor: bool = False) -> None:
        self._table: Dict[Tuple[str, str], _Accum] = defaultdict(_Accum)
        self._hold_avg = hold_avg
        self._break_avg = break_avg
        if half_life_days is not None and half_life_days <= 0:
            raise ValueError("half_life_days must be positive or None")
        self._half_life = half_life_days
        # ATP-only refinement; the WTA box-score feed has no indoor flag
        self._split_indoor = split_indoor

    # ------------------------------------------------------------------ decay

    def _decay_factor(self, acc: _Accum, as_of: Optional[datetime]) -> float:
        if self._half_life is None:
            return 1.0
        last = getattr(acc, "last_date", None)  # old pickles lack the slot
        moment = _to_naive_utc(as_of)
        if last is None or moment is None:
            return 1.0
        days = (moment - last).total_seconds() / 86400.0
        if days <= 0:
            return 1.0  # same day or out-of-order: never inflate
        return 0.5 ** (days / self._half_life)

    def _decayed(self, acc: _Accum, as_of: Optional[datetime]):
        f = self._decay_factor(acc, as_of)
        if f == 1.0:
            return (acc.sv_gms, acc.sv_held, acc.ret_gms, acc.ret_breaks,
                    acc.sv_opp_break_sum, acc.ret_opp_hold_sum)
        return (acc.sv_gms * f, acc.sv_held * f, acc.ret_gms * f,
                acc.ret_breaks * f, acc.sv_opp_break_sum * f,
                acc.ret_opp_hold_sum * f)

    # ------------------------------------------------------------------ update

    def update_from_match_row(self, row, match_date=None) -> None:
        """Consume one ManTennisData stats row (winner/loser box score)."""
        moment = _to_naive_utc(match_date if match_date is not None
                               else row.get("tourney_date"))
        surface = row.get("surface")
        keys = [OVERALL_KEY]
        if surface in SURFACES:
            if (self._split_indoor and surface == "Hard"
                    and row.get("indoor_outdoor") == "Indoor"):
                keys.append(HARD_INDOOR_KEY)  # keep "Hard" not-indoor-pure
            else:
                keys.append(surface)
        winner = self._player_name(row, "win")
        loser = self._player_name(row, "los")
        # Snapshot both opponent rates before either player consumes this match.
        # Otherwise the loser would be adjusted against a winner rate that
        # already contains the same match.
        winner_opponent_rates = self.hold_and_break(loser or "", None, as_of=moment)
        loser_opponent_rates = self.hold_and_break(winner or "", None, as_of=moment)
        self._add_player(
            row,
            "win",
            "los",
            keys,
            moment,
            opponent_rates=winner_opponent_rates,
        )
        self._add_player(
            row,
            "los",
            "win",
            keys,
            moment,
            opponent_rates=loser_opponent_rates,
        )

    _NAME_COLUMN = {"win": "winner_key", "los": "loser_key"}

    def _player_name(self, row, side: str) -> Optional[str]:
        name = row.get(self._NAME_COLUMN[side])
        if not name:
            raw = row.get("winner_name" if side == "win" else "loser_name")
            name = normalize_player_name(raw)
        return name if isinstance(name, str) and name else None

    def _add_player(
        self,
        row,
        me: str,
        opp: str,
        keys,
        moment,
        *,
        opponent_rates: Optional[Tuple[float, float]] = None,
    ) -> None:
        # rows must already carry normalized keys (add_normalized_names);
        # fall back to normalizing the raw name so callers can't mismatch
        name = row.get(self._NAME_COLUMN[me])
        opp_name = row.get(self._NAME_COLUMN[opp])
        if not name:
            raw = row.get("winner_name" if me == "win" else "loser_name")
            name = normalize_player_name(raw)
        if not opp_name:
            raw_opp = row.get("loser_name" if me == "win" else "winner_name")
            opp_name = normalize_player_name(raw_opp)
        if not isinstance(name, str) or not name:
            return
        sv_gms = _num(row.get(f"{me}_service_games_played"))
        ret_gms = _num(row.get(f"{me}_return_games_played"))
        # breaks I conceded = opponent's converted break points
        breaks_conceded = _num(row.get(f"{opp}_break_points_converted"))
        breaks_made = _num(row.get(f"{me}_break_points_converted"))
        if sv_gms is None or ret_gms is None or breaks_conceded is None or breaks_made is None:
            return  # no usable box score for this match

        # opponent's CURRENT overall rates (before this match) for the
        # schedule adjustment; tour average when the opponent is unknown
        if opponent_rates is None:
            opp_hold, opp_break = self.hold_and_break(
                opp_name if isinstance(opp_name, str) else "",
                None,
                as_of=moment,
            )
        else:
            opp_hold, opp_break = opponent_rates

        for key in keys:
            acc = self._table[(name, key)]
            # decay the past to this match's date, then add the match raw
            (d_sv, d_held, d_ret, d_brk, d_oppb, d_opph) = self._decayed(acc, moment)
            acc.sv_gms = d_sv + sv_gms
            acc.sv_held = d_held + max(sv_gms - breaks_conceded, 0.0)
            acc.ret_gms = d_ret + ret_gms
            acc.ret_breaks = d_brk + breaks_made
            acc.sv_opp_break_sum = d_oppb + sv_gms * opp_break
            acc.ret_opp_hold_sum = d_opph + ret_gms * opp_hold
            if moment is not None:
                last = getattr(acc, "last_date", None)
                acc.last_date = moment if last is None else max(last, moment)

    # -------------------------------------------------------------- prediction

    def _bucket_prior(self, key: str) -> Tuple[float, float]:
        """Shrinkage prior (hold, break) for a bucket — environment scale."""
        if key == HARD_INDOOR_KEY:
            return HARD_INDOOR_HOLD_AVG, 1.0 - HARD_INDOOR_HOLD_AVG
        if key == "Hard" and self._split_indoor:
            return HARD_NOTINDOOR_HOLD_AVG, 1.0 - HARD_NOTINDOOR_HOLD_AVG
        return self._hold_avg, self._break_avg

    def service_games(self, player: str, as_of: Optional[datetime] = None) -> float:
        """Decay-weighted tracked service games (overall) — for data gates."""
        acc = self._table.get((player, OVERALL_KEY))
        if acc is None:
            return 0.0
        return self._decayed(acc, as_of)[0]

    def _rates(self, player: str, key: str,
               as_of: Optional[datetime] = None) -> Tuple[Optional[float], Optional[float]]:
        acc = self._table.get((player, key))
        if acc is None:
            return None, None
        sv_gms, sv_held, ret_gms, ret_breaks, opp_break_sum, opp_hold_sum = (
            self._decayed(acc, as_of)
        )
        if sv_gms <= 0 or ret_gms <= 0:
            return None, None
        raw_hold = sv_held / sv_gms
        raw_break = ret_breaks / ret_gms

        # schedule adjustment in odds form (capped).  The opponent sums are
        # stored on the OVERALL scale, so the divisor stays the overall
        # average for every bucket — apples to apples.
        avg_opp_break = opp_break_sum / sv_gms
        avg_opp_hold = opp_hold_sum / ret_gms
        hold_factor = min(max(avg_opp_break / self._break_avg, ADJUST_MIN), ADJUST_MAX)
        break_factor = min(max(avg_opp_hold / self._hold_avg, ADJUST_MIN), ADJUST_MAX)
        adj_hold = _from_odds(_odds(raw_hold) * hold_factor)
        adj_break = _from_odds(_odds(raw_break) * break_factor)

        # shrinkage toward the bucket's environment average
        prior_hold, prior_break = self._bucket_prior(key)
        hold = (adj_hold * sv_gms + PRIOR_GAMES * prior_hold) / (
            sv_gms + PRIOR_GAMES
        )
        brk = (adj_break * ret_gms + PRIOR_GAMES * prior_break) / (
            ret_gms + PRIOR_GAMES
        )
        return hold, brk

    def _surface_rates(self, player: str, key: str,
                       as_of: Optional[datetime]):
        """Surface/compound bucket rates when the decayed sample is big
        enough, else None."""
        acc = self._table.get((player, key))
        if acc is None or self._decayed(acc, as_of)[0] < MIN_SURFACE_GAMES:
            return None, None
        return self._rates(player, key, as_of=as_of)

    def hold_and_break(
        self, player: str, surface: Optional[str],
        as_of: Optional[datetime] = None,
        indoor: Optional[bool] = None,
    ) -> Tuple[float, float]:
        """Adjusted + shrunk (hold%, break%), surface- and environment-aware.

        With ``split_indoor`` a Hard match knows three levels: the pure
        indoor bucket, the not-indoor bucket, and overall.  Fallback
        ratings are translated between environment scales in odds form so
        a league-average player stays league-average in both worlds.
        """
        if self._split_indoor and surface == "Hard":
            if indoor is True:
                hold_s, brk_s = self._surface_rates(player, HARD_INDOOR_KEY, as_of)
                if hold_s is not None:
                    return hold_s, brk_s
                hold_o, brk_o = self._surface_rates(player, "Hard", as_of)
                from_avg, from_break = HARD_NOTINDOOR_HOLD_AVG, 1.0 - HARD_NOTINDOOR_HOLD_AVG
                if hold_o is None:
                    hold_o, brk_o = self._rates(player, OVERALL_KEY, as_of=as_of)
                    from_avg, from_break = self._hold_avg, self._break_avg
                if hold_o is None:
                    return HARD_INDOOR_HOLD_AVG, 1.0 - HARD_INDOOR_HOLD_AVG
                return (
                    _shift(hold_o, from_avg, HARD_INDOOR_HOLD_AVG),
                    _shift(brk_o, from_break, 1.0 - HARD_INDOOR_HOLD_AVG),
                )
            # outdoor / unknown environment
            hold_s, brk_s = self._surface_rates(player, "Hard", as_of)
            if hold_s is not None:
                return hold_s, brk_s
            hold_o, brk_o = self._rates(player, OVERALL_KEY, as_of=as_of)
            if hold_o is None:
                return HARD_NOTINDOOR_HOLD_AVG, 1.0 - HARD_NOTINDOOR_HOLD_AVG
            return (
                _shift(hold_o, self._hold_avg, HARD_NOTINDOOR_HOLD_AVG),
                _shift(brk_o, self._break_avg, 1.0 - HARD_NOTINDOOR_HOLD_AVG),
            )

        hold_s, brk_s = (None, None)
        if surface in SURFACES:
            hold_s, brk_s = self._surface_rates(player, surface, as_of)
        hold_o, brk_o = self._rates(player, OVERALL_KEY, as_of=as_of)
        hold = hold_s if hold_s is not None else (hold_o if hold_o is not None else self._hold_avg)
        brk = brk_s if brk_s is not None else (brk_o if brk_o is not None else self._break_avg)
        return hold, brk

    def expected_hold_probabilities(
        self, player_a: str, player_b: str, surface: Optional[str],
        as_of: Optional[datetime] = None,
        indoor: Optional[bool] = None,
    ) -> Tuple[float, float]:
        """P(A holds serve vs B) and P(B holds serve vs A) via log5."""
        if self._split_indoor and surface == "Hard":
            league_hold = (HARD_INDOOR_HOLD_AVG if indoor is True
                           else HARD_NOTINDOOR_HOLD_AVG)
        else:
            league_hold = self._hold_avg
        hold_a, break_a = self.hold_and_break(player_a, surface, as_of=as_of, indoor=indoor)
        hold_b, break_b = self.hold_and_break(player_b, surface, as_of=as_of, indoor=indoor)
        p_a = _log5(hold_a, break_b, league_hold)
        p_b = _log5(hold_b, break_a, league_hold)
        return p_a, p_b


def _log5(rate: float, opp_counter_rate: float, league_hold: float = TOUR_HOLD_AVG) -> float:
    """League-adjusted odds-ratio combination on the hold% scale.

    rate             = A's hold% (vs average returners)
    opp_counter_rate = B's break% (vs average servers)

    Odds form, normalised by the tour hold average L:

        P = hA·(1-bB)·(1-L) / (hA·(1-bB)·(1-L) + (1-hA)·bB·L)

    Properties: B league-average (bB = 1-L) -> P = hA exactly;
    strong returner (bB > 1-L) pushes P below hA, weak above.
    """
    numerator = rate * (1.0 - opp_counter_rate) * (1.0 - league_hold)
    denominator = numerator + (1.0 - rate) * opp_counter_rate * league_hold
    if denominator <= 0:
        return rate
    return numerator / denominator


def _num(value) -> Optional[float]:
    try:
        if value is None or (isinstance(value, float) and value != value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
