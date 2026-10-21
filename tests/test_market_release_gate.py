from datetime import datetime, timedelta, timezone
import json

import pytest

import challenge_engine as engine
from market_release_gate import (
    BLOCK_REASON, FLAG, PATH_FLAG, market_benchmark_passed, market_benchmark_required, market_benchmark_verdict,
)
from test_market_benchmark import synthetic_league

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def _gate(tmp_path, *, generated_at=NOW, cells=None, name="market_gate.json"):
    document = {"version": "market-benchmark-v1", "generated_at": generated_at.isoformat(), "cells": cells or {}}
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_flag_default_off_and_verdicts_are_fail_closed(tmp_path, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    assert market_benchmark_required() is False
    monkeypatch.setenv(FLAG, "1")
    assert market_benchmark_required() is True
    path = _gate(tmp_path, cells={"39:RESULT_HOME": {"market_beaten": True}, "39:RESULT_AWAY": {"market_beaten": False}})
    assert market_benchmark_verdict(39, "RESULT_HOME", path=path, now=NOW) is True
    assert market_benchmark_verdict(39, "RESULT_AWAY", path=path, now=NOW) is False
    assert market_benchmark_verdict(39, "BTTS_YES", path=path, now=NOW) is None
    assert market_benchmark_passed(39, "RESULT_HOME", path=path, now=NOW) is True
    assert market_benchmark_passed(39, "BTTS_YES", path=path, now=NOW) is False
    assert market_benchmark_passed(39, "RESULT_HOME", path=tmp_path / "missing.json", now=NOW) is False
    stale = _gate(tmp_path, generated_at=NOW - timedelta(days=121), name="stale.json",
                  cells={"39:RESULT_HOME": {"market_beaten": True}})
    assert market_benchmark_verdict(39, "RESULT_HOME", path=stale, now=NOW) is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert market_benchmark_verdict(39, "RESULT_HOME", path=broken, now=NOW) is None


def test_engine_adds_the_block_reason_only_when_enabled_and_not_beaten(tmp_path, monkeypatch):
    fixtures = synthetic_league(rounds=6)
    history, target = fixtures[:-1], fixtures[-1]
    monkeypatch.setattr(engine, "_credible_validation", lambda metric: True)
    monkeypatch.setenv(PATH_FLAG, str(_gate(tmp_path, cells={"39:RESULT_HOME": {"market_beaten": True}})))

    def reasons(key):
        candidates = engine.build_fixture_candidates(target, history, {}, candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER,
                                                     allow_above_challenge_probability=True)
        return next(c.blocked_reasons for c in candidates if c.market_key == key)

    monkeypatch.delenv(FLAG, raising=False)
    assert BLOCK_REASON not in reasons("RESULT_AWAY")
    monkeypatch.setenv(FLAG, "1")
    assert BLOCK_REASON in reasons("RESULT_AWAY")  # No verdict for this cell: fail-closed.
    assert BLOCK_REASON not in reasons("RESULT_HOME")  # Beaten: no block from this gate.
    assert BLOCK_REASON not in reasons("CORNERS_TOTAL_OVER_9_5") if any(
        c.market_key == "CORNERS_TOTAL_OVER_9_5" for c in engine.build_fixture_candidates(
            target, history, {}, candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER, allow_above_challenge_probability=True)
    ) else True
