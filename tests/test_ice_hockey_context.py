"""C3 source/CPU mechanics on synthetic native records, not a real NHL feed."""
from copy import deepcopy
from datetime import timedelta
import math

import pytest

from context_models.contracts import ContextContractError
from context_models.contracts import canonical_bytes, canonical_timestamp, validate_base_distribution
from test_sports_prematch import NOW, event as legacy_event, history as legacy_history


def implementation():
    from context_models import ice_hockey
    return ice_hockey


@pytest.mark.parametrize("home,away,ot", [(2.5, 2.5, .6), (.001, 10., 0.), (10., .001, 1.), (1., 4., .25)])
def test_hockey_separates_regulation_and_ot_with_mirrored_roles(home, away, ot):
    result = implementation().hockey_distribution(home, away, ot)
    reverse = implementation().hockey_distribution(away, home, 1.-ot)
    assert set(result) == {"home_reg", "draw_reg", "away_reg", "home_inclusive", "away_inclusive"}
    assert math.fsum(result[k] for k in ("home_reg", "draw_reg", "away_reg")) == pytest.approx(1., abs=1e-12)
    assert result["home_inclusive"] == result["home_reg"] + ot*result["draw_reg"]
    assert result["home_inclusive"] + result["away_inclusive"] == 1.
    assert result["home_reg"] == pytest.approx(reverse["away_reg"], abs=1e-12)
    assert result["home_inclusive"] == pytest.approx(reverse["away_inclusive"], abs=1e-12)


@pytest.mark.parametrize("home,away,ot", [(0, 2, .5), (-1, 2, .5), (True, 2, .5), (2, "2", .5),
    (2, 2, True), (2, 2, -1e-9), (2, 2, 1.00001), (float("inf"), 2, .5), (2, 2, float("nan"))])
def test_hockey_distribution_refuses_invalid_rates_and_ot_not_clips(home, away, ot):
    with pytest.raises(ContextContractError):
        implementation().hockey_distribution(home, away, ot)


def event():
    return dict(event_key="nhl:ice_hockey:2025029999", sport="ice_hockey", competition="nhl",
        format="nhl_reg60_regular_ot_so", home_id="nhl:ice_hockey:team:1", away_id="nhl:ice_hockey:team:8",
        scheduled_start=canonical_timestamp(NOW+timedelta(hours=6)), schedule_revision="schedule-1", status="scheduled")


def scope():
    return dict(season=20252026, game_type=2, neutral_site=False, rule_version="nhl-2025-26-rule84")


def inputs():
    target = legacy_event("ice_hockey", provider_event_id="2025029999", season=20252026,
        context_rule_version="nhl-2025-26-rule84")
    rows = [{**row, "provider_event_id": str(2025020001+i), "season": 20252026,
             "context_rule_version": "nhl-2025-26-rule84"} for i, row in enumerate(legacy_history("ice_hockey"))]
    return target, rows


def base():
    import sports_prematch
    target, rows = inputs()
    return sports_prematch.hockey_base_distribution(target, rows, NOW, context_event=event(), scope=scope())


def test_original_poisson_export_replays_exact_unrounded_model_and_separate_ot():
    import sports_prematch as legacy
    target, rows = inputs()
    old = legacy.predict_prematch("ice_hockey", target, rows, NOW)
    original = base()
    assert original["markets"]["home_inclusive"] == old.p_home
    assert original["markets"]["away_inclusive"] == old.p_away
    assert original["markets"]["home_reg"] == old.p_home_regulation
    assert original["markets"]["draw_reg"] == old.p_draw_regulation
    assert original["model_hash"] == old.input_hash
    assert len(original["history_refs"]) == 84
    assert original["reference_weights"]["variant"] == "hockey-observed-contributing-exposure-v1"
    assert validate_base_distribution(original) == original


