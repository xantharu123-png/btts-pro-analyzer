"""Real existing requests/model/worker/SQLite, never provider qualification."""
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

import sports_prematch as model
import wettfinder_automation as worker
from config_loader import AppConfig
from context_sources import team_sports_capture as capture
from scanners import basketball_scanner as scanner_module
from test_team_sports_live_original import NOW, raw_inputs
from test_team_sports_binding import source_reply
from test_wettfinder_automation import _football_snapshot

SPORTS = ("basketball", "ice_hockey")


@pytest.fixture
def live_worker(tmp_path, monkeypatch):
    def make(sport, *, risk=True, history_error=False, start_offset=timedelta(hours=6)):
        event, history = raw_inputs(sport)
        event.update(home_team_id="5", away_team_id="4", home_team="Team 5", away_team="Team 4")
        event["starts_at"] = (NOW + start_offset).isoformat()
        body = source_reply("ESPN" if sport == "basketball" else "NHL", event, target=True)
        state = dict(now=NOW, requests=0, history=0, predictions=[], bodies=[body],
            history_error=history_error, on_history=None, source_wrapper=None, history_loader=None)
        def get(url, **kwargs):
            state["requests"] += 1
            def decode():
                state["now"] += timedelta(seconds=1)
                return {"data": []} if "euroleague" in url else deepcopy(state["bodies"][-1])
            query = urlencode(kwargs.get("params") or {})
            return SimpleNamespace(status_code=200, history=[], url=url + ("?" + query if query else ""), json=decode)
        def load(**kwargs):
            state["history"] += 1
            state["now"] += timedelta(seconds=1)
            if state["on_history"] is not None:
                state["on_history"]()
            if state["history_error"]:
                raise RuntimeError("synthetic unavailable")
            return state["history_loader"]() if state["history_loader"] else deepcopy(history)
        real = model.predict_prematch
        def predict(*args, **kwargs):
            result = real(*args, **kwargs)
            state["predictions"].append(result)
            return result
        monkeypatch.setattr(scanner_module.requests, "get", get)
        monkeypatch.setattr(capture, "_receipt_now", lambda: state["now"])
        monkeypatch.setattr(model, "predict_prematch", predict)
        import runtime_paths
        monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", tmp_path / "context_models.db")
        fn = worker._default_basketball_risk_source if sport == "basketball" else worker._default_ice_hockey_risk_source
        football = _football_snapshot(NOW)
        football.update(shortlist=[], riskobet_source_candidates=[])
        def source():
            result = fn(NOW.date(), NOW, load)
            return state["source_wrapper"](result) if state["source_wrapper"] else result
        def run(**kwargs):
            return worker.run_wettfinder(state_path=tmp_path / "wettfinder.json",
                clock=lambda: state["now"], config=AppConfig(api_football_key="synthetic-unused"),
                football_scanner=lambda day: football, football_context_refresher=lambda *args: {},
                tennis_loader=lambda **kw: [], esports_loader=lambda **kw: [],
                riskobet_enabled=kwargs.pop("risk", risk), riskobet_sources={sport: source},
                **kwargs)
        return SimpleNamespace(run=run, state=state, event=event, history=history,
            path=tmp_path / "wettfinder.json", context_path=tmp_path / "context_models.db")
    return make


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("risk", [True, False])
def test_real_worker_same_baseline_visible_with_risk_enabled_or_disabled(live_worker, sport, risk):
    case = live_worker(sport, risk=risk)
    doc = case.run()
    rows = [row for row in doc["model_candidates"] if row["source"] == f"{sport}_baseline"]
    assert len(rows) == len(case.state["predictions"]) == 1
    row = rows[0]
    p = case.state["predictions"][0]
    assert row["probability"].hex() == max(p.p_home, p.p_away).hex()
    assert row["probability_haircut"] is row["conservative_probability"] is row["minimum_odds"] is None
    assert row["evidence_stage"] == "RESEARCH" and "context_ref" not in row
    assert row["baseline_view"]["snapshot"]["modeled_at"] == case.state["now"].isoformat()
    assert row["baseline_view"] == doc["team_sports_baselines"][sport]["entries"][0]
    assert not doc["candidates"] and not doc["challenge_release_candidates"]
    if risk:
        from riskobet_automation import load_latest_riskobet
        risk_run = load_latest_riskobet(db_path=case.path.with_name("riskobet.db"),
            latest_path=case.path.with_name("riskobet_latest.json"), rehydrate=True)
        assert row["baseline_view"]["snapshot"]["snapshot_id"] == risk_run.snapshots[0].snapshot_id
        assert risk_run.snapshots[0].context_ref is None
    else:
        assert "riskobet" not in doc and not case.path.with_name("riskobet.db").exists()


