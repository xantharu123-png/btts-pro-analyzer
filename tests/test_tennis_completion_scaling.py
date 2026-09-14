"""Regression tests for production-sized context work, without live providers."""
from copy import deepcopy
import sqlite3

import pytest

from model_artifacts import canonical_bytes
from test_context_transport import inputs
from test_tennis_live_worker import configure, run_batch


def writer_probe(path):
    # A separate writer must be able to commit while CPU validation runs.
    with sqlite3.connect(path, timeout=.05) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS completion_writer_probe(n INTEGER)")
        connection.execute("INSERT INTO completion_writer_probe VALUES (1)")


@pytest.mark.parametrize("excess,accepted", [(4e-16, True), (1e-12, False), (-2., False)])
def test_serve_tail_roundoff_does_not_hide_genuinely_invalid_probability(monkeypatch, excess, accepted):
    from context_models import tennis_effect as effect
    from context_models.offset import ContextModelError
    from tennis.simulator import simulate_match
    params = {"hold_a": .78, "hold_b": .74, "best_of": 3}
    result = simulate_match(**dict(p_hold_a=params["hold_a"], p_hold_b=params["hold_b"], best_of=3), strict=True)
    result.games_total = {12: 1., 13: excess}
    monkeypatch.setattr(effect, "simulate_match", lambda *args, **kwargs: result)
    if accepted:
        markets = effect.tennis_serve_markets(params)
        assert markets["under_38.5_games"] == 1.
        assert all(0. <= probability <= 1. for probability in markets.values())
    else:
        with pytest.raises(ContextModelError):
            effect.tennis_serve_markets(params)


def test_probability_sum_retains_all_in_range_bytes_and_rejects_large_excess():
    from math import fsum
    from context_models.tennis_effect import _probability_sum
    for values in ([], [.1, .2, .3], [.6, .4], [1e-250, 1e-250]):
        assert _probability_sum(values).hex() == fsum(values).hex()
    assert _probability_sum([1., 1e-12]) > 1.


def test_complete_reference_inventory_is_built_once_not_once_per_feature(monkeypatch):
    import context_transport as transport
    args = inputs()
    args["observation_refs"] = sorted(set(args["observation_refs"] + [f"{n:064x}" for n in range(1000)]))
    payload = transport.calculate_context_payload(**args)
    before = canonical_bytes(payload)
    observed = payload["observation_refs"]
    calls = []
    def counted(values=()):
        if values is observed:
            calls.append(1)
        return set(values)
    monkeypatch.setattr(transport, "set", counted, raising=False)
    transport._inputs(payload)
    # One uniqueness check and one shared membership index, regardless of the
    # number of features. All unused receipts still remain in the input key.
    assert len(calls) <= 2
    assert canonical_bytes(payload) == before


def test_whole_history_decode_does_not_hold_a_database_transaction(monkeypatch, tmp_path):
    import context_observations as observations
    from test_tennis_status_v3 import legacy, read
    db = tmp_path / "context.db"
    legacy(db)
    expected = read(db)
    original = observations._decode_receipt
    calls = []
    def checked(stored):
        writer_probe(db)
        calls.append(1)
        return original(stored)
    monkeypatch.setattr(observations, "_decode_receipt", checked)
    assert read(db) == expected
    assert calls


def test_per_card_feature_calculation_does_not_hold_a_database_transaction(monkeypatch, tmp_path):
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    original = live_context.tennis_features_v3
    def checked(*args, **kwargs):
        writer_probe(db)
        return original(*args, **kwargs)
    monkeypatch.setattr(live_context, "tennis_features_v3", checked)
    result, rows = run_batch(db, predictions)
    assert result["stored"] == len(rows) == 1


def test_snapshot_compute_releases_sqlite_but_still_computes_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from context_snapshots import compute_once
    db = tmp_path / "context.db"
    entered, release = Event(), Event()
    calls = []
    def compute():
        calls.append(1)
        entered.set()
        assert release.wait(10), "writer never released the CPU callback"
        return {"probability": .6}
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(compute_once, db, "a"*64, compute)
        try:
            assert entered.wait(10)
            second = pool.submit(compute_once, db, "a"*64, compute)
            writer_probe(db)
        finally:
            release.set()
        assert first.result(timeout=10) == second.result(timeout=10) == {"probability": .6}
    assert calls == [1]


