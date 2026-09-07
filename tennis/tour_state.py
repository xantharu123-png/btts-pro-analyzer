"""Independent tennis tour training and immutable publication."""

from datetime import date, datetime, timezone
import math
from pathlib import Path
import time
from typing import Callable

import pandas as pd

from model_artifacts import (ManifestConflict, load_artifact, load_manifest,
                             put_artifact, publish_slots)
from runtime_paths import CONTEXT_MODEL_DB_PATH
from .backtest import RESULT_COLUMNS, WalkForwardCalibrator, _is_retired, run_backtest
from .data_loader import add_normalized_names, load_atp_stats, load_market_odds
from .elo import SurfaceElo
from .model_state import ModelState, load_state
from .serve_model import (ServeReturnModel, WTA_TOUR_HOLD_AVG,
                          WTA_TOUR_BREAK_AVG, is_tour_level)
from .state_codec import decode_state, encode_state


class TourUnavailable(LookupError):
    """No separately published model exists for the requested tour."""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware UTC cutoff required")
    return value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.fromtimestamp(time.time(), timezone.utc)


def _tour(tour: str) -> str:
    if tour not in ("ATP", "WTA"):
        raise ValueError("tour must be ATP or WTA")
    return tour


def training_years(as_of: datetime) -> tuple[int, ...]:
    """Include the active UTC season, never a fixed calendar end year."""
    return tuple(range(2010, _utc(as_of).year + 1))


def _dated_inputs(frame, column, tour, cutoff):
    if "tour" in frame and not frame["tour"].eq(tour).all():
        raise ValueError("training source contains a different tour")
    frame = frame.copy()
    frame[column] = pd.to_datetime(frame[column], errors="coerce", utc=True)
    return frame[frame[column].notna() & frame[column].le(cutoff)].sort_values(column, kind="mergesort")


def build_tour_state(tour: str, *, as_of: datetime,
                     refresh_training_data: bool = True) -> ModelState:
    """Build one namespace using sport-only, cutoff-bounded training inputs.

    The fixed 2022/2023/2024 calibration-year policy is intentionally retained.
    Price availability is no longer a calibration sample-selection criterion.
    This population change is not evidence of improved predictive performance.
    """
    tour = _tour(tour)
    cutoff = _utc(as_of)
    if cutoff > _now():
        raise ValueError("training cutoff is in the future")
    years = training_years(cutoff)
    options = {"refresh_current": refresh_training_data, "current_year": cutoff.year}
    elo = SurfaceElo()
    serve = (ServeReturnModel(half_life_days=365., split_indoor=True) if tour == "ATP"
             else ServeReturnModel(hold_avg=WTA_TOUR_HOLD_AVG,
                                   break_avg=WTA_TOUR_BREAK_AVG, half_life_days=365.))
    if tour == "ATP":
        frame = load_atp_stats(years, **options)
        column, winner, loser, surface, retired = "tourney_date", "winner_name", "loser_name", "surface", "match_ret"
    else:
        source = load_market_odds(years, tour="wta", **options)
        frame = source[[name for name in RESULT_COLUMNS if name in source]].copy()
        column, winner, loser, surface, retired = "Date", "Winner", "Loser", "Surface", "Comment"
    frame = _dated_inputs(frame, column, tour, cutoff)
    frame = add_normalized_names(frame, winner, loser)
    consumed = []
    for row in frame.to_dict("records"):
        if _is_retired(row.get(retired)) or not row.get("winner_key") or not row.get("loser_key"):
            continue
        elo.update(row["winner_key"], row["loser_key"], row.get(surface))
        if tour == "ATP" and is_tour_level(row):
            serve.update_from_match_row(row)
        consumed.append(row[column])
    if not consumed:
        raise ValueError("no dated completed training results before cutoff")
    calibration_years = tuple(year for year in (2022, 2023, 2024) if year <= cutoff.year)
    report = run_backtest(
        odds_years=calibration_years, stats_years=years, tours=(tour.lower(),),
        serve_weight=.3 if tour == "ATP" else 0., recalibrate=False,
        serve_half_life_days=365., serve_split_indoor=True,
        end_cutoff=cutoff, calibration_only=True,
    ) if calibration_years else None
    cal = WalkForwardCalibrator(min_samples=1500, refit_every=250)
    rows = report.rows if report is not None else []
    for row in rows:
        moment = pd.to_datetime(row.date, errors="coerce", utc=True)
        if pd.isna(moment) or moment > cutoff or row.tour != tour:
            raise ValueError("calibration row outside tour or cutoff")
        if not math.isfinite(row.p_alpha_raw) or not 0. <= row.p_alpha_raw <= 1. or row.y_alpha not in (0, 1):
            raise ValueError("invalid calibration observation")
        cal.add(row.p_alpha_raw, row.y_alpha)
    cal._fit()
    result = ModelState(
        elo=elo, serve=serve, cal_a=cal.a if tour == "ATP" else 1.,
        cal_b=cal.b if tour == "ATP" else 0., cal_samples=len(rows) if tour == "ATP" else 0,
        cal_wta_a=cal.a if tour == "WTA" else 1., cal_wta_b=cal.b if tour == "WTA" else 0.,
        cal_wta_samples=len(rows) if tour == "WTA" else 0,
        built_at=time.time(), stats_through=max(consumed).date().isoformat(),
        serve_weight=.3 if tour == "ATP" else 0., tour_scope=tour,
        stats_through_kind="tournament_start_proxy" if tour == "ATP" else "result_date",
        training_cutoff=cutoff.isoformat(),
    )
    _validate_coverage(encode_state(result, tour=tour), cutoff)
    _check_predictions(result)
    return result


