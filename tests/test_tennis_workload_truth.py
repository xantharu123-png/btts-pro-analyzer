from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import closing
from copy import deepcopy

import pytest

from tennis import shadow
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


def _revisions():
    prior = _row("901", started_hours_ago=12, observed_hours_ago=8,
                 player_a_sets=2, player_b_sets=0, duration_minutes=80)
    latest = {**prior, "result_observed_at": (NOW-timedelta(hours=1)).isoformat(),
              "player_b_sets": 1, "match_duration_minutes": 120}
    return prior, latest


@pytest.mark.parametrize("newest_first", [False, True])
def test_persisted_model_generations_use_same_latest_native_result(tmp_path, newest_first):
    prior, latest = _revisions()
    path = tmp_path/"shadow.db"
    # The owning schema permits one parent per model/policy generation. An
    # old parent's terminal is not the authoritative newer event correction.
    records = ((latest, "new"), (prior, "old")) if newest_first else ((prior, "old"), (latest, "new"))
    with closing(shadow._connect(path)) as connection, connection:
        for row, model in records:
            values = {**row, "created_utc": NOW.timestamp(), "match_date": NOW.date().isoformat(),
                      "tour": "ATP", "model_version": model, "policy_version": "fixture"}
            connection.execute(
                "INSERT INTO predictions ("+','.join(values)+") VALUES ("+','.join('?' for _ in values)+")",
                tuple(values.values()))
    workload = shadow.workload_history(path)
    assert len(workload) == 2
    context = observed_workload_context("Alpha", "Beta", workload, as_of=NOW)
    player = context["players"]["a"]
    assert player["observed_matches_7d"] == 1
    assert player["observed_sets_7d"] == 3
    assert player["observed_minutes_7d"] == 120
    assert player["most_recent_observed_result_age_hours"] == 1
    assert player["minimum_recovery_hours"] is None
    assert context["probability_adjustment_applied"] is False and context["adjustment_pp"] == 0


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("correction", ["different_pair", "walkover", "unknown_terminal", "invalid_schedule"])
def test_later_identity_or_terminal_correction_cannot_reuse_old_played_work(reverse, correction):
    prior, latest = _revisions()
    if correction == "different_pair":
        latest.update(player_a="Other", player_b="Opponent")
    elif correction == "walkover":
        latest.update(termination="walkover", player_a_sets=None, player_b_sets=None,
                      match_duration_minutes=None)
    elif correction == "unknown_terminal":
        latest["termination"] = "unsupported"
    else:
        latest["scheduled_start_utc"] = None
    rows = [latest, prior] if reverse else [prior, latest]
    player = observed_workload_context("Alpha", "Beta", rows, as_of=NOW)["players"]["a"]
    assert player["previous_match"] is None
    assert player["observed_matches_7d"] == 0 and player["observed_minutes_7d"] is None


def test_future_revision_does_not_replace_result_known_at_cutoff():
    prior, latest = _revisions()
    latest["result_observed_at"] = (NOW+timedelta(seconds=1)).isoformat()
    player = observed_workload_context("Alpha", "Beta", [latest, prior], as_of=NOW)["players"]["a"]
    assert player["observed_sets_7d"] == 2 and player["observed_minutes_7d"] == 80


@pytest.mark.parametrize("reverse", [False, True])
def test_simultaneous_conflicting_revisions_do_not_choose_by_row_order(reverse):
    prior, latest = _revisions()
    prior["result_observed_at"] = latest["result_observed_at"]
    rows = [latest, prior] if reverse else [prior, latest]
    player = observed_workload_context("Alpha", "Beta", rows, as_of=NOW)["players"]["a"]
    assert player["previous_match"] is None and player["observed_minutes_7d"] is None


def test_equal_duplicate_receipts_count_once_without_mutating_history():
    _, latest = _revisions()
    duplicate = deepcopy(latest)
    rows = [latest, duplicate]
    frozen = deepcopy(rows)
    player = observed_workload_context("Alpha", "Beta", rows, as_of=NOW)["players"]["a"]
    assert player["observed_sets_7d"] == 3 and player["observed_minutes_7d"] == 120
    assert rows == frozen


def test_same_native_clock_reversed_orientation_preserves_same_observed_fact():
    _, latest = _revisions()
    reverse = {**latest, "player_a": latest["player_b"], "player_b": latest["player_a"],
               "player_a_sets": latest["player_b_sets"], "player_b_sets": latest["player_a_sets"]}
    player = observed_workload_context("Alpha", "Beta", [latest, reverse], as_of=NOW)["players"]["a"]
    assert player["observed_sets_7d"] == 3 and player["observed_minutes_7d"] == 120


