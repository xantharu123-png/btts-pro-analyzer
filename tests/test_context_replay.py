"""New D1 replay function, strict causal inputs and original football math."""
from copy import deepcopy
from datetime import timedelta

import pytest

import challenge_engine as engine
from context_models.contracts import ContextContractError, digest
from context_training_helpers import NOW, envelope, football_inventory, football_recipe


def run(event, rows, identities, *, recipe=None, decision=NOW):
    from context_models.replay import replay_base_distribution
    return replay_base_distribution("football", event, rows, decision_at=decision, reconstructed_at=NOW,
                                    recipe=recipe or football_recipe(rows), identity_map=identities)


def test_real_replay_function_reuses_raw_base_math_and_separates_reconstruction_clock(tmp_path):
    event, rows, _, identities = football_inventory(tmp_path)
    original = deepcopy((event, rows, identities))
    result = run(event, rows, identities)
    base = result["payload"]["base"]
    target = next(row["payload"]["detail"] for row in rows if row["event_key"] == event["event_key"])
    historical = [row["payload"]["detail"] for row in rows if row["event_key"] != event["event_key"]]
    expected = engine._fixture_model(target, historical)
    assert base["params"] == dict(zip(("home_lambda", "away_lambda"), expected["active_lambdas"]))
    matrix = engine.score_matrix(*expected["active_lambdas"])
    assert base["markets"] == {spec.key: engine.market_probability(matrix, spec)
                              for spec in engine.MARKET_SPECS if spec.key in base["markets"]}
    assert base["version"] == "football-goals-raw-reference-v1"
    assert base["reference_weights"]["kind"] != "unavailable"
    assert all(ref["event_join"] == "verified_native" for ref in base["history_refs"])
    assert result["payload"]["event_identity_hash"] == identities["digest"]
    assert (event, rows, identities) == original
    assert result["digest"] == digest({key: result[key] for key in ("kind", "payload")})


def test_late_import_cannot_be_a_past_prediction_input(tmp_path):
    event, rows, _, identities = football_inventory(tmp_path)
    with pytest.raises(ContextContractError):
        run(event, rows, identities, decision=NOW - timedelta(days=30))


@pytest.mark.parametrize("change", ["time", "orientation", "code", "calibrator", "missing_source", "unknown_market"])
def test_replay_requires_exact_native_scope_code_and_resolved_inputs(tmp_path, change):
    event, rows, _, identities = football_inventory(tmp_path)
    recipe = football_recipe(rows)
    if change == "time":
        event["scheduled_start"] = (NOW + timedelta(hours=4)).isoformat()
    elif change == "orientation":
        event["home_id"], event["away_id"] = event["away_id"], event["home_id"]
    elif change == "code":
        recipe["payload"]["code_hashes"]["challenge_engine.py"] = "f" * 64
    elif change == "calibrator":
        recipe["payload"]["calibrator_ref"] = "c" * 64
    elif change == "missing_source":
        recipe["payload"]["input_refs"][0] = "d" * 64
        recipe["payload"]["input_refs"].sort()
    else:
        recipe["payload"]["target_markets"] = ["HALFTIME_RESULT_HOME"]
    recipe = envelope(recipe["kind"], recipe["payload"])
    with pytest.raises(ContextContractError):
        run(event, rows, identities, recipe=recipe)


def test_insufficient_real_history_is_an_explicit_unavailable_report_not_default_rate(tmp_path):
    from context_models.replay import ReplayUnavailable
    event, rows, _, identities = football_inventory(tmp_path, count=3)
    with pytest.raises(ReplayUnavailable, match="insufficient"):
        run(event, rows, identities)


def test_tennis_alias_truth_cannot_be_supplied_as_a_verified_flag():
    from context_models.replay import ReplayUnavailable, replay_base_distribution
    with pytest.raises(ReplayUnavailable, match="native.*state|state.*native"):
        replay_base_distribution("tennis", {}, (), decision_at=NOW, reconstructed_at=NOW,
                                 recipe={"verified": True}, identity_map={})
