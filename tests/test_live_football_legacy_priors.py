"""Legacy daily editions: both file clocks and same-call evidence precede kickoff."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import json
import os

import pytest

from test_live_football_priors import case
from live_football_priors import _GoalBasis, PRIOR_MODEL
from challenge_engine import CHALLENGE_MARKET_CATALOG_SIGNATURE

START = datetime(2026, 11, 22, 15, 30, tzinfo=timezone.utc)


def edition(start=START):
    fixture, doc, _ = case(start)
    s = doc["football"]
    s.update(candidates=[], last_attempt_at=(start-timedelta(hours=5)).isoformat(),
             discovery_market_catalog_signature=CHALLENGE_MARKET_CATALOG_SIGNATURE)
    as_of = (start-timedelta(hours=4)).isoformat()
    row = dict(fixture_id=81, home_team_id=1, away_team_id=2, league_id=39, home_team="1", away_team="2",
               kickoff=start.isoformat(), model_scope="same_competition", prediction_version=PRIOR_MODEL,
               candidate_id="81:RESULT_HOME", market_key="RESULT_HOME", expected_unit=None,
               expected_home_goals=1.547, expected_away_goals=1.717,
               validation={"prediction_version": PRIOR_MODEL}, blocked_reasons=["Evidenzscore unter 72"],
               market_comparison=dict(schema="league-market-comparison-v1", fixture_id=81, home_id=1, away_id=2,
                                      league_id=39, market_key="RESULT_HOME", scheduled_start=start.isoformat(),
                                      prediction_version=PRIOR_MODEL, validation_prediction_version=PRIOR_MODEL,
                                      latest_kickoff=(start-timedelta(days=1)).isoformat()))
    s.update(discovery_candidates=[row], discovery_candidate_count=1,
             riskobet_source_candidates=[deepcopy(row)], riskobet_source_candidate_count=1,
             football_recent_results={"81": dict(schema="football-recent-results-v1", fixture_id=81, home_id=1,
                 away_id=2, model_scope="same_competition", scheduled_start=start.isoformat(), as_of=as_of,
                 home=[], away=[])})
    return fixture, doc, row


def test_read_legacy_edition_with_a_real_pre_kickoff_handle(tmp_path, monkeypatch):
    if os.name != "posix":  # Windows creation time alone cannot establish when file content last changed.
        pytest.skip("requires POSIX inode ctime")
    import ev_signal_sources
    import live_football_priors as reader
    # An ext4 write timestamp can lag CLOCK_REALTIME. Set the fixture's publication
    # clock from the already created inode, never from a guess about kernel granularity.
    path = tmp_path / "wettfinder_latest.json"
    path.touch()
    created = path.stat()
    now = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
        microseconds=min(created.st_mtime_ns, created.st_ctime_ns) // 1000)
    midnight = now.astimezone(ZoneInfo("Europe/Zurich")).replace(hour=0, minute=0, second=0, microsecond=0)
    start = min(now + timedelta(minutes=20), midnight + timedelta(days=1) - timedelta(microseconds=1))
    if start < now + timedelta(seconds=1):
        pytest.skip("insufficient time remaining in this Zurich calendar day for a future kickoff")
    fixture, doc, _ = edition(start)
    doc["football"]["last_attempt_at"] = max(midnight, now-timedelta(minutes=2)).isoformat()
    doc["football"]["football_recent_results"]["81"]["as_of"] = max(midnight, now-timedelta(minutes=1)).isoformat()
    doc["generated_at"] = now.isoformat()
    path.write_text(json.dumps(doc), encoding="utf8")
    class Live(datetime):
        @classmethod
        def now(cls, tz=None):
            return (start + timedelta(minutes=1)).astimezone(tz)
    monkeypatch.setattr(reader, "datetime", Live)
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    assert reader.stored_goal_priors(fixture) == (1.547, 1.717)
    # The bytes are unchanged, but this edition no longer proves pre-kickoff availability.
    kickoff_ns = (start - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(microseconds=1) * 1000
    os.utime(path, ns=(path.stat().st_atime_ns, kickoff_ns))
    assert reader.stored_goal_priors(fixture) is None


@pytest.mark.parametrize("damage", ["none", "win_creation_time", "stat_missing", "mtime_at_kickoff",
    "ctime_at_kickoff", "before_generated", "postdated_asof", "before_attempt", "refresh", "foreign_side",
    "foreign_model", "bad_scope", "count_only", "unknown_market", "conflict", "bad_recent",
    "future_history", "bad_count", "wrong_day", "alias_key", "missing_goal", "new_format",
    "failed_projection", "missing_reasons", "stale_inputs", "unknown_blocker"])
def test_legacy_projection_is_causal_and_pair_specific(monkeypatch, damage):
    import live_football_legacy_priors as legacy
    _, doc, row = edition()
    s = doc["football"]
    monkeypatch.setattr(legacy, "_POSIX_CTIME", damage != "win_creation_time")
    ns = int(START.timestamp()) * 10**9
    stat = SimpleNamespace(st_mtime_ns=ns-3600*10**9, st_ctime_ns=ns-3600*10**9)
    if damage == "stat_missing": stat = None
    elif damage == "mtime_at_kickoff": stat.st_mtime_ns = ns
    elif damage == "ctime_at_kickoff": stat.st_ctime_ns = ns
    elif damage == "before_generated": stat.st_mtime_ns = ns-6*3600*10**9
    elif damage == "postdated_asof": s["football_recent_results"]["81"]["as_of"] = START.isoformat()
    elif damage == "before_attempt": s["last_attempt_at"] = doc["generated_at"]
    elif damage == "refresh": s["last_context_at"] = doc["generated_at"]
    elif damage == "foreign_side": row["market_comparison"]["home_id"] = True
    elif damage == "foreign_model": row["validation"]["prediction_version"] = "other"
    elif damage == "bad_scope": row["model_scope"] = "foreign"
    elif damage == "count_only":
        for r in (row, s["riskobet_source_candidates"][0]):
            r["market_key"] = "CORNERS_OVER_8_5"
    elif damage == "unknown_market": row["market_key"] = "some-new-market"
    elif damage == "conflict": row["expected_home_goals"] = 2.22
    elif damage == "bad_recent": s["football_recent_results"]["81"]["home_id"] = 3
    elif damage == "future_history": row["market_comparison"]["latest_kickoff"] = START.isoformat()
    elif damage == "bad_count": s["riskobet_source_candidate_count"] = 0
    elif damage == "wrong_day": s["search_date"] = "2026-11-23"
    elif damage == "alias_key": row["candidate_id"] = "82:RESULT_HOME"
    elif damage == "missing_goal": row.pop("expected_away_goals")
    elif damage == "new_format": s["live_goal_priors"] = None
    elif damage == "failed_projection": row["blocked_reasons"].append(
        "Gemeinsame Kalibrierung fehlgeschlagen; kohärente Rohverteilung ohne Freigabe")
    elif damage == "missing_reasons": row.pop("blocked_reasons")
    elif damage == "stale_inputs": row["blocked_reasons"].append("Letzte Formbeobachtung ist zu alt")
    elif damage == "unknown_blocker": row["blocked_reasons"].append("Neue ungültige Modellbasis")
    result = legacy.legacy_unpublished_priors(doc, stat=stat, basis_factory=_GoalBasis, model=PRIOR_MODEL)
    if damage == "none":
        assert result[81].rates == (1.547, 1.717)
        assert result[81].cutoff is None  # no independent exact input-cutoff clock in the old file
    else:
        assert 81 not in result


def test_overflowing_other_fixture_does_not_remove_good_legacy_pair(monkeypatch):
    import live_football_legacy_priors as legacy
    monkeypatch.setattr(legacy, "_POSIX_CTIME", True)
    _, doc, row = edition()
    s = doc["football"]
    invalid = deepcopy(row)
    invalid.update(fixture_id=82, candidate_id="82:RESULT_HOME", kickoff="9999-12-31T23:59:59+00:00")
    invalid["market_comparison"].update(fixture_id=82, scheduled_start=invalid["kickoff"])
    s["football_recent_results"]["82"] = dict(s["football_recent_results"]["81"],
        fixture_id=82, scheduled_start=invalid["kickoff"])
    s["discovery_candidates"].append(invalid)
    s["discovery_candidate_count"] = 2
    ns = int((START - timedelta(hours=1)).timestamp()) * 10**9
    stat = SimpleNamespace(st_mtime_ns=ns, st_ctime_ns=ns)
    result = legacy.legacy_unpublished_priors(doc, stat=stat, basis_factory=_GoalBasis, model=PRIOR_MODEL)
    assert set(result) == {81}
