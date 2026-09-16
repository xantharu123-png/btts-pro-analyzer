"""Existing-response winner receipts, not a trained effect or settlement path."""
from copy import deepcopy
from datetime import timedelta
import json
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND
from context_observations import _SELECT, _decode_receipt, append_observation
from context_sources import tennis_capture as capture
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import put_artifact
from test_tennis_live_worker import NOW, competition, configure, response, run_batch


RECEIVED = NOW + timedelta(hours=8)


def stored(path):
    with sqlite3.connect(path) as connection:
        return tuple(_decode_receipt(row) for row in connection.execute(_SELECT))


def outcomes(path):
    return tuple(row for row in stored(path) if row["kind"] == "match_outcome")


def original_store(monkeypatch, tmp_path, *, tour="ATP"):
    db, predictions, _, _ = configure(monkeypatch, tmp_path, tours=(tour,))
    run_batch(db, predictions)
    with sqlite3.connect(db) as connection:
        ref, payload = connection.execute("SELECT digest,payload FROM artifacts WHERE kind=?",
            (ORIGINAL_ARTIFACT_KIND,)).fetchone()
    return db, predictions, ref, json.loads(payload)["origin"]


def completed(*, event_id="201", winner=0):
    raw = competition(id=event_id)
    raw["status"]["type"].update(state="post", name="STATUS_FINAL", completed=True)
    for index, player in enumerate(raw["competitors"]):
        player["winner"] = index == winner
        player["linescores"] = [{"value": score, "winner": index == winner}
            for score in ((6, 6) if index == winner else (2, 4))]
    return raw


def record(observer, raw=None, *, tour="ATP", clock=RECEIVED):
    observer.record(tour.lower(), response(raw if raw is not None else completed(), tour), observed_at=clock)


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
@pytest.mark.parametrize("reversed_source", [False, True])
def test_actual_native_original_gets_winner_with_original_orientation_and_clock(
        monkeypatch, tmp_path, tour, reversed_source):
    db, predictions, _, origin = original_store(monkeypatch, tmp_path, tour=tour)
    shadow_bytes = predictions.read_bytes()
    raw = completed(event_id=origin["event"]["event_key"].rsplit(":", 1)[-1], winner=1)
    if reversed_source:
        raw["competitors"].reverse()
    before = {row["digest"]: row for row in stored(db)}
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("capture fetched"))
    monkeypatch.setattr("tennis.predict.predict_match", lambda *a, **kw: pytest.fail("capture predicted"))
    monkeypatch.setattr("context_sources.tennis_status.tennis_observations_as_of",
        lambda *a, **kw: pytest.fail("capture replayed the whole tour"))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw, tour=tour)
    result, = outcomes(db)
    event = origin["event"]
    assert result["payload"]["result"] == {"winner_id": event["away_id"]}
    assert result["payload"]["home_id"] == event["home_id"]
    assert result["payload"]["away_id"] == event["away_id"]
    assert result["schedule_revision"] == event["schedule_revision"]
    assert result["observed_at"] == result["valid_from"] == canonical_timestamp(RECEIVED)
    assert result["published_at"] is None and result["publication_proof"] is None
    assert result["digest"] in observer.report()["receipt_refs"]
    assert predictions.read_bytes() == shadow_bytes
    after = {row["digest"]: row for row in stored(db)}
    assert all(after[ref] == row for ref, row in before.items())
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE kind IN ('context-effect-v1','context-approval-v1')").fetchone()[0] == 0


def test_no_original_is_a_noop_for_labels_and_preserves_legacy_capture(tmp_path):
    db = tmp_path / "new.db"
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    assert outcomes(db) == ()
    assert len(stored(db)) == 3 and observer.report()["issues"] == []


@pytest.mark.parametrize("change", ["event", "tour", "tournament", "participant", "group"])
def test_result_cannot_borrow_an_original_from_another_native_scope(monkeypatch, tmp_path, change):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    raw, tour = completed(), "ATP"
    if change == "event": raw["id"] = "777"
    elif change == "tour": tour = "WTA"
    elif change == "participant": raw["competitors"][1]["id"] = "3"
    received = response(raw, tour)
    if change == "tournament": received["events"][0]["id"] = "188-2026"
    if change == "group": received["events"][0]["groupings"][0]["grouping"]["slug"] = "mens-doubles"
    with capture.capture_tennis_worker(path=db) as observer:
        observer.record(tour.lower(), received, observed_at=RECEIVED)
    assert outcomes(db) == ()


