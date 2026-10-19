"""Model-versus-closing-market benchmark (validation only; audit 2026-10-16, K2).

The production release gate compares the walk-forward model with a Laplace
base rate. This module runs the same walk-forward prediction path and compares
each calibrated active probability with the no-vig closing market of a sharp
reference (Pinnacle; Shin for three-way, Power for two-way markets). It also
replays the current price-gate policy (generic haircut, 3 % risk-adjusted ROI,
publication floor 1.20) against the best closing price, reporting realised ROI
and closing-line value with bootstrap intervals.

Nothing here feeds a price into a model: benchmark rows live in a separate
table keyed by fixture id and are only joined after prediction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Any, Iterable, Optional

from betting_math import BettingMathError, minimum_recommendation_odds, no_vig_market
from challenge_engine import (
    CALIBRATION_REFIT_NEW_SAMPLES, MARKET_SPECS, _fit_calibration_map, _fixture_datetime,
    _fixture_market_outcome, _fixture_score, _venue_home_edge_unknown, fixture_market_probabilities,
)
from market_benchmark_history import OFFER_PROVIDERS, REFERENCE_PROVIDER
from model_loss_statistics import benjamini_hochberg_q_values, paired_advantage_statistics

BENCHMARK_VERSION = "market-benchmark-v1"
# ev_calculator default; production haircuts are candidate-specific (3 to 20 pp),
# so this generic policy replay is the *least* strict version of the gate.
GENERIC_HAIRCUT_PP = 5.0
EDGE_CAP_PP = 8.0
RESULT_KEYS = {"home": "RESULT_HOME", "draw": "RESULT_DRAW", "away": "RESULT_AWAY"}
TOTAL_KEYS = {"over": "TOTAL_OVER_2_5", "under": "TOTAL_UNDER_2_5"}
DOUBLE_CHANCE = {"DC_1X": ("home", "draw"), "DC_X2": ("draw", "away"), "DC_12": ("home", "away")}
BENCHMARK_MARKET_KEYS = tuple(RESULT_KEYS.values()) + tuple(DOUBLE_CHANCE) + tuple(TOTAL_KEYS.values())


def walk_forward_model_probabilities(fixtures: Iterable[dict[str, Any]], *, goal_model: str = "legacy") -> tuple[
    dict[int, dict[str, float]], dict[int, dict[str, float]], dict[int, dict[str, int]],
]:
    """Mirror ``challenge_engine._walk_forward_market_records`` while keeping fixture ids.

    Same day grouping, same validation-only prediction call, same calibration
    refit cadence. Returns calibrated active probabilities, raw probabilities
    and settled outcomes, each as ``{fixture_id: {market_key: value}}`` in
    chronological insertion order (needed for the HAC statistics).
    """
    ordered = sorted(
        (fixture for fixture in fixtures if _fixture_datetime(fixture) and _fixture_score(fixture)),
        key=lambda item: _fixture_datetime(item),
    )
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for fixture in ordered:
        day = _fixture_datetime(fixture).replace(hour=0, minute=0, second=0, microsecond=0)
        grouped.setdefault(day, []).append(fixture)
    prior: list[dict[str, Any]] = []
    state = {spec.key: {"map": None, "count": 0, "raw": [], "outcomes": []} for spec in MARKET_SPECS}
    predictions: dict[int, dict[str, float]] = {}
    raw_predictions: dict[int, dict[str, float]] = {}
    outcomes: dict[int, dict[str, int]] = {}
    for day in sorted(grouped):
        day_fixtures = grouped[day]
        calibration = {key: item["map"] for key, item in state.items() if item["map"] is not None}
        for fixture in day_fixtures:
            if _venue_home_edge_unknown(fixture) and fixture.get("challenge_senior_national_team") is not True:
                continue
            prediction = fixture_market_probabilities(fixture, prior, calibration, _validation_only=True,
                                                      goal_model=goal_model)
            if prediction is None:
                continue
            fixture_id = fixture["fixture"]["id"]
            for spec in MARKET_SPECS:
                values = prediction["probabilities"].get(spec.key)
                outcome = _fixture_market_outcome(spec, fixture)
                if values is None or outcome is None:
                    continue
                raw = prediction["raw_probabilities"][spec.key][0]
                predictions.setdefault(fixture_id, {})[spec.key] = float(values[0])
                raw_predictions.setdefault(fixture_id, {})[spec.key] = float(raw)
                outcomes.setdefault(fixture_id, {})[spec.key] = int(outcome)
                state[spec.key]["raw"].append(raw)
                state[spec.key]["outcomes"].append(int(outcome))
        prior.extend(day_fixtures)
        for key, item in state.items():
            if len(item["raw"]) - item["count"] >= CALIBRATION_REFIT_NEW_SAMPLES:
                new_map = _fit_calibration_map(item["raw"], item["outcomes"])
                if new_map is not None:
                    item["map"] = new_map
                    item["count"] = len(item["raw"])
    return predictions, raw_predictions, outcomes


def reference_probabilities(entry: dict[str, Any]) -> tuple[Optional[str], dict[str, float], dict[str, bool]]:
    """No-vig reference probabilities per model market key for one benchmark row.

    Pinnacle is the reference; ``avg`` is the documented fallback. Three-way
    markets use Shin, two-way markets Power. Double chance is the sum of the
    no-vig single probabilities of the same market.
    """
    provider = REFERENCE_PROVIDER if (REFERENCE_PROVIDER in entry["result"] or REFERENCE_PROVIDER in entry["ou25"]) else "avg"
    probabilities: dict[str, float] = {}
    closing: dict[str, bool] = {}
    three = entry["result"].get(provider)
    if three is not None:
        try:
            p = no_vig_market(three, "shin").no_vig_probabilities
        except BettingMathError:
            p = None
        if p is not None:
            singles = dict(zip(("home", "draw", "away"), p))
            for side, key in RESULT_KEYS.items():
                probabilities[key] = singles[side]
                closing[key] = bool(entry["closing"].get(f"result:{provider}", False))
            for key, sides in DOUBLE_CHANCE.items():
                probabilities[key] = sum(singles[side] for side in sides)
                closing[key] = closing["RESULT_HOME"]
    two = entry["ou25"].get(provider)
    if two is not None:
        try:
            p = no_vig_market(two, "power").no_vig_probabilities
        except BettingMathError:
            p = None
        if p is not None:
            probabilities[TOTAL_KEYS["over"]], probabilities[TOTAL_KEYS["under"]] = p
            for key in TOTAL_KEYS.values():
                closing[key] = bool(entry["closing"].get(f"ou25:{provider}", False))
    return (provider if probabilities else None), probabilities, closing


def offered_odds(entry: dict[str, Any]) -> dict[str, tuple[float, str]]:
    """Best available closing price per directly offered selection, with its provider."""
    offers: dict[str, tuple[float, str]] = {}
    for provider in OFFER_PROVIDERS:
        three = entry["result"].get(provider)
        if three is not None:
            for side, key in RESULT_KEYS.items():
                price = three[("home", "draw", "away").index(side)]
                if key not in offers or price > offers[key][0]:
                    offers[key] = (price, provider)
        two = entry["ou25"].get(provider)
        if two is not None:
            for key, price in zip((TOTAL_KEYS["over"], TOTAL_KEYS["under"]), two):
                if key not in offers or price > offers[key][0]:
                    offers[key] = (price, provider)
    return offers


@dataclass(frozen=True)
class CellResult:
    league_id: int
    market_key: str
    provider: str
    closing_share: float
    observations: int
    brier_model: float
    brier_raw: float
    brier_market: float
    logloss_model: float
    logloss_market: float
    mean_model_minus_market_pp: float
    advantage_mean: Optional[float]
    advantage_se: Optional[float]
    advantage_lower: Optional[float]
    p_value: Optional[float]
    q_value: Optional[float] = None

    @property
    def cell_id(self) -> str:
        return f"{self.league_id}:{self.market_key}"

    @property
    def market_beaten(self) -> bool:
        """One-sided HAC lower bound of the paired Brier advantage above zero."""
        return self.advantage_lower is not None and self.advantage_lower > 0.0


def _brier(probabilities: list[float], outcomes: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(outcomes)


def _logloss(probabilities: list[float], outcomes: list[int]) -> float:
    total = 0.0
    for p, y in zip(probabilities, outcomes):
        clipped = min(1.0 - 1e-6, max(1e-6, p))
        total -= math.log(clipped) if y else math.log(1.0 - clipped)
    return total / len(outcomes)


def evaluate_cells(predictions: dict[int, dict[str, float]], raw_predictions: dict[int, dict[str, float]],
                   outcomes: dict[int, dict[str, int]], benchmark: dict[int, dict[str, Any]],
                   *, league_id: int) -> list[CellResult]:
    """Paired Brier advantage (model minus market, positive = model better) per market."""
    rows: dict[str, dict[str, list]] = {}
    for fixture_id, markets in predictions.items():  # Chronological insertion order.
        entry = benchmark.get(fixture_id)
        if entry is None:
            continue
        provider, market_p, closing = reference_probabilities(entry)
        if provider is None:
            continue
        for key, market_probability in market_p.items():
            if key not in markets or key not in outcomes.get(fixture_id, {}):
                continue
            row = rows.setdefault(key, {"model": [], "raw": [], "market": [], "y": [], "closing": [], "provider": provider})
            row["model"].append(markets[key])
            row["raw"].append(raw_predictions[fixture_id][key])
            row["market"].append(market_probability)
            row["y"].append(outcomes[fixture_id][key])
            row["closing"].append(1 if closing.get(key) else 0)
    cells: list[CellResult] = []
    for key in BENCHMARK_MARKET_KEYS:
        row = rows.get(key)
        if not row:
            continue
        advantages = [(m - y) ** 2 - (p - y) ** 2 for p, m, y in zip(row["model"], row["market"], row["y"])]
        mean, se, lower, p_value = paired_advantage_statistics(advantages)
        cells.append(CellResult(
            league_id=league_id, market_key=key, provider=row["provider"],
            closing_share=sum(row["closing"]) / len(row["closing"]), observations=len(row["y"]),
            brier_model=_brier(row["model"], row["y"]), brier_raw=_brier(row["raw"], row["y"]),
            brier_market=_brier(row["market"], row["y"]),
            logloss_model=_logloss(row["model"], row["y"]), logloss_market=_logloss(row["market"], row["y"]),
            mean_model_minus_market_pp=100.0 * sum(p - m for p, m in zip(row["model"], row["market"])) / len(row["y"]),
            advantage_mean=mean, advantage_se=se, advantage_lower=lower, p_value=p_value,
        ))
    return cells


def apply_fdr(cells: list[CellResult]) -> list[CellResult]:
    """Benjamini-Hochberg over the whole family of league x market cells."""
    p_values = {cell.cell_id: (cell.p_value if cell.p_value is not None else 1.0) for cell in cells}
    if not p_values:
        return []
    q_values = benjamini_hochberg_q_values(p_values)
    from dataclasses import replace
    return [replace(cell, q_value=q_values[cell.cell_id]) for cell in cells]


@dataclass(frozen=True)
class PolicyBet:
    league_id: int
    market_key: str
    model_probability: float
    market_probability: Optional[float]
    offered_odds: float
    offer_provider: str
    minimum_odds: float
    won: int

    @property
    def roi(self) -> float:
        return self.offered_odds - 1.0 if self.won else -1.0

    @property
    def clv(self) -> Optional[float]:
        if self.market_probability is None:
            return None
        return self.market_probability * self.offered_odds - 1.0

    @property
    def edge_pp(self) -> Optional[float]:
        if self.market_probability is None:
            return None
        return 100.0 * (self.model_probability - self.market_probability)


def policy_bets(predictions: dict[int, dict[str, float]], outcomes: dict[int, dict[str, int]],
                benchmark: dict[int, dict[str, Any]], *, league_id: int,
                haircut_pp: float = GENERIC_HAIRCUT_PP) -> list[PolicyBet]:
    """Replay the price gate (haircut, 3 % risk-ROI, floor 1.20) on best closing prices."""
    bets: list[PolicyBet] = []
    for fixture_id, markets in predictions.items():
        entry = benchmark.get(fixture_id)
        if entry is None:
            continue
        _provider, market_p, _closing = reference_probabilities(entry)
        for key, (odds, provider) in offered_odds(entry).items():
            probability = markets.get(key)
            outcome = outcomes.get(fixture_id, {}).get(key)
            if probability is None or outcome is None:
                continue
            try:
                minimum = minimum_recommendation_odds(probability * 100.0, probability_haircut=haircut_pp)
            except BettingMathError:
                continue
            if minimum is None or odds < minimum:
                continue
            bets.append(PolicyBet(league_id, key, probability, market_p.get(key), odds, provider, minimum, outcome))
    return bets


def _bootstrap_interval(values: list[float], *, seed: int = 7, samples: int = 2000,
                        level: float = 0.90) -> Optional[tuple[float, float]]:
    if len(values) < 2:
        return None
    generator = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [values[generator.randrange(len(values))] for _ in values]
        means.append(sum(draw) / len(draw))
    means.sort()
    lower_index = int((1.0 - level) / 2.0 * (samples - 1))
    upper_index = int((1.0 + level) / 2.0 * (samples - 1))
    return means[lower_index], means[upper_index]


@dataclass(frozen=True)
class PolicySummary:
    label: str
    bets: int
    roi_mean: Optional[float]
    roi_interval: Optional[tuple[float, float]]
    clv_mean: Optional[float]
    clv_interval: Optional[tuple[float, float]]
    mean_edge_pp: Optional[float]
    share_over_edge_cap: Optional[float]
    hit_rate: Optional[float]


def summarise_policy(bets: list[PolicyBet], *, label: str) -> PolicySummary:
    if not bets:
        return PolicySummary(label, 0, None, None, None, None, None, None, None)
    rois = [bet.roi for bet in bets]
    clvs = [bet.clv for bet in bets if bet.clv is not None]
    edges = [bet.edge_pp for bet in bets if bet.edge_pp is not None]
    return PolicySummary(
        label=label, bets=len(bets), roi_mean=sum(rois) / len(rois), roi_interval=_bootstrap_interval(rois),
        clv_mean=(sum(clvs) / len(clvs)) if clvs else None, clv_interval=_bootstrap_interval(clvs) if clvs else None,
        mean_edge_pp=(sum(edges) / len(edges)) if edges else None,
        share_over_edge_cap=(sum(1 for e in edges if e > EDGE_CAP_PP) / len(edges)) if edges else None,
        hit_rate=sum(bet.won for bet in bets) / len(bets),
    )


@dataclass
class BenchmarkReport:
    haircut_pp: float
    leagues: dict[int, dict[str, Any]] = field(default_factory=dict)
    cells: list[CellResult] = field(default_factory=list)
    bets: list[PolicyBet] = field(default_factory=list)

    def policy_summaries(self) -> list[PolicySummary]:
        summaries = [summarise_policy(self.bets, label="alle Zellen")]
        for key in BENCHMARK_MARKET_KEYS:
            subset = [bet for bet in self.bets if bet.market_key == key]
            if subset:
                summaries.append(summarise_policy(subset, label=key))
        return summaries


def benchmark_league(report: BenchmarkReport, *, league_id: int, fixtures: list[dict[str, Any]],
                     benchmark: dict[int, dict[str, Any]], seasons: list[int]) -> None:
    predictions, raw_predictions, outcomes = walk_forward_model_probabilities(fixtures)
    cells = evaluate_cells(predictions, raw_predictions, outcomes, benchmark, league_id=league_id)
    bets = policy_bets(predictions, outcomes, benchmark, league_id=league_id, haircut_pp=report.haircut_pp)
    joined = sum(1 for fixture_id in predictions if fixture_id in benchmark)
    report.leagues[league_id] = {
        "seasons": list(seasons), "fixtures": len(fixtures), "predicted": len(predictions),
        "joined_with_benchmark": joined,
    }
    report.cells.extend(cells)
    report.bets.extend(bets)


def finalise(report: BenchmarkReport) -> BenchmarkReport:
    report.cells = apply_fdr(report.cells)
    return report


def _fmt(value: Optional[float], digits: int = 4, *, percent: bool = False) -> str:
    if value is None:
        return "–"
    return f"{value * 100:+.1f} %" if percent else f"{value:.{digits}f}"


def render_markdown(report: BenchmarkReport, *, title: str = "Marktbenchmark: Modell gegen No-Vig-Closing") -> str:
    lines = [f"# {title}", "",
             f"Version `{BENCHMARK_VERSION}`. Referenz: Pinnacle-Closing (Fallback Avg), Shin-De-Vig für 1X2, "
             "Power-De-Vig für Über/Unter 2,5. Modell: walk-forward wie im Release-Gate "
             "(`fixture_market_probabilities`, Kalibrierung nur aus Vortagen). Gepaarter Brier-Vorteil = "
             "Brier(Markt) − Brier(Modell) je Spiel, positiv = Modell besser; HAC-Standardfehler, einseitiger "
             "p-Wert, Benjamini-Hochberg über alle Liga×Markt-Zellen.", "",
             "Dieser Bericht ist ein Validierungsnachweis, kein Beleg für profitable Wetten. Quoten fließen "
             "nicht in die Modellschätzung ein.", "",
             "## Datenbasis", "", "| Liga | Saisons | Spiele | Modellprognosen | mit Benchmark |", "|---|---|---:|---:|---:|"]
    for league_id, info in sorted(report.leagues.items()):
        lines.append(f"| {league_id} | {', '.join(str(s) for s in info['seasons'])} | {info['fixtures']} | "
                     f"{info['predicted']} | {info['joined_with_benchmark']} |")
    lines += ["", "## Modell gegen Markt je Zelle", "",
              "| Liga | Markt | n | Closing-Anteil | Brier Modell | Brier roh | Brier Markt | LogLoss Modell | LogLoss Markt | Ø Modell−Markt (pp) | Vorteil | HAC-SE | Untergrenze | p | q (BH) | Markt geschlagen |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|"]
    for cell in sorted(report.cells, key=lambda c: (c.league_id, BENCHMARK_MARKET_KEYS.index(c.market_key))):
        lines.append(
            f"| {cell.league_id} | {cell.market_key} | {cell.observations} | {cell.closing_share * 100:.0f} % | "
            f"{_fmt(cell.brier_model)} | {_fmt(cell.brier_raw)} | {_fmt(cell.brier_market)} | "
            f"{_fmt(cell.logloss_model)} | {_fmt(cell.logloss_market)} | {cell.mean_model_minus_market_pp:+.2f} | "
            f"{_fmt(cell.advantage_mean, 5)} | {_fmt(cell.advantage_se, 5)} | {_fmt(cell.advantage_lower, 5)} | "
            f"{_fmt(cell.p_value, 3)} | {_fmt(cell.q_value, 3)} | {'ja' if cell.market_beaten and (cell.q_value or 1) <= 0.05 else 'nein'} |"
        )
    beaten = [c for c in report.cells if c.market_beaten and (c.q_value or 1.0) <= 0.05]
    worse = [c for c in report.cells if c.advantage_mean is not None and c.advantage_mean < 0]
    lines += ["", f"Zellen gesamt: {len(report.cells)} · Markt geschlagen (HAC-Untergrenze > 0 und q ≤ 0,05): "
              f"{len(beaten)} · Modell im Mittel schlechter als der Markt: {len(worse)}.", "",
              f"## Replay der Preisgate-Policy (Haircut {report.haircut_pp:.0f} pp, 3 % Risiko-ROI, Boden 1,20, bester Closing-Preis)", "",
              "| Teilmenge | Wetten | Trefferquote | ROI | ROI 90 %-Bootstrap | CLV (p_novig×Quote−1) | CLV 90 %-Bootstrap | Ø Modell−Markt (pp) | Anteil > 8 pp |",
              "|---|---:|---:|---:|---|---:|---|---:|---:|"]
    for summary in report.policy_summaries():
        roi_ci = f"[{summary.roi_interval[0] * 100:+.1f} %, {summary.roi_interval[1] * 100:+.1f} %]" if summary.roi_interval else "–"
        clv_ci = f"[{summary.clv_interval[0] * 100:+.1f} %, {summary.clv_interval[1] * 100:+.1f} %]" if summary.clv_interval else "–"
        lines.append(f"| {summary.label} | {summary.bets} | {_fmt(summary.hit_rate, percent=True) if summary.hit_rate is not None else '–'} | "
                     f"{_fmt(summary.roi_mean, percent=True)} | {roi_ci} | {_fmt(summary.clv_mean, percent=True)} | {clv_ci} | "
                     f"{summary.mean_edge_pp:+.1f}" if summary.mean_edge_pp is not None else f"| {summary.label} | 0 | – | – | – | – | – | –")
        if summary.mean_edge_pp is not None:
            lines[-1] += f" | {summary.share_over_edge_cap * 100:.0f} % |"
        else:
            lines[-1] += " | – |"
    lines += ["", "Lesart: Ein negativer CLV bei positivem Modellvorsprung bedeutet, dass die Policy genau die Spiele "
              "auswählt, in denen das Modell vom Markt abweicht (Winner's Curse, Audit K3). Der generische Haircut "
              "ist die *mildeste* Form des Produktgates; produktive Haircuts sind höher.", ""]
    return "\n".join(lines)


__all__ = [
    "BENCHMARK_MARKET_KEYS", "BENCHMARK_VERSION", "BenchmarkReport", "CellResult", "EDGE_CAP_PP",
    "GENERIC_HAIRCUT_PP", "PolicyBet", "PolicySummary", "apply_fdr", "benchmark_league", "evaluate_cells",
    "finalise", "offered_odds", "policy_bets", "reference_probabilities", "render_markdown",
    "summarise_policy", "walk_forward_model_probabilities",
]
