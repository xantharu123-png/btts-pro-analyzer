"""D1 outcome contracts, using saved source shapes and isolated B1 receipts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from context_observations import append_observation, observations_as_of

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def football_input():
    from context_sources.football import _detail_event
    sample = json.loads((Path(__file__).parent / "fixtures/context/football/api-football-20260909.json").read_text(encoding="utf-8"))
    raw = deepcopy(sample["calls"][0]["samples"][0])
    return _detail_event(raw), raw


def tennis_input():
    # Genuine saved ESPN envelope; changing Event.status below is only setup.
    sample = json.loads((Path(__file__).parent / "fixtures/tennis_context_espn_20260907.json").read_text(encoding="utf-8"))
    raw = deepcopy(sample["examples"][0])
    competitors = raw["competitors"]
    tour = sample["tour"]
    event = {"event_key": f"espn:tennis:{tour}:match:{raw['id']}", "sport": "tennis",
             "competition": f"espn:{tour}:tournament:{raw['event_id']}", "format": "singles",
             "home_id": f"espn:tennis:{tour}:player:{competitors[0]['id']}",
             "away_id": f"espn:tennis:{tour}:player:{competitors[1]['id']}",
             "scheduled_start": raw["date"], "schedule_revision": "outcome-source-test-v1",
             "status": "completed", "tour": tour, "surface": "Hard", "indoor": False}
    source = {"source_schema": "espn-scoreboard-v1", "tour": tour,
              "tournament_id": raw["event_id"], "competition": raw}
    return event, source


def test_native_football_result_is_separate_from_player_appearance(tmp_path):
    from context_sources.outcomes import normalize_football_outcome, validate_outcome_record
    event, raw = football_input()
    original = deepcopy(raw)
    record = normalize_football_outcome(event, raw, observed_at=NOW)
    assert record["kind"] == "match_outcome"
    assert record["payload"]["result"] == {"goals_home": raw["goals"]["home"], "goals_away": raw["goals"]["away"]}
    path = tmp_path / "outcomes.db"
    append_observation(path, record, observed_at=NOW)
    selected = observations_as_of(path, event["event_key"], cutoff=NOW, schedule_revision=event["schedule_revision"])
    assert len(selected) == 1
    assert validate_outcome_record(selected[0], event=event) == selected[0]
    assert raw == original


@pytest.mark.parametrize("terminal", ["AET", "PEN", "NS", "ABD", "CANC"])
def test_non_ft_source_does_not_invent_regulation_goal_targets(terminal):
    from context_sources.outcomes import normalize_football_outcome
    event, raw = football_input()
    raw["fixture"]["status"]["short"] = terminal
    assert normalize_football_outcome(event, raw, observed_at=NOW) is None


@pytest.mark.parametrize("goals", [None, True, "2", 1.5, -1])
def test_unknown_or_malformed_goal_target_is_not_zero(goals):
    from context_sources.outcomes import normalize_football_outcome
    event, raw = football_input()
    raw["goals"]["home"] = goals
    with pytest.raises(ContextContractError):
        normalize_football_outcome(event, raw, observed_at=NOW)


@pytest.mark.parametrize("field", ["event", "participant", "schedule", "competition"])
def test_football_outcome_must_bind_original_native_event_scope(field):
    from context_sources.outcomes import normalize_football_outcome
    event, raw = football_input()
    if field == "event":
        raw["fixture"]["id"] += 1
    elif field == "participant":
        raw["teams"]["home"]["id"] += 1
    elif field == "schedule":
        raw["fixture"]["date"] = "2026-08-23T15:00:00Z"
    else:
        raw["league"]["id"] += 1
    with pytest.raises(ContextContractError):
        normalize_football_outcome(event, raw, observed_at=NOW)


def test_native_tennis_winner_comes_from_actual_winner_identity_not_games(tmp_path):
    from context_sources.outcomes import normalize_tennis_outcome, validate_outcome_record
    event, source = tennis_input()
    record = normalize_tennis_outcome(event, source, observed_at=NOW)
    assert record is not None
    winner = next(c for c in source["competition"]["competitors"] if c["winner"] is True)
    assert record["payload"]["result"] == {"winner_id": f"espn:tennis:{event['tour']}:player:{winner['id']}"}
    path = tmp_path / "tennis-outcomes.db"
    append_observation(path, record, observed_at=NOW)
    selected = observations_as_of(path, event["event_key"], cutoff=NOW, schedule_revision=event["schedule_revision"])
    validate_outcome_record(selected[0], event=event)
    assert "service_games" not in repr(record)


@pytest.mark.parametrize("flags", [(True, True), (False, False), (1, False), (None, False)])
def test_ambiguous_or_missing_tennis_winner_flags_never_become_targets(flags):
    from context_sources.outcomes import normalize_tennis_outcome
    event, source = tennis_input()
    for competitor, flag in zip(source["competition"]["competitors"], flags):
        competitor["winner"] = flag
    with pytest.raises(ContextContractError):
        normalize_tennis_outcome(event, source, observed_at=NOW)


@pytest.mark.parametrize("terminal", ["retired", "walkover", "abandoned"])
def test_noncompleted_tennis_contract_does_not_inherit_winner_training(terminal):
    from context_sources.outcomes import normalize_tennis_outcome
    event, source = tennis_input()
    source["competition"]["status"]["type"]["description"] = terminal
    assert normalize_tennis_outcome(event, source, observed_at=NOW) is None


def test_tennis_source_competitor_order_is_bound_by_ids_not_first_item():
    from context_sources.outcomes import normalize_tennis_outcome
    event, source = tennis_input()
    original = normalize_tennis_outcome(event, source, observed_at=NOW)
    source["competition"]["competitors"].reverse()
    assert normalize_tennis_outcome(event, source, observed_at=NOW) == original


def test_results_cannot_be_received_before_the_fixture_started():
    from context_sources.outcomes import normalize_football_outcome
    event, raw = football_input()
    with pytest.raises(ContextContractError):
        normalize_football_outcome(event, raw, observed_at=datetime.fromisoformat(event["scheduled_start"])-timedelta(seconds=1))


def test_native_base_input_keeps_actual_detail_separate_from_result_target(tmp_path):
    from context_sources.outcomes import normalize_football_base_input, validate_football_base_input
    event, raw = football_input()
    record = normalize_football_base_input(raw, observed_at=NOW)
    assert record["kind"] == "base_fixture"
    assert record["payload"]["detail"] == raw
    path = tmp_path / "base.db"
    append_observation(path, record, observed_at=NOW)
    selected = observations_as_of(path, event["event_key"], cutoff=NOW, schedule_revision=event["schedule_revision"])
    assert validate_football_base_input(selected[0]) == selected[0]


def test_native_base_input_rejects_injected_price_or_calculated_xg_columns():
    from context_sources.outcomes import normalize_football_base_input
    _, raw = football_input()
    for field in ("odds", "challenge_stats"):
        changed = deepcopy(raw)
        changed[field] = {"home": 1.2}
        with pytest.raises(ContextContractError):
            normalize_football_base_input(changed, observed_at=NOW)


def serve_payload():
    event, _ = tennis_input()
    event["format"] = "singles_best_of_3"
    payload = {"schema": 1, "outcome_contract": "tennis-completed-serve-v1",
        "home_id": event["home_id"], "away_id": event["away_id"], "scheduled_start": canonical_timestamp(event["scheduled_start"]),
        "terminal": "completed", "result": {"winner_id": event["home_id"],
            "set_scores": [{"home": 6, "away": 0}, {"home": 6, "away": 0}],
            "held_games_home": 6, "service_games_home": 6, "held_games_away": 0, "service_games_away": 6}}
    return event, payload


def test_serving_targets_must_reproduce_the_observed_non_tiebreak_score():
    from context_sources.outcomes import validate_outcome_payload
    event, payload = serve_payload()
    assert validate_outcome_payload(payload, event=event) == payload
    payload["result"].update(held_games_home=0, held_games_away=6)
    with pytest.raises(ContextContractError):
        validate_outcome_payload(payload, event=event)


def test_bilateral_trials_must_allow_actual_service_alternation():
    from context_sources.outcomes import validate_outcome_payload
    event, payload = serve_payload()
    payload["result"].update(held_games_home=2, service_games_home=2, service_games_away=10)
    # Counts/holds still reconstruct 12:0, but 2 vs10 serves is impossible.
    with pytest.raises(ContextContractError):
        validate_outcome_payload(payload, event=event)


def test_tiebreak_is_not_a_held_service_game_and_next_set_server_changes():
    from context_sources.outcomes import validate_outcome_payload
    event, payload = serve_payload()
    payload["result"].update(set_scores=[{"home": 7, "away": 6}, {"home": 6, "away": 1}],
        held_games_home=9, service_games_home=9, held_games_away=7, service_games_away=10)
    assert validate_outcome_payload(payload, event=event) == payload
