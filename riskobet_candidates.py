"""Price-neutral RisikoBet adapters for all six supported sports.

The module deliberately owns no provider clients and performs no price lookup.
It translates already calculated, pre-match model records into the immutable
contracts from :mod:`riskobet_domain`.  Every public adapter enforces causal
timestamps and publishes at most two scenarios for one event.

Football has a two-step API because its selected source candidates must pass
through the existing H2H/injury/weather context run before publication:

``select_football_risk_sources(pool)``
    Select at most two raw ``ChallengeCandidate`` objects per fixture from the
    complete market pool *before* normal Wettfinder gates.

``football_risk_bundle(selected, modeled_at=..., source_pool=...)``
    Freeze one contextualised fixture as a RisikoBet snapshot and candidates.

Tennis and e-sport adapters read their existing shadow databases.  Basketball,
ice hockey and cricket share a transparent beta-smoothed Log5 research model;
when either team's causal history is insufficient, the candidate remains
RESEARCH with ``model_probability=None`` and exact missing-data messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping, Optional, Sequence

from riskobet_domain import (
    ContextState,
    EvidenceStage,
    EventModelSnapshot,
    FactorEvidence,
    FactorRole,
    RiskCandidate,
    canonical_input_hash,
    stable_event_key,
)


RISKOBET_POLICY_VERSION = "riskobet-evidence-order-v2"
FOOTBALL_MODEL_VERSION = "shared-football-market-model-v1"
RESEARCH_MODEL_VERSION = "beta-log5-prematch-v1"
TENNIS_FALLBACK_MODEL_VERSION = "tennis-shadow-model-v1"
ESPORTS_FALLBACK_MODEL_VERSION = "esports-shadow-model-v1"
MIN_RESEARCH_TEAM_GAMES = 8
FOOTBALL_WIN_MIN_PROBABILITY = 0.15
FOOTBALL_DRAW_MIN_PROBABILITY = 0.18
FOOTBALL_DOUBLE_CHANCE_MIN_PROBABILITY = 0.30
FOOTBALL_DOUBLE_CHANCE_MAX_PROBABILITY = 0.75
FOOTBALL_TWO_GOALS_MIN_PROBABILITY = 0.15
FOOTBALL_ONE_GOAL_MIN_PROBABILITY = 0.25
FOOTBALL_ONE_GOAL_MAX_PROBABILITY = 0.80
TENNIS_WIN_MIN_PROBABILITY = 0.12
TENNIS_SIDE_MIN_PROBABILITY = 0.22
TENNIS_SIMPLE_MAX_PROBABILITY = 0.85
ESPORTS_WIN_MIN_PROBABILITY = 0.12
ESPORTS_MAP_MIN_PROBABILITY = 0.30
ESPORTS_SIMPLE_MAX_PROBABILITY = 0.85
RESEARCH_WIN_MIN_PROBABILITY = 0.12
FOOTBALL_CONTEXT_TTL = timedelta(minutes=75)
RESEARCH_HISTORY_TTL = timedelta(days=30)

_UTC = timezone.utc
_PRICE_TOKENS = ("odd", "quote", "price", "bookmaker", "payout", "stake")


@dataclass(frozen=True, slots=True)
class RiskAdapterResult:
    """One event snapshot and its zero-to-two price-independent scenarios."""

    snapshot: EventModelSnapshot
    candidates: tuple[RiskCandidate, ...]

    def __post_init__(self) -> None:
        if len(self.candidates) > 2:
            raise ValueError("an adapter may publish at most two candidates per event")
        for candidate in self.candidates:
            if candidate.snapshot_id != self.snapshot.snapshot_id:
                raise ValueError("candidate does not reference adapter snapshot")
            if candidate.event_key != self.snapshot.event_key:
                raise ValueError("candidate and snapshot event identities differ")


@dataclass(frozen=True, slots=True)
class _Scenario:
    source: Any
    market_key: str
    market_label: str
    selection_key: str
    selection_label: str
    probability: float
    cautious_probability: Optional[float]
    settlement_contract: str
    score: float
    pro: str
    con: str


def _get(item: object, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _probability(value: object, *, percent_allowed: bool = False) -> Optional[float]:
    number = _number(value)
    if number is None:
        return None
    if percent_allowed and 1.0 < number <= 100.0:
        number /= 100.0
    if not 0.0 <= number <= 1.0:
        return None
    return number


def _parse_datetime(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min, tzinfo=_UTC)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            return None
        try:
            parsed = datetime.fromtimestamp(float(value), tz=_UTC)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.combine(date.fromisoformat(text), time.min, tzinfo=_UTC)
            except ValueError:
                return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(_UTC)


def _require_causal_clock(
    starts_at: datetime,
    modeled_at: Optional[datetime],
    input_cutoff_at: Optional[datetime],
) -> tuple[datetime, datetime]:
    model_time = _parse_datetime(modeled_at or datetime.now(_UTC))
    cutoff = _parse_datetime(input_cutoff_at or model_time)
    if model_time is None or cutoff is None:
        raise ValueError("model and input-cutoff times must be timezone-aware")
    if cutoff > model_time:
        raise ValueError("input cutoff must not follow model time")
    if model_time > starts_at:
        raise ValueError("RisikoBet adapters only accept pre-match model states")
    return model_time, cutoff


def _without_prices(value: object) -> object:
    """Return a JSON-safe view with every price-like field removed."""

    if isinstance(value, Mapping):
        output: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if any(token in key.casefold() for token in _PRICE_TOKENS):
                continue
            output[key] = _without_prices(raw_value)
        return output
    if isinstance(value, (list, tuple)):
        return [_without_prices(item) for item in value]
    if isinstance(value, datetime):
        parsed = _parse_datetime(value)
        return parsed.isoformat() if parsed is not None else str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _candidate_probability(candidate: object) -> Optional[float]:
    return _probability(_get(candidate, "probability"))


def _candidate_cautious(candidate: object, probability: float) -> Optional[float]:
    cautious = _probability(_get(candidate, "conservative_probability"))
    if cautious is None:
        return None
    return min(probability, cautious)


def _fixture_group_key(candidate: object) -> tuple[int, str]:
    raw_id = _get(candidate, "fixture_id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
        raise ValueError("football source candidate has no valid fixture_id")
    kickoff = _clean_text(_get(candidate, "kickoff"))
    if not kickoff:
        raise ValueError("football source candidate has no kickoff")
    return raw_id, kickoff


def _consistent_football_identity(pool: Sequence[object]) -> bool:
    if not pool:
        return False
    fields = (
        "fixture_id",
        "league_id",
        "kickoff",
        "home_team_id",
        "away_team_id",
        "home_team",
        "away_team",
    )
    expected = tuple(_clean_text(_get(pool[0], field)) for field in fields)
    if (
        not all(expected)
        or expected[3] == expected[4]
        or expected[5].casefold() == expected[6].casefold()
    ):
        return False
    return all(
        tuple(_clean_text(_get(candidate, field)) for field in fields) == expected
        for candidate in pool[1:]
    )


def _football_goal_factor(candidate: object, side: str) -> Optional[str]:
    expected = _number(
        _get(candidate, "expected_home_goals" if side == "home" else "expected_away_goals")
    )
    if expected is not None and expected >= 1.0:
        return f"Das gemeinsame Tormodell erwartet {expected:.2f} Außenseitertore."
    context = _get(candidate, "context")
    if isinstance(context, Mapping):
        raw_factors = context.get("riskobet_positive_factors")
        if isinstance(raw_factors, Sequence) and not isinstance(raw_factors, (str, bytes)):
            for raw in raw_factors:
                factor = _clean_text(raw)
                if factor:
                    return factor
    return None


def _football_scenarios(pool: Sequence[object]) -> list[_Scenario]:
    by_market = {
        _clean_text(_get(candidate, "market_key")): candidate
        for candidate in pool
        if _clean_text(_get(candidate, "market_key"))
    }
    home_result = by_market.get("RESULT_HOME")
    away_result = by_market.get("RESULT_AWAY")
    p_home = _candidate_probability(home_result) if home_result is not None else None
    p_away = _candidate_probability(away_result) if away_result is not None else None
    if p_home is None or p_away is None:
        return []
    # Exact equality is not an identifiable underdog; publishing either side
    # would make input ordering decide a sporting claim.
    if math.isclose(p_home, p_away, abs_tol=1e-12):
        return []
    underdog_side = "home" if p_home < p_away else "away"
    result_key = "RESULT_HOME" if underdog_side == "home" else "RESULT_AWAY"
    dc_key = "DC_1X" if underdog_side == "home" else "DC_X2"
    goal_prefix = "HOME" if underdog_side == "home" else "AWAY"
    team_label = _clean_text(
        _get(pool[0], "home_team" if underdog_side == "home" else "away_team")
    ) or ("Heimteam" if underdog_side == "home" else "Auswärtsteam")
    settlement_side = underdog_side
    result = by_market[result_key]
    result_probability = _candidate_probability(result)
    assert result_probability is not None
    scenarios: list[_Scenario] = []
    if result_probability >= FOOTBALL_WIN_MIN_PROBABILITY:
        scenarios.append(_Scenario(
            source=result,
            market_key="result_90_minutes",
            market_label="Außenseitersieg nach 90 Minuten",
            selection_key=settlement_side,
            selection_label=team_label,
            probability=result_probability,
            cautious_probability=_candidate_cautious(result, result_probability),
            settlement_contract=(
                f"riskobet-settlement-v1:football:result_90_minutes:{settlement_side}"
            ),
            score=result_probability * 1.20,
            pro=f"Das gemeinsame Ergebnismodell gibt {team_label} {result_probability:.1%} Siegchance.",
            con="Außenseitersiege liegen im dünnen Wahrscheinlichkeitsrand und streuen stark.",
        ))

    draw = by_market.get("RESULT_DRAW")
    draw_probability = _candidate_probability(draw) if draw is not None else None
    if (
        draw is not None
        and draw_probability is not None
        and draw_probability >= FOOTBALL_DRAW_MIN_PROBABILITY
    ):
        scenarios.append(
            _Scenario(
                source=draw,
                market_key="draw_90_minutes",
                market_label="Unentschieden nach 90 Minuten",
                selection_key="draw",
                selection_label="Unentschieden",
                probability=draw_probability,
                cautious_probability=_candidate_cautious(draw, draw_probability),
                settlement_contract="riskobet-settlement-v1:football:draw_90_minutes:draw",
                score=draw_probability,
                pro=f"Das Remismodell weist {draw_probability:.1%} aus.",
                con="Ein einzelnes spätes Tor kann das Remisszenario vollständig kippen.",
            )
        )

    double_chance = by_market.get(dc_key)
    dc_probability = (
        _candidate_probability(double_chance) if double_chance is not None else None
    )
    if (
        double_chance is not None
        and dc_probability is not None
        and FOOTBALL_DOUBLE_CHANCE_MIN_PROBABILITY
        <= dc_probability
        <= FOOTBALL_DOUBLE_CHANCE_MAX_PROBABILITY
    ):
        dc_selection = "home_or_draw" if underdog_side == "home" else "away_or_draw"
        scenarios.append(
            _Scenario(
                source=double_chance,
                market_key="double_chance_90_minutes",
                market_label="Außenseiter verliert nicht",
                selection_key=dc_selection,
                selection_label="1X" if underdog_side == "home" else "X2",
                probability=dc_probability,
                cautious_probability=_candidate_cautious(double_chance, dc_probability),
                settlement_contract=(
                    "riskobet-settlement-v1:football:double_chance_90_minutes:"
                    f"{dc_selection}"
                ),
                score=dc_probability * 0.45,
                pro=f"Sieg oder Remis zusammen ergeben im Modell {dc_probability:.1%}.",
                con="Der breitere Ausgang ist weniger überraschend und häufig preislich knapp.",
            )
        )

    two_goals = by_market.get(f"{goal_prefix}_OVER_1_5")
    two_goal_probability = (
        _candidate_probability(two_goals) if two_goals is not None else None
    )
    if (
        two_goals is not None
        and two_goal_probability is not None
        and two_goal_probability >= FOOTBALL_TWO_GOALS_MIN_PROBABILITY
    ):
        expected = _number(
            _get(
                two_goals,
                "expected_home_goals" if underdog_side == "home" else "expected_away_goals",
            )
        )
        scenarios.append(
            _Scenario(
                source=two_goals,
                market_key="underdog_team_over_1_5_90_minutes",
                market_label="Außenseiter erzielt mindestens zwei Tore",
                selection_key=settlement_side,
                selection_label=f"{team_label} über 1,5 Tore",
                probability=two_goal_probability,
                cautious_probability=_candidate_cautious(two_goals, two_goal_probability),
                settlement_contract=(
                    "riskobet-settlement-v1:football:"
                    f"underdog_team_over_1_5_90_minutes:{settlement_side}"
                ),
                score=two_goal_probability * 0.8,
                pro=(
                    f"Das Tormodell erwartet {expected:.2f} Tore von {team_label}."
                    if expected is not None
                    else f"Das Marktmodell weist {two_goal_probability:.1%} für zwei Tore aus."
                ),
                con="Zwei Außenseitertore reagieren stark auf Spielstand und Chancenverwertung.",
            )
        )

    one_goal = by_market.get(f"{goal_prefix}_OVER_0_5")
    one_goal_probability = (
        _candidate_probability(one_goal) if one_goal is not None else None
    )
    goal_factor = (
        _football_goal_factor(one_goal, underdog_side) if one_goal is not None else None
    )
    if (
        one_goal is not None
        and one_goal_probability is not None
        and FOOTBALL_ONE_GOAL_MIN_PROBABILITY
        <= one_goal_probability
        <= FOOTBALL_ONE_GOAL_MAX_PROBABILITY
        and goal_factor
    ):
        scenarios.append(
            _Scenario(
                source=one_goal,
                market_key="underdog_team_over_0_5_90_minutes",
                market_label="Außenseiter erzielt mindestens ein Tor",
                selection_key=settlement_side,
                selection_label=f"{team_label} über 0,5 Tore",
                probability=one_goal_probability,
                cautious_probability=_candidate_cautious(one_goal, one_goal_probability),
                settlement_contract=(
                    "riskobet-settlement-v1:football:"
                    f"underdog_team_over_0_5_90_minutes:{settlement_side}"
                ),
                score=one_goal_probability * 0.3,
                pro=goal_factor,
                con="Ein Tor ist ein einfacher Markt und wird nur wegen des konkreten Modellfaktors gezeigt.",
            )
        )

    return sorted(
        scenarios,
        key=lambda item: (item.score, item.probability, item.market_key),
        reverse=True,
    )[:2]


def select_football_risk_sources(pool: Iterable[Any]) -> list[Any]:
    """Select at most two raw pre-gate candidates per football fixture.

    The return values are the original objects, so the caller can pass them
    through the established context fetch without reloading or remodelling the
    event.  No blocked-reason, price or quote field participates in selection.
    """

    groups: dict[tuple[int, str], list[Any]] = {}
    for candidate in pool:
        try:
            key = _fixture_group_key(candidate)
        except ValueError:
            continue
        groups.setdefault(key, []).append(candidate)
    selected: list[Any] = []
    for key in sorted(groups, key=lambda item: (item[1], item[0])):
        if _consistent_football_identity(groups[key]):
            selected.extend(scenario.source for scenario in _football_scenarios(groups[key]))
    return selected


def football_risk_source_pool(pool: Iterable[Any]) -> list[Any]:
    """Return the minimal complete pool needed to reproduce football risks.

    For each fixture with at least one plausible scenario this retains both
    result sides (to identify the underdog), draw, the applicable double chance
    and the underdog's 1+/2+ goal markets.  The 80+ unrelated market records do
    not need to enter RisikoBet persistence or context refreshes.
    """

    groups: dict[tuple[int, str], list[Any]] = {}
    for candidate in pool:
        try:
            groups.setdefault(_fixture_group_key(candidate), []).append(candidate)
        except ValueError:
            continue
    support: list[Any] = []
    for key in sorted(groups, key=lambda item: (item[1], item[0])):
        group = groups[key]
        if not _consistent_football_identity(group):
            continue
        if not _football_scenarios(group):
            continue
        by_market = {
            _clean_text(_get(candidate, "market_key")): candidate
            for candidate in group
            if _clean_text(_get(candidate, "market_key"))
        }
        p_home = _candidate_probability(by_market.get("RESULT_HOME"))
        p_away = _candidate_probability(by_market.get("RESULT_AWAY"))
        if p_home is None or p_away is None or math.isclose(p_home, p_away, abs_tol=1e-12):
            continue
        side = "HOME" if p_home < p_away else "AWAY"
        desired = (
            "RESULT_HOME",
            "RESULT_AWAY",
            "RESULT_DRAW",
            "DC_1X" if side == "HOME" else "DC_X2",
            f"{side}_OVER_0_5",
            f"{side}_OVER_1_5",
        )
        support.extend(by_market[market_key] for market_key in desired if market_key in by_market)
    return support


def _football_context_parts(
    selected: Sequence[object],
    modeled_at: datetime,
    starts_at: datetime,
) -> tuple[tuple[FactorEvidence, ...], ContextState, list[str], list[str], object]:
    contexts = [
        _get(candidate, "context")
        for candidate in selected
        if isinstance(_get(candidate, "context"), Mapping)
        and bool(_get(candidate, "context"))
        and any(
            isinstance(_get(candidate, "context").get(section), Mapping)
            for section in ("h2h", "injuries", "weather", "lineups")
        )
    ]
    if not contexts:
        return (
            (),
            ContextState.OPEN,
            [],
            ["H2H, Ausfälle, Wetter und Aufstellungen sind noch nicht vollständig geprüft."],
            {},
        )
    # Each selected market may have market-specific H2H, so keep every
    # sanitized context in the input revision while exposing concise factors.
    factors: list[FactorEvidence] = []
    pros: list[str] = []
    cons: list[str] = []
    complete = True
    oldest_checked_at: Optional[datetime] = None
    for index, context in enumerate(contexts):
        checked_at = _parse_datetime(context.get("checked_at"))
        if checked_at is None:
            complete = False
            checked_at = modeled_at
        elif checked_at > modeled_at:
            complete = False
            checked_at = modeled_at
        else:
            oldest_checked_at = (
                checked_at
                if oldest_checked_at is None or checked_at < oldest_checked_at
                else oldest_checked_at
            )
        observed_at = min(checked_at, modeled_at)
        # ``release_context_complete`` is the canonical result of the shared
        # football context checker.  Do not try to reconstruct completeness
        # from presentation status strings here: successful injury checks use
        # ``observed`` (and aligned/neutral weather may do the same), while the
        # upstream checker has already verified coverage and lineups.
        context_complete = context.get("release_context_complete") is True
        complete = complete and context_complete
        for section_name, display_name in (
            ("h2h", "Direktduelle"),
            ("injuries", "Ausfälle"),
            ("weather", "Wetter"),
            ("lineups", "Aufstellungen"),
        ):
            section = context.get(section_name)
            if not isinstance(section, Mapping):
                complete = False
                continue
            status = _clean_text(section.get("status")) or "offen"
            reason = _clean_text(section.get("reason"))
            summary = f"{display_name}: {reason or status}"
            factors.append(
                FactorEvidence(
                    factor_key=f"football_context_{index}_{section_name}",
                    summary=summary,
                    source="api-football-context",
                    observed_at=observed_at,
                    imported_at=modeled_at,
                    fresh_until=min(observed_at + FOOTBALL_CONTEXT_TTL, starts_at),
                    role=FactorRole.DISPLAY_ONLY,
                )
            )
            # Observing weather or finding no injury veto is not a sporting
            # advantage. Keep these facts in their attributable context factors,
            # not in the candidate's positive match-up evidence.
            if status not in {"passed", "neutral", "observed"}:
                cons.append(summary)
    if not cons and not complete:
        cons.append("Einzelne Kontextdaten sind noch offen.")
    context_is_current = bool(
        oldest_checked_at is not None
        and modeled_at - oldest_checked_at <= FOOTBALL_CONTEXT_TTL
    )
    if complete and context_is_current:
        state = ContextState.FRESH
    elif complete:
        state = ContextState.STALE
        cons.append("Der vollständige Kontext ist älter als 75 Minuten.")
    else:
        state = ContextState.PARTIAL
    return factors, state, pros, cons, _without_prices(contexts)


def _football_model_payload(candidate: object) -> dict[str, object]:
    validation = _get(candidate, "validation")
    validation_payload: object = None
    if validation is not None:
        validation_payload = {
            key: _get(validation, key)
            for key in (
                "observations",
                "brier_score",
                "expected_calibration_error",
                "statistical_release_passed",
            )
        }
    return {
        "candidate_id": _clean_text(_get(candidate, "candidate_id")),
        "market_key": _clean_text(_get(candidate, "market_key")),
        "probability": _candidate_probability(candidate),
        "conservative_probability": _probability(
            _get(candidate, "conservative_probability")
        ),
        "expected_home_goals": _number(_get(candidate, "expected_home_goals")),
        "expected_away_goals": _number(_get(candidate, "expected_away_goals")),
        "venue_samples": list(_get(candidate, "venue_samples", ()) or ()),
        "form_samples": list(_get(candidate, "form_samples", ()) or ()),
        "evidence_score": _number(_get(candidate, "evidence_score")),
        "model_spread_pp": _number(_get(candidate, "model_spread_pp")),
        "model_scope": _clean_text(_get(candidate, "model_scope")),
        "validation": validation_payload,
    }


def _football_scenario_from_selected(
    candidate: object,
    *,
    underdog_side: str,
    home: str,
    away: str,
) -> Optional[_Scenario]:
    """Rehydrate a selected scenario when the full source pool is unavailable."""

    raw_key = _clean_text(_get(candidate, "market_key"))
    probability = _candidate_probability(candidate)
    if probability is None:
        return None
    team = home if underdog_side == "home" else away
    result_key = "RESULT_HOME" if underdog_side == "home" else "RESULT_AWAY"
    dc_key = "DC_1X" if underdog_side == "home" else "DC_X2"
    goal_prefix = "HOME" if underdog_side == "home" else "AWAY"
    if raw_key == result_key and probability < FOOTBALL_WIN_MIN_PROBABILITY:
        return None
    if raw_key == "RESULT_DRAW" and probability < FOOTBALL_DRAW_MIN_PROBABILITY:
        return None
    if raw_key == dc_key and not (
        FOOTBALL_DOUBLE_CHANCE_MIN_PROBABILITY
        <= probability
        <= FOOTBALL_DOUBLE_CHANCE_MAX_PROBABILITY
    ):
        return None
    if (
        raw_key == f"{goal_prefix}_OVER_1_5"
        and probability < FOOTBALL_TWO_GOALS_MIN_PROBABILITY
    ):
        return None
    if raw_key == f"{goal_prefix}_OVER_0_5" and not (
        FOOTBALL_ONE_GOAL_MIN_PROBABILITY
        <= probability
        <= FOOTBALL_ONE_GOAL_MAX_PROBABILITY
    ):
        return None
    if raw_key == result_key:
        return _Scenario(
            source=candidate,
            market_key="result_90_minutes",
            market_label="Außenseitersieg nach 90 Minuten",
            selection_key=underdog_side,
            selection_label=team,
            probability=probability,
            cautious_probability=_candidate_cautious(candidate, probability),
            settlement_contract=(
                f"riskobet-settlement-v1:football:result_90_minutes:{underdog_side}"
            ),
            score=probability,
            pro=f"Das gemeinsame Ergebnismodell gibt {team} {probability:.1%} Siegchance.",
            con="Außenseitersiege liegen im dünnen Wahrscheinlichkeitsrand und streuen stark.",
        )
    if raw_key == "RESULT_DRAW":
        return _Scenario(
            source=candidate,
            market_key="draw_90_minutes",
            market_label="Unentschieden nach 90 Minuten",
            selection_key="draw",
            selection_label="Unentschieden",
            probability=probability,
            cautious_probability=_candidate_cautious(candidate, probability),
            settlement_contract="riskobet-settlement-v1:football:draw_90_minutes:draw",
            score=probability * 0.75,
            pro=f"Das Remismodell weist {probability:.1%} aus.",
            con="Ein einzelnes spätes Tor kann das Remisszenario vollständig kippen.",
        )
    if raw_key == dc_key:
        dc_selection = "home_or_draw" if underdog_side == "home" else "away_or_draw"
        return _Scenario(
            source=candidate,
            market_key="double_chance_90_minutes",
            market_label="Außenseiter verliert nicht",
            selection_key=dc_selection,
            selection_label="1X" if underdog_side == "home" else "X2",
            probability=probability,
            cautious_probability=_candidate_cautious(candidate, probability),
            settlement_contract=(
                "riskobet-settlement-v1:football:double_chance_90_minutes:"
                f"{dc_selection}"
            ),
            score=probability * 0.45,
            pro=f"Sieg oder Remis zusammen ergeben im Modell {probability:.1%}.",
            con="Der breitere Ausgang ist weniger überraschend und häufig preislich knapp.",
        )
    if raw_key == f"{goal_prefix}_OVER_1_5":
        expected = _number(
            _get(
                candidate,
                "expected_home_goals" if underdog_side == "home" else "expected_away_goals",
            )
        )
        return _Scenario(
            source=candidate,
            market_key="underdog_team_over_1_5_90_minutes",
            market_label="Außenseiter erzielt mindestens zwei Tore",
            selection_key=underdog_side,
            selection_label=f"{team} über 1,5 Tore",
            probability=probability,
            cautious_probability=_candidate_cautious(candidate, probability),
            settlement_contract=(
                "riskobet-settlement-v1:football:"
                f"underdog_team_over_1_5_90_minutes:{underdog_side}"
            ),
            score=probability * 0.8,
            pro=(
                f"Das Tormodell erwartet {expected:.2f} Tore von {team}."
                if expected is not None
                else f"Das Marktmodell weist {probability:.1%} für zwei Tore aus."
            ),
            con="Zwei Außenseitertore reagieren stark auf Spielstand und Chancenverwertung.",
        )
    if raw_key == f"{goal_prefix}_OVER_0_5":
        factor = _football_goal_factor(candidate, underdog_side)
        if not factor:
            return None
        return _Scenario(
            source=candidate,
            market_key="underdog_team_over_0_5_90_minutes",
            market_label="Außenseiter erzielt mindestens ein Tor",
            selection_key=underdog_side,
            selection_label=f"{team} über 0,5 Tore",
            probability=probability,
            cautious_probability=_candidate_cautious(candidate, probability),
            settlement_contract=(
                "riskobet-settlement-v1:football:"
                f"underdog_team_over_0_5_90_minutes:{underdog_side}"
            ),
            score=probability * 0.3,
            pro=factor,
            con="Ein Tor ist ein einfacher Markt und wird nur wegen des konkreten Modellfaktors gezeigt.",
        )
    return None


def football_risk_bundle(
    selected: Sequence[Any],
    *,
    modeled_at: Optional[datetime] = None,
    input_cutoff_at: Optional[datetime] = None,
    source_pool: Optional[Sequence[Any]] = None,
    provider: str = "api-football",
    model_version: str = FOOTBALL_MODEL_VERSION,
    policy_version: str = RISKOBET_POLICY_VERSION,
) -> RiskAdapterResult:
    """Freeze one fixture's selected, optionally contextualised candidates."""

    selected = tuple(
        sorted(
            selected,
            key=lambda candidate: _clean_text(_get(candidate, "candidate_id")),
        )
    )
    if not selected or len(selected) > 2:
        raise ValueError("football bundle requires one or two selected candidates")
    group_keys = {_fixture_group_key(candidate) for candidate in selected}
    if len(group_keys) != 1:
        raise ValueError("football bundle candidates must belong to one fixture")
    fixture_id, _kickoff_text = next(iter(group_keys))
    starts_at = _parse_datetime(_get(selected[0], "kickoff"))
    if starts_at is None:
        raise ValueError("football kickoff must be timezone-aware")
    model_time, cutoff = _require_causal_clock(starts_at, modeled_at, input_cutoff_at)
    home = _clean_text(_get(selected[0], "home_team")) or "Heimteam"
    away = _clean_text(_get(selected[0], "away_team")) or "Auswärtsteam"
    competition = _clean_text(_get(selected[0], "league_name")) or "Fußball"
    event_key = stable_event_key("football", provider, str(fixture_id))
    pool = tuple(source_pool or selected)
    if any(_fixture_group_key(candidate) != next(iter(group_keys)) for candidate in pool):
        raise ValueError("source_pool must contain only the bundled fixture")
    if not _consistent_football_identity(pool) or not _consistent_football_identity(selected):
        raise ValueError("football source identity is ambiguous or inconsistent")
    all_scenarios = _football_scenarios(pool)
    if not all_scenarios and source_pool is None:
        result_source = next(
            (
                candidate
                for candidate in selected
                if _clean_text(_get(candidate, "market_key"))
                in {"RESULT_HOME", "RESULT_AWAY"}
            ),
            None,
        )
        if result_source is None:
            raise ValueError("selected football sources do not identify the underdog")
        underdog_side = (
            "home"
            if _clean_text(_get(result_source, "market_key")) == "RESULT_HOME"
            else "away"
        )
        all_scenarios = [
            scenario
            for candidate in selected
            if (
                scenario := _football_scenario_from_selected(
                    candidate,
                    underdog_side=underdog_side,
                    home=home,
                    away=away,
                )
            )
            is not None
        ]
        all_scenarios.sort(
            key=lambda scenario: (scenario.score, scenario.probability, scenario.market_key),
            reverse=True,
        )
    scenario_by_source_id = {
        _clean_text(_get(scenario.source, "candidate_id")): scenario
        for scenario in all_scenarios
    }
    selected_by_id = {
        _clean_text(_get(candidate, "candidate_id")): candidate for candidate in selected
    }
    scenarios: list[_Scenario] = []
    for scenario_source in all_scenarios:
        candidate_id = _clean_text(_get(scenario_source.source, "candidate_id"))
        candidate = selected_by_id.get(candidate_id)
        scenario = scenario_by_source_id.get(candidate_id)
        if candidate is None:
            continue
        if scenario is None:
            # Context enrichment preserves candidate identity; anything else
            # would silently bind a different market to the snapshot.
            raise ValueError("selected candidate is not a current RisikoBet scenario")
        scenarios.append(
            _Scenario(
                source=candidate,
                market_key=scenario.market_key,
                market_label=scenario.market_label,
                selection_key=scenario.selection_key,
                selection_label=scenario.selection_label,
                probability=scenario.probability,
                cautious_probability=scenario.cautious_probability,
                settlement_contract=scenario.settlement_contract,
                score=scenario.score,
                pro=scenario.pro,
                con=scenario.con,
            )
        )
    if len(scenarios) != len(selected):
        raise ValueError("selected candidate is not a current RisikoBet scenario")
    context_factors, context_state, context_pros, context_cons, context_payload = (
        _football_context_parts(selected, model_time, starts_at)
    )
    minimum_venue = min(
        (
            min(tuple(_get(candidate, "venue_samples", ()) or (0,)))
            for candidate in pool
        ),
        default=0,
    )
    model_factor = FactorEvidence(
        # The provider fixture identity is part of the already-causal model
        # factor so settlement can recover it without a name-based guess.
        factor_key=f"football_fixture_id:{fixture_id}",
        summary=(
            f"Vollständige gemeinsame Marktverteilung; mindestens {minimum_venue} "
            "Venue-Beobachtungen je Team."
        ),
        source="challenge_engine.build_fixture_candidates",
        observed_at=cutoff,
        imported_at=model_time,
        fresh_until=starts_at,
        sample_size=max(0, int(minimum_venue)),
        role=FactorRole.MODEL,
    )
    input_hash = canonical_input_hash(
        {
            "fixture_id": fixture_id,
            "home": home,
            "away": away,
            "kickoff": starts_at.isoformat(),
            # These clocks affect frozen snapshot content (factor import
            # times and context freshness).  Bind them to the immutable input
            # revision so a later provider observation cannot reuse an older
            # snapshot identity with different content.
            "modeled_at": model_time.isoformat(),
            "input_cutoff_at": cutoff.isoformat(),
            "model_candidates": sorted(
                (_football_model_payload(candidate) for candidate in pool),
                key=lambda item: str(item["candidate_id"]),
            ),
            "selected_candidate_ids": sorted(
                _clean_text(_get(candidate, "candidate_id")) for candidate in selected
            ),
            "context": context_payload,
        }
    )
    snapshot = EventModelSnapshot(
        event_key=event_key,
        sport="football",
        competition=competition,
        event_label=f"{home} vs {away}",
        starts_at=starts_at,
        modeled_at=model_time,
        input_cutoff_at=cutoff,
        model_version=model_version,
        input_hash=input_hash,
        factors=(model_factor, *context_factors),
        missing_core_data=(),
    )
    candidates = tuple(
        RiskCandidate(
            snapshot_id=snapshot.snapshot_id,
            event_key=event_key,
            sport="football",
            competition=competition,
            event_label=f"{home} vs {away}",
            starts_at=starts_at,
            market_key=scenario.market_key,
            market_label=scenario.market_label,
            selection_key=scenario.selection_key,
            selection_label=scenario.selection_label,
            model_probability=scenario.probability,
            cautious_probability=scenario.cautious_probability,
            stage=EvidenceStage.SHADOW,
            context_state=context_state,
            policy_version=policy_version,
            pros=tuple(dict.fromkeys((scenario.pro, *context_pros)))[:3],
            cons=tuple(dict.fromkeys((scenario.con, *context_cons)))[:3],
            settlement_contract=scenario.settlement_contract,
        )
        for scenario in scenarios
    )
    return RiskAdapterResult(snapshot=snapshot, candidates=candidates)


