"""Same-call mechanics only: synthetic inputs and local SQLite, no feed claim."""
from contextlib import closing, contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import ast
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import types
from unittest.mock import patch

import pytest

import esports_elo
import esports_shadow
import multi_sport_recommendations as recommendations
from context_models.contracts import ContextContractError, digest
from test_esports_context import NOW, legacy_match

PARENT = "6d03ca00c487295a9a336e5917c314762e8ec637"


class FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)


@contextmanager
def calculations():
    """Count original function bodies across aliases, without mocking math."""
    real_code = esports_elo.subgraph_ratings.__code__
    candidate_code = recommendations.esports_match_winner_candidate.__code__
    calls = {"elo": [], "candidate": [], "selector": 0, "public_window": 0}
    previous = sys.getprofile()
    assert previous is None

    def observe(frame, event, returned):
        if event != "return":
            return
        if frame.f_code is real_code:
            calls["elo"].append((deepcopy(returned), deepcopy(frame.f_locals["history1"]), deepcopy(frame.f_locals["history2"])))
        elif frame.f_code is candidate_code:
            calls["candidate"].append(dict(frame.f_locals))
        elif frame.f_code.co_name == "_esports_history_selection" and frame.f_code.co_filename == recommendations.__file__:
            calls["selector"] += 1
        elif frame.f_code is recommendations.esports_history_window.__code__:
            calls["public_window"] += 1

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def capture(match=None, now=NOW):
    return recommendations.esports_match_winner_candidate(
        legacy_match() if match is None else match, now=now, capture_original=True)


def _parent_source(path):
    return subprocess.run(["git", "show", f"{PARENT}:{path}"], cwd=Path(__file__).resolve().parents[1],
                          check=True, capture_output=True).stdout.decode("utf-8")


@pytest.fixture(scope="module")
def old_modules():
    """Execute the actual pinned Git parent, not a rewritten golden formula."""
    legacy = types.ModuleType("_p6a_parent_recommendations")
    legacy.__file__ = recommendations.__file__
    shadow = types.ModuleType("_p6a_parent_shadow")
    shadow.__file__ = esports_shadow.__file__
    sys.modules[legacy.__name__] = legacy
    sys.modules[shadow.__name__] = shadow
    try:
        exec(compile(_parent_source("multi_sport_recommendations.py"), legacy.__file__, "exec"), legacy.__dict__)
        with patch.dict(sys.modules, {"multi_sport_recommendations": legacy}):
            exec(compile(_parent_source("esports_shadow.py"), shadow.__file__, "exec"), shadow.__dict__)
        yield legacy, shadow
    finally:
        sys.modules.pop(legacy.__name__)
        sys.modules.pop(shadow.__name__)


@pytest.mark.parametrize("flag", [None, 0, 1, "", "true", [], {}, 0.0])
def test_capture_flag_is_strict_bool_before_any_math(flag):
    with calculations() as calls, pytest.raises(ContextContractError):
        recommendations.esports_match_winner_candidate(legacy_match(), now=NOW, capture_original=flag)
    assert not calls["elo"]


@pytest.mark.parametrize("clock", [None, "2026-09-09T12:00:00Z", datetime(2026, 9, 9, 12)])
def test_capture_requires_aware_explicit_decision(clock):
    with calculations() as calls, pytest.raises(ContextContractError):
        capture(now=clock)
    assert not calls["elo"]


def test_capture_and_old_native_export_are_exclusive_before_math():
    with calculations() as calls, pytest.raises(ContextContractError):
        recommendations.esports_match_winner_candidate(legacy_match(), now=NOW, capture_original=True,
                                                       base_request={"event": None, "observations": ()})
    assert not calls["elo"]


