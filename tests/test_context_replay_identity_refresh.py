"""Native identity survives refresh; numeric replay still uses latest receipts.

All sporting inputs are synthetic. The tests persist genuine isolated B1
receipts and call the public replay/case assembly, not a verified-flag seam.
"""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

import challenge_engine as engine
from context_models.contracts import ContextContractError, digest
from context_models.replay import replay_base_distribution
from context_observations import append_observation, observations_as_of
from context_sources.football import _detail_event, normalize_football_context
from context_sources.outcomes import normalize_football_base_input
from context_training_helpers import NOW, envelope, football_inventory, football_recipe


@pytest.fixture(scope="module")
def native_inventory(tmp_path_factory):
    return football_inventory(tmp_path_factory.mktemp("d1-refresh-native"))


def persist(tmp_path, raw, received, *, name="refresh", projections=False):
    event = _detail_event(raw)
    records = (normalize_football_base_input(raw, observed_at=received),)
    if projections:
        records += normalize_football_context(event, injuries=[], lineups=[raw],
                                             appearances=[], observed_at=received)
    path = tmp_path / f"{name}.db"
    for record in records:
        append_observation(path, record, observed_at=received)
    return observations_as_of(path, event["event_key"], cutoff=received,
                              schedule_revision=event["schedule_revision"])


def replay(event, history, identities, recipe):
    return replay_base_distribution("football", event, history, decision_at=NOW,
                                    reconstructed_at=NOW, recipe=recipe, identity_map=identities)


def refreshed(native_inventory, tmp_path, *, change="recheck"):
    event, history, _, identities = deepcopy(native_inventory)
    old = next(row for row in history if row["event_key"] == event["event_key"])
    raw = deepcopy(old["payload"]["detail"])
    if change == "lineup":
        raw["lineups"][0]["startXI"][0]["player"]["pos"] = "M"
    new = persist(tmp_path, raw, NOW - timedelta(minutes=5))
    assert len(new) == 1 and new[0]["digest"] != old["digest"]
    selected = tuple(row for row in history if row["event_key"] != event["event_key"]) + new
    return event, history + new, identities, football_recipe(selected), old, new[0]


@pytest.mark.parametrize("change", ["recheck", "lineup"])
@pytest.mark.parametrize("reverse", [False, True])
def test_refreshed_target_retains_earlier_identity_but_replays_only_latest_inputs(
    native_inventory, tmp_path, monkeypatch, change, reverse,
):
    from context_sources import football_native
    event, pool, identities, recipe, old, new = refreshed(native_inventory, tmp_path, change=change)
    if reverse:
        pool = tuple(reversed(pool))
    original = deepcopy((event, pool, identities, recipe))
    calls, native_calls = [], []
    real_model, real_provenance = engine._fixture_model, football_native.football_native_provenance

    def model(target, history, *args, **kwargs):
        calls.append((deepcopy(target), deepcopy(history)))
        return real_model(target, history, *args, **kwargs)

    def provenance(fixtures, receipts, **kwargs):
        native_calls.append(deepcopy(receipts))
        return real_provenance(fixtures, receipts, **kwargs)

    monkeypatch.setattr(engine, "_fixture_model", model)
    monkeypatch.setattr(football_native, "football_native_provenance", provenance)
    result = replay(event, pool, identities, recipe)
    assert len(calls) == len(native_calls) == 1
    target, past = calls[0]
    assert target == new["payload"]["detail"]
    assert len(past) == 26 == len({raw["fixture"]["id"] for raw in past})
    target_receipts = [r for r in native_calls[0] if r["detail"]["fixture"]["id"] == target["fixture"]["id"]]
    assert target_receipts == [{"detail": target, "observed_at": new["observed_at"]}]
    assert old["digest"] not in recipe["payload"]["input_refs"]
    assert new["digest"] in recipe["payload"]["input_refs"]
    assert identities["payload"]["bindings"][0]["source_refs"] == [old["digest"]]
    assert result["payload"]["event_identity_hash"] == identities["digest"]
    assert result["payload"]["input_refs_hash"] == digest(recipe["payload"]["input_refs"])
    expected = real_model(target, past)
    assert result["payload"]["base"]["params"] == dict(zip(
        ("home_lambda", "away_lambda"), expected["active_lambdas"]))
    assert (event, pool, identities, recipe) == original