def adapt_football_candidates(
    pool: Iterable[Any],
    *,
    modeled_at: Optional[datetime] = None,
    input_cutoff_at: Optional[datetime] = None,
    provider: str = "api-football",
    model_version: str = FOOTBALL_MODEL_VERSION,
    policy_version: str = RISKOBET_POLICY_VERSION,
) -> tuple[RiskAdapterResult, ...]:
    """Convenience adapter for pools that need no separate context roundtrip."""

    pool = tuple(pool)
    full_groups: dict[tuple[int, str], list[Any]] = {}
    for candidate in pool:
        try:
            full_groups.setdefault(_fixture_group_key(candidate), []).append(candidate)
        except ValueError:
            continue
    selected = select_football_risk_sources(pool)
    selected_groups: dict[tuple[int, str], list[Any]] = {}
    for candidate in selected:
        selected_groups.setdefault(_fixture_group_key(candidate), []).append(candidate)
    return tuple(
        football_risk_bundle(
            selected_groups[key],
            modeled_at=modeled_at,
            input_cutoff_at=input_cutoff_at,
            source_pool=full_groups[key],
            provider=provider,
            model_version=model_version,
            policy_version=policy_version,
        )
        for key in sorted(selected_groups, key=lambda item: (item[1], item[0]))
    )


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    resolved = db_path.resolve()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _load_json_object(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return {str(key): raw for key, raw in value.items()}
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _shadow_factor(
    *,
    key: str,
    summary: str,
    source: str,
    observed_at: datetime,
    imported_at: datetime,
    starts_at: datetime,
) -> FactorEvidence:
    return FactorEvidence(
        factor_key=key,
        summary=summary,
        source=source,
        observed_at=observed_at,
        imported_at=imported_at,
        fresh_until=starts_at,
        role=FactorRole.MODEL,
    )


def _shadow_identity_factor(
    *,
    key: str,
    summary: str,
    source: str,
    observed_at: datetime,
    imported_at: datetime,
    starts_at: datetime,
) -> FactorEvidence:
    """Freeze a provider-row identity without treating it as model evidence."""

    return FactorEvidence(
        factor_key=key,
        summary=summary,
        source=source,
        observed_at=observed_at,
        imported_at=imported_at,
        fresh_until=starts_at,
        role=FactorRole.DISPLAY_ONLY,
    )


def adapt_tennis_shadow(
    db_path: str | Path,
    *,
    as_of: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    policy_version: str = RISKOBET_POLICY_VERSION,
) -> tuple[RiskAdapterResult, ...]:
    """Read causal, unsettled pre-match tennis model rows from shadow SQLite."""

    now = _parse_datetime(as_of or datetime.now(_UTC))
    end = _parse_datetime(window_end) if window_end is not None else None
    if now is None or (end is not None and end < now):
        raise ValueError("invalid tennis adapter time window")
    path = Path(db_path)
    if not path.is_file():
        return ()
    from tennis.shadow import latest_predictions
    rows = latest_predictions(path, pending_only=True, as_of=now)
    outputs: list[RiskAdapterResult] = []
    for row in rows:
        prediction_id = row["id"]
        if (
            not isinstance(prediction_id, int)
            or isinstance(prediction_id, bool)
            or prediction_id <= 0
        ):
            continue
        starts_at = _parse_datetime(row["scheduled_start_utc"])
        observed_at = _parse_datetime(row["created_utc"])
        if (
            starts_at is None
            or observed_at is None
            or observed_at > now
            or observed_at > starts_at
            or starts_at <= now
            or (end is not None and starts_at > end)
        ):
            continue
        p_a = _probability(row["p_cal"])
        player_a = _clean_text(row["player_a"])
        player_b = _clean_text(row["player_b"])
        if p_a is None or not player_a or not player_b or player_a.casefold() == player_b.casefold():
            continue
        p_b = 1.0 - p_a
        if math.isclose(p_a, p_b, abs_tol=1e-12):
            continue
        underdog_side = "home" if p_a < p_b else "away"
        underdog = player_a if underdog_side == "home" else player_b
        p_underdog = min(p_a, p_b)
        markets = _load_json_object(row["markets_json"])
        tournament = _clean_text(row["tournament"] if "tournament" in row.keys() else "")
        competition = tournament or _clean_text(row["tour"] if "tour" in row.keys() else "") or "Tennis"
        provider_id = _clean_text(
            row["provider_event_id"] if "provider_event_id" in row.keys() else ""
        ) or f"shadow-{row['id']}"
        provider = _clean_text(
            row["fixture_source"] if "fixture_source" in row.keys() else ""
        ) or "tennis-shadow"
        model_version = _clean_text(
            row["model_version"] if "model_version" in row.keys() else ""
        ) or TENNIS_FALLBACK_MODEL_VERSION
        event_key = stable_event_key("tennis", provider, provider_id)
        input_payload = {
            "prediction_id": prediction_id,
            "provider_event_id": provider_id,
            "created_utc": observed_at.isoformat(),
            "scheduled_start_utc": starts_at.isoformat(),
            "tour": _clean_text(row["tour"] if "tour" in row.keys() else ""),
            "tournament": tournament,
            "surface": _clean_text(row["surface"] if "surface" in row.keys() else ""),
            "best_of": row["best_of"] if "best_of" in row.keys() else None,
            "player_a": player_a,
            "player_b": player_b,
            "p_cal": p_a,
            "markets": _without_prices(markets),
            "gates": _without_prices(
                _load_json_object(row["gates_json"] if "gates_json" in row.keys() else None)
            ),
            "model_revision_id": row.get("model_revision_id"),
            "context": _without_prices(_load_json_object(row.get("context_json"))),
        }
        factor = _shadow_factor(
            key="tennis_calibrated_match_model",
            summary=(
                f"Kalibriertes Sieger-Modell plus Satzsimulation; Außenseiter {p_underdog:.1%}."
            ),
            source="tennis_shadow.predictions",
            observed_at=observed_at,
            imported_at=observed_at,
            starts_at=starts_at,
        )
        identity_factor = _shadow_identity_factor(
            key=f"tennis_prediction_id:{prediction_id}",
            summary=(
                f"Eingefrorene Tennis-Quellzeile {prediction_id}: "
                f"{player_a} vs {player_b}."
            ),
            source="tennis_shadow.predictions",
            observed_at=observed_at,
            imported_at=observed_at,
            starts_at=starts_at,
        )
        workload = _load_json_object(row.get("context_json"))
        workload_players = workload.get("players", {})
        workload_factors = []
        if isinstance(workload_players, Mapping):
            for side, player_name in (("a", player_a), ("b", player_b)):
                data = workload_players.get(side, {})
                if not isinstance(data, Mapping):
                    continue
                for index, fact in enumerate(data.get("facts", ())):
                    if not isinstance(fact, str) or not fact.strip():
                        continue
                    workload_factors.append(FactorEvidence(
                        factor_key=f"tennis_workload_{side}_{index}",
                        summary=f"{player_name}: {fact}"[:600],
                        source="tennis-shadow-observed-results",
                        observed_at=observed_at, imported_at=observed_at,
                        fresh_until=starts_at, role=FactorRole.DISPLAY_ONLY,
                    ))
        snapshot = EventModelSnapshot(
            event_key=event_key,
            sport="tennis",
            competition=competition,
            event_label=f"{player_a} vs {player_b}",
            starts_at=starts_at,
            modeled_at=observed_at,
            input_cutoff_at=observed_at,
            model_version=model_version,
            input_hash=canonical_input_hash(input_payload),
            factors=(factor, identity_factor, *workload_factors),
        )
        options: list[tuple[float, str, str, float, float, str, str]] = []
        # (weighted score, market key, label, p, haircut, pro, con)
        over_25 = _probability(markets.get("over_2_5_sets"))
        favorite_straight_key = (
            "set_handicap_b_minus_1_5"
            if underdog_side == "home"
            else "set_handicap_a_minus_1_5"
        )
        favorite_straight = _probability(markets.get(favorite_straight_key))
        at_least_one = 1.0 - favorite_straight if favorite_straight is not None else None
        # A simple 1+ set card needs an additional matchup signal.  The
        # independently simulated probability of a deciding set is that signal.
        if (
            at_least_one is not None
            and TENNIS_SIDE_MIN_PROBABILITY <= at_least_one <= TENNIS_SIMPLE_MAX_PROBABILITY
            and over_25 is not None
            and over_25 >= 0.40
        ):
            options.append(
                (
                    at_least_one * 0.45,
                    "plus_1_5_sets",
                    "Außenseiter gewinnt mindestens einen Satz (+1,5)",
                    at_least_one,
                    0.10,
                    f"Das Satzmodell sieht {over_25:.1%} Chance auf einen Entscheidungssatz.",
                    "Ein einzelner schwacher Aufschlagdurchgang kann den Satzmarkt kippen.",
                )
            )
        if (
            over_25 is not None
            and TENNIS_SIDE_MIN_PROBABILITY <= over_25 <= TENNIS_SIMPLE_MAX_PROBABILITY
        ):
            options.append(
                (
                    over_25 * 0.70,
                    "over_2_5_sets",
                    "Über 2,5 Sätze",
                    over_25,
                    0.10,
                    f"Die Serve-Simulation weist {over_25:.1%} für drei Sätze aus.",
                    "Das Modell setzt ein regulär beendetes Best-of-3-Match voraus.",
                )
            )
        chosen_side = max(options, key=lambda item: (item[0], item[1]), default=None)
        base_specs: list[tuple[str, str, float, float, str, str]] = []
        if p_underdog >= TENNIS_WIN_MIN_PROBABILITY:
            base_specs.append((
                "match_winner",
                "Außenseitersieg",
                p_underdog,
                0.15,
                f"Das kalibrierte Matchmodell gibt {underdog} {p_underdog:.1%} Siegchance.",
                "Belag ist modelliert. Akute Fitness, Verletzungen und Belastung sind noch nicht als numerischer Effekt validiert.",
            ))
        if chosen_side is not None:
            base_specs.append(chosen_side[1:])
        candidates = tuple(
            RiskCandidate(
                snapshot_id=snapshot.snapshot_id,
                event_key=event_key,
                sport="tennis",
                competition=competition,
                event_label=f"{player_a} vs {player_b}",
                starts_at=starts_at,
                market_key=spec[0],
                market_label=spec[1],
                selection_key=("over" if spec[0] == "over_2_5_sets" else underdog_side),
                selection_label=("Über 2,5 Sätze" if spec[0] == "over_2_5_sets" else underdog),
                model_probability=spec[2],
                cautious_probability=max(0.0, spec[2] - spec[3]),
                stage=EvidenceStage.SHADOW,
                context_state=ContextState.PARTIAL,
                policy_version=policy_version,
                pros=(spec[4],),
                cons=(spec[5],),
                settlement_contract=(
                    f"riskobet-settlement-v1:tennis:{spec[0]}:"
                    f"{'over' if spec[0] == 'over_2_5_sets' else underdog_side}"
                ),
            )
            for spec in base_specs
        )
        outputs.append(RiskAdapterResult(snapshot=snapshot, candidates=candidates))
    return tuple(outputs)


def _series_probability(map_probability: float, maps_to_win: int) -> float:
    # P(win a best-of-(2k-1) series) under the same i.i.d. map assumption as
    # the existing e-sport model.
    total = 0.0
    for losses in range(maps_to_win):
        total += (
            math.comb(maps_to_win - 1 + losses, losses)
            * map_probability**maps_to_win
            * (1.0 - map_probability) ** losses
        )
    return total


def _map_probability_from_series(series_probability: float, maps_to_win: int) -> float:
    low, high = 0.0, 1.0
    for _ in range(70):
        middle = (low + high) / 2.0
        if _series_probability(middle, maps_to_win) < series_probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def adapt_esports_shadow(
    db_path: str | Path,
    *,
    as_of: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    policy_version: str = RISKOBET_POLICY_VERSION,
) -> tuple[RiskAdapterResult, ...]:
    """Read pre-match e-sport rows and derive underdog series/map scenarios."""

    now = _parse_datetime(as_of or datetime.now(_UTC))
    end = _parse_datetime(window_end) if window_end is not None else None
    if now is None or (end is not None and end < now):
        raise ValueError("invalid e-sport adapter time window")
    path = Path(db_path)
    if not path.is_file():
        return ()
    with _connect_read_only(path) as connection:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(esports_shadow_predictions)"
            )
        }
        required = {
            "match_id",
            "logged_at",
            "game",
            "team1",
            "team2",
            "team1_id",
            "team2_id",
            "selection",
            "series_type",
            "score1",
            "score2",
            "elo1",
            "elo2",
            "model_probability",
            "risk_adjusted_probability",
            "status",
            "settled",
            "scheduled_at",
        }
        if not required.issubset(columns):
            return ()
        rows = connection.execute(
            """
            SELECT * FROM esports_shadow_predictions
            WHERE settled = 0 AND status = 'upcoming'
            ORDER BY scheduled_at, match_id
            """
        ).fetchall()
    outputs: list[RiskAdapterResult] = []
    for row in rows:
        match_id = row["match_id"]
        if (
            not isinstance(match_id, int)
            or isinstance(match_id, bool)
            or match_id <= 0
        ):
            continue
        starts_at = _parse_datetime(row["scheduled_at"])
        observed_at = _parse_datetime(row["logged_at"])
        if (
            starts_at is None
            or observed_at is None
            or observed_at > now
            or observed_at > starts_at
            or starts_at <= now
            or (end is not None and starts_at > end)
            or row["score1"] != 0
            or row["score2"] != 0
        ):
            continue
        team1 = _clean_text(row["team1"])
        team2 = _clean_text(row["team2"])
        team1_id = row["team1_id"]
        team2_id = row["team2_id"]
        favorite = _clean_text(row["selection"])
        if (
            not team1
            or not team2
            or team1.casefold() == team2.casefold()
            or not isinstance(team1_id, int)
            or isinstance(team1_id, bool)
            or team1_id <= 0
            or not isinstance(team2_id, int)
            or isinstance(team2_id, bool)
            or team2_id <= 0
            or team1_id == team2_id
        ):
            continue
        if favorite == team1:
            underdog, underdog_side = team2, "away"
        elif favorite == team2:
            underdog, underdog_side = team1, "home"
        else:
            continue
        favorite_probability = _probability(row["model_probability"], percent_allowed=True)
        favorite_cautious = _probability(
            row["risk_adjusted_probability"], percent_allowed=True
        )
        series_type = row["series_type"]
        if (
            favorite_probability is None
            or favorite_probability < 0.5
            or isinstance(series_type, bool)
            or not isinstance(series_type, int)
            or series_type < 1
            or series_type % 2 == 0
        ):
            continue
        p_underdog = 1.0 - favorite_probability
        maps_to_win = series_type // 2 + 1
        p_map_underdog = _map_probability_from_series(p_underdog, maps_to_win)
        p_at_least_one_map = 1.0 - (1.0 - p_map_underdog) ** maps_to_win
        elo1 = _number(row["elo1"])
        elo2 = _number(row["elo2"])
        if elo1 is None or elo2 is None:
            continue
        game = _clean_text(row["game"]) or "E-Sport"
        event_key = stable_event_key("esports", "pandascore", str(match_id))
        model_version = _clean_text(
            row["model_version"] if "model_version" in row.keys() else ""
        ) or ESPORTS_FALLBACK_MODEL_VERSION
        factor = _shadow_factor(
            key="esports_subgraph_elo",
            summary=(
                f"Subgraph-Elo {elo1:.0f}/{elo2:.0f}, Best-of-{series_type}; "
                f"abgeleitete Mapchance des Außenseiters {p_map_underdog:.1%}."
            ),
            source="esports_shadow_predictions",
            observed_at=observed_at,
            imported_at=observed_at,
            starts_at=starts_at,
        )
        match_identity = _shadow_identity_factor(
            key=f"esports_match_id:{match_id}",
            summary=f"Eingefrorene PandaScore-Match-ID: {match_id}.",
            source="esports_shadow_predictions",
            observed_at=observed_at,
            imported_at=observed_at,
            starts_at=starts_at,
        )
        team1_identity = _shadow_identity_factor(
            key=f"esports_team1_id:{team1_id}",
            summary=f"Eingefrorene PandaScore-Team-ID für {team1}: {team1_id}.",
            source="esports_shadow_predictions",
            observed_at=observed_at,
            imported_at=observed_at,
            starts_at=starts_at,
        )
        team2_identity = _shadow_identity_factor(
            key=f"esports_team2_id:{team2_id}",
            summary=f"Eingefrorene PandaScore-Team-ID für {team2}: {team2_id}.",
            source="esports_shadow_predictions",
            observed_at=observed_at,
            imported_at=observed_at,
            starts_at=starts_at,
        )
        snapshot = EventModelSnapshot(
            event_key=event_key,
            sport="esports",
            competition=game,
            event_label=f"{team1} vs {team2}",
            starts_at=starts_at,
            modeled_at=observed_at,
            input_cutoff_at=observed_at,
            model_version=model_version,
            input_hash=canonical_input_hash(
                {
                    "match_id": match_id,
                    "logged_at": observed_at.isoformat(),
                    "scheduled_at": starts_at.isoformat(),
                    "game": game,
                    "team1": team1,
                    "team2": team2,
                    "team1_id": team1_id,
                    "team2_id": team2_id,
                    "favorite": favorite,
                    "series_type": series_type,
                    "elo1": elo1,
                    "elo2": elo2,
                    "favorite_probability": favorite_probability,
                    "favorite_cautious_probability": favorite_cautious,
                }
            ),
            factors=(factor, match_identity, team1_identity, team2_identity),
        )
        specs: list[tuple[str, str, float, str, str]] = []
        if p_underdog >= ESPORTS_WIN_MIN_PROBABILITY:
            specs.append((
                "series_winner",
                "Außenseitersieg in der Serie",
                p_underdog,
                f"Die Gegenwahrscheinlichkeit des eingefrorenen Serienmodells beträgt {p_underdog:.1%}.",
                "Rosterwechsel und Map-Vetos sind im öffentlichen Feed nicht vollständig identifiziert.",
            ))
        # At least one map is a simple scenario and therefore needs a concrete
        # closeness signal in addition to its own high headline probability.
        if (
            p_map_underdog >= 0.30
            and ESPORTS_MAP_MIN_PROBABILITY
            <= p_at_least_one_map
            <= ESPORTS_SIMPLE_MAX_PROBABILITY
            and abs(elo1 - elo2) <= 200.0
        ):
            specs.append(
                (
                    "at_least_one_map",
                    "Außenseiter gewinnt mindestens eine Map",
                    p_at_least_one_map,
                    f"Die aus der Serie invertierte Einzelmap-Chance liegt bei {p_map_underdog:.1%}.",
                    "Die i.i.d.-Mapannahme bildet Veto- und Seiteneffekte nicht vollständig ab.",
                )
            )
        candidates = tuple(
            RiskCandidate(
                snapshot_id=snapshot.snapshot_id,
                event_key=event_key,
                sport="esports",
                competition=game,
                event_label=f"{team1} vs {team2}",
                starts_at=starts_at,
                market_key=market_key,
                market_label=market_label,
                selection_key=underdog_side,
                selection_label=underdog,
                model_probability=probability,
                cautious_probability=max(0.0, probability - 0.10),
                stage=EvidenceStage.SHADOW,
                context_state=ContextState.PARTIAL,
                policy_version=policy_version,
                pros=(pro,),
                cons=(con,),
                settlement_contract=(
                    f"riskobet-settlement-v1:esports:{market_key}:{underdog_side}"
                ),
            )
            for market_key, market_label, probability, pro, con in specs[:2]
        )
        outputs.append(RiskAdapterResult(snapshot=snapshot, candidates=candidates))
    return tuple(outputs)