def test_exact_same_call_original_is_immutable_and_detached():
    from context_models.esports_live import EsportsOriginal, validate_esports_original
    match = legacy_match()
    with calculations() as calls:
        output = capture(match)
    original = output["original"]
    assert isinstance(original, EsportsOriginal)
    assert len(calls["elo"]) == len(calls["candidate"]) == calls["selector"] == 1
    assert calls["public_window"] == 0
    body = original.to_dict()
    raw = calls["candidate"][0]
    for key in body["outputs"]:
        if key == "selection_side":
            continue
        value = body["outputs"][key]
        assert value == raw[key]
        if type(value) is float:
            assert value.hex() == raw[key].hex()
    assert body["outputs"]["team1_live_probability"] * 100 != output["candidate"].model_probability
    assert body["source_evidence"] == "unresolved"
    assert validate_esports_original(body) == body
    initial = original.to_dict()
    body["outputs"]["elo1"] += 1
    match["team1_history"][0]["won"] = not match["team1_history"][0]["won"]
    assert original.to_dict() == initial
    with pytest.raises((FrozenInstanceError, AttributeError)):
        original._payload = b"{}"


@pytest.mark.parametrize("status,score", [("upcoming", 0), ("live", 1)])
@pytest.mark.parametrize("best_of", [1, 3, 5, 7])
def test_actual_parent_prediction_bytes_and_offline_replay(old_modules, status, score, best_of):
    from context_models.esports_live import replay_esports_original
    match = legacy_match()
    match.update(status=status, team1_score=min(score, best_of // 2), series_type=best_of)
    expected = asdict(old_modules[0].esports_match_winner_candidate(deepcopy(match), now=NOW))
    default = recommendations.esports_match_winner_candidate(deepcopy(match), now=NOW)
    output = capture(deepcopy(match))
    assert asdict(default) == asdict(output["candidate"]) == expected
    for key, value in expected.items():
        if type(value) is float:
            assert getattr(default, key).hex() == getattr(output["candidate"], key).hex() == value.hex()
    assert replay_esports_original(output["original"]) == output["original"].to_dict()


def test_raw_positions_preserve_distinct_equal_and_same_object_occurrences(old_modules):
    match = legacy_match()
    rows = match["team1_history"]
    equal, same = deepcopy(rows[-1]), deepcopy(rows[-1])
    future = {**rows[-1], "end_at": (NOW + timedelta(microseconds=1)).isoformat()}
    match["team1_history"] = [future, equal, None, same, same, *rows[:-1]]
    output = capture(match)
    body = output["original"].to_dict()
    assert body["consumed"]["history_indices"]["team1"][:3] == [1, 3, 4]
    assert body["consumed"]["matches1"] == 20
    assert body["outputs"]["subgraph_size"] == 38
    assert asdict(output["candidate"]) == asdict(old_modules[0].esports_match_winner_candidate(match, now=NOW))


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_raw_causal_cutoff_microseconds_preserved(offset):
    match = legacy_match()
    extra = {**match["team1_history"][-1], "match_id": 9001,
             "end_at": (NOW + timedelta(microseconds=offset)).isoformat()}
    match["team1_history"].insert(0, extra)
    body = capture(match)["original"].to_dict()
    assert (0 in body["consumed"]["history_indices"]["team1"]) is (offset < 0)


def test_inputs_distinguish_missing_null_and_native_primitive_types():
    source = legacy_match()
    bodies = []
    for value in ("missing", None, 1, 1.0, True):
        match = deepcopy(source)
        if value != "missing":
            match["game_id"] = value
        bodies.append(capture(match)["original"].to_dict())
    assert len({body["inputs_hash"] for body in bodies}) == 5


def test_price_fields_are_not_in_capture_hash_and_input_mutation_is_bound():
    match = legacy_match()
    plain = capture(match)
    match.update(odds=1.01, prices={"bookmaker": "ignored"}, minimum_odds=999., unknownPrice=5.)
    for side in ("team1_history", "team2_history"):
        for item in match[side]:
            item.update(odds=1.01, unknown={"price": 9.})
    assert capture(match)["original"].to_dict() == plain["original"].to_dict()
    match["team1_history"][0]["won"] = not match["team1_history"][0]["won"]
    assert capture(match)["original"].to_dict()["inputs_hash"] != plain["original"].to_dict()["inputs_hash"]


@pytest.mark.parametrize("value", [Decimal("7"), float("inf"), {"price": 9.}, object()])
def test_nontransportable_ignored_or_consumed_values_preserve_baseline(old_modules, value):
    from context_models.esports_live import replay_esports_original
    match = legacy_match()
    # History number_of_games uses only equality-to-1 in the legacy model.
    match["team1_history"][0]["number_of_games"] = value
    expected = old_modules[0].esports_match_winner_candidate(match, now=NOW)
    output = capture(match)
    assert asdict(output["candidate"]) == asdict(expected)
    body = output["original"].to_dict()
    assert body["unavailable_inputs"]
    assert "price" not in json.dumps(body["inputs"])
    with pytest.raises(ContextContractError, match="unavailable"):
        replay_esports_original(output["original"])


def test_no_prediction_yields_none_original_without_elo():
    match = legacy_match()
    match["team1_history"] = match["team1_history"][:19]
    with calculations() as calls:
        result = capture(match)
    assert result["original"] is None and not result["candidate"].model_ready
    assert not calls["elo"]


def test_form_hash_validation_is_separate_from_fresh_offline_replay():
    from context_models.esports_live import EsportsOriginal, validate_esports_original, replay_esports_original
    body = capture()["original"].to_dict()
    body["outputs"]["elo1"] += 1.0
    # A pure shape check is not a new Elo computation or fitted provenance.
    with calculations() as calls:
        validate_esports_original(body)
        rewritten = EsportsOriginal.from_dict(body)
    assert not calls["elo"] and not calls["candidate"]
    with pytest.raises(ContextContractError):
        replay_esports_original(rewritten)


@pytest.mark.parametrize("change", [
    lambda x: x.update(source_evidence="verified_native"),
    lambda x: x.update(schema=True),
    lambda x: x.update(issued_at=NOW.isoformat()),
    lambda x: x["outputs"].update(elo1=True),
    lambda x: x["outputs"].update(team1_live_probability=float("nan")),
    lambda x: x["consumed"]["history_indices"]["team1"].__setitem__(0, True),
    lambda x: x.update(inputs_hash="0" * 64),
])
def test_closed_capture_contract_rejects_claims_types_and_hash_damage(change):
    from context_models.esports_live import validate_esports_original
    body = capture()["original"].to_dict()
    change(body)
    with pytest.raises(ContextContractError):
        validate_esports_original(body)


def test_actual_parent_sql_row_first_observation_and_settlement_are_identical(old_modules, tmp_path):
    databases = [tmp_path / "old.sqlite", tmp_path / "new.sqlite"]
    modules = [old_modules[1], esports_shadow]
    rows = []
    for module, path in zip(modules, databases):
        log = module.EsportsShadowLog(path)
        match = legacy_match()
        with patch.object(module, "datetime", FrozenClock):
            assert log.log_predictions([match]) == 1
            changed = deepcopy(match)
            changed["team1_history"][0]["won"] = not changed["team1_history"][0]["won"]
            assert log.log_predictions([changed]) == 0
            assert log.settle_open(lambda identity: {"winner_team_id": 7, "team1_id": 7, "team2_id": 8,
                "score1": 2, "score2": 0, "termination": "normal"}) == 1
            assert log.settle_open(lambda identity: None) == 0
        with closing(sqlite3.connect(path)) as connection:
            rows.append((connection.execute("PRAGMA table_info(esports_shadow_predictions)").fetchall(),
                         connection.execute("SELECT * FROM esports_shadow_predictions").fetchall()))
    assert rows[0] == rows[1]
    for a, b in zip(rows[0][1][0], rows[1][1][0]):
        if type(a) is float:
            assert a.hex() == b.hex()


def test_actual_logger_one_calculation_no_extra_window_and_same_rows(tmp_path):
    log = esports_shadow.EsportsShadowLog(tmp_path / "new.sqlite")
    with patch.object(esports_shadow, "datetime", FrozenClock), calculations() as calls:
        assert log.log_predictions([legacy_match()]) == 1
    assert len(calls["elo"]) == len(calls["candidate"]) == calls["selector"] == 1
    assert calls["public_window"] == 0
    origin = calls["candidate"][0]["original"].to_dict()
    assert origin["consumed"]["history_indices"]["team1"] == list(range(19, -1, -1))
    assert origin["outputs"]["elo1"].hex() == calls["elo"][0][0][0].hex()


def test_unchanged_elo_candidate_math_and_sql_ast(old_modules):
    root = Path(__file__).resolve().parents[1]
    assert ast.dump(ast.parse((root / "esports_elo.py").read_text(encoding="utf-8"))) == ast.dump(ast.parse(_parent_source("esports_elo.py")))
    old = ast.parse(_parent_source("multi_sport_recommendations.py"))
    new = ast.parse((root / "multi_sport_recommendations.py").read_text(encoding="utf-8"))
    for name in ("_candidate", "_series_win_probability", "_map_probability_from_series_probability", "build_candidate"):
        nodes = [next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name) for tree in (old, new)]
        assert ast.dump(nodes[0]) == ast.dump(nodes[1])
    def numerical_body(tree):
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "esports_match_winner_candidate")
        start = next(i for i, node in enumerate(function.body) if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                     and isinstance(node.value.func, ast.Name) and node.value.func.id == "subgraph_ratings")
        end = next(i for i, node in enumerate(function.body) if i > start and isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                   and isinstance(node.value.func, ast.Name) and node.value.func.id == "_candidate")
        return [ast.dump(node) for node in function.body[start:end+1]]
    assert numerical_body(old) == numerical_body(new)
    old_shadow = ast.parse(_parent_source("esports_shadow.py"))
    new_shadow = ast.parse((root / "esports_shadow.py").read_text(encoding="utf-8"))
    for name in ("__init__", "_connect", "settle_open", "summary", "release_status", "run_shadow_scan"):
        nodes = [next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
                 for tree in (old_shadow, new_shadow)]
        assert ast.dump(nodes[0]) == ast.dump(nodes[1])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "\ud800", 10**5000], ids=["nan", "infinity", "surrogate", "huge-integer"])