@pytest.mark.parametrize("sport", SPORTS)
def test_six_hour_reuse_is_price_tab_and_risk_switch_independent(live_worker, sport):
    case = live_worker(sport, risk=False)
    first = case.run()
    counts = case.state["requests"], case.state["history"], len(case.state["predictions"])
    second = case.run(risk=True)
    assert counts == (case.state["requests"], case.state["history"], len(case.state["predictions"]))
    assert first["team_sports_baselines"] == second["team_sports_baselines"]
    assert first["model_candidates"] == second["model_candidates"]


@pytest.mark.parametrize("sport", SPORTS)
def test_closed_identity_corruption_is_not_reused_or_silently_recomputed(live_worker, sport):
    case = live_worker(sport)
    document = case.run()
    document["team_sports_baselines"][sport]["entries"][0]["prediction"]["p_home"] = 0.99
    case.path.write_text(json.dumps(document), encoding="utf-8")
    count = case.state["requests"]
    with pytest.raises(ValueError, match="baseline"):
        case.run()
    assert case.state["requests"] == count


@pytest.mark.parametrize("sport", SPORTS)
def test_null_uncertainty_readback_card_cannot_be_a_money_candidate(live_worker, sport):
    from ev_signal_sources import automated_wettfinder_forecasts
    from wettfinder_surface import build_wettfinder_card, wettfinder_recommendation_candidate
    case = live_worker(sport)
    case.run()
    signals = automated_wettfinder_forecasts(case.path, now=case.state["now"])
    assert len(signals) == 1
    signal = signals[0]
    assert signal.probability_haircut is signal.minimum_odds is None
    card = build_wettfinder_card(signal, now=case.state["now"])
    assert card.cautious_probability is card.value_threshold is None
    assert not card.confirmed_tip and card.price_code == "BOUNDARY_UNAVAILABLE"
    assert "konkrete Modellgrundlagen fehlen" not in card.analysis_basis
    with pytest.raises(ValueError, match="boundary"):
        wettfinder_recommendation_candidate(signal)


@pytest.mark.parametrize("sport", SPORTS)
def test_actual_app_loop_renders_unknown_boundary_without_price_or_money_actions(live_worker, sport):
    import ast
    from contextlib import nullcontext
    from pathlib import Path
    from ev_signal_sources import automated_wettfinder_forecasts
    import wettfinder_surface as surface
    case = live_worker(sport)
    case.run()
    signals = automated_wettfinder_forecasts(case.path, now=case.state["now"])
    assert len(signals) == 1
    path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    renderer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_render_automated_daily_selection")
    loop = next(n for n in renderer.body if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == "signal")
    actions = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_render_wettfinder_card_actions")
    def forbidden(*args, **kwargs):
        pytest.fail("null-boundary forecast reached price/money evaluation")
    notes = []
    namespace = dict(signals=signals, rows=[], evaluation_now=case.state["now"], bankroll=100,
        _automated_signal_candidate=surface.wettfinder_recommendation_candidate,
        wettfinder_quote_binding_candidate=surface.wettfinder_quote_binding_candidate,
        evaluate_reference_price=forbidden, _automatic_release_overlay=forbidden,
        build_wettfinder_card=surface.build_wettfinder_card,
        render_price_decision=forbidden,
        st=SimpleNamespace(container=lambda **kwargs: nullcontext(), caption=notes.append))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[loop, actions], type_ignores=[])), str(path), "exec"), namespace)
    assert len(namespace["rows"]) == 1
    signal, card, candidate, binding, evaluation = namespace["rows"][0]
    assert card.model_probability == signals[0].probability and not card.confirmed_tip
    namespace["_render_wettfinder_card_actions"](signal, card, candidate, binding, evaluation)
    assert notes and candidate is evaluation is None


