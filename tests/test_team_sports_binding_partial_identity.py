"""Known native contradictions survive incomplete identities; no new usability."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_sources.team_sports_binding import resolve_team_sport_original
from model_artifacts import canonical_bytes
from tests.test_team_sports_binding import (
    NOW, PROVIDERS, native_game, original, pool, record, source_inputs, source_reply,
)


def participant(body, provider, side, value):
    native = native_game(provider, body)
    if provider == "ESPN":
        next(person for person in native["competitors"] if person["homeAway"] == side)["team"]["id"] = value
    elif provider == "EuroLeague":
        native["local" if side == "home" else "road"]["club"]["code"] = value
    else:
        native[side + "Team"]["id"] = value


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("missing_side", ["home", "away"])
@pytest.mark.parametrize("is_target", [True, False])
@pytest.mark.parametrize("conflict", [True, False])
def test_partial_native_identity_retains_only_independently_known_conflict(
        tmp_path, provider, missing_side, is_target, conflict):
    _, target, history = source_inputs(provider)
    raw = target if is_target else history[7]
    original_value, prediction = original(provider)
    assert prediction.p_home is not None
    original_bytes = canonical_bytes(prediction.to_dict())
    body = source_reply(provider, raw, target=is_target)
    participant(body, provider, missing_side, None)
    other = "away" if missing_side == "home" else "home"
    if conflict: participant(body, provider, other, "Club77" if provider == "EuroLeague" else 77)
    path = tmp_path / "actual-native.db"
    record(path, provider, body, target=is_target)
    rows = pool(path)
    assert "invalid-participants" in rows[0]["payload"]["projection"]["issues"]
    assert rows[0]["payload"]["projection"][missing_side + "_id"] is None
    binding = resolve_team_sport_original(original_value, rows)
    detail = binding.input_bindings[0 if is_target else 8]
    assert binding.event is None
    assert detail["current_state"] == "unknown"
    assert detail["match_state"] == ("conflicting" if conflict else "unknown")
    assert ("native-participants-conflict" in detail["reasons"]) is conflict
    assert not detail["matching_receipt_refs"]
    assert detail["lineage_refs"] == [rows[0]["digest"]]
    assert binding.receipt_binding["event_receipt"] is None
    assert binding.receipt_binding["history_receipts"] == []
    assert canonical_bytes(prediction.to_dict()) == original_bytes


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("missing_side", ["home", "away"])
def test_current_partial_conflict_does_not_relabel_older_documentary_match(tmp_path, provider, missing_side):
    _, target, _ = source_inputs(provider)
    original_value, prediction = original(provider)
    frozen = canonical_bytes(prediction.to_dict())
    body = source_reply(provider, target, target=True)
    path = tmp_path / "native-revisions.db"
    record(path, provider, body, target=True, observed=NOW-timedelta(seconds=2))
    earlier = pool(path)
    bad = deepcopy(body)
    participant(bad, provider, missing_side, None)
    participant(bad, provider, "away" if missing_side == "home" else "home", "Club77" if provider == "EuroLeague" else 77)
    record(path, provider, bad, target=True, observed=NOW-timedelta(seconds=1))
    result = resolve_team_sport_original(original_value, pool(path))
    detail = result.input_bindings[0]
    assert result.event is None and detail["current_state"] == "unknown"
    assert detail["match_state"] == "matched"  # only the actual old raw fact
    assert detail["matching_receipt_refs"] == [earlier[0]["digest"]]
    assert "native-participants-conflict" in detail["reasons"]
    assert len(detail["lineage_refs"]) == 2
    record(path, provider, body, target=True, observed=NOW)
    restored = resolve_team_sport_original(original_value, pool(path)).input_bindings[0]
    assert restored["match_state"] == "matched" and restored["current_state"] == "available"
    assert "native-participants-conflict" not in restored["reasons"]
    assert len(restored["matching_receipt_refs"]) == 2 and len(restored["lineage_refs"]) == 3
    assert canonical_bytes(prediction.to_dict()) == frozen


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("known_conflict", [True, False])
def test_unknown_status_is_not_itself_reclassified_as_a_known_contradiction(tmp_path, provider, known_conflict):
    _, target, _ = source_inputs(provider)
    original_value, _ = original(provider)
    body = source_reply(provider, target, target=True)
    native = native_game(provider, body)
    if provider == "ESPN": native["status"]["type"]["name"] = "STATUS_UNKNOWN"
    elif provider == "EuroLeague": native["gameStatus"] = "UNREVIEWED"
    else: native["gameState"] = "UNREVIEWED"
    if known_conflict: participant(body, provider, "away", "Club77" if provider == "EuroLeague" else 77)
    path = tmp_path / "unknown-status.db"
    record(path, provider, body, target=True)
    result = resolve_team_sport_original(original_value, pool(path))
    detail = result.input_bindings[0]
    assert result.event is None and detail["current_state"] == "unknown"
    assert detail["match_state"] == ("conflicting" if known_conflict else "unknown")
    assert "native-status-conflict" not in detail["reasons"]
    assert ("native-participants-conflict" in detail["reasons"]) is known_conflict
    assert detail["matching_receipt_refs"] == []
