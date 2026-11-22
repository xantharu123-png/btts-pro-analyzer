"""Open regulation-time goal markets on two paired, price-independent rest-of-game laws."""

from dataclasses import dataclass
from itertools import accumulate
import math

from redcard_events import period_clock, score_pair


@dataclass(frozen=True)
class LiveMarketPick:
    market: str
    side: str
    label: str
    probability: float
    reference: float


@dataclass(frozen=True)
class _Event:
    """Inclusive integer interval on the final count or goal margin; None means unbounded."""

    axis: str
    low: int | None = None
    high: int | None = None
    invert: bool = False

    def contains(self, value):
        inside = (self.low is None or value >= self.low) and (self.high is None or value <= self.high)
        return not inside if self.invert else inside


_MARKETS = {
    "ft_result": "Spielausgang",
    "ft_dc": "Doppelte Chance",
    "ft_handicap": "Handicap",
    "ft_total": "Gesamttore",
    "ft_team_total": "Teamtore",
    "ft_multigoal": "Torbereich",
    "next_goal": "Noch ein Tor",
    "team_scores": "Team trifft noch",
    "btts": "BTTS",
    "next_scorer": "Nächstes Tor",
}


def _catalog():
    # A single outcome definition drives display, probability, open status and final settlement.
    e = _Event
    rows = {
        ("ft_result", "home"): (e("margin", 1), "Sieg {home}"),
        ("ft_result", "draw"): (e("margin", 0, 0), "Unentschieden"),
        ("ft_result", "away"): (e("margin", high=-1), "Sieg {away}"),
        ("ft_dc", "1x"): (e("margin", 0), "{home} oder Unentschieden"),
        ("ft_dc", "x2"): (e("margin", high=0), "{away} oder Unentschieden"),
        ("ft_dc", "12"): (e("margin", 0, 0, True), "Kein Unentschieden"),
        ("btts", "yes"): (e("btts", 1), "Beide Teams treffen"),
        ("btts", "no"): (e("btts", 1, invert=True), "Mindestens ein Team bleibt ohne Tor"),
        ("next_goal", "any"): (e("remaining_total", 1), "Mindestens 1 weiteres Tor"),
        ("team_scores", "home"): (e("remaining_home", 1), "{home} trifft noch"),
        ("team_scores", "away"): (e("remaining_away", 1), "{away} trifft noch"),
        ("next_scorer", "home"): (e("next_home"), "Nächstes Tor: {home}"),
        ("next_scorer", "away"): (e("next_away"), "Nächstes Tor: {away}"),
        ("next_scorer", "none"): (e("remaining_total", 0, 0), "Kein weiteres Tor"),
    }
    for axis in ("total", "home", "away"):
        group = "ft_total" if axis == "total" else "ft_team_total"
        prefix = "" if axis == "total" else axis + "_"
        for n in range(5 if axis == "total" else 3):
            for direction, label, event in (("over", "Über", e(axis, n + 1)), ("under", "Unter", e(axis, high=n))):
                text = (
                    f"{label} {n},5 Tore im Spiel"
                    if axis == "total"
                    else "{" + axis + "}: " + f"{label} {n},5 Tore"
                )
                rows[group, f"{prefix}{direction}_{n}_5"] = event, text
        bounds = ((1, 3), (1, 4), (2, 4), (2, 3)) if axis == "total" else ((1, 3), (1, 4), (2, 4))
        for lo, hi in bounds:
            text = f"{lo}–{hi} Tore im Spiel" if axis == "total" else "{" + axis + "}: " + f"{lo}–{hi} Tore"
            rows["ft_multigoal", f"{axis}_{lo}_{hi}"] = e(axis, lo, hi), text
    for team in ("home", "away"):
        for n in (0, 1):
            for sign, symbol in (("minus", "−"), ("plus", "+")):
                # home + handicap > away, or equivalently margin below the mirrored away cut.
                cut = n + 1 if sign == "minus" else -n
                event = e("margin", cut) if team == "home" else e("margin", high=-cut)
                rows["ft_handicap", f"{team}_{sign}_{n}_5"] = event, "{" + team + "} Handicap " + f"{symbol}{n},5"
    return rows


