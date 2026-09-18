"""Same-call native publication mechanics, not empirical qualification."""
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError
from test_context_football_capture import detail, stored
from test_football_context_provider import NOW, payload, provider
from copy import deepcopy


def test_baseline_flush_is_readable_before_worker_exit(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "native.db"
    with capture_football_worker(owner, path=path) as capture:
        received = owner.details_by_fixture([1575469])
        assert callable(getattr(capture, "flush_baseline_receipts", None)), "baseline receipts exist only after worker exit"
        refs = capture.flush_baseline_receipts(tuple(received.values()), max_new_payload_bytes=100_000)
        assert refs and any(row["kind"] == "base_fixture" for row in stored(path))
        from context_observations import freeze_named_receipts
        frozen = freeze_named_receipts(path, tuple(sorted({ref for values in refs.values() for ref in values})))
        assert len(frozen) == 1 and frozen[0]["observed_at"] == "2026-09-09T09:00:00.000000Z"
    assert len(calls) == 1


def test_named_reader_distinguishes_empty_from_missing_and_corruption(tmp_path, monkeypatch):
    import context_observations as observations
    assert callable(getattr(observations, "freeze_named_receipts", None)), "exact named reader missing"
    path = tmp_path / "missing.db"
    assert observations.freeze_named_receipts(path, ()) == ()
    with pytest.raises(ContextIntegrityError):
        observations.freeze_named_receipts(path, ("a" * 64,))
    from context_sources.outcomes import normalize_football_base_input
    ref = observations.append_observation(path, normalize_football_base_input(detail(), observed_at=NOW), observed_at=NOW)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE context_observations SET source='other' WHERE digest=?", (ref,))
    with pytest.raises(ContextIntegrityError):
        observations.freeze_named_receipts(path, (ref,))


def test_resolver_gets_selected_union_and_integrity_is_not_swallowed():
    import challenge_engine as engine
    from test_football_base_provenance import history, target, fixture
    rows = history()
    extra = fixture(55555, -90, 1, 2)
    selected = []
    def resolve(actual):
        selected.extend(actual)
        return None
    normal = engine.fixture_market_probabilities(target(), rows, team_history=rows + [extra])
    captured = []
    actual = engine.fixture_market_probabilities(target(), rows, team_history=rows + [extra],
        original_capture=captured.append, native_resolver=resolve)
    assert actual == normal and len(captured) == 1
    assert {row["fixture"]["id"] for row in selected} == {10001, *range(1, 129)}
    assert len(selected) == 129
    def corrupt(actual):
        raise ContextIntegrityError("named source corrupt")
    with pytest.raises(ContextIntegrityError, match="named source corrupt"):
        engine.fixture_market_probabilities(target(), rows, original_capture=captured.append, native_resolver=corrupt)
    with pytest.raises(ValueError):
        engine.fixture_market_probabilities(target(), rows, original_capture=captured.append,
            native_provenance={}, native_resolver=resolve)


def test_atomic_publication_budget_idempotence_and_binding_readback(tmp_path, monkeypatch):
    import importlib.util
    assert importlib.util.find_spec("context_models.football_original_publication") is not None, "atomic publisher missing"
    from context_models.football_original_publication import FootballOriginalPublication, BINDING_KIND
    from test_football_original_storage import capture, NOW as CAPTURED, rows_in
    from context_models.football_original_storage import load_original
    from test_football_base_provenance import history, target
    import challenge_engine as engine
    original = capture(monkeypatch)
    path = tmp_path / "publication.db"
    session = FootballOriginalPublication(path, None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=0)
    session.freeze(tuple([target(), *history()]))
    decision = CAPTURED - timedelta(seconds=1)
    kwargs = session.model_kwargs(decision_at=decision)
    engine.fixture_market_probabilities(target(), history(), **kwargs)
    report = session.report()
    assert report["published_count"] == 1 and report["inserted_payload_bytes"] > 0
    event = report["events"][0]
    assert event["status"] == "partial"
    stored_rows = rows_in(path)
    binding = next(row for row in stored_rows.values() if row[0] == BINDING_KIND)
    import json
    data = json.loads(binding[1])
    assert data["decision_at"] < data["captured_at"]
    assert data["unresolved"] and not data["consumed_receipts"]
    assert load_original(path, data["original_manifest_digest"]).to_dict()["source_evidence"] == original.to_dict()["source_evidence"]
    before = session.remaining_payload_bytes
    kwargs["original_capture"](load_original(path, data["original_manifest_digest"]))
    assert session.remaining_payload_bytes == before
    assert rows_in(path) == stored_rows
    empty = tmp_path / "budget.db"
    exhausted = FootballOriginalPublication(empty, None, max_publication_payload_bytes=0,
        max_worker_payload_bytes=0, max_source_payload_bytes=0)
    exhausted.freeze(tuple([target(), *history()]))
    engine.fixture_market_probabilities(target(), history(), **exhausted.model_kwargs(decision_at=decision))
    assert exhausted.report()["events"][0]["status"] == "budget-exhausted"
    assert not rows_in(empty)


def test_opt_in_domestic_capture_keeps_original_clock_and_drain(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    raw = detail()
    raw["fixture"]["status"]["short"] = "FT"
    raw["fixture"]["date"] = "2026-09-01T12:00:00+00:00"
    raw["goals"] = {"home": 2, "away": 1}
    owner, _ = provider(monkeypatch, details=payload([raw]))
    path = tmp_path / "domestic.db"
    with capture_football_worker(owner, path=path, baseline_enabled=True) as capture:
        capture.record("fixtures", {"team": raw["teams"]["home"]["id"], "last": 50,
            "status": "FT", "timezone": "Europe/Zurich"}, payload([raw]), observed_at=NOW, status=200)
        refs = capture.flush_baseline_receipts((raw,), max_new_payload_bytes=100_000)
        assert len(next(iter(refs.values()))) == 1
        first = next(iter(refs.values()))
        again = capture.flush_baseline_receipts((raw,), max_new_payload_bytes=0)
        assert next(iter(again.values())) == first
    assert {row["kind"] for row in stored(path)} >= {"base_fixture", "appearance", "match_outcome"}


def test_flushed_detail_still_drains_nonbaseline_observations(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    owner, _ = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "drain.db"
    with capture_football_worker(owner, path=path) as capture:
        received = owner.details_by_fixture([1575469])
        capture.flush_baseline_receipts(tuple(received.values()), max_new_payload_bytes=100_000)
    assert {row["kind"] for row in stored(path)} >= {"base_fixture", "confirmed_lineup"}


def test_source_zero_budget_rolls_back_and_cannot_become_unlimited(tmp_path):
    from context_observations import append_bounded_observation_batch
    from context_sources.outcomes import normalize_football_base_input
    from context_models.football_original_storage import StorageBudgetExceeded
    path = tmp_path / "source.db"
    with pytest.raises(StorageBudgetExceeded):
        append_bounded_observation_batch(path, ((normalize_football_base_input(detail(), observed_at=NOW), NOW),),
            max_new_payload_bytes=0)
    assert stored(path) == []


def test_unsupported_native_projection_stays_partial_not_a_forecast_failure(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    raw = detail()
    raw["unknown_provider_field"] = "unsupported"
    owner, _ = provider(monkeypatch, details=payload([raw]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    with capture_football_worker(owner, path=tmp_path / "unsupported.db") as capture:
        received = owner.details_by_fixture([1575469])
        refs = capture.flush_baseline_receipts(tuple(received.values()), max_new_payload_bytes=100_000)
        assert all(not values for values in refs.values())
        assert capture.report()["status"] == "partial"


def test_nonselected_unrepresentable_scope_row_cannot_abort_valid_native_flush(tmp_path, monkeypatch):
    from context_sources.football_capture import capture_football_worker
    owner, _ = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "scope.db"
    invalid = detail()
    invalid["fixture"]["date"] = "not-a-date"
    with capture_football_worker(owner, path=path) as capture:
        received = owner.details_by_fixture([1575469])
        refs = capture.flush_baseline_receipts(tuple([*received.values(), invalid]), max_new_payload_bytes=100_000)
        assert len(refs) == 1 and next(iter(refs.values()))


def test_source_budget_charges_new_receipt_even_when_content_is_shared(tmp_path):
    from context_observations import append_bounded_observation_batch
    from context_sources.outcomes import normalize_football_base_input
    from context_models.football_original_storage import StorageBudgetExceeded
    path = tmp_path / "repeat.db"
    record = normalize_football_base_input(detail(), observed_at=NOW)
    refs, inserted = append_bounded_observation_batch(path, ((record, NOW),), max_new_payload_bytes=100_000)
    assert inserted > 0
    assert append_bounded_observation_batch(path, ((record, NOW),), max_new_payload_bytes=0) == (refs, 0)
    with pytest.raises(StorageBudgetExceeded):
        append_bounded_observation_batch(path, ((record, NOW + timedelta(seconds=1)),), max_new_payload_bytes=0)
    assert len(stored(path)) == 1


def test_refresh_forwards_session_to_final_scan_with_float_parity(tmp_path, monkeypatch):
    from test_challenge_15k import fixture, candidate, credible_validation, MARKET_SPECS
    from datetime import datetime, timezone
    from unittest.mock import Mock
    import challenge_15k as scan
    from football_model_refresh import refresh_fixture_models
    from context_models.football_original_publication import FootballOriginalPublication
    now = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
    old = candidate("1:BTTS_YES", 1, .60, kickoff=now + timedelta(hours=5))
    upcoming = fixture(1, now + timedelta(hours=5), 10, 11)
    rows = [fixture(1000+i, now-timedelta(days=i+1), 10 if i % 2 else 11,
        11 if i % 2 else 10, 1+i % 3, i % 2) for i in range(60)]
    owner = Mock()
    owner.errors = []
    owner.details_by_fixture.return_value = {1: upcoming}
    owner.completed_history.return_value = rows
    owner.coverage.return_value = {"injuries": True, "lineups": False}
    owner.injuries_by_fixture.return_value = {1: []}
    owner.h2h.return_value = []
    owner.weather.return_value = {"temperature_c": 20., "wind_kmh": 5., "precipitation_mm": 0.}
    monkeypatch.setattr(scan, "_cached_market_validation", lambda *a: {spec.key: credible_validation() for spec in MARKET_SPECS})
    monkeypatch.setattr(scan, "_cached_market_calibration", lambda *a: {})
    monkeypatch.setattr(scan, "annotate_history_xg", lambda *a, **k: {"coverage": 1.})
    plain = refresh_fixture_models(owner, [old], now.date(), now=now)
    session = FootballOriginalPublication(tmp_path / "refresh.db", None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=0)
    captured = refresh_fixture_models(owner, [old], now.date(), now=now, original_publication=session)
    assert session.report()["published_count"] == 1
    assert [(c.candidate_id, c.probability) for c in plain["candidates"]] == [(c.candidate_id, c.probability) for c in captured["candidates"]]
    assert captured["football_original_capture"] == session.report()


@pytest.mark.parametrize("revision", ["same", "correction", "tie", "late", "csv", "unlinked"])
def test_real_receipt_resolution_keeps_native_revision_authority(tmp_path, monkeypatch, revision):
    from context_sources.football_capture import capture_football_worker
    from context_models.football_original_publication import FootballOriginalPublication
    from test_football_native_context import raw
    rows, _ = raw()
    baseline = deepcopy(rows[0])
    owner, _ = provider(monkeypatch, details=payload([baseline]))
    path = tmp_path / "revision.db"
    with capture_football_worker(owner, path=path) as capture:
        if revision != "unlinked":
            capture.record("fixtures", {"id": baseline["fixture"]["id"]}, payload([baseline]),
                observed_at=NOW - timedelta(minutes=2), status=200)
        if revision in {"correction", "tie", "late"}:
            changed = deepcopy(baseline)
            changed["goals"]["home"] += 1
            capture.record("fixtures", {"id": baseline["fixture"]["id"]}, payload([changed]),
                observed_at=NOW + timedelta(minutes=1) if revision == "late" else
                    NOW - timedelta(minutes=2 if revision == "tie" else 1), status=200)
        if revision == "csv":
            baseline["challenge_source"] = "football-data-results-only"
        session = FootballOriginalPublication(path, capture, max_publication_payload_bytes=2_000_000,
            max_worker_payload_bytes=2_000_000, max_source_payload_bytes=500_000)
        session.freeze((baseline,))
        proof = session.model_kwargs(decision_at=NOW)["native_resolver"]((baseline,))
        assert bool(proof["records"]) == (revision in {"same", "late"})
        if revision in {"correction", "tie", "late"}:
            assert len(session._rows) == 2


def test_named_reader_never_inventory_scans_and_releases_before_decode(tmp_path, monkeypatch):
    from contextlib import contextmanager
    import context_models.dataset as dataset
    import context_observations as observations
    from context_sources.outcomes import normalize_football_base_input
    path = tmp_path / "named.db"
    ref = observations.append_observation(path, normalize_football_base_input(detail(), observed_at=NOW), observed_at=NOW)
    reader, decoder = dataset._reader, observations._decode_receipt
    held = []
    queries = []
    @contextmanager
    def tracked(path):
        with reader(path) as connection:
            def trace(sql):
                if "FROM context_observations AS r" in sql:
                    queries.append(sql)
            connection.set_trace_callback(trace)
            held.append(True)
            try:
                yield connection
            finally:
                held.pop()
    def decode(row):
        assert not held
        return decoder(row)
    monkeypatch.setattr(dataset, "_reader", tracked)
    monkeypatch.setattr(observations, "_decode_receipt", decode)
    assert observations.freeze_named_receipts(path, (ref,))[0]["digest"] == ref
    assert queries and all("WHERE r.digest=" in query for query in queries)


def test_binding_failure_rolls_back_entire_original_and_concurrent_retry_costs_zero(tmp_path, monkeypatch):
    from contextlib import closing
    from concurrent.futures import ThreadPoolExecutor
    import model_artifacts as a1
    from context_models.football_original_publication import FootballOriginalPublication, BINDING_KIND
    from test_football_original_storage import capture, NOW as CAPTURED, rows_in
    from test_football_base_provenance import history, target
    original = capture(monkeypatch)
    path = tmp_path / "atomic.db"
    session = FootballOriginalPublication(path, None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=0)
    session.freeze(tuple([target(), *history()]))
    kwargs = session.model_kwargs(decision_at=CAPTURED - timedelta(seconds=1))
    kwargs["native_resolver"](tuple([target(), *history()]))
    with closing(a1._connect(path)) as connection, connection:
        connection.execute("CREATE TRIGGER corrupt_binding AFTER INSERT ON artifacts WHEN NEW.kind='" + BINDING_KIND + "' BEGIN UPDATE artifacts SET payload=x'7b7d' WHERE digest=NEW.digest; END")
    with pytest.raises(ValueError):
        kwargs["original_capture"](original)
    assert rows_in(path) == {} and session.remaining_payload_bytes == 2_000_000
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER corrupt_binding")
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: kwargs["original_capture"](original), range(2)))
    report = session.report()
    assert sum(event["inserted_payload_bytes"] == 0 for event in report["events"]) == 1
    assert report["inserted_payload_bytes"] == sum(len(row[1]) for row in rows_in(path).values())


def test_late_binding_trigger_cannot_rewrite_original_dependency_clock(tmp_path, monkeypatch):
    from contextlib import closing
    import model_artifacts as a1
    from context_models.football_original_publication import FootballOriginalPublication, BINDING_KIND
    from test_football_original_storage import capture, NOW as CAPTURED, rows_in
    from test_football_base_provenance import target, history
    original = capture(monkeypatch)
    path = tmp_path / "late-trigger.db"
    session = FootballOriginalPublication(path, None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=0)
    session.freeze(tuple([target(), *history()]))
    kwargs = session.model_kwargs(decision_at=CAPTURED-timedelta(seconds=1))
    kwargs["native_resolver"](tuple([target(), *history()]))
    with closing(a1._connect(path)) as connection, connection:
        connection.execute("CREATE TRIGGER late_clock AFTER INSERT ON artifacts WHEN NEW.kind='" + BINDING_KIND + "' BEGIN UPDATE artifacts SET created_at='2099-01-01T00:00:00.000000Z' WHERE kind='football-original-json-chunk-v1'; END")
    with pytest.raises(ValueError):
        kwargs["original_capture"](original)
    assert rows_in(path) == {}


def test_new_code_fingerprint_is_not_an_old_raw_replay_recipe():
    from context_models.football_original_publication import executed_code_identity, CODE_KIND
    from context_models.replay import _recipe
    from context_models.contracts import ContextContractError, digest
    packet = {"kind": CODE_KIND, "payload": executed_code_identity()}
    with pytest.raises(ContextContractError):
        _recipe({**packet, "digest": digest(packet)}, sport="football")


def test_same_call_binding_rejects_a_different_original_target(tmp_path, monkeypatch):
    from context_models.football_original_publication import FootballOriginalPublication
    from test_football_original_storage import capture, NOW as CAPTURED
    from test_football_base_provenance import target, history
    session = FootballOriginalPublication(tmp_path / "wrong.db", None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=0)
    session.freeze(tuple([target(), *history()]))
    kwargs = session.model_kwargs(decision_at=CAPTURED-timedelta(seconds=1))
    kwargs["native_resolver"](tuple([target(), *history()]))
    other = target()
    other["fixture"]["id"] += 1
    with pytest.raises(ContextIntegrityError):
        kwargs["original_capture"](capture(monkeypatch, current=other))


def test_code_and_empirical_states_are_separate_from_native_capture(tmp_path, monkeypatch):
    from context_models.football_original_publication import FootballOriginalPublication
    from test_football_original_storage import capture, NOW as CAPTURED
    from test_football_base_provenance import target, history
    session = FootballOriginalPublication(tmp_path / "states.db", None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=0)
    original = capture(monkeypatch)
    session.freeze(tuple([target(), *history()]))
    kwargs = session.model_kwargs(decision_at=CAPTURED-timedelta(seconds=1))
    kwargs["native_resolver"](tuple([target(), *history()]))
    kwargs["original_capture"](original)
    event = session.report()["events"][0]
    assert event["source_state"] == "partial"
    assert event["code_state"] == "execution-fingerprint-only"
    assert event["empirical_state"] == "not-evaluated"


@pytest.mark.parametrize("full_family", [False, True])
def test_season380_publication_volume(tmp_path, monkeypatch, capsys, full_family):
    from time import perf_counter
    from contextlib import closing
    from datetime import datetime, timezone
    from test_football_base_provenance import fixture
    import challenge_engine as engine
    import football_original
    import model_artifacts as a1
    from context_models.football_original_publication import FootballOriginalPublication, CODE_KIND, BINDING_KIND
    from test_football_original_storage import rows_in
    from context_models.football_original_storage import load_original
    rows = [fixture(i+1, i//4, *([(1,3),(4,2),(5,6),(7,8)][i%4])) for i in range(380)]
    current = fixture(10001, 100, 1, 2, xg=False, goals=False)
    if full_family:
        current["fixture"]["referee"] = "Test Ref"
        for i, row in enumerate(rows):
            row["fixture"]["referee"] = "Test Ref"
            row["challenge_stats"].update(corners_home=3+i%7, corners_away=2+i%4,
                yellow_cards_home=1+i%4, yellow_cards_away=i%3)
    at = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(football_original, "_capture_now", lambda: at)
    path = tmp_path / "volume.db"
    with closing(a1._connect(path)):
        pass
    empty_size = path.stat().st_size
    started = perf_counter()
    session = FootballOriginalPublication(path, None, max_publication_payload_bytes=4_000_000,
        max_worker_payload_bytes=5_000_000, max_source_payload_bytes=0)
    session.freeze(tuple([current, *rows]))
    engine.fixture_market_probabilities(current, rows, **session.model_kwargs(decision_at=at-timedelta(seconds=1)))
    initial_seconds = perf_counter()-started
    first_size = path.stat().st_size
    saved = rows_in(path)
    import json
    binding = json.loads(next(row[1] for row in saved.values() if row[0] == BINDING_KIND))
    original = load_original(path, binding["original_manifest_digest"])
    first_payload = session.inserted_payload_bytes
    at += timedelta(seconds=1)
    started = perf_counter()
    engine.fixture_market_probabilities(current, rows, **session.model_kwargs(decision_at=at-timedelta(seconds=1)))
    repeat_seconds = perf_counter()-started
    repeat_payload = session.inserted_payload_bytes-first_payload
    assert first_payload < len(original._bytes)
    assert 0 < repeat_payload < first_payload
    with capsys.disabled():
        print({"full_family": full_family, "expanded_bytes": len(original._bytes),
            "initial_payload_bytes": first_payload, "code_bytes": sum(len(row[1]) for row in saved.values() if row[0] == CODE_KIND),
            "binding_bytes": sum(len(row[1]) for row in saved.values() if row[0] == BINDING_KIND),
            "initial_sqlite_growth": first_size-empty_size, "repeat_payload_bytes": repeat_payload,
            "repeat_sqlite_growth": path.stat().st_size-first_size,
            "initial_seconds": initial_seconds, "repeat_seconds": repeat_seconds})


def test_partial_worker_budget_keeps_next_forecast_without_orphans(tmp_path, monkeypatch):
    from context_models.football_original_publication import FootballOriginalPublication
    from test_football_original_storage import capture, NOW as CAPTURED, rows_in
    from test_football_base_provenance import target, history
    import challenge_engine as engine
    import football_original
    first = capture(monkeypatch)
    path = tmp_path / "partial.db"
    session = FootballOriginalPublication(path, None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=0)
    session.freeze(tuple([target(), *history()]))
    kwargs = session.model_kwargs(decision_at=CAPTURED-timedelta(seconds=1))
    kwargs["native_resolver"](tuple([target(), *history()]))
    kwargs["original_capture"](first)
    actual_first_cost = session.inserted_payload_bytes
    path = tmp_path / "exact-worker-budget.db"
    session = FootballOriginalPublication(path, None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=actual_first_cost, max_source_payload_bytes=0)
    session.freeze(tuple([target(), *history()]))
    kwargs = session.model_kwargs(decision_at=CAPTURED-timedelta(seconds=1))
    kwargs["native_resolver"](tuple([target(), *history()]))
    kwargs["original_capture"](first)
    before = rows_in(path)
    assert session.remaining_payload_bytes == 0
    monkeypatch.setattr(football_original, "_capture_now", lambda: CAPTURED+timedelta(seconds=1))
    actual = engine.fixture_market_probabilities(target(), history(),
        **session.model_kwargs(decision_at=CAPTURED))
    expected = engine.fixture_market_probabilities(target(), history())
    assert actual == expected
    assert [event["status"] for event in session.report()["events"]] == ["partial", "budget-exhausted"]
    assert rows_in(path) == before


def test_domestic_same_provider_cache_reuses_original_response_clock(tmp_path, monkeypatch):
    import challenge_15k
    from test_football_context_provider import Response
    from context_sources.football_capture import capture_football_worker
    from context_observations import freeze_named_receipts
    raw = detail()
    raw["fixture"]["status"]["short"] = "FT"
    raw["fixture"]["date"] = "2026-09-01T12:00:00+00:00"
    raw["goals"] = {"home": 2, "away": 1}
    owner, _ = provider(monkeypatch, details=payload([raw]))
    calls = []
    def fetch(url, **kwargs):
        calls.append(url.rsplit("/", 1)[-1])
        return Response(payload([{"league": {"id": 94, "type": "League"}, "country": {"name": "Portugal"},
            "seasons": [{"year": 2026, "current": True, "start": "2026-01-01", "end": "2026-12-31"}]}])
            if calls[-1] == "leagues" else payload([raw]))
    monkeypatch.setattr(challenge_15k, "api_football_get", fetch)
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "cache.db"
    with capture_football_worker(owner, path=path, baseline_enabled=True) as capture:
        first = owner.domestic_team_history(raw["teams"]["home"]["id"], NOW.date(), NOW)
        second = owner.domestic_team_history(raw["teams"]["home"]["id"], NOW.date(), NOW)
        assert first == second and calls == ["leagues", "fixtures"]
        refs = capture.flush_baseline_receipts(tuple(second["fixtures"]), max_new_payload_bytes=100_000)
        receipts = freeze_named_receipts(path, tuple(next(iter(refs.values()))))
        assert receipts[0]["observed_at"] == "2026-09-09T09:00:00.000000Z"
    with capture_football_worker(owner, path=path, baseline_enabled=True) as capture:
        cached = owner.domestic_team_history(raw["teams"]["home"]["id"], NOW.date(), NOW)
        refs = capture.flush_baseline_receipts(tuple(cached["fixtures"]), max_new_payload_bytes=100_000)
        assert all(not values for values in refs.values())
        assert calls == ["leagues", "fixtures"]


@pytest.mark.parametrize("entry", ["scan", "model-refresh", "context-only"])
def test_automatic_worker_explicit_opt_in_owns_capture_and_serializes_metadata(tmp_path, monkeypatch, entry):
    import wettfinder_automation as automation
    import runtime_paths
    import challenge_engine as engine
    from config_loader import AppConfig
    from test_football_base_provenance import history
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    monkeypatch.setattr(automation, "ChallengeDataProvider", lambda *a: owner)
    path = tmp_path / "worker.db"
    monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", path)
    rows = history()
    for row in rows:
        for side in ("home", "away"):
            if row["teams"][side]["id"] == 1:
                row["teams"][side]["id"] = 215
            elif row["teams"][side]["id"] == 2:
                row["teams"][side]["id"] = 211
    def work(provider_arg, *args, **kwargs):
        assert provider_arg is owner and owner._context_capture is not None
        fixture = owner.details_by_fixture([1575469])[1575469]
        publication = kwargs.get("original_publication")
        result = {}
        if entry == "context-only":
            assert publication is None and not owner._context_capture.baseline_enabled
        else:
            assert publication is not None and owner._context_capture.baseline_enabled
            publication.freeze(tuple([fixture, *rows]))
            engine.fixture_market_probabilities(fixture, rows,
                **publication.model_kwargs(decision_at=NOW+timedelta(seconds=1)))
            result["football_original_capture"] = publication.report()
        return result
    monkeypatch.setattr(automation, "scan_daily_challenge", work)
    monkeypatch.setattr(automation, "refresh_fixture_models", work)
    monkeypatch.setattr(automation, "refresh_discovered_candidates", work)
    config = AppConfig(api_football_key="test-key", weather_key=None)
    limits = {"max_publication_payload_bytes": 2_000_000,
        "max_worker_payload_bytes": 2_000_000, "max_source_payload_bytes": 100_000}
    if entry == "scan":
        result = automation._default_football_scan(NOW.date(), config, original_capture_limits=limits)
    else:
        result = automation._default_football_context_refresh([], NOW.date(), NOW, config,
            recompute_models=entry == "model-refresh", original_capture_limits=limits)
    assert owner._context_capture is None and len(calls) == 1
    if entry == "context-only":
        assert "football_original_capture" not in result
    else:
        assert result["football_original_capture"]["published_count"] == 1
        serialized = automation._football_state_from_snapshot(result, attempted_at=NOW, search_date=NOW.date())
        assert serialized["football_original_capture"] == result["football_original_capture"]
        merged = automation._merge_context_refresh(serialized, result, fixture_ids=[], checked_at=NOW)
        assert merged["football_original_capture"] == result["football_original_capture"]


def test_legacy_naive_history_still_computes_when_native_union_is_unavailable(tmp_path):
    from test_football_base_provenance import target, history
    from context_models.football_original_publication import FootballOriginalPublication, original_capture_report_fields
    import challenge_engine as engine
    from datetime import datetime, timezone
    rows = history()
    rows[0]["fixture"]["date"] = rows[0]["fixture"]["date"].replace("+00:00", "")
    normal = engine.fixture_market_probabilities(target(), rows)
    session = FootballOriginalPublication(tmp_path / "legacy.db", None, max_publication_payload_bytes=2_000_000,
        max_worker_payload_bytes=2_000_000, max_source_payload_bytes=0)
    session.freeze(tuple([target(), *rows]))
    actual = engine.fixture_market_probabilities(target(), rows, **session.model_kwargs(decision_at=datetime.now(timezone.utc)))
    assert actual == normal
    report = session.report()
    assert report["events"][0]["status"] == "unavailable"
    assert report["events"][0]["unavailable_reason"] == "selected-native-provenance-unavailable"
    assert report["published_count"] == 0 and not (tmp_path / "legacy.db").exists()
    assert original_capture_report_fields({"football_original_capture": report})["football_original_capture"] == report
