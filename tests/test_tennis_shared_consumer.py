"""Same saved live winner for both views; no new prediction at read time."""
from contextlib import closing
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import sqlite3

import pytest

from context_links import ContextReference
from context_models.contracts import ContextContractError, canonical_timestamp
from test_tennis_live_worker import NOW, configure, context_rows, run_batch


def stored(monkeypatch, tmp_path, *, tours=("ATP",)):
    db, predictions, _, _ = configure(monkeypatch, tmp_path, tours=tours)
    _, rows = run_batch(db, predictions)
    return db, predictions, rows


def read(row, db):
    from tennis.context_consumer import load_tennis_winner_context
    return load_tennis_winner_context(row, path=db)


@pytest.mark.parametrize("tours", [("ATP",), ("WTA",), ("ATP", "WTA")])
def test_actual_unrounded_original_is_shared_with_no_model_or_source_calls(monkeypatch, tmp_path, tours):
    db, predictions, rows = stored(monkeypatch, tmp_path, tours=tours)
    before = db.read_bytes(), predictions.read_bytes()
    for module, name in (("tennis.predict", "predict_match"), ("context_snapshots", "compute_once"),
                         ("context_transport", "calculate_context_payload"), ("model_artifacts", "put_artifact"),
                         ("requests", "get"), ("requests.sessions.Session", "request")):
        monkeypatch.setattr(module+"."+name, lambda *a, **k: pytest.fail("reader invoked a producer"))
    packets = dict(context_rows(db))
    for row in rows:
        actual = read(row, db)
        ref = json.loads(row["context_json"])["context_model"]["reference"]
        packet = packets[ref["key"]]
        assert actual["context_ref"] == ContextReference.from_dict(ref)
        assert actual["probabilities"] == {"A": packet["result"]["used_markets"]["winner_a"],
                                            "B": packet["result"]["used_markets"]["winner_b"]}
        assert actual["base_probabilities"] == actual["probabilities"]
        assert actual["probabilities"]["A"] != row["p_cal"]
        assert actual["probabilities"]["A"] + actual["probabilities"]["B"] == 1.
        assert all(len(summary) <= 300 for summary in actual["summaries"].values())
        assert "eingerechnet" not in " ".join(actual["summaries"].values())
        actual["probabilities"]["A"] = .999
        assert read(row, db)["probabilities"]["A"] != .999
    assert (db.read_bytes(), predictions.read_bytes()) == before


@pytest.mark.parametrize("context", [None, "{}", '{"players":{}}'])
def test_genuine_legacy_absence_does_not_open_or_create_a_context_database(monkeypatch, tmp_path, context):
    monkeypatch.setattr("context_consumers._reader", lambda *a, **k: pytest.fail("legacy opened context DB"))
    missing = tmp_path/"absent"/"models.db"
    assert read({"context_json": context}, missing) is None
    assert not missing.parent.exists()


@pytest.mark.parametrize("part", ["sidecar-null", "sidecar-schema-bool", "sidecar-schema-float", "reference-key",
    "reference-digest", "original-hash", "player-a", "player-b", "tour", "provider-id", "provider-source",
    "start", "decision", "append", "p-cal", "p-raw", "surface", "best-of", "indoor", "model-hash"])
def test_present_link_must_belong_to_this_exact_shadow_revision(monkeypatch, tmp_path, part):
    db, _, rows = stored(monkeypatch, tmp_path)
    row = deepcopy(rows[0])
    context = json.loads(row["context_json"])
    sidecar = context["context_model"]
    if part == "sidecar-null": context["context_model"] = None
    elif part == "sidecar-schema-bool": sidecar["schema"] = True
    elif part == "sidecar-schema-float": sidecar["schema"] = 1.
    elif part.startswith("reference-"): sidecar["reference"]["key" if part.endswith("key") else "payload_digest"] = "e"*64
    elif part == "original-hash": sidecar["original_artifact_hash"] = "e"*64
    elif part in {"player-a", "player-b"}: row[part.replace("-", "_")] += " changed"
    elif part == "tour": row["tour"] = "WTA"
    elif part == "provider-id": row["provider_event_id"] = "999"
    elif part == "provider-source": row["fixture_source"] = "different"
    elif part == "start": row["scheduled_start_utc"] = canonical_timestamp(NOW+timedelta(hours=7))
    elif part == "decision": row["created_utc"] += 1.
    elif part == "append": row["append_observed_at"] = canonical_timestamp(NOW)
    elif part in {"p-cal", "p-raw"}: row[part.replace("-", "_")] = .1234
    elif part == "surface": row["surface"] = "Clay"
    elif part == "best-of": row["best_of"] = 5
    elif part == "indoor": context["model_inputs"]["indoor"] = True
    else: context["model_inputs"]["model_artifact_hash"] = "e"*64
    row["context_json"] = json.dumps(context)
    before = db.read_bytes()
    with pytest.raises(ContextContractError):
        read(row, db)
    assert db.read_bytes() == before


