"""Same-CPU exact comparison with the immutable pre-change predictor source."""
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import sys
import types

import pytest

from model_artifacts import canonical_bytes
from test_tennis_live_worker import NOW
from test_tennis_predict import _synthetic_state
from tennis.predict import predict_match


def exact_structure(value):
    """Lossless typed comparison, including the simulator's tuple-key maps."""
    if value is None or type(value) in (str, bool, int):
        return [type(value).__name__, value]
    if type(value) is float:
        return ["float", value.hex()]
    if type(value) is datetime:
        return ["datetime", value.isoformat(), str(value.tzinfo), value.fold]
    if type(value) in (tuple, list):
        return [type(value).__name__, [exact_structure(item) for item in value]]
    if type(value) is dict:
        return ["dict", sorted([[exact_structure(key), exact_structure(item)] for key, item in value.items()], key=canonical_bytes)]
    raise TypeError(f"unhandled comparison type {type(value).__name__}")


@pytest.fixture
def legacy(monkeypatch):
    path = Path(__file__).parent/"fixtures/tennis_predict_legacy_da0ae34.py"
    source = path.read_bytes().replace(b"\r\n", b"\n")
    git_blob = b"blob "+str(len(source)).encode()+b"\0"+source
    assert hashlib.sha1(git_blob).hexdigest() == "19f92678de5b236b72ec8fee921ef598d98bc223"
    module = types.ModuleType("tennis._pre_live_predict_fixture")
    module.__package__ = "tennis"
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
@pytest.mark.parametrize("surface", [None, "Hard", "Clay"])
@pytest.mark.parametrize("best_of", [3, 5])
@pytest.mark.parametrize("indoor", [None, True])
@pytest.mark.parametrize("odds", [None, 1.85])
def test_legacy_default_and_same_call_collector_preserve_all_output_bytes(legacy, tour, surface, best_of, indoor, odds):
    state = _synthetic_state()
    state.built_at = (NOW-timedelta(hours=2)).timestamp()
    state.cal_a, state.cal_b = .9142, .1473
    state.cal_wta_a, state.cal_wta_b = .67183, -.0719
    kwargs = dict(best_of=best_of, tour=tour, indoor=indoor, odds_a=odds, odds_b=odds, as_of=NOW)
    expected = legacy.predict_match(state, "Hero H.", "Grinder G.", surface, **kwargs)
    current = predict_match(state, "Hero H.", "Grinder G.", surface, **kwargs)
    captured = []
    linked = predict_match(state, "Hero H.", "Grinder G.", surface, **kwargs, original_capture=captured.append)
    assert canonical_bytes(exact_structure(asdict(expected))) == canonical_bytes(exact_structure(asdict(current))) == canonical_bytes(exact_structure(asdict(linked)))
    assert canonical_bytes(expected.market_summary()) == canonical_bytes(current.market_summary()) == canonical_bytes(linked.market_summary())
    assert len(captured) == 1
    assert round(captured[0]["values"]["p_a_cal"], 4) == current.p_a_cal
    assert captured[0]["values"]["p_b_cal"] == 1-captured[0]["values"]["p_a_cal"]