@pytest.mark.parametrize("newest_first", [False, True])
def test_persisted_atp_wta_native_numbers_have_separate_revision_scopes(tmp_path, newest_first):
    prior, latest = _revisions()
    atp = {**prior, "tour": "ATP"}
    wta = {**latest, "tour": "WTA", "player_a": "Other", "player_b": "Opponent"}
    records = (wta, atp) if newest_first else (atp, wta)
    path = tmp_path/"tour-shadow.db"
    with closing(shadow._connect(path)) as connection, connection:
        for row in records:
            values = {**row, "created_utc": NOW.timestamp(), "match_date": NOW.date().isoformat(),
                      "model_version": "fixture", "policy_version": "fixture"}
            connection.execute(
                "INSERT INTO predictions ("+','.join(values)+") VALUES ("+','.join('?' for _ in values)+")",
                tuple(values.values()))
    workload = shadow.workload_history(path)
    assert len(workload) == 2 and {row["tour"] for row in workload} == {"ATP", "WTA"}
    atp_player = observed_workload_context("Alpha", "Beta", workload, as_of=NOW)["players"]["a"]
    wta_player = observed_workload_context("Other", "Unseen", workload, as_of=NOW)["players"]["a"]
    assert atp_player["observed_matches_7d"] == wta_player["observed_matches_7d"] == 1
    assert atp_player["observed_sets_7d"] == 2 and atp_player["observed_minutes_7d"] == 80
    assert wta_player["observed_sets_7d"] == 3 and wta_player["observed_minutes_7d"] == 120


@pytest.mark.parametrize("reverse", [False, True])
def test_scoped_newer_revision_does_not_also_count_legacy_unscoped_parent(reverse):
    prior, latest = _revisions()
    latest["tour"] = "ATP"
    rows = [latest, prior] if reverse else [prior, latest]
    player = observed_workload_context("Alpha", "Beta", rows, as_of=NOW)["players"]["a"]
    assert player["observed_matches_7d"] == 1
    assert player["observed_sets_7d"] == 3 and player["observed_minutes_7d"] == 120


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("simultaneous", [False, True])
def test_unscoped_new_or_equal_revision_cannot_infer_tour_or_reuse_old_scoped_parent(reverse, simultaneous):
    prior, latest = _revisions()
    prior["tour"] = "ATP"
    if simultaneous:
        latest["result_observed_at"] = prior["result_observed_at"]
    rows = [latest, prior] if reverse else [prior, latest]
    player = observed_workload_context("Alpha", "Beta", rows, as_of=NOW)["players"]["a"]
    assert player["previous_match"] is None and player["observed_matches_7d"] == 0


def test_future_unscoped_revision_cannot_withdraw_known_scoped_result():
    prior, latest = _revisions()
    prior["tour"] = "ATP"
    latest["result_observed_at"] = (NOW+timedelta(seconds=1)).isoformat()
    player = observed_workload_context("Alpha", "Beta", [latest, prior], as_of=NOW)["players"]["a"]
    assert player["observed_sets_7d"] == 2 and player["observed_minutes_7d"] == 80


def test_workload_revision_correction_does_not_change_point_probabilities_or_markets():
    from tests.test_tennis_predict import _synthetic_state
    from tennis.predict import predict_match
    from tennis.simulator import POINT_MODEL_VERSION

    state = _synthetic_state()
    state.built_at = (NOW-timedelta(days=1)).timestamp()
    state.market_model_version = POINT_MODEL_VERSION
    prior, latest = _revisions()
    for row in (prior, latest):
        row.update(player_a="Hero H.", player_b="Other O.", tour="ATP")
    baseline = predict_match(state, "Hero H.", "Grinder G.", "Hard", as_of=NOW)
    old_first = predict_match(state, "Hero H.", "Grinder G.", "Hard", as_of=NOW,
                              workload_history=[prior, latest])
    new_first = predict_match(state, "Hero H.", "Grinder G.", "Hard", as_of=NOW,
                              workload_history=[latest, prior])
    assert baseline.markets is not None
    for prediction in (old_first, new_first):
        assert prediction.p_a_raw == baseline.p_a_raw
        assert prediction.p_a_cal == baseline.p_a_cal and prediction.p_b_cal == baseline.p_b_cal
        assert prediction.markets == baseline.markets and prediction.gates == baseline.gates
        assert prediction.verdict == baseline.verdict
        assert prediction.context_evidence["probability_adjustment_applied"] is False
        assert prediction.context_evidence["adjustment_pp"] == 0
        player = prediction.context_evidence["players"]["a"]
        assert player["observed_sets_7d"] == 3 and player["observed_minutes_7d"] == 120
        assert player["minimum_recovery_hours"] is None
    assert old_first.context_evidence == new_first.context_evidence
