"""C3 review regressions: causal withdrawals and original native identity.

Synthetic native records, actual local B1 storage and actual B2 fit; no new
provider capability, empirical approval or default prediction change.
"""
from copy import deepcopy
from datetime import timedelta

import pytest

import sports_prematch
from context_models.contracts import ContextIntegrityError, canonical_bytes, canonical_timestamp
from test_ice_hockey_context import NOW, event, scope, inputs, base, implementation
from test_ice_hockey_revisions import historical_item, incomplete, write, read, calculate, change_team
from test_ice_hockey_effects import fitted_artifact, result


def withdrawal(recent):
    changed = incomplete(deepcopy(recent))
    changed["event"].update(status="cancelled", schedule_revision="withdrawal-v2")
    for key in ("actual_start", "actual_end", "regulation_seconds", "overtime_seconds", "terminal_phase"):
        changed["data"][key] = None
    return changed


def recovery_history(path, *, validity="valid", micros=0, move_side=None, received=None):
    older = historical_item(event_id=2025021777, end_hours=120)
    recent = historical_item(end_hours=30)
    cancelled = withdrawal(recent)
    if move_side is not None:
        change_team(cancelled, move_side, "nhl:ice_hockey:team:99")
        incomplete(cancelled)
    if validity == "until": cancelled["valid_until"] = canonical_timestamp(NOW+timedelta(microseconds=micros))
    elif validity == "from": cancelled["valid_from"] = canonical_timestamp(NOW+timedelta(microseconds=micros))
    refs = [write(path, item, NOW-timedelta(minutes=2)) for item in (older, recent)]
    refs.append(write(path, cancelled, received if received is not None else NOW-timedelta(minutes=1)))
    keys = [item["event"]["event_key"] for item in (older, recent)]
    return calculate(path, keys), refs, keys


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("validity", ["until", "from"])
@pytest.mark.parametrize("micros", [-1, 0, 1])
def test_withdrawal_validity_boundaries_do_not_manufacture_exact_rest_or_load(tmp_path, side, validity, micros):
    fv, refs, _ = recovery_history(tmp_path/"validity.db", validity=validity, micros=micros)
    usable = micros > 0 if validity == "until" else micros <= 0
    exact = "observed_recovery_exact_hours_"+side
    if usable:
        assert fv["values"][exact] == 126 and fv["states"][exact] == "available"
        assert fv["values"][f"observed_regulation_complete_7d_{side}"] == 1
    else:
        for name in (exact, "observed_recovery_minimum_hours_"+side):
            assert fv["values"][name] is None and fv["states"][name] == "conflicting"
            assert set(refs) <= set(fv["refs"][name])
        for days in (1, 3, 7):
            for phase in ("regulation", "overtime"):
                name = f"observed_{phase}_complete_{days}d_{side}"
                assert fv["values"][name] is None and fv["states"][name] == "conflicting"
                assert set(refs) <= set(fv["refs"][name])


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("validity,micros", [("until", 0), ("from", 1)])
def test_unusable_participant_withdrawal_retains_all_prior_and_new_team_uncertainty(tmp_path, side, validity, micros):
    path = tmp_path/"participant.db"
    fv, refs, keys = recovery_history(path, validity=validity, micros=micros, move_side=side)
    for affected in ("home", "away"):
        name = "observed_recovery_exact_hours_"+affected
        assert fv["values"][name] is None and set(refs) <= set(fv["refs"][name])
    _, uncertainty = implementation()._selection(read(path, keys), NOW, NOW+timedelta(hours=6))
    assert {event()["home_id"], event()["away_id"], "nhl:ice_hockey:team:99"} <= set(uncertainty)
    assert all(item["upper"] is None for items in uncertainty.values() for item in items)


@pytest.mark.parametrize("micros", [-1, 0, 1])
def test_cancellation_actual_receipt_cutoff_remains_independent_of_validity(tmp_path, micros):
    fv, _, _ = recovery_history(tmp_path/"receipt.db", received=NOW+timedelta(microseconds=micros))
    for side in ("home", "away"):
        assert fv["values"]["observed_recovery_exact_hours_"+side] == (36 if micros > 0 else 126)