@pytest.mark.parametrize("mutation", ["unknown-season", "unknown-neutral", "unknown-rule", "native-alias", "pseudo-id"])
def test_unqualified_native_reference_preserves_legacy_base_without_roster_claim(mutation):
    import sports_prematch as legacy
    target, rows = inputs()
    if mutation == "unknown-season": rows[0].pop("season")
    elif mutation == "unknown-neutral": target.pop("neutral_site")
    elif mutation == "unknown-rule": rows[0].pop("context_rule_version")
    elif mutation == "native-alias": rows.append({**rows[0], "provider_event_id": "2025021888"})
    else: rows[0]["provider_event_id"] = "-2025020001"
    old = legacy.predict_prematch("ice_hockey", target, rows, NOW)
    original = legacy.hockey_base_distribution(target, rows, NOW, context_event=event(), scope=scope())
    assert original["reference_weights"]["kind"] == "unavailable"
    assert original["markets"]["home_inclusive"] == old.p_home
    assert original["markets"]["away_inclusive"] == old.p_away


@pytest.mark.parametrize("mutation", ["coefficient", "ot", "event", "fit-scope", "history", "market"])
def test_original_poisson_provenance_rejects_independent_rewrites(mutation):
    original = base()
    altered = deepcopy(original)
    if mutation == "coefficient": altered["reference_weights"]["fit"]["coefficients"][0] += .001
    elif mutation == "ot": altered["params"]["overtime_home_probability"] = .5
    elif mutation == "event": altered["reference_weights"]["event"]["schedule_revision"] = "other"
    elif mutation == "fit-scope": altered["reference_weights"]["scope"]["season"] = 20262027
    elif mutation == "history": altered["reference_weights"]["selected"][0]["home_score"] += 1
    else: altered["markets"]["home_reg"] += .001
    with pytest.raises(ContextContractError): validate_base_distribution(altered)


@pytest.mark.parametrize("mutation", ["event-id", "home", "away", "schedule", "status"])
def test_known_original_target_identity_mismatch_is_not_benign_unavailable_provenance(mutation):
    import sports_prematch
    target, history = inputs()
    target.pop("context_rule_version")  # Missing scope cannot hide known corruption.
    current = event()
    if mutation == "event-id": current["event_key"] = "nhl:ice_hockey:2025021999"
    elif mutation in ("home", "away"): current[mutation+"_id"] = "nhl:ice_hockey:team:99"
    elif mutation == "schedule": current["scheduled_start"] = canonical_timestamp(NOW+timedelta(hours=7))
    else: current["status"] = "cancelled"
    with pytest.raises(ContextContractError):
        sports_prematch.hockey_base_distribution(target, history, NOW, context_event=current, scope=scope())


def test_hockey_cannot_reuse_generic_flat_binomial_training_rows_without_owning_d1():
    from context_models.contracts import validate_training_row
    row = {"event_key": event()["event_key"], "decision_at": canonical_timestamp(NOW),
        "result_observed_at": canonical_timestamp(NOW+timedelta(days=1)), "block": "synthetic",
        "population": {"sport": "ice_hockey", "competitions": ["nhl"], "formats": [event()["format"]],
            "tours": [None], "surfaces": [None], "indoor": [None]}, "coverage": {"version": "synthetic", "case": "synthetic"},
        "feature_names": ["unreviewed-flat"], "x": [1.], "offset": .1, "target": 1, "trials": 1,
        "base_hash": "a"*64, "feature_refs": {"unreviewed-flat": ["b"*64]}, "evidence_class": "prospective",
        "family": "ice_hockey:regulation_goals", "head": "home"}
    with pytest.raises(ContextContractError): validate_training_row(row)


@pytest.mark.parametrize("kind", [[], {}])
@pytest.mark.parametrize("family", ["ice_hockey:regulation_goals", "football:goals:90min"])
def test_new_family_routing_does_not_turn_malformed_reference_kind_into_untyped_error(kind, family):
    from context_models.contracts import validate_reference_weights
    with pytest.raises(ContextContractError):
        validate_reference_weights({"schema": 1, "kind": kind}, [], family=family)
