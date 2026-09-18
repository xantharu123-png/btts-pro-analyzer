from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tennis.workload import observed_workload_context


NOW = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)


def _row(event_id: str, *, started_hours_ago: int, observed_hours_ago: int,
         player_a_sets: int, player_b_sets: int, duration_minutes: int) -> dict:
    return {
        "settled": 1,
        "player_a": "Alpha",
        "player_b": "Gamma",
        "fixture_source": "ESPN",
        "provider_event_id": event_id,
        "scheduled_start_utc": (NOW - timedelta(hours=started_hours_ago)).isoformat(),
        "result_observed_at": (NOW - timedelta(hours=observed_hours_ago)).isoformat(),
        "termination": "normal",
        "player_a_sets": player_a_sets,
        "player_b_sets": player_b_sets,
        "match_duration_minutes": duration_minutes,
    }


def test_disordered_start_and_receipt_times_do_not_claim_actual_recovery():
    later_started = _row(
        "later-start", started_hours_ago=52, observed_hours_ago=48,
        player_a_sets=3, player_b_sets=2, duration_minutes=230,
    )
    recently_received = _row(
        "recent-result", started_hours_ago=60, observed_hours_ago=1,
        player_a_sets=2, player_b_sets=0, duration_minutes=80,
    )

    result = observed_workload_context(
        "Alpha", "Beta", [later_started, recently_received], as_of=NOW,
    )
    player = result["players"]["a"]

    assert player["previous_match"]["event_id"] == "later-start"
    assert player["minimum_recovery_hours"] is None
    assert player["most_recent_observed_result_age_hours"] == 1
    assert player["observed_sets_7d"] == 7
    assert player["observed_minutes_7d"] == 310
    assert result["probability_adjustment_applied"] is False
    assert any("Ergebnis" in fact for fact in player["facts"])
    assert not any("tatsächliche Erholung mindestens" in fact for fact in player["facts"])