def _validate_coverage(payload: dict, cutoff: datetime) -> None:
    if cutoff.timestamp() > payload["built_at"]:
        raise ValueError("training cutoff is later than actual build time")
    if date.fromisoformat(payload["stats_through"]) > cutoff.date():
        raise ValueError("coverage is later than training cutoff")
    expected_kind = "result_date" if payload["tour"] == "WTA" else "tournament_start_proxy"
    if payload["stats_through_kind"] != expected_kind:
        raise ValueError("coverage kind does not match tour")
    if payload["tour"] == "WTA" and (payload["serve_weight"] != 0. or payload["serve"]["rows"]):
        raise ValueError("WTA build must remain Elo-only")
    for row in payload["serve"]["rows"]:
        if row["last_date"] is not None:
            moment = pd.Timestamp(row["last_date"])
            moment = moment.tz_localize("UTC") if moment.tzinfo is None else moment.tz_convert("UTC")
            if moment > cutoff or moment.date() > date.fromisoformat(payload["stats_through"]):
                raise ValueError("serve input exceeds declared coverage")


def _decode_wrapper(payload, tour, *, decision_cutoff=None):
    if not isinstance(payload, dict) or set(payload) != {"schema", "training_cutoff", "state"}:
        raise ValueError("invalid tour artifact envelope")
    if type(payload["schema"]) is not int or payload["schema"] != 1:
        raise ValueError("unsupported tour artifact schema")
    text = payload["training_cutoff"]
    if not isinstance(text, str):
        raise ValueError("training cutoff must be canonical UTC text")
    cutoff = _utc(datetime.fromisoformat(text))
    if cutoff.isoformat() != text:
        raise ValueError("training cutoff must be canonical UTC text")
    state = decode_state(payload["state"], decision_cutoff=decision_cutoff)
    if state.tour_scope != tour:
        raise ValueError("artifact belongs to another tour")
    _validate_coverage(payload["state"], cutoff)
    state.training_cutoff = text
    return state


def _load_digest(path, digest, tour):
    artifact = load_artifact(path, digest)
    if artifact["kind"] != "tennis-tour-state":
        raise ValueError("unexpected tour artifact kind")
    state = _decode_wrapper(artifact["payload"], tour)
    state.artifact_hash = digest
    return state


def load_tour_state(tour: str, *, path: Path = CONTEXT_MODEL_DB_PATH,
                    allow_legacy: bool = False) -> ModelState:
    """Structural load; forecast consumers must check their decision cutoff."""
    tour = _tour(tour)
    _, slots = load_manifest(path)
    digest = slots.get(f"tennis:{tour}")
    if digest is None:
        if allow_legacy:
            return load_state()
        raise TourUnavailable(tour)
    return _load_digest(path, digest, tour)


