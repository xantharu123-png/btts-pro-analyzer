"""Full-history validation precedes a lossless, worker-local event projection."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from context_sources.tennis_status import select_tennis_observations
from test_context_tennis_capture import NOW, competition, records


def selected(comp, *, clock=NOW-timedelta(hours=1), tour="ATP"):
    raw = records(comp, clock=clock, tour=tour,
                  slug="mens-singles" if tour == "ATP" else "womens-singles")
    rows = tuple({**row, "content_digest": digest(row),
                  "digest": digest({"content_digest": digest(row),
                                    "observed_at": canonical_timestamp(clock)}),
                  "observed_at": canonical_timestamp(clock)} for row in raw)
    return select_tennis_observations(rows, cutoff=NOW, tour=tour)


def event(key="target", home="espn:tennis:player:1", away="espn:tennis:player:9"):
    return {"event_key": key, "home_id": home, "away_id": away}


def status(rows):
    return next(row for row in rows if "participant_ids" in row["payload"])


def test_projection_keeps_whole_event_including_correction_removing_player():
    from tennis.history_projection import PreparedTennisHistory
    before = selected(competition())
    changed = competition()
    changed["competitors"][0]["id"] = "7"
    after = selected(changed, clock=NOW-timedelta(minutes=10))
    unrelated = competition(id="202")
    unrelated["competitors"] = [{"id": "3"}, {"id": "4"}]
    other = selected(unrelated)
    history = before + after + other
    owner = PreparedTennisHistory(history)
    player = status(before)["payload"]["participant_ids"][0]
    result = owner.for_event(event(home=player))
    assert result == tuple(row for row in history if row["event_key"] == before[0]["event_key"])
    assert owner.observation_refs == sorted({row["digest"] for row in history})
    assert owner.for_event(event(key=other[0]["event_key"], home=player)) == history


def test_unrelated_corrupt_receipt_is_not_hidden_by_projection():
    from tennis.history_projection import PreparedTennisHistory
    rows = deepcopy(selected(competition()))
    status(rows)["payload"]["participant_ids"][0] = "espn:tennis:player:999"
    with pytest.raises(ContextContractError):
        PreparedTennisHistory(rows)


def test_original_and_returned_mutations_cannot_change_owned_history():
    from tennis.history_projection import PreparedTennisHistory
    rows = deepcopy(selected(competition()))
    player = status(rows)["payload"]["participant_ids"][0]
    target = event(home=player)
    owner = PreparedTennisHistory(rows)
    expected = owner.for_event(target)
    status(rows)["payload"]["participant_ids"].clear()
    returned = owner.for_event(target)
    status(returned)["payload"]["participant_ids"].clear()
    owner.observation_refs.clear()
    assert owner.for_event(target) == expected
    assert owner.observation_refs == sorted(row["digest"] for row in expected)


def test_unrelated_events_are_not_revalidated_for_each_card(monkeypatch):
    from tennis import history_projection as module
    rows = selected(competition())
    calls = []
    real = module.validate_selected_tennis_receipt
    def counted(row):
        calls.append(row["digest"])
        return real(row)
    monkeypatch.setattr(module, "validate_selected_tennis_receipt", counted)
    owner = module.PreparedTennisHistory(rows)
    for _ in range(20):
        assert owner.for_event(event(home="unrelated:a", away="unrelated:b")) == ()
    assert len(calls) == len(rows)


@pytest.mark.parametrize("correction", ["none", "started", "cancelled", "players", "conflict", "partial", "schedule"])
def test_feature_bytes_equal_full_history_including_retractions(correction):
    from context_models.tennis_v3 import tennis_features_v3
    from model_artifacts import canonical_bytes
    from tennis.history_projection import PreparedTennisHistory
    from test_tennis_context_features import event as actual_event, base
    history = selected(competition())
    comp = competition()
    if correction in {"started", "cancelled"}:
        comp["status"] = {"type": {"state": "in" if correction == "started" else "post",
                                  "name": "STATUS_IN_PROGRESS" if correction == "started" else "STATUS_CANCELED",
                                  "completed": correction == "cancelled"}}
    elif correction == "players":
        comp["competitors"][0]["id"] = "7"
    elif correction == "schedule":
        comp["date"] = "2026-09-08T20:00Z"
    elif correction == "conflict":
        comp["competitors"][0]["linescores"][0]["value"] = 7
    if correction != "none":
        clock = NOW-timedelta(hours=1) if correction == "conflict" else NOW-timedelta(minutes=10)
        new = selected(comp, clock=clock)
        history += new[:1] if correction == "partial" else new
    for index in range(5):
        comp = competition(id=str(300+index))
        comp["competitors"][0]["id"] = str(50+index)
        comp["competitors"][1]["id"] = str(60+index)
        history += selected(comp)
    ev = actual_event()
    projected = PreparedTennisHistory(history).for_event(ev)
    assert len(projected) < len(history)
    assert canonical_bytes(tennis_features_v3(ev, projected, base(ev), cutoff=NOW)) == canonical_bytes(
        tennis_features_v3(ev, history, base(ev), cutoff=NOW))
    with PreparedTennisHistory(history).feature_scope(ev) as scoped:
        assert canonical_bytes(tennis_features_v3(ev, scoped, base(ev), cutoff=NOW)) == canonical_bytes(
            tennis_features_v3(ev, history, base(ev), cutoff=NOW))


def test_owned_feature_scope_reuses_only_exact_validated_bytes(monkeypatch):
    from context_sources import tennis_status as source
    from tennis.history_projection import PreparedTennisHistory
    rows = selected(competition())
    owner = PreparedTennisHistory(rows)
    target = event(key=rows[0]["event_key"])
    cold = source._validate_selected_tennis_receipt_cold
    calls = []
    def counted(row):
        calls.append(row["digest"])
        return cold(row)
    monkeypatch.setattr(source, "_validate_selected_tennis_receipt_cold", counted)
    with owner.feature_scope(target) as scoped:
        assert scoped == owner.for_event(target)
        for row in scoped:
            source.validate_selected_tennis_receipt(row)
        assert not calls
        # Even identical caller-created dictionaries are not scope-owned.
        source.validate_selected_tennis_receipt(deepcopy(scoped[0]))
        assert len(calls) == 1
    source.validate_selected_tennis_receipt(scoped[0])
    assert len(calls) == 2


@pytest.mark.parametrize("change", ["payload", "digest", "alias", "nonfinite"])
def test_owned_scope_cannot_hide_changed_receipts(monkeypatch, change):
    from context_sources import tennis_status as source
    from tennis.history_projection import PreparedTennisHistory
    rows = selected(competition())
    owner = PreparedTennisHistory(rows)
    cold = source._validate_selected_tennis_receipt_cold
    calls = []
    def checked(row):
        calls.append(1)
        return cold(row)
    monkeypatch.setattr(source, "_validate_selected_tennis_receipt_cold", checked)
    with owner.feature_scope(event(key=rows[0]["event_key"])) as scoped:
        row = status(scoped)
        if change == "payload": row["payload"]["participant_ids"][0] = "changed"
        elif change == "digest": row["digest"] = "a" * 64
        elif change == "nonfinite": row["payload"]["status"] = float("nan")
        else:
            class Alias(str): pass
            row["digest"] = Alias(row["digest"])
        if change == "alias":
            # Preserve cold semantics: this str alias is accepted only after
            # the original validator, never through byte-reuse authorization.
            source.validate_selected_tennis_receipt(row)
        else:
            with pytest.raises(ContextContractError):
                source.validate_selected_tennis_receipt(row)
        assert calls == [1]
    assert owner.for_event(event(key=rows[0]["event_key"])) == rows


def test_owned_scope_closes_on_exception_and_does_not_authorize_later_use(monkeypatch):
    from context_sources import tennis_status as source
    from tennis.history_projection import PreparedTennisHistory
    owner = PreparedTennisHistory(selected(competition()))
    with pytest.raises(RuntimeError):
        with owner.feature_scope(event(home="espn:tennis:ATP:player:1")) as scoped:
            assert scoped
            raise RuntimeError("interrupted computation")
    def cold(row): raise RuntimeError("cold validation required")
    monkeypatch.setattr(source, "_validate_selected_tennis_receipt_cold", cold)
    with pytest.raises(RuntimeError, match="cold validation required"):
        source.validate_selected_tennis_receipt(scoped[0])


def test_replaced_private_row_storage_does_not_grant_reuse():
    import json
    from context_sources.tennis_status import validate_selected_tennis_receipt
    from model_artifacts import canonical_bytes
    from tennis.history_projection import PreparedTennisHistory
    rows = selected(competition())
    owner = PreparedTennisHistory(rows)
    changed = json.loads(owner._rows[0])
    changed["digest"] = "a" * 64
    owner._rows = (canonical_bytes(changed),) + owner._rows[1:]
    with owner.feature_scope(event(key=rows[0]["event_key"])) as scoped:
        with pytest.raises(ContextContractError):
            validate_selected_tennis_receipt(scoped[0])


def test_nested_scope_restores_outer_exact_owner(monkeypatch):
    from context_sources import tennis_status as source
    from tennis.history_projection import PreparedTennisHistory
    rows = selected(competition())
    owner = PreparedTennisHistory(rows)
    target = event(key=rows[0]["event_key"])
    def cold(row): raise RuntimeError("not owned by current scope")
    monkeypatch.setattr(source, "_validate_selected_tennis_receipt_cold", cold)
    with owner.feature_scope(target) as outer:
        with owner.feature_scope(target) as inner:
            source.validate_selected_tennis_receipt(inner[0])
            with pytest.raises(RuntimeError): source.validate_selected_tennis_receipt(outer[0])
        source.validate_selected_tennis_receipt(outer[0])
        with pytest.raises(RuntimeError): source.validate_selected_tennis_receipt(inner[0])


def test_cold_receipt_validation_does_not_require_live_worker_module(monkeypatch):
    import builtins
    from context_sources.tennis_status import validate_selected_tennis_receipt
    row = deepcopy(selected(competition())[0])
    original = builtins.__import__
    def isolated(name, *args, **kwargs):
        if name == "tennis.history_projection":
            raise ImportError("live worker is not part of the cold replay package")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", isolated)
    assert validate_selected_tennis_receipt(row) == row
