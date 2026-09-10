"""Opt-in final scanner/worker witnesses, not persistent context publication.

The break under test is losing the existing same-call unrounded original at
the final scanner boundary. HTTP and previously cached histories/artifacts are
synthetic; scanner, provider observer, model, calibrators and B1 SQLite are real.
"""
import ast
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
import inspect
import itertools
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

import alternative_markets_tab_extended as manual
import challenge_15k as scanner
import challenge_engine as engine
import football_original
import runtime_paths
import wettfinder_automation as automation
from config_loader import AppConfig
from context_models.contracts import canonical_timestamp
from context_observations import _SELECT, _decode_receipt
from context_sources.football_capture import capture_football_worker
from test_challenge_15k import credible_validation
from test_football_context_provider import Response, payload
from tests.test_football_original_capture import calibration, values


ROOT = Path(__file__).resolve().parents[1]
PARENT = "887cb4713d996d2f6efc8b70fbb4cc71e867f13d"
NOW = datetime(2030, 8, 4, 10, tzinfo=timezone.utc)
OMITTED = object()
ENTRIES = ("scanner", "automatic", "manual")
FUNCTIONS = {
    "scanner": (scanner, "scan_daily_challenge", "fixture_candidates", "build_fixture_candidates"),
    "automatic": (automation, "_default_football_scan", "snapshot", "scan_daily_challenge"),
    "manual": (manual, "_run_market_scan_worker", "challenge_snapshot", "scan_daily_challenge"),
}


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


def plain(value):
    if hasattr(value, "to_dict"):
        return plain(value.to_dict())
    if is_dataclass(value):
        return plain(asdict(value))
    if isinstance(value, dict):
        return {str(key): plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(child) for child in value]
    if type(value) is float:
        return {"float_hex": value.hex()}
    return value


