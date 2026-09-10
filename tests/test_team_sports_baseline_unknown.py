"""R1 unknown status is not adverse evidence; R2 completed-only was withdrawn."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import json

import pytest

from test_team_sports_baseline import SPORTS, live_worker, correction
from test_team_sports_binding import native_game, record


def both_views(case, document):
    from riskobet_automation import load_latest_riskobet
    latest = load_latest_riskobet(db_path=case.path.with_name("riskobet.db"),
        latest_path=case.path.with_name("riskobet_latest.json"), rehydrate=True)
    return len(document["model_candidates"]), len(latest.snapshots)


def unknown_with_identity(case, sport, field):
    provider = "ESPN" if sport == "basketball" else "NHL"
    body = deepcopy(case.state["bodies"][-1])
    game = native_game(provider, body)
    if provider == "ESPN":
        game["status"] = {"type": dict(state="pre", name="NOT_A_KNOWN_STATE", completed=False)}
        if field == "missing-participant": game["competitors"] = game["competitors"][:1]
        elif field == "changed-participant": game["competitors"][1]["team"]["id"] = "66"
        elif field == "missing-schedule": game.pop("date")
        elif field == "changed-schedule": game["date"] = (case.state["now"]+timedelta(hours=3)).isoformat()
    else:
        game["gameState"] = "NOT_A_KNOWN_STATE"
        if field == "missing-participant": game.pop("awayTeam")
        elif field == "changed-participant": game["awayTeam"]["id"] = 66
        elif field == "missing-schedule": game.pop("startTimeUTC")
        elif field == "changed-schedule": game["startTimeUTC"] = (case.state["now"]+timedelta(hours=3)).isoformat()
    record(case.context_path, provider, body, target=True, observed=case.state["now"])


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("mode", ["acquisition", "reuse", "failed-fallback"])
@pytest.mark.parametrize("adverse", ["cancelled", "started"])
def test_later_unknown_does_not_erase_last_proven_adverse_status(live_worker, sport, mode, adverse):
    case = live_worker(sport, start_offset=timedelta(hours=7))
    old = case.run() if mode != "acquisition" else None
    if old is not None:
        case.state["now"] += timedelta(hours=6 if mode == "failed-fallback" else 0, seconds=1)
    def corrections():
        correction(case, sport, adverse, observed=case.state["now"]-timedelta(microseconds=1))
        correction(case, sport, "unknown")
    if mode == "reuse": corrections()
    else: case.state["on_history"] = corrections
    case.state["history_error"] = mode == "failed-fallback"
    doc = case.run()
    assert both_views(case, doc) == (0, 0)
    assert len(case.state["predictions"]) == int(old is not None)
    if old is not None:
        assert doc["team_sports_baselines"][sport]["entries"] == old["team_sports_baselines"][sport]["entries"]


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("field", ["missing-participant", "changed-participant", "missing-schedule", "changed-schedule"])
@pytest.mark.parametrize("mode", ["acquisition", "reuse", "failed-fallback"])
def test_unknown_status_cannot_hide_current_native_identity_defects(live_worker, sport, field, mode):
    case = live_worker(sport, start_offset=timedelta(hours=7))
    old = case.run() if mode != "acquisition" else None
    if old is not None:
        case.state["now"] += timedelta(hours=6 if mode == "failed-fallback" else 0, seconds=1)
    callback = lambda: unknown_with_identity(case, sport, field)
    if mode == "reuse": callback()
    else: case.state["on_history"] = callback
    case.state["history_error"] = mode == "failed-fallback"
    doc = case.run()
    assert both_views(case, doc) == (0, 0)
    assert len(case.state["predictions"]) == int(old is not None)


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_only_later_known_scheduled_revision_clears_proven_cancellation(live_worker, sport, offset):
    case = live_worker(sport)
    first = case.run()
    case.state["now"] += timedelta(seconds=2)
    canceled_at = case.state["now"]-timedelta(seconds=1)
    correction(case, sport, "cancelled", observed=canceled_at)
    provider = "ESPN" if sport == "basketball" else "NHL"
    record(case.context_path, provider, deepcopy(case.state["bodies"][-1]), target=True,
        observed=canceled_at+timedelta(microseconds=offset))
    # The later uninformative row is not the reason to restore the baseline.
    correction(case, sport, "unknown")
    document = case.run()
    assert both_views(case, document) == (int(offset > 0), int(offset > 0))
    assert len(case.state["predictions"]) == case.state["history"] == 1
    assert document["team_sports_baselines"] == first["team_sports_baselines"]


@pytest.mark.parametrize("sport", SPORTS)
def test_valid_partial_views_survive_repeated_errors_without_retiming_original(live_worker, sport):
    case = live_worker(sport)
    case.state["source_wrapper"] = lambda batch: replace(batch, errors=("source_partial",))
    first = case.run()
    old = deepcopy(first["team_sports_baselines"][sport])
    assert old["status"] == "partial" and old["entries"]
    case.state["source_wrapper"], case.state["history_error"] = None, True
    for number in range(3):
        case.state["now"] += timedelta(seconds=1)
        document = case.run()
        batch = document["team_sports_baselines"][sport]
        assert batch["status"] == "partial" and batch["errors"] == ["source_failed"]
        assert batch["entries"] == old["entries"]
        assert batch["checked_at"] != old["checked_at"]
        assert both_views(case, document) == (1, 1)
        assert len(case.state["predictions"]) == 1 and case.state["history"] == number+2


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("mutation", ["dropped-row", "count-bool", "count-float", "count-fraction", "count-missing", "count-low"])
def test_baseline_publication_count_checks_both_directions_without_recomputing(live_worker, sport, mutation):
    from ev_signal_sources import automated_wettfinder_snapshot
    case = live_worker(sport)
    document = case.run()
    if mutation == "dropped-row": document["model_candidates"] = []
    elif mutation == "count-missing": document["sources"][sport].pop("candidate_count")
    else:
        document["sources"][sport]["candidate_count"] = {
            "count-bool": True, "count-float": 1.0, "count-fraction": 1.5, "count-low": 0}[mutation]
    case.path.write_text(json.dumps(document), encoding="utf-8")
    loaded = automated_wettfinder_snapshot(case.path, now=case.state["now"])
    assert loaded.status is None and loaded.forecasts == ()


@pytest.mark.parametrize("sport", SPORTS)
@pytest.mark.parametrize("mode", ["acquisition", "reuse", "failed-fallback"])
@pytest.mark.parametrize("kind", ["status", "participants", "schedule"])
def test_simultaneous_native_revision_conflicts_are_not_missing_status(live_worker, sport, mode, kind):
    case = live_worker(sport, start_offset=timedelta(hours=7))
    old = case.run() if mode != "acquisition" else None
    if old is not None:
        case.state["now"] += timedelta(hours=6 if mode == "failed-fallback" else 0, seconds=1)
    def simultaneous():
        correction(case, sport, "unknown")
        if kind == "status":
            # Same native identity, but two different current source states.
            provider = "ESPN" if sport == "basketball" else "NHL"
            record(case.context_path, provider, deepcopy(case.state["bodies"][-1]),
                target=True, observed=case.state["now"])
        else:
            unknown_with_identity(case, sport, "changed-participant" if kind == "participants" else "changed-schedule")
    if mode == "reuse": simultaneous()
    else: case.state["on_history"] = simultaneous
    case.state["history_error"] = mode == "failed-fallback"
    document = case.run()
    assert both_views(case, document) == (0, 0)
    assert len(case.state["predictions"]) == int(old is not None)


@pytest.mark.parametrize("sport", SPORTS)
def test_zero_published_count_allows_current_lifecycle_withdrawal_without_reconstruction(live_worker, sport):
    from ev_signal_sources import automated_wettfinder_snapshot
    case = live_worker(sport)
    first = case.run()
    case.state["now"] += timedelta(seconds=1)
    correction(case, sport, "cancelled")
    document = case.run()
    assert both_views(case, document) == (0, 0)
    assert document["sources"][sport]["candidate_count"] == 0
    assert document["team_sports_baselines"] == first["team_sports_baselines"]
    counts = (len(case.state["predictions"]), case.state["history"], case.state["requests"])
    loaded = automated_wettfinder_snapshot(case.path, now=case.state["now"])
    assert loaded.status is not None and loaded.forecasts == ()
    assert (len(case.state["predictions"]), case.state["history"], case.state["requests"]) == counts