@pytest.mark.parametrize("flags", [(True, True), (False, False), (1, False), (None, True), (True, None)])
def test_ambiguous_or_missing_flags_are_not_targets(monkeypatch, tmp_path, flags):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    raw = completed()
    for player, flag in zip(raw["competitors"], flags):
        player["winner"] = flag
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw)
    assert outcomes(db) == ()
    assert "native-outcome-unavailable" in observer.report()["issues"]


@pytest.mark.parametrize("terminal", ["retired", "walkover", "abandoned"])
def test_non_normal_terminal_never_inherits_winner_label(monkeypatch, tmp_path, terminal):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    raw = completed()
    raw["notes"] = [{"text": terminal}]
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, raw)
    assert outcomes(db) == ()


def test_repeated_persist_is_idempotent_but_new_receptions_keep_their_own_time(monkeypatch, tmp_path):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
        observer.persist(db)
        initial = outcomes(db)
        assert len(initial) == 1
        observer.persist(db)
        assert outcomes(db) == initial
        record(observer, clock=RECEIVED + timedelta(minutes=1))
        observer.persist(db)
    rows = outcomes(db)
    assert len(rows) == 2
    assert {row["observed_at"] for row in rows} == {
        canonical_timestamp(RECEIVED), canonical_timestamp(RECEIVED + timedelta(minutes=1))}
    assert next(row for row in rows if row["digest"] == initial[0]["digest"]) == initial[0]


def test_later_unambiguous_winner_correction_is_a_separate_receipt(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, completed(winner=0))
        observer.persist(db)
        first, = outcomes(db)
        record(observer, completed(winner=1), clock=RECEIVED + timedelta(minutes=1))
    rows = sorted(outcomes(db), key=lambda row: row["observed_at"])
    assert rows[0] == first and len(rows) == 2
    assert [row["payload"]["result"]["winner_id"] for row in rows] == [
        origin["event"]["home_id"], origin["event"]["away_id"]]


@pytest.mark.parametrize("conflict", ["winner", "cancelled", "missing_winner"])
def test_simultaneous_conflicting_replies_do_not_manufacture_a_target(monkeypatch, tmp_path, conflict):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    second = completed(winner=1)
    if conflict == "cancelled":
        second["status"]["type"]["name"] = "STATUS_CANCELED"
    elif conflict == "missing_winner":
        second["competitors"][0].pop("winner")
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer, completed())
        record(observer, second)
    assert outcomes(db) == ()
    assert "native-outcome-conflicting" in observer.report()["issues"]


def test_capture_freezes_only_sport_fields_not_mutable_prices_or_names(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path)
    raw = completed()
    raw["odds"] = {"bookmaker": "private-price-marker", "price": 9.25}
    raw["competitors"][0]["athlete"]["displayName"] = "private-name-marker"
    received = response(raw)
    with capture.capture_tennis_worker(path=db) as observer:
        observer.record("atp", received, observed_at=RECEIVED)
        assert "private-price-marker" not in repr(observer.__dict__)
        assert "private-name-marker" not in repr(observer.__dict__)
        received["events"][0]["groupings"][0]["competitions"][0]["competitors"][0]["winner"] = False
    result, = outcomes(db)
    assert result["payload"]["result"]["winner_id"] == origin["event"]["home_id"]


@pytest.mark.parametrize("corruption", ["payload", "clock", "native_receipt", "state"])
def test_corrupt_stored_original_propagates_instead_of_becoming_missing(monkeypatch, tmp_path, corruption):
    db, _, original_ref, origin = original_store(monkeypatch, tmp_path)
    with sqlite3.connect(db) as connection:
        if corruption == "payload":
            connection.execute("UPDATE artifacts SET payload=? WHERE digest=?", (b"{}", original_ref))
        elif corruption == "clock":
            connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
                (canonical_timestamp(NOW - timedelta(minutes=1)), original_ref))
        elif corruption == "native_receipt":
            connection.execute("DELETE FROM context_observations WHERE digest=?", (origin["native_receipt"],))
        else:
            connection.execute("DELETE FROM artifacts WHERE digest=?", (origin["state_hash"],))
    with pytest.raises(ContextIntegrityError):
        with capture.capture_tennis_worker(path=db) as observer:
            record(observer)
    assert outcomes(db) == ()