def test_cached_snapshot_decode_does_not_hold_sqlite(monkeypatch, tmp_path):
    import context_snapshots as snapshots
    db = tmp_path / "context.db"
    expected = snapshots.compute_once(db, "a"*64, lambda: {"x": 1})
    decode = snapshots._decode_snapshot
    def checked(*args):
        writer_probe(db)
        return decode(*args)
    monkeypatch.setattr(snapshots, "_decode_snapshot", checked)
    assert snapshots.compute_once(db, "a"*64, lambda: pytest.fail("cached result recomputed")) == expected


@pytest.mark.parametrize("copies", [1, 2])
def test_actual_state_validation_scales_with_models_not_cards(monkeypatch, tmp_path, copies):
    from tennis import tour_state
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    decode = tour_state._decode_wrapper
    calls = []
    def checked(*args, **kwargs):
        writer_probe(db)
        calls.append(1)
        return decode(*args, **kwargs)
    def extend(batch, fixtures, result):
        item = batch.pending[0]
        states = [item["state"]] + ([deepcopy(item["state"])] if copies == 2 else [])
        for index in range(19):
            batch.pending.append({**item, "state": states[index % copies]})
        monkeypatch.setattr(tour_state, "_decode_wrapper", checked)
    result, rows = run_batch(db, predictions, before_finish=extend)
    assert result["stored"] == len(rows) == 1
    assert len(calls) == copies


def test_earliest_batch_cutoff_is_used_for_shared_model(monkeypatch, tmp_path):
    from datetime import timedelta
    from context_models.contracts import ContextContractError
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    def extend(batch, fixtures, result):
        item = batch.pending[0]
        batch.pending.append({**item, "decision": item["decision"] - timedelta(hours=2)})
    with pytest.raises((ContextContractError, ValueError)):
        run_batch(db, predictions, before_finish=extend)
    assert not predictions.exists()


def test_later_receipt_is_not_mixed_into_an_in_progress_history_read(monkeypatch, tmp_path):
    import context_observations as observations
    from test_tennis_status_v3 import legacy, read
    db = tmp_path / "context.db"
    legacy(db)
    expected = read(db)
    decode = observations._decode_receipt
    calls = []
    def checked(stored):
        if not calls:
            calls.append(1)
            legacy(db, match="102")
        return decode(stored)
    monkeypatch.setattr(observations, "_decode_receipt", checked)
    assert read(db) == expected
    assert len(read(db)) > len(expected)


def test_pending_prechecks_share_history_and_decode_outside_sqlite(monkeypatch, tmp_path):
    from datetime import timedelta
    from tennis import live_context
    from test_tennis_live_worker import NOW
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    read = live_context.tennis_observations_as_of
    decode = live_context._decode_snapshot
    calls = []
    def checked_read(*args, **kwargs):
        calls.append(1)
        return read(*args, **kwargs)
    def checked_decode(*args):
        writer_probe(db)
        return decode(*args)
    monkeypatch.setattr(live_context, "tennis_observations_as_of", checked_read)
    monkeypatch.setattr(live_context, "_decode_snapshot", checked_decode)
    batch = live_context.LiveWorker(db)
    for _ in range(10):
        batch.bind_pending(rows[0], decision_at=NOW+timedelta(hours=1))
    assert calls == [1]


@pytest.mark.parametrize("separate_state", [False, True])
def test_changed_actual_state_is_not_hidden_by_batch_reuse(monkeypatch, tmp_path, separate_state):
    from context_models.contracts import ContextContractError
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    def changed(batch, fixtures, result):
        if separate_state:
            other = dict(batch.pending[0])
            other["state"] = deepcopy(other["state"])
            batch.pending.append(other)
        batch.pending[-1]["state"].cal_a += .1
    with pytest.raises((ContextContractError, ValueError)):
        run_batch(db, predictions, before_finish=changed)
    assert not predictions.exists()