def _check_predictions(state: ModelState) -> None:
    # Extremal ratings bound all logistic matchups, without an O(players**2)
    # validation pass. Exercise both orientations and every surface table.
    ratings = state.elo.to_payload()
    tables = [(None, state.elo.overall, ratings["overall"])]
    tables.extend((surface, table, ratings["by_surface"][surface])
                  for surface, table in state.elo.by_surface.items())
    for surface, table, players in tables:
        if surface is not None:
            # Match win_probability's default surface eligibility: otherwise
            # inexperienced extrema trigger its overall fallback and can hide
            # an overflowing matchup between experienced surface players.
            players = [player for player in players if table.matches(player) >= 8]
        if not players:
            continue
        low, high = min(players, key=table.rating), max(players, key=table.rating)
        for a, b in ((low, high), (high, low)):
            raw = state.elo.win_probability(a, b, surface)
            p = state.calibrate_match(raw, a, b, tour=state.tour_scope)
            if not math.isfinite(p) or not 0. <= p <= 1.:
                raise ValueError("invalid model prediction")
    if state.serve_weight > 0:
        players = {row["player"] for row in state.serve.to_payload()["rows"]}
        for player in players:
            for surface in (None, "Hard", "Clay", "Grass", "Carpet"):
                for indoor in ((False, True) if surface == "Hard" else (False,)):
                    holds = state.serve.expected_hold_probabilities(
                        player, player, surface, as_of=state.training_cutoff, indoor=indoor)
                    if any(not math.isfinite(p) or not 0. <= p <= 1. for p in holds):
                        raise ValueError("invalid serve prediction")


def _record(status, state=None, error=None):
    return {"status": status, "artifact_hash": state.artifact_hash if state else None,
            "built_at": state.built_at if state else None,
            "training_cutoff": state.training_cutoff if state else None,
            "stats_through": state.stats_through if state else None,
            "stats_through_kind": state.stats_through_kind if state else None,
            "error_type": type(error).__name__ if error else None}


def refresh_tours(*, path: Path, as_of: datetime,
                  builder: Callable[[str], ModelState],
                  publication_clock: Callable[[], datetime] | None = None,
                  if_stale_days: float | None = None) -> dict:
    """Attempt each tour independently and CAS-publish only validated states.

    A failed tour retains its exact previous identity and metadata. Conflict
    retries reload the manifest, protecting other slots and newer coverage.
    """
    cutoff = _utc(as_of)
    clock = publication_clock or _now
    if if_stale_days is not None and (isinstance(if_stale_days, bool) or
            not math.isfinite(if_stale_days) or if_stale_days < 0):
        raise ValueError("stale days must be finite and nonnegative")
    result = {"tours": {}}
    for tour in ("ATP", "WTA"):
        previous = None
        try:
            decision = _utc(clock())
            if cutoff > decision:
                raise ValueError("training cutoff is in the future")
            try:
                previous = load_tour_state(tour, path=path)
            except TourUnavailable:
                pass
            if previous is not None and if_stale_days is not None:
                decode_state(encode_state(previous, tour=tour), decision_cutoff=decision.timestamp())
                age = (decision.timestamp() - previous.built_at) / 86400.
                coverage_age = (decision.date() - date.fromisoformat(previous.stats_through)).days
                if 0 <= age < if_stale_days and 0 <= coverage_age < if_stale_days:
                    _check_predictions(previous)
                    result["tours"][tour] = _record("retained_fresh", previous)
                    continue
            state = builder(tour)
            payload = encode_state(state, tour=tour)
            if state.training_cutoff is not None and state.training_cutoff != cutoff.isoformat():
                raise ValueError("builder training cutoff does not match refresh")
            envelope = {"schema": 1, "training_cutoff": cutoff.isoformat(), "state": payload}
            completed = _utc(clock())
            if completed < decision:
                raise ValueError("publication clock moved backwards")
            checked = _decode_wrapper(envelope, tour, decision_cutoff=completed.timestamp())
            _check_predictions(checked)
            digest = None
            for attempt in range(4):
                manifest, slots = load_manifest(path)
                current = _load_digest(path, slots[f"tennis:{tour}"], tour) if f"tennis:{tour}" in slots else None
                if current is not None:
                    previous = current
                    if date.fromisoformat(checked.stats_through) < date.fromisoformat(current.stats_through):
                        raise ValueError("incoming training coverage regressed")
                if digest is None:
                    digest = put_artifact(path, kind="tennis-tour-state", payload=envelope, created_at=completed)
                # Storage may take time; sample the CAS receipt after that I/O.
                published = _utc(clock())
                if published < completed:
                    raise ValueError("publication clock moved backwards")
                _decode_wrapper(envelope, tour, decision_cutoff=published.timestamp())
                try:
                    publish_slots(path, {f"tennis:{tour}": digest},
                                  expected_manifest=manifest, published_at=published)
                    checked.artifact_hash = digest
                    result["tours"][tour] = _record("published", checked)
                    break
                except ManifestConflict:
                    completed = published
                    if attempt == 3:
                        raise
        except Exception as exc:
            result["tours"][tour] = _record("failed", previous, exc)
    statuses = [record["status"] for record in result["tours"].values()]
    healthy = {"published", "retained_fresh"}
    result["status"] = ("complete" if all(s in healthy for s in statuses)
                        else "partial" if any(s in healthy for s in statuses) else "failed")
    return result