@pytest.mark.parametrize("sport", SPORTS)
def test_duplicate_actual_scanner_result_is_calculated_once(live_worker, monkeypatch, sport):
    name = "get_upcoming_games" if sport == "basketball" else "get_upcoming_nhl_games"
    real = getattr(scanner_module.BasketballScanner, name)
    def repeated(*args, **kwargs):
        rows = real(*args, **kwargs)
        return rows + deepcopy(rows)
    monkeypatch.setattr(scanner_module.BasketballScanner, name, repeated)
    case = live_worker(sport)
    doc = case.run()
    assert len(doc["model_candidates"]) == len(case.state["predictions"]) == 1


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("mutation", ["probability", "discarded", "version"])
def test_captured_result_cannot_be_replaced_by_a_divergent_risk_batch(live_worker, sport, mutation):
    from dataclasses import replace
    case = live_worker(sport)
    def damage(batch):
        if mutation == "discarded":
            return replace(batch, snapshots=(), candidates=())
        candidate = batch.candidates[0]
        if mutation == "probability":
            return replace(batch, candidates=(replace(candidate, model_probability=0.1),))
        snapshot = replace(batch.snapshots[0], model_version="not-the-original")
        return replace(batch, snapshots=(snapshot,), candidates=(replace(candidate, snapshot_id=snapshot.snapshot_id),))
    case.state["source_wrapper"] = damage
    with pytest.raises(ValueError, match="baseline"):
        case.run()
    assert not case.path.exists() and not case.path.with_name("riskobet.db").exists()


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("mutation", ["inactive", "future_checked"])
def test_reader_validates_all_owning_batches_even_without_visible_rows(live_worker, sport, mutation):
    from ev_signal_sources import automated_wettfinder_snapshot
    case = live_worker(sport)
    doc = case.run()
    batch = doc["team_sports_baselines"][sport]
    if mutation == "inactive":
        doc["model_candidates"] = []
        batch["schema"] = True
    else:
        import hashlib
        batch["checked_at"] = (case.state["now"] + timedelta(microseconds=1)).isoformat()
        body = {key: value for key, value in batch.items() if key != "digest"}
        batch["digest"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    case.path.write_text(json.dumps(doc), encoding="utf-8")
    loaded = automated_wettfinder_snapshot(case.path, now=case.state["now"])
    assert loaded.status is None and loaded.forecasts == ()


def correction(case, sport, kind, *, observed=None):
    """Real owning normalization/SQLite; entirely synthetic native responses."""
    from test_team_sports_binding import native_game, record
    provider = "ESPN" if sport == "basketball" else "NHL"
    body = deepcopy(case.state["bodies"][-1])
    game = native_game(provider, body)
    if kind in ("cancelled", "started", "unknown"):
        if provider == "ESPN":
            game["status"] = {"type": dict(state={"cancelled": "post", "started": "in", "unknown": "?"}[kind],
                name={"cancelled": "STATUS_CANCELED", "started": "STATUS_IN_PROGRESS", "unknown": "?"}[kind], completed=False)}
        else:
            game["gameState"] = {"cancelled": "CANC", "started": "LIVE", "unknown": "?"}[kind]
    elif kind == "opponent":
        if provider == "ESPN": game["competitors"][1]["team"]["id"] = "66"
        else: game["awayTeam"]["id"] = 66
    elif kind == "incomplete":
        if provider == "ESPN": game["competitors"] = game["competitors"][:1]
        else: game.pop("awayTeam")
    return record(case.context_path, provider, body, target=True,
        observed=case.state["now"] if observed is None else observed)


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("kind", ["cancelled", "started", "unknown", "opponent", "incomplete"])
def test_native_correction_during_history_prevents_target_calculation(live_worker, sport, kind):
    case = live_worker(sport)
    case.state["on_history"] = lambda: correction(case, sport, kind)
    doc = case.run()
    assert not doc["model_candidates"] and not case.state["predictions"]
    assert not doc["team_sports_baselines"][sport]["entries"]


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("kind", ["cancelled", "started", "unknown", "opponent", "incomplete"])
def test_new_native_correction_within_six_hours_withdraws_both_views_without_refit(live_worker, sport, kind):
    from riskobet_automation import load_latest_riskobet
    case = live_worker(sport)
    first = case.run()
    counts = case.state["requests"], case.state["history"], len(case.state["predictions"])
    case.state["now"] += timedelta(seconds=1)
    correction(case, sport, kind)
    doc = case.run()
    assert counts == (case.state["requests"], case.state["history"], len(case.state["predictions"]))
    assert not doc["model_candidates"]
    latest = load_latest_riskobet(db_path=case.path.with_name("riskobet.db"),
        latest_path=case.path.with_name("riskobet_latest.json"), rehydrate=True)
    assert not latest.snapshots and not latest.candidates
    # Historical model identity stays intact; only current views withdraw it.
    assert doc["team_sports_baselines"] == first["team_sports_baselines"]


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_actual_decision_clock_start_boundary_after_history(live_worker, sport, offset):
    seconds = 3 if sport == "basketball" else 2
    case = live_worker(sport, start_offset=timedelta(seconds=seconds, microseconds=offset))
    doc = case.run()
    assert len(case.state["predictions"]) == len(doc["model_candidates"]) == int(offset > 0)


@pytest.mark.parametrize("sport", SPORTS)
def test_already_started_target_does_not_spend_history_budget(live_worker, sport):
    case = live_worker(sport, start_offset=timedelta(seconds=-1))
    doc = case.run()
    assert not doc["model_candidates"] and not case.state["predictions"]
    assert case.state["history"] == 0


@pytest.mark.parametrize("sport", SPORTS)
def test_failed_history_is_not_called_twice_and_retries_next_worker(live_worker, sport):
    case = live_worker(sport, history_error=True)
    failed = case.run()
    assert case.state["history"] == 1 and not case.state["predictions"]
    assert failed["team_sports_baselines"][sport]["status"] == "failed"
    case.state["history_error"] = False
    recovered = case.run()
    assert len(recovered["model_candidates"]) == 1
    assert case.state["history"] == 2 and len(case.state["predictions"]) == 1
    assert case.state["requests"] == (4 if sport == "basketball" else 2)


@pytest.mark.parametrize("sport", SPORTS)
def test_exact_six_hour_boundary_refreshes_once(live_worker, sport):
    from datetime import datetime
    case = live_worker(sport, start_offset=timedelta(hours=7))
    first = case.run()
    checked = datetime.fromisoformat(first["team_sports_baselines"][sport]["checked_at"])
    case.state["now"] = checked + timedelta(hours=6, microseconds=-1)
    before = case.run()
    assert len(case.state["predictions"]) == case.state["history"] == 1
    assert before["team_sports_baselines"] == first["team_sports_baselines"]
    case.state["now"] = checked + timedelta(hours=6)
    after = case.run()
    assert len(case.state["predictions"]) == case.state["history"] == 2
    assert after["team_sports_baselines"][sport]["checked_at"] != checked.isoformat()


@pytest.mark.parametrize("sport", SPORTS)
def test_capture_clock_cannot_be_backdated(live_worker, monkeypatch, sport):
    case = live_worker(sport)
    monkeypatch.setattr(capture, "_receipt_now", lambda: case.state["now"] + timedelta(seconds=30))
    with pytest.raises(ValueError, match="baseline"):
        case.run()
    assert not case.state["predictions"] and not case.path.exists()


@pytest.mark.parametrize("sport", SPORTS)
def test_parallel_real_workers_hold_ipc_lock_across_read_acquire_publish(live_worker, monkeypatch, sport):
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from threading import Event, RLock
    from pathlib import Path
    import subprocess
    import sys
    import team_sports_baseline as baseline
    case = live_worker(sport)
    reached, release, attempts, mutex = Event(), Event(), Queue(), RLock()
    class ObservedLock:
        def __enter__(self):
            attempts.put(True)  # Instrument only entry; real RLock stays held.
            return mutex.__enter__()
        def __exit__(self, *args):
            return mutex.__exit__(*args)
    monkeypatch.setitem(baseline._LOCKS, str(case.path.resolve()), ObservedLock())
    def pending_history():
        reached.set()
        assert release.wait(8), "private worker was not released"
    case.state["on_history"] = pending_history
    child = """
import os, sys
with open(sys.argv[1], 'a+b') as handle:
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('blocked')
    else:
        print('acquired')
        if os.name == 'nt':
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
"""
    def ipc_probe():
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", child, str(case.path) + ".lock"],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=5)
        assert proc.returncode == 0 and not proc.stderr
        return proc.stdout.strip()
    with ThreadPoolExecutor(max_workers=2) as executor:
        one = executor.submit(case.run)
        try:
            assert attempts.get(timeout=5) and reached.wait(5)
            two = executor.submit(case.run)
            assert attempts.get(timeout=5)  # Both actually requested this lock.
            assert ipc_probe() == "blocked"
            assert case.state["history"] == 1 and not case.state["predictions"]
        finally:
            release.set()
        first, second = one.result(timeout=8), two.result(timeout=8)
    assert ipc_probe() == "acquired"
    assert first["team_sports_baselines"] == second["team_sports_baselines"]
    assert len(case.state["predictions"]) == case.state["history"] == 1
    assert case.state["requests"] == (2 if sport == "basketball" else 1)


@pytest.mark.parametrize("sport", SPORTS)
def test_warm_completed_store_is_only_legacy_baseline_not_native_history_proof(live_worker, sport):
    from contextlib import closing
    import sqlite3
    from scanners.completed_history import CompletedHistoryStore
    from context_sources.team_sports_status import team_sport_observations_as_of
    case = live_worker(sport)
    store = CompletedHistoryStore(case.path.with_name("history.db"), clock=lambda: NOW-timedelta(minutes=1))
    provider = "ESPN" if sport == "basketball" else "NHL"
    rows = [{**row, "event_id": row["provider_event_id"]} for row in case.history]
    store.record(provider, "synthetic-existing-cache", rows)
    store.clock = lambda: case.state["now"]
    before = store.path.read_bytes()
    case.state["history_loader"] = lambda: store.read((provider,), NOW.date()-timedelta(days=365), NOW.date())
    doc = case.run()
    assert len(doc["model_candidates"]) == 1 and case.state["predictions"][0].training_games == 84
    assert store.path.read_bytes() == before  # No historical rewrite/migration.
    pool = team_sport_observations_as_of(case.context_path, cutoff=case.state["now"])
    assert len(pool) == 1 and pool[0]["payload"]["request"]["phase"] == "schedule"
    with closing(sqlite3.connect(case.context_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("field", ["neutral", "season", "native-observer"])
def test_unqualified_native_metadata_does_not_erase_valid_legacy_baseline(live_worker, monkeypatch, sport, field):
    from test_team_sports_binding import native_game
    case = live_worker(sport)
    provider = "ESPN" if sport == "basketball" else "NHL"
    game = native_game(provider, case.state["bodies"][-1])
    if field == "neutral": game.pop("neutralSite")
    elif field == "season":
        if provider == "ESPN": case.state["bodies"][-1].pop("season")
        else: game.pop("season")
    else:
        name = "observe_espn_basketball_schedule" if provider == "ESPN" else "observe_nhl_schedule"
        monkeypatch.setattr(scanner_module, name, lambda *args: None)
    doc = case.run()
    assert len(doc["model_candidates"]) == len(case.state["predictions"]) == 1
    row = doc["model_candidates"][0]
    assert row["probability"].hex() == max(case.state["predictions"][0].p_home, case.state["predictions"][0].p_away).hex()
    assert row["evidence_stage"] == "RESEARCH" and "context_ref" not in row


@pytest.mark.parametrize("sport", SPORTS)
def test_b1_only_historical_cancellation_is_explicitly_not_a_legacy_cache_rewrite(live_worker, sport):
    from test_team_sports_binding import native_game, record
    case = live_worker(sport)
    provider = "ESPN" if sport == "basketball" else "NHL"
    row = deepcopy(case.history[5])
    body = source_reply(provider, row)
    game = native_game(provider, body)
    if provider == "ESPN":
        game["status"]["type"] = dict(state="post", name="STATUS_CANCELED", completed=False)
    else: game["gameState"] = "CANC"
    record(case.context_path, provider, body, observed=NOW-timedelta(seconds=1))
    historical = deepcopy(case.history)
    doc = case.run()
    # Deliberate (a)/(b) boundary: P4b2 is NOT yet used to replace a model's
    # input history. Status receipts are not backfilled into the legacy store.
    assert case.history == historical and len(doc["model_candidates"]) == 1
    assert case.state["predictions"][0].training_games == len(historical)
    assert "context_ref" not in doc["model_candidates"][0]


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_native_correction_causal_cutoff_and_simultaneous_conflict(live_worker, sport, offset):
    case = live_worker(sport)
    first = case.run()
    correction(case, sport, "cancelled", observed=case.state["now"]+timedelta(microseconds=offset))
    doc = case.run()
    assert len(doc["model_candidates"]) == int(offset > 0)
    assert first["team_sports_baselines"] == doc["team_sports_baselines"]
    assert len(case.state["predictions"]) == 1


@pytest.mark.parametrize("sport", SPORTS)
def test_missing_boundary_copy_never_claims_a_heuristic_discount_was_computed(live_worker, sport):
    from ev_signal_sources import automated_wettfinder_forecasts
    from wettfinder_surface import build_wettfinder_card, render_top_card_html
    case = live_worker(sport)
    case.run()
    signal, = automated_wettfinder_forecasts(case.path, now=case.state["now"])
    card = build_wettfinder_card(signal, now=case.state["now"])
    markup = render_top_card_html(card)
    assert "Modell mit heuristischem" not in markup
    assert "Preisgrenze" in markup and "keine" in markup


@pytest.mark.parametrize("sport", SPORTS)
def test_price_filter_and_render_consume_persisted_view_without_model_or_io(live_worker, monkeypatch, sport):
    from ev_signal_sources import automated_wettfinder_forecasts
    from test_wettfinder_surface import _quote
    import wettfinder_surface as surface
    case = live_worker(sport)
    case.run()
    def forbidden(*args, **kwargs): pytest.fail("pure consumer invoked fetch/fit/predict/price boundary")
    monkeypatch.setattr(scanner_module.requests, "get", forbidden)
    for name in ("predict_prematch", "_fit", "_predict"):
        monkeypatch.setattr(model, name, forbidden)
    monkeypatch.setattr(surface, "wettfinder_reference_price_status", forbidden)
    signals = automated_wettfinder_forecasts(case.path, now=case.state["now"])
    assert len(signals) == 1
    signal = signals[0]
    baseline = surface.build_wettfinder_card(signal, now=case.state["now"])
    for odds in ((1.01, 1.02, 1.03), (99.0, 199.0, 999.0)):
        priced = surface.build_wettfinder_card(signal, _quote(signal, odds, fetched_at=case.state["now"]), now=case.state["now"])
        assert priced == baseline  # Free ID equality is not a qualified quote.
    for sport_filter in ("Alle", signal.sport, "Cricket"):
        surface.compose_wettfinder_catalog([baseline], sport_filter=sport_filter)
    for method in (surface.render_top_card_html, surface.render_compact_row_html):
        assert signal.selection in method(baseline)
    for kwargs in (dict(price_evaluation=object()), dict(release_overlay=object())):
        with pytest.raises(ValueError, match="boundary"):
            surface.build_wettfinder_card(signal, now=case.state["now"], **kwargs)


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("change", ["zero", "threshold", "sport", "release", "empty-view", "missing-marker", "statistical"])
def test_unknown_boundary_is_not_a_generic_numeric_or_release_bypass(live_worker, sport, change):
    from dataclasses import replace
    from ev_signal_sources import automated_wettfinder_forecasts
    case = live_worker(sport)
    case.run()
    signal, = automated_wettfinder_forecasts(case.path, now=case.state["now"])
    options = dict(zero=dict(probability_haircut=0), threshold=dict(minimum_odds=1.50),
        sport=dict(sport="Fussball", source="football_challenge"), release=dict(evidence_stage="RELEASED"),
        **{"empty-view": dict(baseline_view={}), "missing-marker": dict(uncertainty_contract=None)},
        statistical=dict(statistical_release_passed=True))
    with pytest.raises(ValueError):
        replace(signal, **options[change])


@pytest.mark.parametrize("sport", [*SPORTS, "cricket"])
def test_actual_parent_research_output_ids_float_bytes_and_default_math_are_unchanged(sport):
    import subprocess
    import types
    import sys
    from pathlib import Path
    import riskobet_candidates as current
    from test_sports_prematch import event, history
    source = subprocess.run(["git", "show", "898652bbd2343cef6d67e8573f32c14b891f1057:riskobet_candidates.py"],
        cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True).stdout.decode("utf-8-sig")
    parent = types.ModuleType("_p4b3_parent_risk_candidates")
    sys.modules[parent.__name__] = parent
    try:
        exec(compile(source, "898652b:riskobet_candidates.py", "exec"), parent.__dict__)
        target, rows = event(sport, home_team_id="5", away_team_id="4",
            home_team="Team 5", away_team="Team 4", source_observed_at=NOW.isoformat()), history(sport)
        before = parent.adapt_research_matchwinner(sport, target, rows, modeled_at=NOW)
        after = current.adapt_research_matchwinner(sport, target, rows, modeled_at=NOW)
        assert before.snapshot.to_dict() == after.snapshot.to_dict()
        assert [c.to_dict() for c in before.candidates] == [c.to_dict() for c in after.candidates]
        for old, new in zip(before.candidates, after.candidates):
            assert old.model_probability == new.model_probability
            if old.model_probability is not None:
                assert old.model_probability.hex() == new.model_probability.hex()
    finally:
        del sys.modules[parent.__name__]


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("mutation", ["completed-errors", "partial-empty", "failed-empty", "date", "view-schema",
    "context-ref", "pair", "count-bool", "eval-bool", "unknown-price", "missing-entry", "duplicate"])
def test_complete_batch_reader_rejects_inconsistent_rehashed_known_transport(live_worker, sport, mutation):
    from ev_signal_sources import automated_wettfinder_snapshot
    from team_sports_baseline import _digest
    case = live_worker(sport)
    doc = case.run()
    batch = doc["team_sports_baselines"][sport]
    view = batch["entries"][0]
    if mutation == "completed-errors": batch["errors"] = ["source_failed"]
    elif mutation == "partial-empty": batch["status"] = "partial"
    elif mutation == "failed-empty":
        batch.update(status="failed", entries=[])
        doc["model_candidates"] = []
    elif mutation == "date": batch["target_date"] = (NOW.date()+timedelta(days=1)).isoformat()
    elif mutation == "view-schema": view["schema"] = True
    elif mutation == "context-ref": view["snapshot"]["context_ref"] = None
    elif mutation == "pair": view["prediction"]["p_away"] = 0.999
    elif mutation == "count-bool": view["prediction"]["home_games"] = True
    elif mutation == "eval-bool": view["prediction"]["evaluation"]["count"] = True
    elif mutation == "unknown-price": view["prediction"]["closing_odds"] = 999
    elif mutation == "missing-entry": batch["entries"] = []
    elif mutation == "duplicate": batch["entries"].append(deepcopy(view))
    view["digest"] = _digest({k: v for k, v in view.items() if k != "digest"})
    batch["digest"] = _digest({k: v for k, v in batch.items() if k != "digest"})
    case.path.write_text(json.dumps(doc), encoding="utf-8")
    result = automated_wettfinder_snapshot(case.path, now=case.state["now"])
    assert result.status is None and result.forecasts == ()


@pytest.mark.parametrize("sport", SPORTS)
def test_duplicate_conflicting_scanner_projection_rejected_before_model(live_worker, monkeypatch, sport):
    name = "get_upcoming_games" if sport == "basketball" else "get_upcoming_nhl_games"
    real = getattr(scanner_module.BasketballScanner, name)
    def conflicting(*args, **kwargs):
        rows = real(*args, **kwargs)
        changed = deepcopy(rows[0])
        changed["home_team_id"] = "different-known-team"
        return [*rows, changed]
    monkeypatch.setattr(scanner_module.BasketballScanner, name, conflicting)
    case = live_worker(sport)
    with pytest.raises(ValueError, match="baseline"):
        case.run()
    assert not case.state["predictions"] and not case.path.exists()


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("latest", ["scheduled", "cancelled", "unknown"])
def test_failed_refresh_reuses_one_explicitly_partial_old_view_for_both_consumers(live_worker, sport, latest):
    from datetime import datetime
    from riskobet_automation import load_latest_riskobet
    case = live_worker(sport, start_offset=timedelta(hours=7))
    first = case.run()
    old = deepcopy(first["team_sports_baselines"][sport])
    case.state["now"] = datetime.fromisoformat(old["checked_at"]) + timedelta(hours=6)
    case.state["history_error"] = True
    if latest != "scheduled":
        case.state["on_history"] = lambda: correction(case, sport, latest)
    failed = case.run()
    assert failed["team_sports_baselines"][sport]["entries"] == old["entries"]
    assert failed["team_sports_baselines"][sport]["status"] == "partial"
    assert failed["team_sports_baselines"][sport]["errors"] == ["source_failed"]
    assert failed["team_sports_baselines"][sport]["checked_at"] != old["checked_at"]
    risk = load_latest_riskobet(db_path=case.path.with_name("riskobet.db"),
        latest_path=case.path.with_name("riskobet_latest.json"), rehydrate=True)
    assert len(failed["model_candidates"]) == len(risk.snapshots) == int(latest == "scheduled")
    assert len(case.state["predictions"]) == 1 and case.state["history"] == 2
    # A new real schedule response can restore the event. Partial is never a
    # successful six-hour refresh and the original cutoff was not retimed.
    case.state["history_error"], case.state["on_history"] = False, None
    recovered = case.run()
    assert recovered["team_sports_baselines"][sport]["status"] == "completed"
    assert len(case.state["predictions"]) == 2 and case.state["history"] == 3