def canonical(value):
    return json.dumps(plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parent_blob(filename):
    return subprocess.run(["git", "show", PARENT + ":" + filename], cwd=ROOT,
                          check=True, capture_output=True).stdout


def parent_function(module, name, **overrides):
    tree = ast.parse(parent_blob(Path(module.__file__).name))
    original = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = dict(vars(module), **overrides)
    exec(compile(ast.Module(body=[original], type_ignores=[]), PARENT + ":" + name, "exec"), namespace)
    return namespace[name]


def strip_exact_a0_additions(function, entry):
    """Assert the complete optional seam before removing it for parent parity."""
    _, expected_name, assignment, callee = FUNCTIONS[entry]
    assert function.name == expected_name
    assert ast.dump(function.args.kwonlyargs[-1]) == ast.dump(ast.arg(arg="original_capture"))
    assert ast.dump(function.args.kw_defaults[-1]) == ast.dump(ast.Constant(value=None))
    function.args.kwonlyargs.pop()
    function.args.kw_defaults.pop()
    guard_index = int(isinstance(function.body[0], ast.Expr)
                      and isinstance(function.body[0].value, ast.Constant)
                      and isinstance(function.body[0].value.value, str))
    guard = ast.parse('if original_capture is not None and not callable(original_capture):\n'
                      '    raise ValueError("original_capture must be callable or None")').body[0]
    assert ast.dump(function.body[guard_index], include_attributes=False) == ast.dump(guard, include_attributes=False)
    function.body.pop(guard_index)
    spread = ast.parse('f(**({"original_capture": original_capture} if original_capture is not None else {}))').body[0].value.keywords[0]
    additions = [(node, keyword) for node in ast.walk(function) if isinstance(node, ast.Call)
                 for keyword in node.keywords if ast.dump(keyword, include_attributes=False) == ast.dump(spread, include_attributes=False)]
    assert len(additions) == 1
    call, keyword = additions[0]
    assert isinstance(call.func, ast.Name) and call.func.id == callee
    owners = [node for node in ast.walk(function) if isinstance(node, ast.Assign) and node.value is call]
    assert len(owners) == 1 and ast.dump(owners[0].targets[0]) == ast.dump(ast.Name(id=assignment, ctx=ast.Store()))
    call.keywords.remove(keyword)
    return function


def prepare(monkeypatch, tmp_path, *, uefa=False, no_model=False, incomplete=False, duplicate=False):
    upcoming, history = values()
    shift = NOW + timedelta(hours=8) - datetime.fromisoformat(upcoming["fixture"]["date"])
    for row in [upcoming, *history]:
        row["fixture"]["date"] = (datetime.fromisoformat(row["fixture"]["date"]) + shift).isoformat()
        row["fixture"]["status"] = {"short": "NS" if row is upcoming else "FT"}
        row["league"].update(name="Synthetic League", country="England", season=2030)
    league_id = 2 if uefa else 39
    upcoming["league"]["id"] = league_id
    detail = deepcopy(upcoming)
    detail.pop("challenge_stats", None)  # Local annotations are NOT native HTTP.
    detail["lineups"] = [
        {"team": {"id": team}, "startXI": [
            {"player": {"id": team * 100 + n, "pos": "M"}} for n in range(1, 12)],
         "substitutes": [{"player": {"id": team * 100 + 12, "pos": "F"}}]}
        for team in (1, 2)
    ]
    if incomplete:
        detail.pop("lineups")
    discovery = deepcopy(detail)
    discovery.pop("lineups", None)
    injury = {"fixture": deepcopy(upcoming["fixture"]), "league": deepcopy(upcoming["league"]),
              "team": {"id": 1}, "player": {"id": 112, "type": "Missing Fixture", "reason": "Knee Injury"}}
    state = SimpleNamespace(path=tmp_path / "context.db", league=league_id, upcoming=upcoming,
                            history=history, calls=[], clocks=[], providers=[], quote_calls=[], history_calls=[])
    ticks = itertools.count()

    def received(self):
        moment = NOW + timedelta(seconds=next(ticks))
        state.clocks.append(moment)
        return moment

    def fetch(url, **kwargs):
        endpoint, params = url.split(".io/", 1)[1], kwargs["params"]
        state.calls.append((endpoint, deepcopy(params)))
        if endpoint == "fixtures":
            rows = [detail] if "ids" in params or "id" in params else [discovery] * (2 if duplicate else 1)
        elif endpoint == "injuries":
            rows = [injury]
        elif endpoint == "leagues":
            rows = [{"seasons": [{"year": 2030, "coverage": {"injuries": True, "fixtures": {"lineups": True}}}]}]
        elif endpoint == "fixtures/headtohead":
            rows = []
        else:
            pytest.fail("Unexpected provider request: " + endpoint)
        return Response(payload(rows))

    real_init = scanner.ChallengeDataProvider.__init__
    def init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        state.providers.append(self)

    def cached_history(self, lid, season, fixtures):
        state.history_calls.append((lid, season))
        if no_model:
            return []
        rows = deepcopy(history)
        if lid == 2:
            # Genuine qualifier fallback needs a league rate history, but no
            # target-team series. An entirely empty league cannot be modeled.
            for row in rows:
                row["league"]["id"] = 2
                for side in ("home", "away"):
                    row["teams"][side]["id"] += 100
        return rows

    def cached_domestic(self, team_id, search_date, kickoff):
        return {"league_id": 39 if team_id == 1 else 140, "season": 2030,
                "fixtures": deepcopy(history)}

    def quotes(*args):
        state.quote_calls.append(args)
        assert state.providers[-1]._context_capture is None
        return {}, []

    monkeypatch.setattr(scanner.ChallengeDataProvider, "__init__", init)
    monkeypatch.setattr(scanner.ChallengeDataProvider, "_rate_limit", lambda self: None)
    monkeypatch.setattr(scanner.ChallengeDataProvider, "_context_received_at", received)
    monkeypatch.setattr(scanner.ChallengeDataProvider, "completed_history", cached_history)
    monkeypatch.setattr(scanner.ChallengeDataProvider, "domestic_team_history", cached_domestic)
    monkeypatch.setattr(scanner.ChallengeDataProvider, "weather", lambda *_: {
        "temperature_c": 20., "wind_kmh": 5., "precipitation_mm": 0.})
    monkeypatch.setattr(scanner, "api_football_get", fetch)
    monkeypatch.setattr(scanner, "datetime", Clock)
    monkeypatch.setattr(manual, "datetime", Clock)
    monkeypatch.setattr(scanner, "current_season_start_year_for_id", lambda *_: 2030)
    monkeypatch.setattr(scanner, "annotate_history_xg", lambda *_args, **_kw: {"coverage": 1.})
    monkeypatch.setattr(scanner, "_cached_market_validation", lambda *_: {
        spec.key: credible_validation() for spec in engine.MARKET_SPECS})
    monkeypatch.setattr(scanner, "_cached_market_calibration", lambda *_: calibration())
    monkeypatch.setattr(automation, "ALTERNATIVE_MARKET_LEAGUES", {league_id: "Synthetic League"})
    monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", state.path)
    monkeypatch.setattr(manual, "fetch_football_consensus", quotes)
    monkeypatch.setattr(football_original, "_capture_now", lambda: NOW + timedelta(seconds=1, microseconds=500000))
    # Unexpected alternate HTTP paths must never escape this synthetic fixture.
    import requests
    def no_network(*args, **kwargs):
        pytest.fail("An unplanned external HTTP path was reached")
    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    return state


def invoke(entry, state, *, sink=OMITTED, parent=False, profile="wettfinder"):
    optional = {} if sink is OMITTED else {"original_capture": sink}
    scan = parent_function(scanner, "scan_daily_challenge") if parent else scanner.scan_daily_challenge
    if entry == "scanner":
        owner = scanner.ChallengeDataProvider("synthetic", None)
        with capture_football_worker(owner):
            return scan(owner, [state.league], NOW.date(), 20,
                        allow_above_challenge_probability=True, candidate_profile=profile, **optional)
    if entry == "automatic":
        run = (parent_function(automation, "_default_football_scan", scan_daily_challenge=scan)
               if parent else automation._default_football_scan)
        return run(NOW.date(), AppConfig(api_football_key="synthetic"), **optional)
    run = (parent_function(manual, "_run_market_scan_worker", scan_daily_challenge=scan)
           if parent else manual._run_market_scan_worker)
    return run("synthetic", None, [state.league], NOW.date(), NOW.date(), 20,
               {"league_ids": [state.league]}, **optional)


def trace(operation):
    functions = {
        engine._fixture_model: "goal_model", engine._fixture_count_model: "count_model",
        engine.score_matrix: "score_matrix", engine._market_probabilities: "market_law",
        engine.MarketCalibration.__call__: "curve", engine.ConservativeMarketCalibration.__call__: "conservative",
        football_original.capture_football_original: "capture", football_original._capture_now: "capture_clock",
        engine._football_reference_provenance: "provenance",
    }
    codes = {function.__code__: name for function, name in functions.items()}
    counts, models, raw_laws = Counter(), [], []
    old_profile = sys.getprofile()
    def record(frame, event, value):
        if event == "call" and frame.f_code in codes:
            counts[codes[frame.f_code]] += 1
        if event == "return" and frame.f_code is engine.fixture_market_probabilities.__code__ and isinstance(value, dict):
            models.append(deepcopy(value))
        if event == "return" and frame.f_code is engine._market_probabilities.__code__ and isinstance(value, dict):
            raw_laws.append(deepcopy(value))
    sys.setprofile(record)
    try:
        result = operation()
    finally:
        sys.setprofile(old_profile)
    return result, counts, models, raw_laws


def snapshot(entry, result):
    return result["challenge"] if entry == "manual" else result


def receipts(state):
    if not state.path.exists():
        return []
    with sqlite3.connect(state.path) as connection:
        return [_decode_receipt(row) for row in connection.execute(_SELECT)]


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("uefa", [False, True])
def test_final_original_is_actual_once_only_and_exact_parent_worker_output(monkeypatch, tmp_path, entry, uefa):
    with monkeypatch.context() as before_patch:
        before = prepare(before_patch, tmp_path / "parent", uefa=uefa)
        expected, before_counts, before_models, before_laws = trace(lambda: invoke(entry, before, parent=True))
    actual_state = prepare(monkeypatch, tmp_path / "actual", uefa=uefa)
    originals = []
    actual, counts, models, _ = trace(lambda: invoke(entry, actual_state, sink=originals.append))
    assert canonical(actual) == canonical(expected)
    assert actual_state.calls == before.calls
    assert actual_state.history_calls == before.history_calls
    assert len(actual_state.calls) == 5
    assert len(actual_state.quote_calls) == int(entry == "manual")
    assert counts["goal_model"] == before_counts["goal_model"] == (4 if uefa else 1)
    assert {key: counts[key] for key in before_counts} == dict(before_counts)
    assert counts["capture"] == counts["capture_clock"] == counts["provenance"] == len(originals) == 1
    assert all(type(original) is football_original.FootballOriginal for original in originals)
    packet = originals[0].to_dict()
    assert packet["probabilities"] == {key: list(val) for key, val in before_models[-1]["probabilities"].items()}
    assert packet["goal_model"]["active_lambdas"] == list(before_models[-1]["active_lambdas"])
    assert len(packet["probabilities"]) == 90
    laws = before_laws[-9:]
    expected_raw = {key: [laws[start + column][key] for column in range(3)]
                    for start in (0, 3, 6) for key in laws[start]}
    assert packet["raw_probabilities"] == expected_raw
    assert packet["count_models"]["corners"]["active_counts"] == list(before_models[-1]["count_models"]["corners"]["active_counts"])
    assert packet["captured_at"] == canonical_timestamp(NOW + timedelta(seconds=1, microseconds=500000))
    assert packet["logical_history_cutoff"] == canonical_timestamp(NOW + timedelta(hours=8))
    saved = receipts(actual_state)
    assert len([row for row in saved if row["kind"] == "confirmed_lineup"]) == 24
    assert {row["observed_at"] for row in saved if row["kind"] == "availability"} == {canonical_timestamp(NOW + timedelta(seconds=2))}
    assert packet["captured_at"] < canonical_timestamp(NOW + timedelta(seconds=2))
    assert all(row["published_at"] is None for row in saved)
    assert actual_state.providers[-1]._context_capture is None
    assert snapshot(entry, actual)["market_candidates"] == 90
    assert packet["source_evidence"] == "unresolved-receipts-not-in-this-capture"
    if uefa:
        assert packet["team_history"]
        assert packet["calibration_recipes"]["RESULT_HOME"]["kind"] == "legacy-minimum-source-calibration-v1"
    else:
        assert packet["team_history"] is None
    # The actual object cannot rewrite results via its detached JSON projection.
    detached = originals[0].to_dict()
    detached["probabilities"]["RESULT_HOME"][0] = 0.0
    assert originals[0].to_dict() == packet
    assert "football-original-market-calculation-v1" not in canonical(actual)
    assert "league_history" not in canonical(actual)
    if entry == "manual":
        assert "league_history" not in canonical(manual._market_audit_payload(actual))
    else:
        public = automation._football_state_from_snapshot(snapshot(entry, actual), attempted_at=NOW, search_date=NOW.date())
        assert "league_history" not in canonical(public)


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("callback", [OMITTED, None], ids=["omitted", "explicit-none"])
def test_default_has_no_capture_work_and_preserves_exact_lower_call_signature(monkeypatch, tmp_path, entry, callback):
    before = prepare(monkeypatch, tmp_path / "parent")
    expected, _, _, _ = trace(lambda: invoke(entry, before, parent=True))
    with monkeypatch.context() as after_patch:
        after = prepare(after_patch, tmp_path / "actual")
        def forbidden(*args, **kwargs):
            pytest.fail("Default executed capture/provenance without a receiving owner")
        after_patch.setattr(football_original, "capture_football_original", forbidden)
        after_patch.setattr(football_original, "_capture_now", forbidden)
        after_patch.setattr(engine, "_football_reference_provenance", forbidden)
        actual = invoke(entry, after, sink=callback)
    assert canonical(actual) == canonical(expected)
    assert after.calls == before.calls


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("invalid", [False, 0, "callback", {}, [], object()])
def test_bad_callback_is_rejected_before_any_source_or_model_work(monkeypatch, tmp_path, entry, invalid):
    state = prepare(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="original_capture"):
        invoke(entry, state, sink=invalid)
    assert state.calls == [] and state.history_calls == [] and not state.path.exists()
    assert all(owner._context_capture is None for owner in state.providers)


@pytest.mark.parametrize("entry", ENTRIES)
def test_callback_is_keyword_only(entry):
    function = {"scanner": scanner.scan_daily_challenge, "automatic": automation._default_football_scan,
                "manual": manual._run_market_scan_worker}[entry]
    assert inspect.signature(function).parameters["original_capture"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize("entry", ENTRIES)
def test_missing_model_never_manufactures_a_capture(monkeypatch, tmp_path, entry):
    state = prepare(monkeypatch, tmp_path, no_model=True)
    originals = []
    result, counts, _, _ = trace(lambda: invoke(entry, state, sink=originals.append))
    assert originals == [] and counts["capture"] == 0 and counts["goal_model"] == 1
    assert snapshot(entry, result)["fixtures_modeled"] == 0
    assert len(state.calls) == 2


@pytest.mark.parametrize("entry", ENTRIES)
def test_incomplete_source_does_not_gate_the_computed_original(monkeypatch, tmp_path, entry):
    state = prepare(monkeypatch, tmp_path, incomplete=True)
    originals = []
    result = invoke(entry, state, sink=originals.append)
    assert snapshot(entry, result)["market_candidates"] == 90 and len(originals) == 1
    assert originals[0].to_dict()["source_evidence"] == "unresolved-receipts-not-in-this-capture"
    assert not any(row["kind"] == "confirmed_lineup" for row in receipts(state))


@pytest.mark.parametrize("entry", ENTRIES)
def test_callback_error_is_not_a_completed_or_unavailable_scan(monkeypatch, tmp_path, entry):
    state = prepare(monkeypatch, tmp_path)
    seen = []
    def broken(original):
        seen.append(original)
        raise RuntimeError("synthetic-original-sink-failed")
    with pytest.raises(RuntimeError, match="synthetic-original-sink-failed"):
        invoke(entry, state, sink=broken)
    assert len(seen) == 1 and type(seen[0]) is football_original.FootballOriginal
    assert len(state.calls) == 2 and state.quote_calls == []
    assert state.providers[-1]._context_capture is None


@pytest.mark.parametrize("entry", ENTRIES)
def test_explicit_falsy_callable_is_not_silently_disabled(monkeypatch, tmp_path, entry):
    state = prepare(monkeypatch, tmp_path)
    class Sink(list):
        def __call__(self, value):
            self.append(value)
    sink = Sink()
    assert not sink
    result = invoke(entry, state, sink=sink)
    assert len(sink) == 1 and snapshot(entry, result)["market_candidates"] == 90


def test_existing_duplicate_fixture_policy_still_executes_one_final_original(monkeypatch, tmp_path):
    state = prepare(monkeypatch, tmp_path, duplicate=True)
    originals = []
    result, counts, _, _ = trace(lambda: invoke("scanner", state, sink=originals.append))
    assert result["fixtures_found"] == result["fixtures_modeled"] == len(originals) == counts["goal_model"] == 1
    assert any("doppelter Provider-Eintrag" in error for error in result["errors"])


def test_15k_default_remains_uncaptured_and_exact_parent(monkeypatch, tmp_path):
    before = prepare(monkeypatch, tmp_path / "parent")
    expected = invoke("scanner", before, parent=True, profile="challenge")
    with monkeypatch.context() as after_patch:
        after = prepare(after_patch, tmp_path / "actual")
        actual, counts, _, _ = trace(lambda: invoke("scanner", after, profile="challenge"))
    assert counts["capture"] == counts["provenance"] == counts["capture_clock"] == 0
    assert canonical(actual) == canonical(expected)


@pytest.mark.parametrize("entry", ENTRIES)
def test_none_preserves_callable_injection_with_the_old_explicit_signature(monkeypatch, tmp_path, entry):
    state = prepare(monkeypatch, tmp_path)
    if entry == "scanner":
        real_builder = engine.build_fixture_candidates
        def legacy_builder(fixture, history, validation, calibration=None, *, team_history=None,
                           model_scope=engine.MODEL_SCOPE_SAME_COMPETITION,
                           allow_above_challenge_probability=False, candidate_profile="challenge"):
            return real_builder(fixture, history, validation, calibration, team_history=team_history,
                model_scope=model_scope, allow_above_challenge_probability=allow_above_challenge_probability,
                candidate_profile=candidate_profile)
        monkeypatch.setattr(scanner, "build_fixture_candidates", legacy_builder)
    else:
        owner = automation if entry == "automatic" else manual
        # The exact real parent signature rejects even original_capture=None;
        # its body still executes the full scanner, not a mocked prediction.
        monkeypatch.setattr(owner, "scan_daily_challenge", parent_function(scanner, "scan_daily_challenge"))
    result = invoke(entry, state, sink=None)
    assert snapshot(entry, result)["market_candidates"] == 90
    assert len(state.calls) == 5


def test_actual_manual_job_reports_sink_failure_and_publishes_no_completed_result(monkeypatch, tmp_path):
    import scan_jobs
    from tests.test_scan_jobs import _wait_for_state
    state = prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(scan_jobs, "JOBS_DIR", tmp_path / "jobs")
    seen = []
    def broken(original):
        seen.append(original)
        raise RuntimeError("synthetic-original-sink-failed")
    key = "p5b-a0-original-error"
    try:
        assert scan_jobs.start_job(key, manual._run_market_scan_worker,
            args=("synthetic", None, [39], NOW.date(), NOW.date(), 20, {}),
            kwargs={"original_capture": broken}, persist_name="manual-a0",
            persist_fn=manual._market_audit_payload)
        result = _wait_for_state(key, {"done", "error"})
        assert result["state"] == "error" and "synthetic-original-sink-failed" in result["error"]
        assert "result" not in result
        assert len(seen) == 1 and type(seen[0]) is football_original.FootballOriginal
        assert state.providers[-1]._context_capture is None
        assert not (tmp_path / "jobs" / "manual-a0.json").exists()
    finally:
        scan_jobs.clear_job(key)


def test_automatic_state_writer_never_receives_the_in_memory_original(monkeypatch, tmp_path):
    state = prepare(monkeypatch, tmp_path)
    originals = []
    result = invoke("automatic", state, sink=originals.append)
    public = automation._football_state_from_snapshot(result, attempted_at=NOW, search_date=NOW.date())
    target = tmp_path / "automatic-state.json"
    automation.write_state(public, target)
    saved = json.loads(target.read_bytes())
    assert saved["fixtures_modeled"] == 1 and len(originals) == 1
    text = target.read_text(encoding="utf-8")
    assert "football-original-market-calculation-v1" not in text and "league_history" not in text


@pytest.mark.parametrize("entry", ENTRIES)
def test_whole_worker_module_keeps_exact_parent_ast_outside_checked_a0_seam(entry):
    module, name, _, _ = FUNCTIONS[entry]
    actual = ast.parse(Path(module.__file__).read_bytes())
    expected = ast.parse(parent_blob(Path(module.__file__).name))
    function = next(node for node in actual.body if isinstance(node, ast.FunctionDef) and node.name == name)
    strip_exact_a0_additions(function, entry)
    assert ast.dump(actual, include_attributes=False) == ast.dump(expected, include_attributes=False)


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("mutation", ["unrelated", "guard", "wrong-assignment"])
def test_parent_parity_does_not_discard_unrelated_or_relocated_changes(entry, mutation):
    module, name, assignment, _ = FUNCTIONS[entry]
    actual = ast.parse(Path(module.__file__).read_bytes())
    expected = ast.parse(parent_blob(Path(module.__file__).name))
    function = next(node for node in actual.body if isinstance(node, ast.FunctionDef) and node.name == name)
    if mutation == "unrelated":
        function.body.append(ast.parse("unrelated_change = 12345").body[0])
    elif mutation == "guard":
        guard = next(node for node in function.body if isinstance(node, ast.If))
        guard.body[0].exc.args[0] = ast.Constant(value="wrong-exception-contract")
    else:
        owner = next(node for node in ast.walk(function) if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == assignment for target in node.targets))
        owner.targets[0].id = "probe_candidates"
    with pytest.raises(AssertionError):
        strip_exact_a0_additions(function, entry)
        assert ast.dump(actual, include_attributes=False) == ast.dump(expected, include_attributes=False)
