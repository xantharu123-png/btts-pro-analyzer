"""Offline-only UEFA cross-competition transfer validation.

This module deliberately has no provider, HTTP, Streamlit, price, or publishing
dependency.  It consumes an already assembled, result-only replay dataset and
produces a hash-bound *shadow* artifact.  Nothing in the production Wettfinder
loads this artifact yet.

The replay contract is stricter than the live fallback:

* every target has explicit UEFA competition and domestic-source provenance;
* competition and team histories are filtered to dates strictly before the
  target's UTC match day (future and same-day results are invisible);
* rolling calibration and base rates are updated only after a complete match
  day has been predicted;
* validation is market-specific, and fewer than 200 real out-of-sample
  predictions in any declared competition can never yield ``validated=True``;
* the resulting document is shadow-only and bound to its dataset, model
  signature, competition set, cohort, and training cutoff.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from statistics import fmean
from typing import Any, Iterable, Mapping, Optional, Sequence

from challenge_engine import (
    CALIBRATION_REFIT_NEW_SAMPLES,
    MARKET_BY_KEY,
    MAX_EXPECTED_CALIBRATION_ERROR,
    MIN_CALIBRATION_BINS,
    MIN_CALIBRATION_BIN_SIZE,
    MIN_FORM_MATCHES,
    MIN_VALIDATION_MATCHES,
    MIN_VENUE_MATCHES,
    MarketCalibration,
    ValidationMetrics,
    _calibration_diagnostics,
    _credible_validation,
    _fit_calibration_map,
    _fixture_market_outcome,
    adaptive_bin_threshold,
    fixture_market_probabilities,
)


TRANSFER_DATASET_SCHEMA_VERSION = 1
TRANSFER_ARTIFACT_SCHEMA_VERSION = 1
TRANSFER_ARTIFACT_KIND = "uefa_transfer_shadow_backtest"
SUPPORTED_COMPETITION_IDS = frozenset({2, 3, 848})
SUPPORTED_COHORTS = frozenset({"qualification", "main"})
MIN_TRANSFER_COMPETITION_OBSERVATIONS = MIN_VALIDATION_MATCHES
_TEAM_FORM_HISTORY_LIMIT = 6
_TEAM_VENUE_HISTORY_LIMIT = 12
_MODEL_SIGNATURE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+-]{7,199}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_ALLOWED_STATS = frozenset(
    {
        "xg_home",
        "xg_away",
        "corners_home",
        "corners_away",
        "yellow_cards_home",
        "yellow_cards_away",
    }
)


class TransferBacktestError(ValueError):
    """Raised when replay data or artifact provenance is not trustworthy."""


@dataclass(frozen=True)
class TransferReplayFixture:
    """One historical UEFA target plus its replayable pre-match inputs."""

    fixture: dict[str, Any]
    competition_history: tuple[dict[str, Any], ...]
    home_team_history: tuple[dict[str, Any], ...]
    away_team_history: tuple[dict[str, Any], ...]
    competition_id: int
    cohort: str
    source_league_ids: tuple[int, int]

    @classmethod
    def from_dict(cls, raw: object) -> "TransferReplayFixture":
        if not isinstance(raw, dict):
            raise TransferBacktestError("each replay must be an object")
        expected = {
            "fixture",
            "competition_history",
            "home_team_history",
            "away_team_history",
            "competition_id",
            "cohort",
            "source_league_ids",
        }
        if set(raw) != expected:
            raise TransferBacktestError("replay fields do not match schema version 1")
        source_ids = raw.get("source_league_ids")
        if not isinstance(source_ids, (list, tuple)) or len(source_ids) != 2:
            raise TransferBacktestError("source_league_ids must contain two IDs")
        histories = []
        for name in (
            "competition_history",
            "home_team_history",
            "away_team_history",
        ):
            value = raw.get(name)
            if not isinstance(value, list):
                raise TransferBacktestError(f"{name} must be a list")
            histories.append(tuple(value))
        return cls(
            fixture=raw.get("fixture"),
            competition_history=histories[0],
            home_team_history=histories[1],
            away_team_history=histories[2],
            competition_id=raw.get("competition_id"),
            cohort=raw.get("cohort"),
            source_league_ids=tuple(source_ids),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture": self.fixture,
            "competition_history": list(self.competition_history),
            "home_team_history": list(self.home_team_history),
            "away_team_history": list(self.away_team_history),
            "competition_id": self.competition_id,
            "cohort": self.cohort,
            "source_league_ids": list(self.source_league_ids),
        }


@dataclass(frozen=True)
class TransferPrediction:
    fixture_id: int
    kickoff: str
    competition_id: int
    cohort: str
    source_league_ids: tuple[int, int]
    market_key: str
    raw_probability: float
    probability: float
    baseline_probability: float
    outcome: int


@dataclass(frozen=True)
class TransferMarketResult:
    validation: ValidationMetrics
    calibration: Optional[MarketCalibration]
    competition_observations: tuple[tuple[int, int], ...]
    validated: bool


@dataclass(frozen=True)
class TransferBacktestResult:
    predictions: tuple[TransferPrediction, ...]
    markets: dict[str, TransferMarketResult]
    modeled_fixture_ids: tuple[int, ...]


@dataclass(frozen=True)
class TransferScopeProvenance:
    competition_id: int
    cohort: str
    home_source_league_id: int
    away_source_league_id: int
    replay_count: int
    modeled_replay_count: int
    home_form_observations: int
    away_form_observations: int
    home_venue_observations: int
    away_venue_observations: int


@dataclass(frozen=True)
class TransferArtifactProvenance:
    model_signature: str
    dataset_hash: str
    competition_ids: tuple[int, ...]
    cohort: str
    training_start: str
    training_end: str
    training_cutoff: str
    replay_count: int
    modeled_replay_count: int
    scope_observations: tuple[TransferScopeProvenance, ...]
    market_keys: tuple[str, ...]


@dataclass(frozen=True)
class TransferBacktestArtifact:
    artifact_id: str
    provenance: TransferArtifactProvenance
    markets: dict[str, TransferMarketResult]
    release_authorized: bool = False

    @property
    def validated_market_keys(self) -> tuple[str, ...]:
        return tuple(
            sorted(key for key, value in self.markets.items() if value.validated)
        )


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TransferBacktestError(f"{label} must be a positive integer")
    return value


def _finite_number(
    value: object,
    label: str,
    *,
    minimum: float = 0.0,
    maximum: Optional[float] = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransferBacktestError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise TransferBacktestError(f"{label} is outside its allowed range")
    if maximum is not None and number > maximum:
        raise TransferBacktestError(f"{label} is outside its allowed range")
    return number


def _aware_datetime(value: object, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise TransferBacktestError(f"{label} is not an ISO datetime") from exc
    else:
        raise TransferBacktestError(f"{label} is not an ISO datetime")
    if parsed.tzinfo is None:
        raise TransferBacktestError(f"{label} must contain a timezone")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise TransferBacktestError("datetime must contain a timezone")
    return value.astimezone(timezone.utc).isoformat()


def _cohort_from_round(value: object) -> str:
    """Map an API-Football UEFA round to one conservative release cohort."""

    if not isinstance(value, str) or not value.strip():
        raise TransferBacktestError("fixture round is missing")
    normalised = re.sub(r"[\s_-]+", " ", value.strip().casefold())
    if "qualif" in normalised or "preliminary" in normalised:
        return "qualification"
    if any(
        marker in normalised
        for marker in (
            "league stage",
            "group",
            "round of",
            "knockout",
            "quarter final",
            "quarterfinal",
            "semi final",
            "semifinal",
        )
    ) or normalised in {"final", "finals"}:
        return "main"
    raise TransferBacktestError("fixture round cannot be mapped to a UEFA cohort")


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise TransferBacktestError("document is not canonical JSON") from exc


def _sha256_document(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalise_fixture(
    raw: object,
    *,
    expected_league_id: int,
    label: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TransferBacktestError(f"{label} must be an object")
    fixture = raw.get("fixture")
    league = raw.get("league")
    teams = raw.get("teams")
    goals = raw.get("goals")
    if not all(isinstance(value, dict) for value in (fixture, league, teams, goals)):
        raise TransferBacktestError(f"{label} is missing fixture result fields")

    fixture_id = _positive_integer(fixture.get("id"), f"{label}.fixture.id")
    kickoff = _aware_datetime(fixture.get("date"), f"{label}.fixture.date")
    league_id = _positive_integer(league.get("id"), f"{label}.league.id")
    if league_id != expected_league_id:
        raise TransferBacktestError(f"{label} has the wrong league provenance")
    season = _positive_integer(league.get("season"), f"{label}.league.season")

    normalised_teams: dict[str, dict[str, Any]] = {}
    for side in ("home", "away"):
        team = teams.get(side)
        if not isinstance(team, dict):
            raise TransferBacktestError(f"{label}.teams.{side} is missing")
        team_id = _positive_integer(team.get("id"), f"{label}.teams.{side}.id")
        normalised_teams[side] = {
            "id": team_id,
            "name": str(team.get("name") or f"Team {team_id}").strip(),
        }
    if normalised_teams["home"]["id"] == normalised_teams["away"]["id"]:
        raise TransferBacktestError(f"{label} has identical teams")

    normalised_goals = {}
    for side in ("home", "away"):
        value = goals.get(side)
        number = _finite_number(value, f"{label}.goals.{side}", maximum=30.0)
        if not number.is_integer():
            raise TransferBacktestError(f"{label}.goals.{side} must be an integer")
        normalised_goals[side] = int(number)

    normalised: dict[str, Any] = {
        "fixture": {
            "id": fixture_id,
            "date": _iso_utc(kickoff),
            "referee": (
                str(fixture.get("referee")).strip()
                if fixture.get("referee") is not None
                else None
            ),
        },
        "league": {
            "id": league_id,
            "season": season,
            "round": str(league.get("round") or "").strip(),
        },
        "teams": normalised_teams,
        "goals": normalised_goals,
    }
    stats = raw.get("challenge_stats")
    if stats is not None:
        if not isinstance(stats, dict):
            raise TransferBacktestError(f"{label}.challenge_stats must be an object")
        clean_stats: dict[str, Any] = {}
        for key in sorted(_ALLOWED_STATS):
            if key not in stats or stats.get(key) is None:
                continue
            maximum = 12.0 if key.startswith("xg_") else (
                40.0 if key.startswith("corners_") else 20.0
            )
            number = _finite_number(
                stats.get(key),
                f"{label}.challenge_stats.{key}",
                maximum=maximum,
            )
            if not key.startswith("xg_"):
                if not number.is_integer():
                    raise TransferBacktestError(
                        f"{label}.challenge_stats.{key} must be an integer"
                    )
                clean_stats[key] = int(number)
            else:
                clean_stats[key] = number
        if clean_stats:
            normalised["challenge_stats"] = clean_stats
    return normalised


def _normalise_history(
    raw: Iterable[object],
    *,
    expected_league_id: int,
    label: str,
) -> tuple[dict[str, Any], ...]:
    if isinstance(raw, (str, bytes, dict)):
        raise TransferBacktestError(f"{label} must be a fixture sequence")
    by_id: dict[int, dict[str, Any]] = {}
    for index, item in enumerate(raw):
        fixture = _normalise_fixture(
            item,
            expected_league_id=expected_league_id,
            label=f"{label}[{index}]",
        )
        fixture_id = fixture["fixture"]["id"]
        previous = by_id.get(fixture_id)
        if previous is not None and previous != fixture:
            raise TransferBacktestError(f"{label} contains a conflicting fixture ID")
        by_id[fixture_id] = fixture
    return tuple(
        sorted(
            by_id.values(),
            key=lambda item: (item["fixture"]["date"], item["fixture"]["id"]),
        )
    )


def _team_history_counts(
    history: tuple[dict[str, Any], ...],
    *,
    team_id: int,
    target_day: datetime,
    required_venue: str,
    label: str,
) -> tuple[int, int]:
    admissible: list[dict[str, Any]] = []
    for item in history:
        home_id = item["teams"]["home"]["id"]
        away_id = item["teams"]["away"]["id"]
        if team_id not in {home_id, away_id}:
            raise TransferBacktestError(f"{label} contains a wrong-team fixture")
        if _fixture_datetime(item) < target_day:
            admissible.append(item)
    form_count = min(len(admissible), _TEAM_FORM_HISTORY_LIMIT)
    venue_count = min(
        sum(
            1
            for item in admissible
            if item["teams"][required_venue]["id"] == team_id
        ),
        _TEAM_VENUE_HISTORY_LIMIT,
    )
    if form_count < MIN_FORM_MATCHES or venue_count < MIN_VENUE_MATCHES:
        raise TransferBacktestError(
            f"{label} lacks usable pre-target-day form/venue history"
        )
    return form_count, venue_count


def _replay_history_counts(
    replay: TransferReplayFixture,
) -> tuple[int, int, int, int]:
    target_day = _day_start(_fixture_datetime(replay.fixture))
    home_id = replay.fixture["teams"]["home"]["id"]
    away_id = replay.fixture["teams"]["away"]["id"]
    home_form, home_venue = _team_history_counts(
        replay.home_team_history,
        team_id=home_id,
        target_day=target_day,
        required_venue="home",
        label="home_team_history",
    )
    away_form, away_venue = _team_history_counts(
        replay.away_team_history,
        team_id=away_id,
        target_day=target_day,
        required_venue="away",
        label="away_team_history",
    )
    return home_form, away_form, home_venue, away_venue


def _normalise_replay(replay: TransferReplayFixture) -> TransferReplayFixture:
    if not isinstance(replay, TransferReplayFixture):
        raise TransferBacktestError("replays must contain TransferReplayFixture objects")
    competition_id = _positive_integer(replay.competition_id, "competition_id")
    if competition_id not in SUPPORTED_COMPETITION_IDS:
        raise TransferBacktestError("competition_id is not a supported UEFA competition")
    cohort = str(replay.cohort or "").strip().casefold()
    if cohort not in SUPPORTED_COHORTS:
        raise TransferBacktestError("cohort must be qualification or main")
    if not isinstance(replay.source_league_ids, tuple) or len(replay.source_league_ids) != 2:
        raise TransferBacktestError("source_league_ids must be a pair")
    source_ids = tuple(
        _positive_integer(value, "source_league_id")
        for value in replay.source_league_ids
    )
    if any(value in SUPPORTED_COMPETITION_IDS for value in source_ids):
        raise TransferBacktestError("source leagues must be domestic competitions")

    fixture = _normalise_fixture(
        replay.fixture,
        expected_league_id=competition_id,
        label="fixture",
    )
    fixture_cohort = _cohort_from_round(fixture["league"]["round"])
    if cohort != fixture_cohort:
        raise TransferBacktestError("cohort does not match fixture round")
    competition_history = _normalise_history(
        replay.competition_history,
        expected_league_id=competition_id,
        label="competition_history",
    )
    home_history = _normalise_history(
        replay.home_team_history,
        expected_league_id=source_ids[0],
        label="home_team_history",
    )
    away_history = _normalise_history(
        replay.away_team_history,
        expected_league_id=source_ids[1],
        label="away_team_history",
    )
    normalised = TransferReplayFixture(
        fixture=fixture,
        competition_history=competition_history,
        home_team_history=home_history,
        away_team_history=away_history,
        competition_id=competition_id,
        cohort=cohort,
        source_league_ids=source_ids,
    )
    _replay_history_counts(normalised)
    return normalised


def _normalise_replays(
    replays: Iterable[TransferReplayFixture],
) -> tuple[TransferReplayFixture, ...]:
    if isinstance(replays, (str, bytes, dict)):
        raise TransferBacktestError("replays must be a sequence")
    normalised = [_normalise_replay(replay) for replay in replays]
    normalised.sort(
        key=lambda replay: (
            replay.fixture["fixture"]["date"],
            replay.competition_id,
            replay.fixture["fixture"]["id"],
        )
    )
    seen: set[tuple[int, int]] = set()
    for replay in normalised:
        key = (replay.competition_id, replay.fixture["fixture"]["id"])
        if key in seen:
            raise TransferBacktestError("target fixtures must be unique")
        seen.add(key)
    return tuple(normalised)


def dataset_hash(replays: Iterable[TransferReplayFixture]) -> str:
    """Return a deterministic hash over the odds-blind replay payload."""

    normalised = _normalise_replays(replays)
    document = {
        "schema_version": TRANSFER_DATASET_SCHEMA_VERSION,
        "replays": [replay.to_dict() for replay in normalised],
    }
    return _sha256_document(document)


def _fixture_datetime(fixture: Mapping[str, Any]) -> datetime:
    return _aware_datetime(fixture["fixture"]["date"], "fixture date")


def _day_start(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _admissible_history(
    history: Iterable[dict[str, Any]],
    day: datetime,
) -> list[dict[str, Any]]:
    """Exclude the target day itself, not merely results after kickoff."""

    return [item for item in history if _fixture_datetime(item) < day]


def _combined_team_history(
    replay: TransferReplayFixture,
    day: datetime,
) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    for item in (
        *_admissible_history(replay.home_team_history, day),
        *_admissible_history(replay.away_team_history, day),
    ):
        fixture_id = item["fixture"]["id"]
        previous = by_id.get(fixture_id)
        if previous is not None and previous != item:
            raise TransferBacktestError("team histories conflict on a fixture ID")
        by_id[fixture_id] = item
    return sorted(
        by_id.values(),
        key=lambda item: (item["fixture"]["date"], item["fixture"]["id"]),
    )


def _market_keys(values: Optional[Iterable[str]]) -> tuple[str, ...]:
    if values is None:
        return tuple(sorted(MARKET_BY_KEY))
    if isinstance(values, (str, bytes, dict)):
        raise TransferBacktestError("market_keys must be a sequence")
    keys = tuple(sorted({str(value).strip() for value in values if str(value).strip()}))
    if not keys or any(key not in MARKET_BY_KEY for key in keys):
        raise TransferBacktestError("market_keys contains an unsupported market")
    return keys


def _validation_metrics(records: Sequence[TransferPrediction]) -> ValidationMetrics:
    observations = len(records)
    if observations == 0:
        return ValidationMetrics(0, None, None, None, None, False)
    probabilities = [record.probability for record in records]
    raw_probabilities = [record.raw_probability for record in records]
    outcomes = [record.outcome for record in records]
    baselines = [record.baseline_probability for record in records]
    brier = fmean((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes))
    raw_brier = fmean((probability - outcome) ** 2 for probability, outcome in zip(raw_probabilities, outcomes))
    baseline_brier = fmean((probability - outcome) ** 2 for probability, outcome in zip(baselines, outcomes))
    improvement = (
        (baseline_brier - brier) / baseline_brier
        if baseline_brier > 0.0
        else None
    )
    (
        ece,
        calibration_bins,
        min_bin_size,
        max_calibration_error,
        max_error_bin_size,
        max_error_bin_mean,
    ) = _calibration_diagnostics(probabilities, outcomes)
    bin_threshold = adaptive_bin_threshold(max_error_bin_mean, max_error_bin_size)
    passed = bool(
        observations >= MIN_VALIDATION_MATCHES
        and improvement is not None
        and improvement >= 0.02
        and ece <= MAX_EXPECTED_CALIBRATION_ERROR
        and calibration_bins >= MIN_CALIBRATION_BINS
        and min_bin_size >= MIN_CALIBRATION_BIN_SIZE
        and max_calibration_error is not None
        and max_calibration_error <= bin_threshold
    )
    return ValidationMetrics(
        observations=observations,
        brier_score=round(brier, 6),
        baseline_brier_score=round(baseline_brier, 6),
        relative_improvement=(
            round(improvement, 6) if improvement is not None else None
        ),
        expected_calibration_error=round(ece, 6),
        passed=passed,
        calibration_bins=calibration_bins,
        min_bin_size=min_bin_size,
        max_calibration_error=(
            round(max_calibration_error, 6)
            if max_calibration_error is not None
            else None
        ),
        max_error_bin_size=max_error_bin_size,
        max_error_bin_mean_probability=(
            round(max_error_bin_mean, 6)
            if max_error_bin_mean is not None
            else None
        ),
        raw_brier_score=round(raw_brier, 6),
    )


def _run_normalised(
    replays: tuple[TransferReplayFixture, ...],
    keys: tuple[str, ...],
) -> TransferBacktestResult:
    grouped: dict[datetime, list[TransferReplayFixture]] = defaultdict(list)
    for replay in replays:
        grouped[_day_start(_fixture_datetime(replay.fixture))].append(replay)

    successes = {key: 0 for key in keys}
    totals = {key: 0 for key in keys}
    calibration_state: dict[str, dict[str, Any]] = {
        key: {"raw": [], "outcomes": [], "map": None, "count": 0}
        for key in keys
    }
    predictions: list[TransferPrediction] = []
    modeled_fixture_ids: set[int] = set()

    for day in sorted(grouped):
        day_replays = sorted(
            grouped[day],
            key=lambda replay: (
                replay.competition_id,
                replay.fixture["fixture"]["id"],
            ),
        )
        day_predictions: list[TransferPrediction] = []
        for replay in day_replays:
            competition_history = _admissible_history(
                replay.competition_history,
                day,
            )
            team_history = _combined_team_history(replay, day)
            prediction = fixture_market_probabilities(
                replay.fixture,
                competition_history,
                calibration=None,
                team_history=team_history,
            )
            if prediction is None:
                continue
            fixture_modeled = False
            for key in keys:
                values = prediction.get("probabilities", {}).get(key)
                outcome_value = _fixture_market_outcome(
                    MARKET_BY_KEY[key],
                    replay.fixture,
                )
                if values is None or outcome_value is None:
                    continue
                raw_probability = float(values[0])
                if not math.isfinite(raw_probability) or not 0.0 <= raw_probability <= 1.0:
                    continue
                curve = calibration_state[key]["map"]
                probability = (
                    float(curve(raw_probability))
                    if isinstance(curve, MarketCalibration)
                    else raw_probability
                )
                baseline = (successes[key] + 1.0) / (totals[key] + 2.0)
                day_predictions.append(
                    TransferPrediction(
                        fixture_id=replay.fixture["fixture"]["id"],
                        kickoff=replay.fixture["fixture"]["date"],
                        competition_id=replay.competition_id,
                        cohort=replay.cohort,
                        source_league_ids=replay.source_league_ids,
                        market_key=key,
                        raw_probability=raw_probability,
                        probability=probability,
                        baseline_probability=baseline,
                        outcome=int(outcome_value),
                    )
                )
                fixture_modeled = True
            if fixture_modeled:
                modeled_fixture_ids.add(replay.fixture["fixture"]["id"])

        # Outcomes from the entire day become visible only after every replay
        # on that day has been predicted.
        for replay in day_replays:
            for key in keys:
                outcome_value = _fixture_market_outcome(
                    MARKET_BY_KEY[key],
                    replay.fixture,
                )
                if outcome_value is not None:
                    successes[key] += int(outcome_value)
                    totals[key] += 1
        predictions.extend(day_predictions)
        for record in day_predictions:
            state = calibration_state[record.market_key]
            state["raw"].append(record.raw_probability)
            state["outcomes"].append(record.outcome)
        for key in keys:
            state = calibration_state[key]
            if len(state["raw"]) - int(state["count"]) < CALIBRATION_REFIT_NEW_SAMPLES:
                continue
            curve = _fit_calibration_map(state["raw"], state["outcomes"])
            if curve is not None:
                state["map"] = curve
                state["count"] = len(state["raw"])

    market_results: dict[str, TransferMarketResult] = {}
    replay_competitions = {replay.competition_id for replay in replays}
    for key in keys:
        records = [record for record in predictions if record.market_key == key]
        validation = _validation_metrics(records)
        calibration = _fit_calibration_map(
            [record.raw_probability for record in records],
            [record.outcome for record in records],
        )
        counts: dict[int, int] = defaultdict(int)
        for record in records:
            counts[record.competition_id] += 1
        validated = bool(
            validation.observations >= MIN_VALIDATION_MATCHES
            and _credible_validation(validation)
            and set(counts) == replay_competitions
            and all(
                count >= MIN_TRANSFER_COMPETITION_OBSERVATIONS
                for count in counts.values()
            )
        )
        market_results[key] = TransferMarketResult(
            validation=validation,
            calibration=calibration,
            competition_observations=tuple(sorted(counts.items())),
            validated=validated,
        )
    return TransferBacktestResult(
        predictions=tuple(predictions),
        markets=market_results,
        modeled_fixture_ids=tuple(sorted(modeled_fixture_ids)),
    )


def run_transfer_backtest(
    replays: Iterable[TransferReplayFixture],
    *,
    market_keys: Optional[Iterable[str]] = None,
) -> TransferBacktestResult:
    """Run a chronological, same-day-isolated transfer replay."""

    normalised = _normalise_replays(replays)
    return _run_normalised(normalised, _market_keys(market_keys))


def _market_document(result: TransferMarketResult) -> dict[str, Any]:
    calibration = (
        {
            "points": [list(point) for point in result.calibration.points],
            "samples": result.calibration.samples,
        }
        if result.calibration is not None
        else None
    )
    return {
        "validation": asdict(result.validation),
        "calibration": calibration,
        "competition_observations": {
            str(key): value for key, value in result.competition_observations
        },
        "validated": result.validated,
    }


def build_transfer_artifact(
    replays: Iterable[TransferReplayFixture],
    *,
    model_signature: str,
    competition_ids: Iterable[int],
    cohort: str,
    training_cutoff: datetime,
    market_keys: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    """Build a deterministic shadow artifact; never authorize production use."""

    if not isinstance(model_signature, str) or not _MODEL_SIGNATURE_PATTERN.fullmatch(
        model_signature
    ):
        raise TransferBacktestError("model_signature is invalid")
    if isinstance(competition_ids, (str, bytes, dict)):
        raise TransferBacktestError("competition_ids must be a sequence")
    competitions = tuple(
        sorted({_positive_integer(value, "competition_id") for value in competition_ids})
    )
    if not competitions or any(
        value not in SUPPORTED_COMPETITION_IDS for value in competitions
    ):
        raise TransferBacktestError("competition_ids contains an unsupported competition")
    normalised_cohort = str(cohort or "").strip().casefold()
    if normalised_cohort not in SUPPORTED_COHORTS:
        raise TransferBacktestError("cohort must be qualification or main")
    cutoff = _aware_datetime(training_cutoff, "training_cutoff")
    keys = _market_keys(market_keys)

    selected = tuple(
        replay
        for replay in _normalise_replays(replays)
        if replay.competition_id in competitions
        and replay.cohort == normalised_cohort
        and _fixture_datetime(replay.fixture) <= cutoff
    )
    if not selected:
        raise TransferBacktestError("no replay matches the requested artifact scope")
    if {replay.competition_id for replay in selected} != set(competitions):
        raise TransferBacktestError(
            "every declared competition must contain an in-scope replay"
        )
    starts = [_fixture_datetime(replay.fixture) for replay in selected]
    result = _run_normalised(selected, keys)
    data_hash = _sha256_document(
        {
            "schema_version": TRANSFER_DATASET_SCHEMA_VERSION,
            "replays": [replay.to_dict() for replay in selected],
        }
    )
    modeled_targets = {
        (prediction.competition_id, prediction.fixture_id)
        for prediction in result.predictions
    }
    scope_totals: dict[tuple[int, str, int, int], dict[str, int]] = {}
    for replay in selected:
        scope_key = (
            replay.competition_id,
            replay.cohort,
            replay.source_league_ids[0],
            replay.source_league_ids[1],
        )
        totals = scope_totals.setdefault(
            scope_key,
            {
                "replay_count": 0,
                "modeled_replay_count": 0,
                "home_form_observations": 0,
                "away_form_observations": 0,
                "home_venue_observations": 0,
                "away_venue_observations": 0,
            },
        )
        home_form, away_form, home_venue, away_venue = _replay_history_counts(
            replay
        )
        totals["replay_count"] += 1
        totals["modeled_replay_count"] += int(
            (replay.competition_id, replay.fixture["fixture"]["id"])
            in modeled_targets
        )
        totals["home_form_observations"] += home_form
        totals["away_form_observations"] += away_form
        totals["home_venue_observations"] += home_venue
        totals["away_venue_observations"] += away_venue
    scope_observations = tuple(
        TransferScopeProvenance(
            competition_id=scope_key[0],
            cohort=scope_key[1],
            home_source_league_id=scope_key[2],
            away_source_league_id=scope_key[3],
            **scope_totals[scope_key],
        )
        for scope_key in sorted(scope_totals)
    )
    modeled_replay_count = sum(
        scope.modeled_replay_count for scope in scope_observations
    )
    provenance = TransferArtifactProvenance(
        model_signature=model_signature,
        dataset_hash=data_hash,
        competition_ids=competitions,
        cohort=normalised_cohort,
        training_start=_iso_utc(min(starts)),
        training_end=_iso_utc(max(starts)),
        training_cutoff=_iso_utc(cutoff),
        replay_count=len(selected),
        modeled_replay_count=modeled_replay_count,
        scope_observations=scope_observations,
        market_keys=keys,
    )
    body = {
        "schema_version": TRANSFER_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": TRANSFER_ARTIFACT_KIND,
        "release_authorized": False,
        "provenance": {
            **asdict(provenance),
            "competition_ids": list(provenance.competition_ids),
            "scope_observations": [
                asdict(scope) for scope in provenance.scope_observations
            ],
            "market_keys": list(provenance.market_keys),
        },
        "markets": {
            key: _market_document(result.markets[key])
            for key in keys
        },
    }
    return {**body, "artifact_id": _sha256_document(body)}


def _parse_validation(raw: object) -> ValidationMetrics:
    if not isinstance(raw, dict) or set(raw) != set(
        asdict(ValidationMetrics(0, None, None, None, None, False))
    ):
        raise TransferBacktestError("validation payload does not match its schema")
    try:
        metric = ValidationMetrics(**raw)
    except TypeError as exc:
        raise TransferBacktestError("validation payload is invalid") from exc
    for value in (
        metric.observations,
        metric.calibration_bins,
        metric.min_bin_size,
        metric.max_error_bin_size,
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TransferBacktestError("validation count is invalid")
    if metric.passed is not True and metric.passed is not False:
        raise TransferBacktestError("validation passed flag must be boolean")
    bounded = (
        (metric.brier_score, "brier_score"),
        (metric.baseline_brier_score, "baseline_brier_score"),
        (metric.expected_calibration_error, "expected_calibration_error"),
        (metric.max_calibration_error, "max_calibration_error"),
        (metric.max_error_bin_mean_probability, "max_error_bin_mean_probability"),
        (metric.raw_brier_score, "raw_brier_score"),
    )
    for value, label in bounded:
        if value is not None:
            _finite_number(value, f"validation {label}", maximum=1.0)
    if metric.relative_improvement is not None:
        value = metric.relative_improvement
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) > 1.0
        ):
            raise TransferBacktestError("validation relative_improvement is invalid")
    return metric


def _parse_calibration(raw: object, observations: int) -> Optional[MarketCalibration]:
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {"points", "samples"}:
        raise TransferBacktestError("calibration payload does not match its schema")
    samples = raw.get("samples")
    if isinstance(samples, bool) or not isinstance(samples, int) or samples != observations:
        raise TransferBacktestError("calibration sample count is inconsistent")
    points_raw = raw.get("points")
    if not isinstance(points_raw, list) or len(points_raw) < 2:
        raise TransferBacktestError("calibration requires at least two points")
    points: list[tuple[float, float]] = []
    for point in points_raw:
        if not isinstance(point, list) or len(point) != 2:
            raise TransferBacktestError("calibration point is invalid")
        x = _finite_number(point[0], "calibration x", maximum=1.0)
        y = _finite_number(point[1], "calibration y", maximum=1.0)
        if points and (x <= points[-1][0] or y < points[-1][1]):
            raise TransferBacktestError("calibration points must be monotone")
        points.append((x, y))
    return MarketCalibration(points=tuple(points), samples=samples)


def verify_transfer_artifact(
    document: object,
    *,
    expected_model_signature: str,
    expected_competition_id: int,
    expected_cohort: str,
    fixture_round: str,
    expected_source_league_ids: tuple[int, int],
    fixture_kickoff: datetime,
    expected_dataset_hash: str,
    expected_artifact_id: str,
) -> TransferBacktestArtifact:
    """Verify a shadow artifact without granting any release permission."""

    if not isinstance(document, dict):
        raise TransferBacktestError("artifact must be an object")
    expected_top = {
        "schema_version",
        "artifact_kind",
        "release_authorized",
        "provenance",
        "markets",
        "artifact_id",
    }
    if set(document) != expected_top:
        raise TransferBacktestError("artifact fields do not match schema version 1")
    if document.get("schema_version") != TRANSFER_ARTIFACT_SCHEMA_VERSION:
        raise TransferBacktestError("artifact schema version is unsupported")
    if document.get("artifact_kind") != TRANSFER_ARTIFACT_KIND:
        raise TransferBacktestError("artifact kind is invalid")
    if document.get("release_authorized") is not False:
        raise TransferBacktestError("this artifact contract is shadow-only")
    artifact_id = document.get("artifact_id")
    if not isinstance(artifact_id, str) or not _SHA256_PATTERN.fullmatch(artifact_id):
        raise TransferBacktestError("artifact_id is invalid")
    body = {key: value for key, value in document.items() if key != "artifact_id"}
    if _sha256_document(body) != artifact_id:
        raise TransferBacktestError("artifact hash does not match its content")
    if (
        not isinstance(expected_artifact_id, str)
        or not _SHA256_PATTERN.fullmatch(expected_artifact_id)
        or artifact_id != expected_artifact_id
    ):
        raise TransferBacktestError("artifact_id does not match the registered artifact")

    raw_provenance = document.get("provenance")
    provenance_fields = {
        "model_signature",
        "dataset_hash",
        "competition_ids",
        "cohort",
        "training_start",
        "training_end",
        "training_cutoff",
        "replay_count",
        "modeled_replay_count",
        "scope_observations",
        "market_keys",
    }
    if not isinstance(raw_provenance, dict) or set(raw_provenance) != provenance_fields:
        raise TransferBacktestError("artifact provenance does not match its schema")
    model_signature = raw_provenance.get("model_signature")
    if (
        not isinstance(expected_model_signature, str)
        or not _MODEL_SIGNATURE_PATTERN.fullmatch(expected_model_signature)
        or model_signature != expected_model_signature
    ):
        raise TransferBacktestError("model signature does not match")
    data_hash = raw_provenance.get("dataset_hash")
    if not isinstance(data_hash, str) or not _SHA256_PATTERN.fullmatch(data_hash):
        raise TransferBacktestError("dataset hash is invalid")
    if (
        not isinstance(expected_dataset_hash, str)
        or not _SHA256_PATTERN.fullmatch(expected_dataset_hash)
        or data_hash != expected_dataset_hash
    ):
        raise TransferBacktestError("dataset hash does not match")
    competitions_raw = raw_provenance.get("competition_ids")
    if not isinstance(competitions_raw, list) or not competitions_raw:
        raise TransferBacktestError("competition provenance is invalid")
    competitions = tuple(
        _positive_integer(value, "competition_id") for value in competitions_raw
    )
    if competitions != tuple(sorted(set(competitions))) or any(
        value not in SUPPORTED_COMPETITION_IDS for value in competitions
    ):
        raise TransferBacktestError("competition provenance is invalid")
    expected_competition = _positive_integer(
        expected_competition_id,
        "expected_competition_id",
    )
    if expected_competition not in competitions:
        raise TransferBacktestError("artifact does not cover the fixture competition")
    cohort = raw_provenance.get("cohort")
    fixture_cohort = _cohort_from_round(fixture_round)
    if (
        cohort != str(expected_cohort or "").strip().casefold()
        or cohort != fixture_cohort
        or cohort not in SUPPORTED_COHORTS
    ):
        raise TransferBacktestError("cohort does not match")
    start = _aware_datetime(raw_provenance.get("training_start"), "training_start")
    end = _aware_datetime(raw_provenance.get("training_end"), "training_end")
    cutoff = _aware_datetime(raw_provenance.get("training_cutoff"), "training_cutoff")
    kickoff = _aware_datetime(fixture_kickoff, "fixture_kickoff")
    if not start <= end <= cutoff:
        raise TransferBacktestError("training dates are inconsistent")
    if cutoff >= _day_start(kickoff):
        raise TransferBacktestError("artifact cutoff is not before the fixture UTC day")

    replay_count = raw_provenance.get("replay_count")
    modeled_count = raw_provenance.get("modeled_replay_count")
    if (
        isinstance(replay_count, bool)
        or not isinstance(replay_count, int)
        or replay_count < 1
        or isinstance(modeled_count, bool)
        or not isinstance(modeled_count, int)
        or not 0 <= modeled_count <= replay_count
    ):
        raise TransferBacktestError("replay counts are invalid")
    if (
        not isinstance(expected_source_league_ids, (tuple, list))
        or len(expected_source_league_ids) != 2
    ):
        raise TransferBacktestError("expected source leagues must be a pair")
    expected_source_pair = tuple(
        _positive_integer(value, "expected_source_league_id")
        for value in expected_source_league_ids
    )
    if any(value in SUPPORTED_COMPETITION_IDS for value in expected_source_pair):
        raise TransferBacktestError("artifact does not cover the fixture source leagues")
    scopes_raw = raw_provenance.get("scope_observations")
    scope_fields = {
        "competition_id",
        "cohort",
        "home_source_league_id",
        "away_source_league_id",
        "replay_count",
        "modeled_replay_count",
        "home_form_observations",
        "away_form_observations",
        "home_venue_observations",
        "away_venue_observations",
    }
    if not isinstance(scopes_raw, list) or not scopes_raw:
        raise TransferBacktestError("scope provenance is invalid")
    scopes: list[TransferScopeProvenance] = []
    scope_keys: list[tuple[int, str, int, int]] = []
    for scope_raw in scopes_raw:
        if not isinstance(scope_raw, dict) or set(scope_raw) != scope_fields:
            raise TransferBacktestError("scope provenance is invalid")
        scope_competition = _positive_integer(
            scope_raw.get("competition_id"),
            "scope competition_id",
        )
        scope_cohort = scope_raw.get("cohort")
        home_source = _positive_integer(
            scope_raw.get("home_source_league_id"),
            "scope home_source_league_id",
        )
        away_source = _positive_integer(
            scope_raw.get("away_source_league_id"),
            "scope away_source_league_id",
        )
        if (
            scope_competition not in competitions
            or scope_cohort != cohort
            or home_source in SUPPORTED_COMPETITION_IDS
            or away_source in SUPPORTED_COMPETITION_IDS
        ):
            raise TransferBacktestError("scope provenance is invalid")
        count_names = (
            "replay_count",
            "modeled_replay_count",
            "home_form_observations",
            "away_form_observations",
            "home_venue_observations",
            "away_venue_observations",
        )
        counts = {name: scope_raw.get(name) for name in count_names}
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in counts.values()
        ):
            raise TransferBacktestError("scope observation counts are invalid")
        scope_replays = counts["replay_count"]
        if (
            scope_replays < 1
            or counts["modeled_replay_count"] > scope_replays
            or not MIN_FORM_MATCHES * scope_replays
            <= counts["home_form_observations"]
            <= _TEAM_FORM_HISTORY_LIMIT * scope_replays
            or not MIN_FORM_MATCHES * scope_replays
            <= counts["away_form_observations"]
            <= _TEAM_FORM_HISTORY_LIMIT * scope_replays
            or not MIN_VENUE_MATCHES * scope_replays
            <= counts["home_venue_observations"]
            <= _TEAM_VENUE_HISTORY_LIMIT * scope_replays
            or not MIN_VENUE_MATCHES * scope_replays
            <= counts["away_venue_observations"]
            <= _TEAM_VENUE_HISTORY_LIMIT * scope_replays
        ):
            raise TransferBacktestError("scope observation counts are inconsistent")
        scope = TransferScopeProvenance(
            competition_id=scope_competition,
            cohort=scope_cohort,
            home_source_league_id=home_source,
            away_source_league_id=away_source,
            **counts,
        )
        scopes.append(scope)
        scope_keys.append(
            (scope_competition, scope_cohort, home_source, away_source)
        )
    if (
        scope_keys != sorted(set(scope_keys))
        or {scope.competition_id for scope in scopes} != set(competitions)
        or sum(scope.replay_count for scope in scopes) != replay_count
        or sum(scope.modeled_replay_count for scope in scopes) != modeled_count
    ):
        raise TransferBacktestError("scope provenance is inconsistent")
    expected_scope = (
        expected_competition,
        cohort,
        expected_source_pair[0],
        expected_source_pair[1],
    )
    if expected_scope not in scope_keys:
        raise TransferBacktestError("artifact does not cover the exact fixture scope")
    keys_raw = raw_provenance.get("market_keys")
    if not isinstance(keys_raw, list):
        raise TransferBacktestError("market provenance is invalid")
    keys = tuple(keys_raw)
    if keys != tuple(sorted(set(keys))) or any(key not in MARKET_BY_KEY for key in keys):
        raise TransferBacktestError("market provenance is invalid")

    raw_markets = document.get("markets")
    if not isinstance(raw_markets, dict) or set(raw_markets) != set(keys):
        raise TransferBacktestError("market payload does not match provenance")
    markets: dict[str, TransferMarketResult] = {}
    for key in keys:
        raw = raw_markets[key]
        if not isinstance(raw, dict) or set(raw) != {
            "validation",
            "calibration",
            "competition_observations",
            "validated",
        }:
            raise TransferBacktestError("market artifact does not match its schema")
        validation = _parse_validation(raw.get("validation"))
        calibration = _parse_calibration(
            raw.get("calibration"),
            validation.observations,
        )
        counts_raw = raw.get("competition_observations")
        if not isinstance(counts_raw, dict):
            raise TransferBacktestError("competition observations are invalid")
        counts: list[tuple[int, int]] = []
        for competition_text, count in counts_raw.items():
            try:
                competition = int(competition_text)
            except (TypeError, ValueError) as exc:
                raise TransferBacktestError("competition observation key is invalid") from exc
            if (
                str(competition) != competition_text
                or competition not in competitions
                or isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise TransferBacktestError("competition observations are invalid")
            counts.append((competition, count))
        if sum(count for _, count in counts) != validation.observations:
            raise TransferBacktestError("competition observations do not sum to total")
        recomputed_validated = bool(
            validation.observations >= MIN_VALIDATION_MATCHES
            and _credible_validation(validation)
            and {competition for competition, _ in counts} == set(competitions)
            and all(
                count >= MIN_TRANSFER_COMPETITION_OBSERVATIONS
                for _, count in counts
            )
        )
        if raw.get("validated") is not recomputed_validated:
            raise TransferBacktestError("market validation flag is inconsistent")
        if recomputed_validated and calibration is None:
            raise TransferBacktestError("validated market lacks calibration")
        markets[key] = TransferMarketResult(
            validation=validation,
            calibration=calibration,
            competition_observations=tuple(sorted(counts)),
            validated=recomputed_validated,
        )

    provenance = TransferArtifactProvenance(
        model_signature=model_signature,
        dataset_hash=data_hash,
        competition_ids=competitions,
        cohort=cohort,
        training_start=_iso_utc(start),
        training_end=_iso_utc(end),
        training_cutoff=_iso_utc(cutoff),
        replay_count=replay_count,
        modeled_replay_count=modeled_count,
        scope_observations=tuple(scopes),
        market_keys=keys,
    )
    return TransferBacktestArtifact(
        artifact_id=artifact_id,
        provenance=provenance,
        markets=markets,
        release_authorized=False,
    )


__all__ = [
    "SUPPORTED_COHORTS",
    "SUPPORTED_COMPETITION_IDS",
    "MIN_TRANSFER_COMPETITION_OBSERVATIONS",
    "TRANSFER_ARTIFACT_KIND",
    "TRANSFER_ARTIFACT_SCHEMA_VERSION",
    "TRANSFER_DATASET_SCHEMA_VERSION",
    "TransferArtifactProvenance",
    "TransferBacktestArtifact",
    "TransferBacktestError",
    "TransferBacktestResult",
    "TransferMarketResult",
    "TransferPrediction",
    "TransferReplayFixture",
    "TransferScopeProvenance",
    "build_transfer_artifact",
    "dataset_hash",
    "run_transfer_backtest",
    "verify_transfer_artifact",
]