_CATALOG = _catalog()
_SIDES = {key: tuple(side for market, side in _CATALOG if market == key) for key in _MARKETS}
_RELATIVE = {"next_goal", "team_scores", "next_scorer"}


def catalog_sides():
    return dict(_SIDES)


def display_market(market):
    return _MARKETS.get(market, "") if isinstance(market, str) else ""


def _entry(market, side):
    return _CATALOG.get((market, side)) if isinstance(market, str) and isinstance(side, str) else None


def selection_labels(market, side, home_name, away_name):
    entry = _entry(market, side)
    if (
        not entry
        or not all(isinstance(n, str) and n.strip() for n in (home_name, away_name))
        or home_name.strip().casefold() == away_name.strip().casefold()
    ):
        return None
    return _MARKETS[market], entry[1].format(home=home_name, away=away_name)


def _axis_value(axis, home, away):
    return {
        "margin": home - away,
        "total": home + away,
        "home": home,
        "away": away,
        "btts": int(min(home, away) > 0),
    }[axis]


def market_open(market, side, home, away):
    entry = _entry(market, side)
    if not entry or score_pair({"home": home, "away": away}) is None:
        return False
    event = entry[0]
    if market in _RELATIVE or event.axis == "margin":
        return True
    value = _axis_value(event.axis, home, away)
    if event.axis == "btts":
        return value == 0
    return (event.high is None and value < event.low) or (event.high is not None and value <= event.high)


def final_verdict(market, side, home, away):
    """Relative/event-order markets cannot be settled from a final score."""
    entry = _entry(market, side)
    if not entry or market in _RELATIVE or score_pair({"home": home, "away": away}) is None:
        return None
    event = entry[0]
    return event.contains(_axis_value(event.axis, home, away))


def _poisson_mass(rate):
    """Marginal only; bound the omitted tail by its decreasing geometric envelope."""
    value = math.exp(-rate)
    mass = [value]
    while True:
        index = len(mass)
        next_value = value * rate / index
        ratio = rate / (index + 1)
        if ratio < 1 and next_value <= 1e-16 * (1 - ratio):
            return mass
        mass.append(next_value)
        value = next_value


class _Law:
    """One pair of independent residual Poisson rates; no per-market score matrices."""

    def __init__(self, rates, scores):
        h, a = rates
        self.rates = {"home": h, "away": a, "total": h + a}
        self.scores = {"home": scores[0], "away": scores[1], "total": sum(scores)}
        self.margin = scores[0] - scores[1]
        self.away_mass = _poisson_mass(a)
        self.home_cdf = list(accumulate(_poisson_mass(h)))
        self.cdfs = {}

    def cdf(self, axis, bound):
        if (axis, bound) in self.cdfs:
            return self.cdfs[axis, bound]
        if axis == "margin":
            # Given j further away goals, D <= k iff i <= k - (score_H-score_A) + j.
            cut = bound - self.margin
            value = math.fsum(
                p * self.home_cdf[min(cut + j, len(self.home_cdf) - 1)]
                for j, p in enumerate(self.away_mass)
                if cut + j >= 0
            )
        else:
            team = axis.removeprefix("remaining_")
            k = bound - (0 if axis.startswith("remaining_") else self.scores[team])
            rate = self.rates[team]
            value = 0.0 if k < 0 else math.exp(-rate) * sum(rate**i / math.factorial(i) for i in range(k + 1))
        self.cdfs[axis, bound] = min(1.0, max(0.0, value))  # floating-point summation only
        return self.cdfs[axis, bound]

    def probability(self, event):
        if event.axis == "btts":
            # If one team has scored, these are the same events as the other team's
            # over/under 0.5. A double complement would move an identical pick by an ULP.
            if self.scores["home"] or self.scores["away"]:
                team = "away" if self.scores["home"] else "home"
                no_goal = self.cdf(team, 0)
                return no_goal if event.invert else 1.0 - no_goal
            p = (1.0 - self.cdf("home", 0)) * (1.0 - self.cdf("away", 0))
        elif event.axis in ("next_home", "next_away"):
            rate = self.rates["total"]
            p = (1.0 - self.cdf("remaining_total", 0)) * (self.rates[event.axis[5:]] / rate) if rate else 0.0
        else:
            upper = 1.0 if event.high is None else self.cdf(event.axis, event.high)
            lower = 0.0 if event.low is None else self.cdf(event.axis, event.low - 1)
            p = upper - lower
        return 1.0 - p if event.invert else p