def _history_timestamp(row: Mapping[str, object]) -> Optional[datetime]:
    # A scheduled/start timestamp never proves that the eventual result was
    # already known.  Accept only explicit completion or result-observation
    # clocks so offline/backfill calls cannot leak a later outcome past their
    # input cutoff.
    for key in (
        "result_observed_at",
        "result_recorded_at",
        "settled_at",
        "completed_at",
        "ended_at",
        "finished_at",
        "final_at",
    ):
        parsed = _parse_datetime(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _research_source_observed_at(
    event: Mapping[str, object],
    *,
    starts_at: datetime,
    as_of: Optional[datetime],
) -> datetime:
    """Return the explicit event-fetch clock used by a research revision.

    The caller's run time is only an as-of guard.  It must not become model
    provenance because rereading an unchanged event later would otherwise
    mutate an immutable snapshot under the same input identity.
    """

    raw_source_time: object = None
    source_field = ""
    for key in ("source_observed_at", "fetched_at"):
        if event.get(key) not in (None, ""):
            raw_source_time = event.get(key)
            source_field = key
            break
    if not source_field:
        raise ValueError(
            "research event requires a timezone-aware source_observed_at or fetched_at"
        )
    source_time = _parse_datetime(raw_source_time)
    if source_time is None:
        raise ValueError(f"research event {source_field} must be timezone-aware")
    if source_time > starts_at:
        raise ValueError("research event source observation must not follow event start")

    if as_of is not None:
        requested = _parse_datetime(as_of)
        if requested is None:
            raise ValueError("modeled_at must be timezone-aware")
        if requested < source_time:
            raise ValueError("modeled_at must not precede the event source observation")
        if requested > starts_at:
            raise ValueError("RisikoBet adapters only accept pre-match model states")
    return source_time


def _history_team_side(
    row: Mapping[str, object], team_id: str, team_name: str
) -> Optional[str]:
    home_id = _clean_text(row.get("home_team_id"))
    away_id = _clean_text(row.get("away_team_id"))
    home_name = _clean_text(row.get("home_team"))
    away_name = _clean_text(row.get("away_team"))
    if team_id and home_id == team_id:
        return "home"
    if team_id and away_id == team_id:
        return "away"
    if team_name and home_name.casefold() == team_name.casefold():
        return "home"
    if team_name and away_name.casefold() == team_name.casefold():
        return "away"
    return None


def _history_winner_side(row: Mapping[str, object]) -> Optional[str]:
    outcome = _clean_text(row.get("outcome") or row.get("winner_side")).casefold()
    if outcome in {"home", "home_win", "team1", "1"}:
        return "home"
    if outcome in {"away", "away_win", "team2", "2"}:
        return "away"
    winner_id = _clean_text(row.get("winner_team_id"))
    winner_name = _clean_text(row.get("winner") or row.get("winner_team"))
    if winner_id:
        if winner_id == _clean_text(row.get("home_team_id")):
            return "home"
        if winner_id == _clean_text(row.get("away_team_id")):
            return "away"
    if winner_name:
        if winner_name.casefold() == _clean_text(row.get("home_team")).casefold():
            return "home"
        if winner_name.casefold() == _clean_text(row.get("away_team")).casefold():
            return "away"
    home_score = _number(
        row.get("home_score_final", row.get("home_score"))
    )
    away_score = _number(
        row.get("away_score_final", row.get("away_score"))
    )
    if home_score is None or away_score is None or home_score == away_score:
        return None
    return "home" if home_score > away_score else "away"


def _causal_team_record(
    history: Iterable[Mapping[str, object]],
    *,
    team_id: str,
    team_name: str,
    cutoff: datetime,
    starts_at: datetime,
) -> tuple[int, int, tuple[dict[str, object], ...], Optional[datetime]]:
    wins = 0
    games = 0
    causal_rows: list[dict[str, object]] = []
    latest: Optional[datetime] = None
    for raw in history:
        if not isinstance(raw, Mapping):
            continue
        status = _clean_text(raw.get("status")).casefold()
        if status and status not in {
            "final",
            "finished",
            "completed",
            "closed",
            "ended",
        }:
            continue
        observed = _history_timestamp(raw)
        if observed is None or observed > cutoff or observed >= starts_at:
            continue
        side = _history_team_side(raw, team_id, team_name)
        winner = _history_winner_side(raw)
        if side is None or winner is None:
            continue
        games += 1
        wins += int(side == winner)
        latest = observed if latest is None or observed > latest else latest
        causal_rows.append(
            {
                "completed_at": observed.isoformat(),
                "home_team_id": _clean_text(raw.get("home_team_id")),
                "away_team_id": _clean_text(raw.get("away_team_id")),
                "home_team": _clean_text(raw.get("home_team")),
                "away_team": _clean_text(raw.get("away_team")),
                "winner_side": winner,
            }
        )
    causal_rows.sort(key=lambda item: (str(item["completed_at"]), str(item["home_team"])))
    return wins, games, tuple(causal_rows), latest


def _smoothed_rate(wins: int, games: int) -> float:
    # Symmetric Beta(2, 2) prior prevents 0/1 extremes in young histories.
    return (wins + 2.0) / (games + 4.0)


def _log5(a: float, b: float) -> float:
    denominator = a + b - 2.0 * a * b
    if denominator <= 0.0:
        return 0.5
    return max(0.0, min(1.0, (a - a * b) / denominator))


def adapt_research_matchwinner(
    sport: str,
    event: Mapping[str, object],
    history: Iterable[Mapping[str, object]],
    *,
    modeled_at: Optional[datetime] = None,
    minimum_team_games: int = MIN_RESEARCH_TEAM_GAMES,
    policy_version: str = RISKOBET_POLICY_VERSION,
    model_version: str = RESEARCH_MODEL_VERSION,
) -> RiskAdapterResult:
    """Share one causal sport-specific prematch fit per competition snapshot."""

    if sport not in {"basketball", "ice_hockey", "cricket"}:
        raise ValueError("research match-winner adapter supports basketball, ice_hockey and cricket")
    if (
        isinstance(minimum_team_games, bool)
        or not isinstance(minimum_team_games, int)
        or minimum_team_games < 2
    ):
        raise ValueError("minimum_team_games must be an integer of at least two")
    starts_at = _parse_datetime(
        event.get(
            "starts_at",
            event.get("start_time", event.get("scheduled_at", event.get("begin_at"))),
        )
    )
    if starts_at is None:
        raise ValueError("research event requires a timezone-aware starts_at")
    source_observed_at = _research_source_observed_at(
        event,
        starts_at=starts_at,
        as_of=modeled_at,
    )
    model_time, cutoff = _require_causal_clock(
        starts_at,
        modeled_at or source_observed_at,
        modeled_at or source_observed_at,
    )
    provider = _clean_text(event.get("provider") or event.get("source"))
    provider_event_id = _clean_text(
        event.get(
            "provider_event_id",
            event.get(
                "event_id",
                event.get("game_id", event.get("match_id", event.get("id"))),
            ),
        )
    )
    home = _clean_text(event.get("home_team", event.get("team1")))
    away = _clean_text(event.get("away_team", event.get("team2")))
    home_id = _clean_text(event.get("home_team_id", event.get("team1_id")))
    away_id = _clean_text(event.get("away_team_id", event.get("team2_id")))
    if not provider or not provider_event_id or not home or not away:
        raise ValueError("research event requires provider/event/team identities")
    if home.casefold() == away.casefold() or (home_id and away_id and home_id == away_id):
        raise ValueError("research event teams must be distinct")
    competition = _clean_text(
        event.get("competition", event.get("league", event.get("tournament")))
    ) or sport
    from sports_prematch import predict_prematch
    prediction = predict_prematch(sport, event, history, as_of=model_time)
    home_games, away_games = prediction.home_games, prediction.away_games
    missing: list[str] = list(prediction.missing)
    if home_games < minimum_team_games:
        missing.append(
            f"{home}: {minimum_team_games} abgeschlossene Spiele vor Start erforderlich, {home_games} vorhanden"
        )
    if away_games < minimum_team_games:
        missing.append(
            f"{away}: {minimum_team_games} abgeschlossene Spiele vor Start erforderlich, {away_games} vorhanden"
        )
    probability: Optional[float] = None
    cautious: Optional[float] = None
    if not missing and prediction.p_home is not None:
        p_home = prediction.p_home
        if math.isclose(p_home, 0.5, abs_tol=1e-12):
            missing.append("Kein eindeutiger Außenseiter aus der kausalen Historie bestimmbar")
            underdog_side = "open"
            underdog = "Außenseiter noch offen"
        else:
            underdog_side = "home" if p_home < 0.5 else "away"
            underdog = home if underdog_side == "home" else away
            probability = min(p_home, 1.0 - p_home)
    else:
        underdog_side = "open"
        underdog = "Außenseiter noch offen"
    event_key = stable_event_key(sport, provider, provider_event_id)
    factors = tuple(
        FactorEvidence(
            factor_key=f"prematch_model_{index}",
            summary=summary,
            source=f"{provider}:historical_results",
            observed_at=prediction.latest_result_observed_at,
            imported_at=model_time,
            fresh_until=min(model_time + RESEARCH_HISTORY_TTL, starts_at),
            coverage=min(1.0, min(home_games, away_games) / minimum_team_games),
            sample_size=prediction.training_games,
            role=FactorRole.MODEL,
        )
        for index, summary in enumerate(prediction.factors)
        if prediction.latest_result_observed_at is not None
    )
    input_hash = canonical_input_hash(
        {
            "sport": sport,
            "provider": provider,
            "provider_event_id": provider_event_id,
            "source_observed_at": source_observed_at.isoformat(),
            "starts_at": starts_at.isoformat(),
            "home": {"id": home_id, "name": home},
            "away": {"id": away_id, "name": away},
            "minimum_team_games": minimum_team_games,
            "model_input_hash": prediction.input_hash,
            "model_decision_at": model_time.isoformat(),
        }
    )
    snapshot = EventModelSnapshot(
        event_key=event_key,
        sport=sport,
        competition=competition,
        event_label=f"{home} vs {away}",
        starts_at=starts_at,
        modeled_at=model_time,
        input_cutoff_at=cutoff,
        model_version=prediction.model_version,
        input_hash=input_hash,
        factors=factors,
        missing_core_data=tuple(missing),
    )
    market_by_sport = {
        "basketball": ("match_winner_including_ot", "Außenseitersieg inklusive Overtime"),
        "ice_hockey": ("match_winner_including_ot", "Außenseitersieg inklusive Verlängerung"),
        "cricket": ("match_winner", "Außenseiter gewinnt das Match"),
    }
    market_key, market_label = market_by_sport[sport]
    if probability is not None and probability < RESEARCH_WIN_MIN_PROBABILITY:
        return RiskAdapterResult(snapshot=snapshot, candidates=())
    if probability is None:
        pros = ("Event- und Gegneridentität sind eindeutig und vor dem Start erfasst.",)
        cons = tuple(missing)
    else:
        pros = (
            f"Das sportspezifische Modell aus {prediction.training_games} Ergebnissen ergibt {probability:.1%}.",
        )
        cons = (
            "Noch keine unabhängig bestätigte Treffergenauigkeit; kein nachgewiesener Wettvorteil.",
            *prediction.limitations,
        )
    candidate = RiskCandidate(
        snapshot_id=snapshot.snapshot_id,
        event_key=event_key,
        sport=sport,
        competition=competition,
        event_label=f"{home} vs {away}",
        starts_at=starts_at,
        market_key=market_key,
        market_label=market_label,
        selection_key=underdog_side,
        selection_label=underdog,
        model_probability=probability,
        cautious_probability=cautious,
        stage=EvidenceStage.RESEARCH,
        context_state=ContextState.PARTIAL if probability is not None else ContextState.OPEN,
        policy_version=policy_version,
        pros=pros,
        cons=cons,
        missing_core_data=tuple(missing),
        settlement_contract=(
            f"riskobet-settlement-v1:{sport}:{market_key}:{underdog_side}"
            if underdog_side in {"home", "away"}
            else None
        ),
    )
    return RiskAdapterResult(snapshot=snapshot, candidates=(candidate,))


def adapt_basketball_research(
    event: Mapping[str, object],
    history: Iterable[Mapping[str, object]],
    **kwargs: Any,
) -> RiskAdapterResult:
    return adapt_research_matchwinner("basketball", event, history, **kwargs)


def adapt_ice_hockey_research(
    event: Mapping[str, object],
    history: Iterable[Mapping[str, object]],
    **kwargs: Any,
) -> RiskAdapterResult:
    return adapt_research_matchwinner("ice_hockey", event, history, **kwargs)


def adapt_cricket_research(
    event: Mapping[str, object],
    history: Iterable[Mapping[str, object]],
    **kwargs: Any,
) -> RiskAdapterResult:
    return adapt_research_matchwinner("cricket", event, history, **kwargs)


__all__ = [
    "ESPORTS_FALLBACK_MODEL_VERSION",
    "ESPORTS_MAP_MIN_PROBABILITY",
    "ESPORTS_SIMPLE_MAX_PROBABILITY",
    "ESPORTS_WIN_MIN_PROBABILITY",
    "FOOTBALL_CONTEXT_TTL",
    "FOOTBALL_DOUBLE_CHANCE_MAX_PROBABILITY",
    "FOOTBALL_DOUBLE_CHANCE_MIN_PROBABILITY",
    "FOOTBALL_DRAW_MIN_PROBABILITY",
    "FOOTBALL_MODEL_VERSION",
    "FOOTBALL_ONE_GOAL_MAX_PROBABILITY",
    "FOOTBALL_ONE_GOAL_MIN_PROBABILITY",
    "FOOTBALL_TWO_GOALS_MIN_PROBABILITY",
    "FOOTBALL_WIN_MIN_PROBABILITY",
    "MIN_RESEARCH_TEAM_GAMES",
    "RESEARCH_HISTORY_TTL",
    "RESEARCH_MODEL_VERSION",
    "RESEARCH_WIN_MIN_PROBABILITY",
    "RISKOBET_POLICY_VERSION",
    "RiskAdapterResult",
    "TENNIS_FALLBACK_MODEL_VERSION",
    "TENNIS_SIDE_MIN_PROBABILITY",
    "TENNIS_SIMPLE_MAX_PROBABILITY",
    "TENNIS_WIN_MIN_PROBABILITY",
    "adapt_basketball_research",
    "adapt_cricket_research",
    "adapt_esports_shadow",
    "adapt_football_candidates",
    "adapt_ice_hockey_research",
    "adapt_research_matchwinner",
    "adapt_tennis_shadow",
    "football_risk_bundle",
    "football_risk_source_pool",
    "select_football_risk_sources",
]