def test_original_only_published_after_start_does_not_authorize_prospective_capture(monkeypatch, tmp_path):
    db, _, ref, origin = original_store(monkeypatch, tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
            (canonical_timestamp(RECEIVED - timedelta(minutes=1)), ref))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    assert outcomes(db) == ()


def test_result_received_before_original_publication_cannot_be_upgraded_later(monkeypatch, tmp_path):
    db, _, ref, _ = original_store(monkeypatch, tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
            (canonical_timestamp(RECEIVED + timedelta(minutes=1)), ref))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    assert outcomes(db) == ()


def test_distinct_native_original_revisions_are_not_silently_joined(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path)
    revised = competition()
    revised["competitors"][1]["id"] = "3"
    clock = NOW + timedelta(minutes=1)
    status, = normalize_tennis_status("ATP", "189-2026", revised,
        grouping_slug="mens-singles", observed_at=clock)
    receipt = append_observation(db, status, observed_at=clock)
    conflicting = deepcopy(origin)
    conflicting.update(cutoff=canonical_timestamp(clock + timedelta(seconds=1)),
        native_receipt=receipt, native_observed_at=canonical_timestamp(clock),
        competition_revision=status["payload"]["competition_revision"])
    conflicting["event"]["away_id"] = "espn:tennis:ATP:player:3"
    put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND, payload={"schema": 1, "origin": conflicting},
        created_at=clock + timedelta(seconds=2))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    assert outcomes(db) == ()
    assert "native-outcome-conflicting" in observer.report()["issues"]


def test_outcome_stays_with_its_status_and_workload_in_bounded_batches(monkeypatch, tmp_path):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    calls = []
    actual = capture.append_observation_batch
    def checked(path, rows):
        calls.append(len(rows))
        assert len(rows) <= 512
        by_clock = {}
        for row, clock in rows:
            by_clock.setdefault(clock, []).append(row)
        assert all(sorted(row["kind"] for row in group) ==
            ["event_status", "match_outcome", "workload", "workload"] for group in by_clock.values())
        return actual(path, rows)
    monkeypatch.setattr(capture, "append_observation_batch", checked)
    with capture.capture_tennis_worker(path=db) as observer:
        for index in range(130):
            record(observer, clock=RECEIVED + timedelta(seconds=index))
    assert calls == [512, 8] and len(outcomes(db)) == 130


def test_reversed_duplicate_reply_does_not_create_a_second_label(monkeypatch, tmp_path):
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    reversed_reply = completed()
    reversed_reply["competitors"].reverse()
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
        record(observer, reversed_reply)
    assert len(outcomes(db)) == 1 and not observer.report()["issues"]


def test_terminal_capture_uses_only_indexed_target_reads_not_full_history(monkeypatch, tmp_path):
    from contextlib import contextmanager
    import context_sources.tennis_outcome_capture as outcome_capture
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    queries = []
    actual = outcome_capture._reader
    @contextmanager
    def traced(path):
        with actual(path) as connection:
            connection.set_trace_callback(queries.append)
            yield connection
    monkeypatch.setattr(outcome_capture, "_reader", traced)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    target_reads = [query for query in queries if "FROM context_observations AS r" in query]
    assert len(target_reads) == 1
    assert "WHERE r.event_key=" in target_reads[0] and "LIMIT 2" in target_reads[0]
    assert len(outcomes(db)) == 1


def test_new_result_receipt_remains_compatible_with_existing_d4_verification(monkeypatch, tmp_path):
    from context_runtime import verify_context_database
    db, _, _, _ = original_store(monkeypatch, tmp_path)
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    before = db.read_bytes()
    report = verify_context_database(db)
    assert report["empirical_approval_verified"] is False
    assert report["verification_level"] == "transport_only"
    assert "unrecognized-artifact-schema" not in report["limitations"]
    assert db.read_bytes() == before and len(outcomes(db)) == 1


def test_multiple_original_calculations_of_same_native_event_produce_one_receipt(monkeypatch, tmp_path):
    db, _, _, origin = original_store(monkeypatch, tmp_path)
    repeated = deepcopy(origin)
    repeated["cutoff"] = canonical_timestamp(NOW + timedelta(seconds=2))
    put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND, payload={"schema": 1, "origin": repeated},
        created_at=NOW + timedelta(seconds=3))
    with capture.capture_tennis_worker(path=db) as observer:
        record(observer)
    assert len(outcomes(db)) == 1 and observer.report()["issues"] == []