def test_noncanonical_json_cells_are_typed_failures(value):
    from context_models.esports_live import validate_esports_original
    body = capture()["original"].to_dict()
    body["inputs"]["event"]["values"]["id"]["value"] = value
    with pytest.raises(ContextContractError):
        validate_esports_original(body)


def test_offline_forged_nonobject_event_is_typed_not_an_attribute_error():
    from context_models.esports_live import replay_esports_original
    body = capture()["original"].to_dict()
    body["inputs"]["event"] = {"kind": "other", "value": {"kind": "value", "value": None}}
    body["inputs_hash"] = digest(body["inputs"])
    with pytest.raises(ContextContractError):
        replay_esports_original(body)


def test_capture_and_form_check_never_touch_io_or_native_replay(monkeypatch):
    from context_models import esports as native
    from context_models.esports_live import validate_esports_original
    import requests

    def prohibited(*args, **kwargs):
        raise AssertionError("capture/form check must not access IO or native replay")

    monkeypatch.setattr(sqlite3, "connect", prohibited)
    monkeypatch.setattr(requests, "get", prohibited)
    monkeypatch.setattr(Path, "read_bytes", prohibited)
    monkeypatch.setattr(native, "_replay", prohibited)
    monkeypatch.setattr(native, "export_esports_base", prohibited)
    with calculations() as calls:
        original = capture()["original"]
        validate_esports_original(original.to_dict())
    assert len(calls["elo"]) == len(calls["candidate"]) == calls["selector"] == 1


@pytest.mark.parametrize("payload", [b"null", b"[]", b"{", "{}", bytearray(b"{}"), b'{"schema":1,"schema":1}'])
def test_immutable_wrapper_rejects_noncanonical_or_wrong_json(payload):
    from context_models.esports_live import EsportsOriginal
    with pytest.raises(ContextContractError):
        EsportsOriginal(payload)


def test_default_legacy_missing_format_is_not_promoted_to_native_rules(old_modules):
    from context_models.esports_live import replay_esports_original
    match = legacy_match()
    match.pop("series_type")
    actual = capture(match)
    assert asdict(actual["candidate"]) == asdict(old_modules[0].esports_match_winner_candidate(match, now=NOW))
    body = actual["original"].to_dict()
    assert "series_type" not in body["inputs"]["event"]["values"]
    assert body["consumed"]["series_type"] == 3
    assert body["source_evidence"] == "unresolved"
    assert replay_esports_original(actual["original"]) == body