@pytest.mark.parametrize("part", ["missing-original", "late-original", "late-state", "missing-state", "artifacts-view"])
def test_reader_checks_actual_original_publication_not_only_a_repeated_sidecar(monkeypatch, tmp_path, part):
    db, _, rows = stored(monkeypatch, tmp_path)
    sidecar = json.loads(rows[0]["context_json"])["context_model"]
    _, packet = context_rows(db)[0]
    with closing(sqlite3.connect(db)) as conn, conn:
        if part == "missing-original": conn.execute("DELETE FROM artifacts WHERE digest=?", (sidecar["original_artifact_hash"],))
        elif part == "late-original": conn.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
            (canonical_timestamp(NOW+timedelta(seconds=5)), sidecar["original_artifact_hash"]))
        elif part == "missing-state": conn.execute("DELETE FROM artifacts WHERE digest=?", (packet["base"]["model_hash"],))
        elif part == "late-state": conn.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
            (canonical_timestamp(NOW+timedelta(seconds=1)), packet["base"]["model_hash"]))
        else:
            conn.execute("ALTER TABLE artifacts RENAME TO hidden_artifacts")
            conn.execute("CREATE VIEW artifacts AS SELECT * FROM hidden_artifacts")
    before = db.read_bytes()
    with pytest.raises(ContextContractError):
        read(rows[0], db)
    assert db.read_bytes() == before


def test_both_actual_adapters_keep_the_same_reference_and_full_winner_probability(monkeypatch, tmp_path):
    from ev_signal_sources import tennis_model_signals, tennis_signals
    from riskobet_candidates import adapt_tennis_shadow
    db, predictions, rows = stored(monkeypatch, tmp_path)
    # This adapter fixture qualifies the existing non-context model gates; it
    # does not assert that the small synthetic training set passed real QA.
    qualified = deepcopy(rows[0])
    qualified["gates_json"] = json.dumps({"fixture-model-gate": {"passed": True},
        "Quote/Risiko-EV": {"passed": False}})
    qualified["verdict"], qualified["recommended_side"] = "WETTE", "A"
    monkeypatch.setattr("ev_signal_sources._latest_tennis_rows", lambda *a: [qualified])
    current = NOW+timedelta(seconds=3)
    normal = tennis_model_signals(predictions, today="2026-09-09", now=current)
    strict = tennis_signals(predictions, today="2026-09-09", now=current)
    risk = adapt_tennis_shadow(predictions, as_of=current)
    shared = read(rows[0], db)
    assert len(normal) == len(strict) == len(risk) == 1
    assert normal[0].context_ref == strict[0].context_ref == risk[0].snapshot.context_ref == shared["context_ref"]
    assert normal[0].probability == max(shared["probabilities"].values())
    assert strict[0].probability == shared["probabilities"]["A"]
    winner = next(c for c in risk[0].candidates if c.market_key == "match_winner")
    assert winner.model_probability == min(shared["probabilities"].values())
    assert all(c.stage.value == "SHADOW" for c in risk[0].candidates)
    assert all(c.context_state.value == "PARTIAL" for c in risk[0].candidates)
    assert "context_ref" in risk[0].snapshot.to_dict()


def test_missing_linked_database_is_an_error_not_an_ordinary_legacy_prediction(monkeypatch, tmp_path):
    db, _, rows = stored(monkeypatch, tmp_path)
    missing = tmp_path/"other"/"context.db"
    with pytest.raises(ContextContractError):
        read(rows[0], missing)
    assert not missing.parent.exists()


def _legacy_functions(module, name):
    namespace = vars(module).copy()
    source = (Path(__file__).parent/"fixtures"/name).read_text(encoding="utf-8")
    exec(compile(source, name, "exec"), namespace)
    return namespace