@pytest.mark.parametrize("validity,micros", [("until", 0), ("from", 1)])
@pytest.mark.parametrize("approved", [False, True])
def test_invalid_withdrawal_cannot_feed_actual_fitted_recovery_effect(tmp_path, validity, micros, approved):
    original = base()
    fv, refs, _ = recovery_history(tmp_path/"effect.db", validity=validity, micros=micros)
    artifact = fitted_artifact(fv)  # Actual B2 fit, mirrored observed-recovery heads.
    answer = result(original, fv, artifact, approved=approved)
    assert canonical_bytes(answer["used_params"]) == canonical_bytes(original["params"])
    assert canonical_bytes(answer["used_markets"]) == canonical_bytes(original["markets"])
    assert answer["role"] == "not_applied" and answer["comparison_params"] is None
    assert answer["approval_hash"] is None and answer["certified_markets"] == []


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("primary", [None, "", 0, False])
def test_actual_native_fallback_team_is_checked_before_missing_rule_fallback(side, primary):
    target, history = inputs()
    fallback = ("team1" if side == "home" else "team2")+"_id"
    target[fallback], target[side+"_team_id"] = target[side+"_team_id"], primary
    target.pop("context_rule_version")
    current = event()
    current[side+"_id"] = "nhl:ice_hockey:team:99"
    assert sports_prematch.predict_prematch("ice_hockey", target, history, NOW).p_home is not None
    with pytest.raises(ContextIntegrityError, match="team orientation"):
        sports_prematch.hockey_base_distribution(target, history, NOW, context_event=current, scope=scope())


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("use_fallback", [False, True])
def test_original_team_precedence_and_matching_unavailable_base_stay_unchanged(side, use_fallback):
    target, history = inputs()
    fallback = ("team1" if side == "home" else "team2")+"_id"
    target.pop("context_rule_version")
    if use_fallback: target[fallback] = target.pop(side+"_team_id")
    else: target[fallback] = "99"  # Not consumed when the primary ID is present.
    before = canonical_bytes({"target": target, "history": history})
    legacy = sports_prematch.predict_prematch("ice_hockey", target, history, NOW)
    exported = sports_prematch.hockey_base_distribution(target, history, NOW, context_event=event(), scope=scope())
    assert exported["reference_weights"]["kind"] == "unavailable"
    assert exported["markets"]["home_inclusive"] == legacy.p_home
    assert exported["model_hash"] == legacy.input_hash
    assert canonical_bytes({"target": target, "history": history}) == before


@pytest.mark.parametrize("original_type", [1, 2, 3])
@pytest.mark.parametrize("target_format", ["nhl_reg60_regular_ot_so", "nhl_reg60_playoff_ot"])
@pytest.mark.parametrize("scope_missing", [False, True])
def test_known_original_variant_cannot_be_relabelled_by_missing_reference(original_type, target_format, scope_missing):
    target, history = inputs()
    target.update(game_type=original_type)
    target.pop("context_rule_version")
    for row in history: row["game_type"] = original_type
    current = {**event(), "format": target_format}
    expected_type = implementation().FORMATS[target_format]
    source_scope = None if scope_missing else {**scope(), "game_type": expected_type}
    legacy = sports_prematch.predict_prematch("ice_hockey", target, history, NOW)
    assert legacy.p_home is not None
    if original_type != expected_type:
        with pytest.raises(ContextIntegrityError, match="game type"):
            sports_prematch.hockey_base_distribution(target, history, NOW, context_event=current, scope=source_scope)
    else:
        exported = sports_prematch.hockey_base_distribution(target, history, NOW, context_event=current, scope=source_scope)
        assert exported["reference_weights"]["kind"] == "unavailable"
        assert exported["markets"]["home_inclusive"] == legacy.p_home
        assert exported["model_hash"] == legacy.input_hash