def test_refresh_still_resolves_only_requested_event_of_the_global_identity_map(native_inventory, tmp_path):
    event, pool, identities, recipe, _, _ = refreshed(native_inventory, tmp_path)
    identities["payload"]["bindings"].append({"event_key": "api-football:football:9999999",
        "home_id": "api-football:team:3", "away_id": "api-football:team:4", "source_refs": ["f" * 64]})
    identities = envelope(identities["kind"], identities["payload"])
    result = replay(event, pool, identities, recipe)
    assert result["payload"]["event_identity_hash"] == identities["digest"]


@pytest.mark.parametrize("missing", ["receipt", "ref"])
def test_latest_target_cannot_replace_missing_frozen_identity_proof(native_inventory, tmp_path, missing):
    event, pool, identities, recipe, old, _ = refreshed(native_inventory, tmp_path)
    if missing == "receipt":
        pool = tuple(row for row in pool if row["digest"] != old["digest"])
    else:
        identities["payload"]["bindings"][0]["source_refs"] = ["f" * 64]
        identities = envelope(identities["kind"], identities["payload"])
    with pytest.raises(ContextContractError, match="identity proof receipt is missing"):
        replay(event, pool, identities, recipe)


def test_other_native_event_receipt_is_not_the_target_identity_proof(native_inventory, tmp_path):
    event, pool, identities, recipe, _, _ = refreshed(native_inventory, tmp_path)
    foreign = next(row for row in pool if row["event_key"] != event["event_key"])
    identities["payload"]["bindings"][0]["source_refs"] = [foreign["digest"]]
    identities = envelope(identities["kind"], identities["payload"])
    with pytest.raises(ContextContractError, match="another event"):
        replay(event, pool, identities, recipe)


def changed_home(raw):
    raw = deepcopy(raw)
    raw["teams"]["home"]["id"] = 3
    raw["lineups"][0]["team"]["id"] = 3
    return raw


def test_obsolete_different_participant_proof_is_not_revived_by_latest_valid_target(native_inventory, tmp_path):
    event, pool, identities, recipe, old, _ = refreshed(native_inventory, tmp_path)
    foreign = persist(tmp_path, changed_home(old["payload"]["detail"]),
                      NOW - timedelta(minutes=20), name="different-participant")
    identities["payload"]["bindings"][0]["source_refs"] = [foreign[0]["digest"]]
    identities = envelope(identities["kind"], identities["payload"])
    with pytest.raises(ContextContractError, match="native source orientation"):
        replay(event, pool + foreign, identities, recipe)


def test_stale_identity_map_cannot_authorize_a_current_changed_team(native_inventory, tmp_path):
    event, history, _, identities = deepcopy(native_inventory)
    old = next(row for row in history if row["event_key"] == event["event_key"])
    raw = changed_home(old["payload"]["detail"])
    current = _detail_event(raw)
    new = persist(tmp_path, raw, NOW - timedelta(minutes=5))
    selected = tuple(row for row in history if row["event_key"] != event["event_key"]) + new
    with pytest.raises(ContextContractError, match="original event differs from the whole-dataset native mapping"):
        replay(current, history + new, identities, football_recipe(selected))


def test_valid_older_identity_proof_does_not_bypass_current_schedule_binding(native_inventory, tmp_path):
    event, pool, identities, recipe, _, new = refreshed(native_inventory, tmp_path)
    raw = deepcopy(new["payload"]["detail"])
    raw["fixture"]["date"] = (NOW + timedelta(hours=3)).isoformat()
    current = _detail_event(raw)
    assert current["schedule_revision"] != event["schedule_revision"]
    with pytest.raises(ContextContractError, match="original event schedule/status/scope"):
        replay(current, pool, identities, recipe)


