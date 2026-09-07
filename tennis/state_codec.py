"""Strict JSON-shaped codec for independent ATP and WTA model states."""

from __future__ import annotations

from datetime import date
import math

from .elo import SurfaceElo
from .model_state import ModelState
from .serve_model import ServeReturnModel


_TOURS = {"ATP", "WTA"}
_STATE_KEYS = {
    "schema",
    "tour",
    "elo",
    "serve",
    "cal_a",
    "cal_b",
    "cal_samples",
    "cal_wta_a",
    "cal_wta_b",
    "cal_wta_samples",
    "built_at",
    "stats_through",
    "stats_through_kind",
    "serve_weight",
}


def _finite_number(value: object, *, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _sample_count(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if value < 0:
        raise ValueError(f"{label} must be nonnegative")
    return value


def _nonempty_string(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value:
        raise ValueError(f"{label} must not be empty")
    return value


def _tour(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("tour must be a string")
    if value not in _TOURS:
        raise ValueError("tour must be ATP or WTA")
    return value


def _coverage_date(value: object) -> str:
    text = _nonempty_string(value, label="stats_through")
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("stats_through must be an ISO calendar date") from exc
    return text


def encode_state(state: ModelState, *, tour: str) -> dict:
    """Encode one explicitly scoped tour state into a JSON-shaped mapping."""

    if not isinstance(state, ModelState):
        raise TypeError("state must be a ModelState")
    selected_tour = _tour(tour)
    state_tour = getattr(state, "tour_scope", "legacy-combined")
    if state_tour == "legacy-combined":
        raise ValueError("legacy-combined state cannot be encoded as tour-specific")
    if state_tour != selected_tour:
        raise ValueError("state tour does not match requested tour")

    payload = {
        "schema": 1,
        "tour": selected_tour,
        "elo": state.elo.to_payload(),
        "serve": state.serve.to_payload(),
        "cal_a": state.cal_a,
        "cal_b": state.cal_b,
        "cal_samples": state.cal_samples,
        "cal_wta_a": state.cal_wta_a,
        "cal_wta_b": state.cal_wta_b,
        "cal_wta_samples": state.cal_wta_samples,
        "built_at": state.built_at,
        "stats_through": state.stats_through,
        "stats_through_kind": getattr(
            state, "stats_through_kind", "tournament_start_proxy"
        ),
        "serve_weight": state.serve_weight,
    }
    decode_state(payload)
    return payload


def decode_state(
    payload: dict,
    *,
    decision_cutoff: float | None = None,
) -> ModelState:
    """Decode structure, optionally checking eligibility for a decision cutoff.

    Without ``decision_cutoff`` this only validates and reconstructs the stored
    state. Omission never establishes that the artifact is decision-ready.
    Supplying a cutoff additionally requires ``built_at <= decision_cutoff``.
    """

    if not isinstance(payload, dict):
        raise TypeError("state payload must be a dictionary")
    if set(payload) != _STATE_KEYS:
        raise ValueError("state payload has missing or unexpected keys")
    if not isinstance(payload["schema"], int) or isinstance(
        payload["schema"], bool
    ) or payload["schema"] != 1:
        raise ValueError("unsupported state schema")

    tour = _tour(payload["tour"])
    built_at = _finite_number(payload["built_at"], label="built_at")
    if decision_cutoff is not None:
        cutoff = _finite_number(decision_cutoff, label="decision_cutoff")
        if built_at > cutoff:
            raise ValueError("built_at is later than the decision cutoff")

    cal_a = _finite_number(payload["cal_a"], label="cal_a")
    cal_b = _finite_number(payload["cal_b"], label="cal_b")
    cal_wta_a = _finite_number(payload["cal_wta_a"], label="cal_wta_a")
    cal_wta_b = _finite_number(payload["cal_wta_b"], label="cal_wta_b")
    serve_weight = _finite_number(payload["serve_weight"], label="serve_weight")
    if not 0.0 <= serve_weight <= 1.0:
        raise ValueError("serve_weight must be between zero and one")

    return ModelState(
        elo=SurfaceElo.from_payload(payload["elo"]),
        serve=ServeReturnModel.from_payload(payload["serve"]),
        cal_a=cal_a,
        cal_b=cal_b,
        cal_samples=_sample_count(payload["cal_samples"], label="cal_samples"),
        built_at=built_at,
        stats_through=_coverage_date(payload["stats_through"]),
        serve_weight=serve_weight,
        cal_wta_a=cal_wta_a,
        cal_wta_b=cal_wta_b,
        cal_wta_samples=_sample_count(
            payload["cal_wta_samples"], label="cal_wta_samples"
        ),
        tour_scope=tour,
        stats_through_kind=_nonempty_string(
            payload["stats_through_kind"], label="stats_through_kind"
        ),
        artifact_hash=None,
    )