@pytest.mark.parametrize("probability", [.35, .5, .8])
@pytest.mark.parametrize("quote", [None, 1.01, 999.])
def test_no_link_keeps_exact_legacy_normal_and_risk_bytes_ids_and_set_markets(monkeypatch, tmp_path, probability, quote):
    import ev_signal_sources as normal
    import riskobet_candidates as risk
    from dataclasses import asdict
    db, predictions, rows = stored(monkeypatch, tmp_path)
    row = deepcopy(rows[0])
    context = json.loads(row["context_json"])
    context.pop("context_model")
    row.update(context_json=json.dumps(context), p_cal=probability, odds_a=quote, odds_b=quote,
        gates_json=json.dumps({"model-gate": {"passed": True}, "Quote/Risiko-EV": {"passed": False}}),
        markets_json='{"over_2_5_sets":0.45,"set_handicap_a_minus_1_5":0.12,"set_handicap_b_minus_1_5":0.35}',
        verdict="WETTE", recommended_side="A")
    monkeypatch.setattr(normal, "_latest_tennis_rows", lambda *a: [deepcopy(row)])
    monkeypatch.setattr("tennis.shadow.latest_predictions", lambda *a, **k: [deepcopy(row)])
    old_normal = _legacy_functions(normal, "tennis_normal_consumers_5d5bab6.py")
    old_risk = _legacy_functions(risk, "tennis_risk_consumer_5d5bab6.py")
    monkeypatch.setattr("context_consumers._reader", lambda *a, **k: pytest.fail("legacy read context"))
    current = NOW+timedelta(seconds=3)
    before = db.read_bytes(), predictions.read_bytes()
    for name in ("tennis_signals", "tennis_model_signals"):
        actual = getattr(normal, name)(predictions, today="2026-09-09", now=current)
        old = old_normal[name](predictions, today="2026-09-09", now=current)
        assert [asdict(item) for item in actual] == [asdict(item) for item in old]
    actual = risk.adapt_tennis_shadow(predictions, as_of=current)
    old = old_risk["adapt_tennis_shadow"](predictions, as_of=current)
    assert [(x.snapshot.to_dict(), [c.to_dict() for c in x.candidates]) for x in actual] == [
        (x.snapshot.to_dict(), [c.to_dict() for c in x.candidates]) for x in old]
    assert (db.read_bytes(), predictions.read_bytes()) == before


def test_both_probabilities_and_original_are_read_in_one_transaction(monkeypatch, tmp_path):
    import context_consumers
    from contextlib import contextmanager
    db, _, rows = stored(monkeypatch, tmp_path)
    original, reads = context_consumers._reader, []
    @contextmanager
    def tracked(path):
        with original(path) as connection:
            reads.append(path)
            yield connection
    monkeypatch.setattr(context_consumers, "_reader", tracked)
    assert set(read(rows[0], db)["probabilities"]) == {"A", "B"}
    assert reads == [db]


@pytest.mark.parametrize("quote", [None, 1.01, 99.])
def test_linked_price_changes_cannot_change_probability_reference_or_risk_identity(monkeypatch, tmp_path, quote):
    import ev_signal_sources as normal
    import riskobet_candidates as risk
    from wettfinder_automation import _signal_record
    db, predictions, rows = stored(monkeypatch, tmp_path)
    row = deepcopy(rows[0])
    row["gates_json"] = '{"model-gate":{"passed":true},"Quote/Risiko-EV":{"passed":false}}'
    monkeypatch.setattr(normal, "_latest_tennis_rows", lambda *a: [deepcopy(row)])
    monkeypatch.setattr("tennis.shadow.latest_predictions", lambda *a, **k: [deepcopy(row)])
    current = NOW+timedelta(seconds=3)
    model_before = normal.tennis_model_signals(predictions, today="2026-09-09", now=current)
    risk_before = risk.adapt_tennis_shadow(predictions, as_of=current)
    row.update(odds_a=quote, odds_b=quote, closing_odds_a=quote)
    model_after = normal.tennis_model_signals(predictions, today="2026-09-09", now=current)
    risk_after = risk.adapt_tennis_shadow(predictions, as_of=current)
    assert model_after == model_before
    assert risk_after == risk_before
    record = _signal_record(model_after[0])
    assert record["context_ref"] == model_after[0].context_ref.to_dict()
    assert record["probability"] == model_after[0].probability


@pytest.mark.parametrize("winner_a", [.2, .5, .8])
def test_adapter_winner_projection_never_changes_separate_set_simulation(monkeypatch, tmp_path, winner_a):
    """Adapter contract only: substituted projection is NOT an effect approval."""
    import riskobet_candidates as risk
    db, predictions, rows = stored(monkeypatch, tmp_path)
    row = deepcopy(rows[0])
    row["markets_json"] = '{"over_2_5_sets":0.45,"set_handicap_a_minus_1_5":0.12,"set_handicap_b_minus_1_5":0.35}'
    monkeypatch.setattr("tennis.shadow.latest_predictions", lambda *a, **k: [deepcopy(row)])
    shared = read(rows[0], db)
    monkeypatch.setattr(risk, "load_tennis_winner_context", lambda r: deepcopy(shared))
    current = NOW+timedelta(seconds=3)
    original = risk.adapt_tennis_shadow(predictions, as_of=current)[0]
    shared["probabilities"] = {"A": winner_a, "B": 1-winner_a}
    actual = risk.adapt_tennis_shadow(predictions, as_of=current)[0]
    sets = lambda output: [(c.market_key, c.selection_key, c.model_probability, c.stage, c.pros, c.cons)
        for c in output.candidates if c.market_key != "match_winner"]
    assert sets(actual) == sets(original) and sets(actual)
    assert all(c.stage.value == "SHADOW" for c in actual.candidates)
    winners = [c for c in actual.candidates if c.market_key == "match_winner"]
    if winner_a == .5:
        assert winners == []
    else:
        assert winners[0].model_probability == min(winner_a, 1-winner_a)
        assert winners[0].selection_key == ("home" if winner_a < .5 else "away")