def _numbers(values, limit):
    return all(type(v) in (int, float) and 0 <= v <= limit for v in values)


def compare_live_markets(ordinary):
    """None = unsupported snapshot, [] = checked and no open market with positive lift."""
    from live_football_priors import PRIOR_MODEL, PRIOR_REVISION
    from scanners.ultra_live_scanner_v3 import UltraLiveScanner

    if (
        not isinstance(ordinary, dict)
        or ordinary.get("prematch_prior_source") != PRIOR_MODEL
        or ordinary.get("model_version") != UltraLiveScanner.MODEL_VERSION + PRIOR_REVISION
        or ordinary.get("live_data_quality") != "MEDIUM"
    ):
        return None
    basis, stats, phase, red = [ordinary.get(key) for key in ("breakdown", "xg_data", "phase_data", "red_cards")]
    if not all(isinstance(v, dict) for v in (basis, stats, phase, red)) or red.get("supported") is not True:
        return None
    status = red.get("status")
    home_cards, away_cards = red.get("home_count"), red.get("away_count")
    if (
        not isinstance(status, str)
        or type(home_cards) is not int
        or type(away_cards) is not int
        or (home_cards, away_cards)
        != {"VERIFIED_NONE": (0, 0), "HOME_DISMISSED_ADJUSTED": (1, 0), "AWAY_DISMISSED_ADJUSTED": (0, 1)}.get(
            status
        )
        or red.get("applied") is not bool(home_cards + away_cards)
    ):
        return None
    priors = (stats.get("home_prior"), stats.get("away_prior"))
    rates = (basis.get("remaining_home_mean"), basis.get("remaining_away_mean"))
    observed = (stats.get("home_xg"), stats.get("away_xg"))
    scores = score_pair({"home": ordinary.get("home_score"), "away": ordinary.get("away_score")})
    names = ordinary.get("home_team"), ordinary.get("away_team")
    minute, period = ordinary.get("minute"), phase.get("status")
    extra = phase.get("extra")
    if (
        scores is None
        or selection_labels("ft_result", "draw", *names) is None
        or "extra" not in phase
        or period_clock(period, minute, 0 if extra is None else extra) is None
        or not 0 < minute < 90
        or not _numbers(priors, 8)
        or not _numbers(observed, 20)
        or not _numbers(rates, 256)
    ):  # safety bound above any representable supported scanner rate; never clip
        return None
    remaining = 45 if period in ("1H", "HT") and minute >= 45 else 90 - minute
    if not _numbers((phase.get("remaining_minutes"),), 90) or phase["remaining_minutes"] != remaining:
        return None
    reference = tuple(prior * remaining / 90 for prior in priors)
    # At neutral xG tempo the scanner computes the same intensity through several differently
    # ordered binary64 operations. Reconcile their rounding BEFORE summing Poisson terms:
    # a marginal can amplify one rate ULP into many output ULPs. Keep a real change to either team.
    rates = tuple(
        r0 if abs(r - r0) <= 8 * max(math.ulp(r), math.ulp(r0)) else r for r, r0 in zip(rates, reference)
    )
    if rates == reference:
        return []
    live, baseline = _Law(rates, scores), _Law(reference, scores)
    candidates = []
    for (market, side), (event, template) in _CATALOG.items():
        if not market_open(market, side, *scores):
            continue
        p, p0 = live.probability(event), baseline.probability(event)
        # Distinct laws can still produce the same outcome probability up to summation error.
        if 0.55 <= p < 1.0 and p - p0 > 8 * max(math.ulp(p), math.ulp(p0)):
            candidates.append(LiveMarketPick(market, side, template.format(home=names[0], away=names[1]), p, p0))
    return sorted(candidates, key=lambda v: (v.reference - v.probability, -v.probability, v.market, v.side))