def test_late_identity_receipt_is_rejected_before_any_identity_resolution(native_inventory, tmp_path, monkeypatch):
    import context_models.replay as module
    event, pool, identities, recipe, old, _ = refreshed(native_inventory, tmp_path)
    late = persist(tmp_path, old["payload"]["detail"], NOW + timedelta(microseconds=1), name="late")
    identities["payload"]["bindings"][0]["source_refs"] = [late[0]["digest"]]
    identities = envelope(identities["kind"], identities["payload"])

    def forbidden(*args, **kwargs):
        pytest.fail("identity resolver must not receive a late proof pool")

    monkeypatch.setattr(module, "resolve_identity_map", forbidden)
    with pytest.raises(ContextContractError, match="late_import_is_not_predecision"):
        replay(event, pool + late, identities, recipe)


def test_malformed_older_proof_cannot_hide_behind_a_valid_latest_receipt(native_inventory, tmp_path, monkeypatch):
    import context_models.replay as module
    event, pool, identities, recipe, old, _ = refreshed(native_inventory, tmp_path)
    old["payload"]["detail"]["lineups"][0]["startXI"][0]["player"]["pos"] = "M"

    def forbidden(*args, **kwargs):
        pytest.fail("identity resolver must not receive unvalidated source bytes")

    monkeypatch.setattr(module, "resolve_identity_map", forbidden)
    with pytest.raises(ContextContractError):
        replay(event, pool, identities, recipe)


@pytest.mark.parametrize("selection", ["obsolete", "whole_pool"])
def test_identity_pool_is_not_permission_to_replay_obsolete_or_duplicate_math_inputs(native_inventory, tmp_path, selection):
    event, pool, identities, _, _, new = refreshed(native_inventory, tmp_path)
    recipe_rows = tuple(row for row in pool if row["digest"] != new["digest"]) if selection == "obsolete" else pool
    with pytest.raises(ContextContractError, match="exactly the latest resolved"):
        replay(event, pool, identities, football_recipe(recipe_rows))


def test_refreshed_case_assembles_from_current_projection_with_unchanged_identity_map(tmp_path):
    from context_models.football import football_features
    from context_models.training_cases import assemble_training_cases
    from context_models.training_contracts import validate_resolved_case
    from test_context_training_cases import football_case
    resolved, config = football_case(tmp_path)
    original = deepcopy(resolved)
    payload = resolved["case"]["payload"]
    event, decision = payload["event"], datetime.fromisoformat(payload["base"]["cutoff"])
    old_history = tuple(row for row in resolved["observations"] if row["kind"] == "base_fixture")
    old = next(row for row in old_history if row["event_key"] == event["event_key"])
    raw = deepcopy(old["payload"]["detail"])
    raw["lineups"][0]["startXI"][0]["player"]["pos"] = "M"
    added = persist(tmp_path, raw, decision - timedelta(minutes=5), projections=True)
    new = tuple(row for row in added if row["kind"] == "base_fixture")
    recipe = football_recipe(tuple(row for row in old_history if row["event_key"] != event["event_key"]) + new)
    identities = resolved["artifacts"][payload["event_identity_hash"]]
    rebuilt = replay_base_distribution("football", event, old_history + new, decision_at=decision,
        reconstructed_at=NOW, recipe=recipe, identity_map=identities)
    resolved["observations"] += added
    base = rebuilt["payload"]["base"]
    features = football_features(event, tuple(row for row in resolved["observations"]
                                if row["kind"] != "match_outcome"), base, cutoff=decision)
    payload.update(base=base, features=features, replay_ref=rebuilt["digest"])
    resolved["artifacts"] = {obj["digest"]: obj for obj in (rebuilt, recipe, identities)}
    resolved["case"] = envelope("context-training-case-v1", payload)
    assert payload["event_identity_hash"] == original["case"]["payload"]["event_identity_hash"]
    assert validate_resolved_case(resolved, config=config) == resolved
    report = assemble_training_cases((resolved,), config)
    assert report["canonical_events"] == 1 and len(report["rows"]) == 2 and report["excluded"] == ()
    assert {row["head"] for row in report["rows"]} == {"home", "away"}
    assert {row["base_hash"] for row in report["rows"]} == {digest(base)}
