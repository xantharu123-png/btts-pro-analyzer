"""Offline goal-strength comparison: no live probability or release changes."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import math

import pytest

import football_opponent_strength as model

NOW = datetime(2026, 10, 11, 9, tzinfo=timezone.utc)


def fixture(event_id=9999, home=1, away=2, *, start=None, **changes):
    result = {"fixture": {"id": event_id, "date": (start or NOW + timedelta(days=1)).isoformat(),
                          "status": {"short": "NS"}},
              "league": {"id": 39}, "teams": {"home": {"id": home}, "away": {"id": away}},
              "goals": {"home": None, "away": None}, "challenge_neutral_venue": True}
    result.update(changes)
    return result


def history(*, weak_schedule_goals=3, late_form=False):
    rows = []
    # Team 1 and team 2 have the SAME 3:1 scores, but their opponents differ.
    # Team 3 consistently concedes; team 4 is much stronger across shared games.
    for home, away, scored, conceded, count in (
        (1, 3, weak_schedule_goals, 1, 8), (2, 4, 3, 1, 8),
        (3, 4, 0, 5, 12), (5, 3, 5, 0, 8), (5, 4, 0, 3, 8),
    ):
        for _ in range(count):
            start = NOW - timedelta(days=150-len(rows))
            row = fixture(len(rows)+1, home, away, start=start)
            row["fixture"]["status"]["short"] = "FT"
            row["goals"] = {"home": scored, "away": conceded}
            row["result_observed_at"] = (start+timedelta(hours=2)).isoformat()
            rows.append(row)
    if late_form:
        for home, away in ((1, 3), (2, 4)):
            for _ in range(6):
                start = NOW-timedelta(days=25-len(rows)+44)
                row = fixture(len(rows)+1, home, away, start=start)
                row["fixture"]["status"]["short"] = "FT"
                row["goals"] = {"home": 3, "away": 1}
                row["result_observed_at"] = (start+timedelta(hours=2)).isoformat()
                rows.append(row)
    return rows


def test_identical_raw_scores_against_different_opponents_do_not_mean_equal_strength():
    result = model.compare_football_goal_strength(fixture(), history(), NOW)
    assert result.expected_away_goals > result.expected_home_goals
    assert result.p_away > result.p_home
    assert result.version == model.VERSION
    assert result.role == "experimental-offline"
    assert result.empirically_qualified is False


def test_more_goals_against_weak_defences_do_not_automatically_beat_tough_schedule():
    result = model.compare_football_goal_strength(fixture(), history(weak_schedule_goals=4), NOW)
    assert result.expected_away_goals > result.expected_home_goals
    assert result.p_away > result.p_home


def test_shared_poisson_mechanics_reproduce_existing_attack_defence_fit():
    import sports_prematch as existing
    rows = history()
    result = model.compare_football_goal_strength(fixture(), rows, NOW)
    accepted = tuple(existing._Match(str(row["fixture"]["id"]),
        datetime.fromisoformat(row["fixture"]["date"]), datetime.fromisoformat(row["result_observed_at"]),
        str(row["teams"]["home"]["id"]), str(row["teams"]["away"]["id"]),
        int(row["goals"]["home"] > row["goals"]["away"]),
        row["goals"]["home"], row["goals"]["away"], True, False) for row in rows)
    fitted = existing._fit("ice_hockey", accepted)
    expected = tuple(float(value) for value in fitted.coefficients)
    assert result.fit.coefficients == expected
    # No NHL overtime frequency or target probability is reused.
    assert result.p_home + result.p_draw + result.p_away == pytest.approx(1, abs=1e-12)


def test_score_law_is_normalized_and_derived_markets_share_the_same_law():
    result = model.compare_football_goal_strength(fixture(), history(), NOW)
    law = {(h, a): mass for h, a, mass in result.score_law}
    assert math.fsum(law.values()) == pytest.approx(1, abs=1e-12)
    assert sum(p for (h, a), p in law.items() if h > a) == result.p_home
    assert sum(p for (h, a), p in law.items() if h == a) == result.p_draw
    assert sum(p for (h, a), p in law.items() if h < a) == result.p_away


def test_side_reversal_at_neutral_venue_reverses_goal_and_winner_probabilities():
    left = model.compare_football_goal_strength(fixture(), history(), NOW)
    right = model.compare_football_goal_strength(fixture(home=2, away=1), history(), NOW)
    assert left.expected_home_goals == right.expected_away_goals
    assert left.expected_away_goals == right.expected_home_goals
    assert left.p_home == pytest.approx(right.p_away, abs=1e-12)
    assert left.p_draw == pytest.approx(right.p_draw, abs=1e-12)


def test_future_unfinished_foreign_and_late_observed_results_do_not_enter_fit():
    rows = history()
    baseline = model.compare_football_goal_strength(fixture(), rows, NOW)
    future = deepcopy(rows[0]); future["fixture"]["id"] = 9001
    future["fixture"]["date"] = (NOW+timedelta(hours=1)).isoformat()
    live = deepcopy(rows[0]); live["fixture"]["id"] = 9002; live["fixture"]["status"]["short"] = "2H"
    foreign = deepcopy(rows[0]); foreign["fixture"]["id"] = 9003; foreign["league"]["id"] = 140
    late = deepcopy(rows[0]); late["fixture"]["id"] = 9004; late["result_observed_at"] = (NOW+timedelta(hours=1)).isoformat()
    assert model.compare_football_goal_strength(fixture(), rows+[future, live, foreign, late], NOW) == baseline


@pytest.mark.parametrize("field", ["goals", "teams", "fixture"])
def test_conflicting_duplicate_native_identity_is_rejected(field):
    rows = history(); changed = deepcopy(rows[0])
    if field == "goals": changed[field]["home"] += 1
    elif field == "teams": changed[field]["away"]["id"] = 4
    else:
        changed[field]["date"] = (NOW-timedelta(days=1)).isoformat()
        changed["result_observed_at"] = (NOW-timedelta(hours=22)).isoformat()
    with pytest.raises(model.ComparisonUnavailable, match="conflicting"):
        model.compare_football_goal_strength(fixture(), rows+[changed], NOW)


def test_identical_duplicate_and_native_alias_do_not_inflate_or_reweight_fit():
    rows = history(); alias = deepcopy(rows[0]); alias["fixture"]["id"] = 5555
    expected = model.compare_football_goal_strength(fixture(), rows, NOW)
    actual = model.compare_football_goal_strength(fixture(), rows+[deepcopy(rows[0]), alias], NOW)
    assert actual == expected


def test_disconnected_target_histories_cannot_be_compared():
    rows = history()
    rows = [row for row in rows if {row["teams"]["home"]["id"], row["teams"]["away"]["id"]} <= {1, 3}]
    for row in history():
        clone = deepcopy(row)
        for side in ("home", "away"): clone["teams"][side]["id"] += 10
        clone["fixture"]["id"] += 1000
        rows.append(clone)
    with pytest.raises(model.ComparisonUnavailable, match="connected"):
        model.compare_football_goal_strength(fixture(away=12), rows, NOW)


def test_insufficient_team_history_does_not_create_a_coinflip():
    rows = [row for row in history() if row["fixture"]["id"] != 1]
    with pytest.raises(model.ComparisonUnavailable, match="eight"):
        model.compare_football_goal_strength(fixture(), rows, NOW)


@pytest.mark.parametrize("defect", ["naive", "boolean_team", "negative_goal", "unknown_status", "after_kickoff", "aet"])
def test_invalid_clock_identity_or_regulation_result_never_becomes_a_fit(defect):
    target, rows, cutoff = fixture(), history(), NOW
    if defect == "naive": cutoff = NOW.replace(tzinfo=None)
    elif defect == "boolean_team": target["teams"]["home"]["id"] = True
    elif defect == "negative_goal": rows[0]["goals"]["home"] = -1
    elif defect == "unknown_status": target["fixture"]["status"]["short"] = "FT"
    elif defect == "after_kickoff": cutoff = NOW+timedelta(days=2)
    else:
        for row in rows: row["fixture"]["status"]["short"] = "AET"
    with pytest.raises(model.ComparisonUnavailable):
        model.compare_football_goal_strength(target, rows, cutoff)


def test_source_match_bounds_are_not_a_silent_recent_suffix():
    with pytest.raises(model.ComparisonUnavailable, match="1200"):
        model.compare_football_goal_strength(fixture(), history()*28, NOW)


def test_causal_form_refits_before_each_result_and_never_uses_its_own_outcome():
    rows = history(late_form=True)
    result = model.compare_football_goal_strength(fixture(home=2, away=5), rows, NOW, include_form=True)
    assert result.form_residuals
    assert len(result.form_residuals) <= 12
    by_id = {row["fixture"]["id"]: row for row in rows}
    for residual in result.form_residuals:
        assert residual.fixture_id not in residual.prior_fixture_ids
        assert all(datetime.fromisoformat(by_id[ref]["result_observed_at"]) < residual.played_at
                   for ref in residual.prior_fixture_ids)
    changed = deepcopy(rows)
    first = result.form_residuals[0]
    row = next(row for row in changed if row["fixture"]["id"] == first.fixture_id)
    row["goals"]["home"] += 1
    after = model.compare_football_goal_strength(fixture(home=2, away=5), changed, NOW, include_form=True)
    matched = next(r for r in after.form_residuals if r.fixture_id == first.fixture_id and r.team_id == first.team_id)
    assert matched.expected_scored == first.expected_scored
    assert matched.expected_conceded == first.expected_conceded


def test_missing_receipt_clocks_do_not_support_causal_form_or_validation_claims():
    rows = history(late_form=True)
    for row in rows: row.pop("result_observed_at")
    result = model.compare_football_goal_strength(fixture(home=2, away=5), rows, NOW, include_form=True)
    assert result.receipt_clock_matches == 0
    assert result.form_residuals == ()
    assert result.empirically_qualified is False


def test_comparison_is_detached_immutable_and_never_changes_existing_fixture_model():
    from challenge_engine import _fixture_model
    target, rows = fixture(home=2, away=5), history(late_form=True)
    before = deepcopy(rows); legacy = _fixture_model(target, rows)
    result = model.compare_football_goal_strength(target, rows, NOW)
    assert rows == before
    assert _fixture_model(target, rows) == legacy
    with pytest.raises(FrozenInstanceError): result.p_home = .99
    rows[0]["goals"]["home"] = 99
    assert result.fit.matches[0].home_goals == 3


def test_fitted_home_effect_is_removed_only_for_neutral_or_unknown_venue():
    rows = []
    for cycle in range(4):
        for home in range(1, 6):
            for away in range(home+1, 6):
                if cycle % 2: home_id, away_id = away, home
                else: home_id, away_id = home, away
                start = NOW-timedelta(days=100-len(rows))
                row = fixture(len(rows)+1, home_id, away_id, start=start, challenge_neutral_venue=False)
                row["fixture"]["status"]["short"] = "FT"
                row["goals"] = {"home": 3, "away": 1}
                row["result_observed_at"] = (start+timedelta(hours=2)).isoformat()
                rows.append(row)
    neutral = model.compare_football_goal_strength(fixture(), rows, NOW)
    hosted = model.compare_football_goal_strength(fixture(challenge_neutral_venue=False), rows, NOW)
    unknown = model.compare_football_goal_strength(fixture(challenge_neutral_venue=False, challenge_venue_unknown=True), rows, NOW)
    assert hosted.fit == neutral.fit == unknown.fit
    assert hosted.expected_home_goals > neutral.expected_home_goals
    assert hosted.expected_away_goals < neutral.expected_away_goals
    assert hosted.expected_home_goals / neutral.expected_home_goals == pytest.approx(math.exp(hosted.fit.coefficients[-1]/2))
    assert unknown.expected_home_goals == neutral.expected_home_goals


def test_team_bound_is_explicit_and_does_not_drop_uncomfortable_opponents():
    rows = history()
    for team in range(6, 71):
        row = deepcopy(rows[0]); row["fixture"]["id"] = 1000+team
        row["teams"]["home"]["id"] = team; row["teams"]["away"]["id"] = 5
        rows.append(row)
    with pytest.raises(model.ComparisonUnavailable, match="64 teams"):
        model.compare_football_goal_strength(fixture(), rows, NOW)


def test_extreme_extrapolation_is_unavailable_instead_of_clipped_to_a_safe_tip():
    with pytest.raises(model.ComparisonUnavailable, match="score-law"):
        model.compare_football_goal_strength(fixture(), history(late_form=True), NOW)


def test_repeated_identical_result_at_later_receipt_does_not_change_the_fit():
    rows = history(); later = deepcopy(rows[0])
    later["result_observed_at"] = (datetime.fromisoformat(later["result_observed_at"])+timedelta(hours=3)).isoformat()
    expected = model.compare_football_goal_strength(fixture(), rows, NOW)
    assert model.compare_football_goal_strength(fixture(), rows+[later], NOW) == expected
    assert model.compare_football_goal_strength(fixture(), [later]+rows, NOW) == expected


@pytest.mark.parametrize("field,value", [("league", None), ("goals", []), ("score", [])])
def test_malformed_nested_objects_are_explicitly_unavailable(field, value):
    rows = history(); rows[0][field] = value
    with pytest.raises(model.ComparisonUnavailable):
        model.compare_football_goal_strength(fixture(), rows, NOW)


@pytest.mark.parametrize("value", [True, float("nan"), 3.0])
def test_ft_fulltime_fields_require_actual_integer_score_even_when_goals_match(value):
    rows = history(); rows[0]["score"] = {"fulltime": {"home": value, "away": 1}}
    with pytest.raises(model.ComparisonUnavailable):
        model.compare_football_goal_strength(fixture(), rows, NOW)


@pytest.mark.parametrize("target", [False, True])
@pytest.mark.parametrize("value", [None, [], "FT"])
def test_malformed_status_is_explicitly_unavailable(target, value):
    event, rows = fixture(), history()
    (event if target else rows[0])["fixture"]["status"] = value
    with pytest.raises(model.ComparisonUnavailable):
        model.compare_football_goal_strength(event, rows, NOW)


def test_csv_source_is_not_relabelled_as_native_api_history():
    rows = history(); rows[0]["challenge_source"] = "football-data-results-only"
    with pytest.raises(model.ComparisonUnavailable, match="API-Football"):
        model.compare_football_goal_strength(fixture(), rows, NOW)


def test_rolling_quality_comparison_uses_same_prefix_and_does_not_claim_prospective_proof():
    from itertools import combinations
    rows = []
    for cycle in range(8):
        for a, b in combinations(range(1, 7), 2):
            home, away = (a, b) if cycle % 2 == 0 else (b, a)
            start = NOW-timedelta(days=180-len(rows))
            row = fixture(len(rows)+1, home, away, start=start, challenge_neutral_venue=False)
            row["fixture"]["status"]["short"] = "FT"
            row["goals"] = {"home": (home+cycle) % 4, "away": (away+cycle) % 3}
            rows.append(row)
    report = model.compare_retrospective_winner_quality(rows, 39, NOW, max_targets=10)
    assert len(report.points) == 10
    assert report.receipt_clock_matches == 0
    assert report.role == "retrospective-offline-not-prospective-validation"
    assert report.empirically_qualified is False
    assert report.experimental_brier is not None and report.legacy_brier is not None
    assert report.experimental_log_loss is not None and report.legacy_log_loss is not None
    dates = {r["fixture"]["id"]: datetime.fromisoformat(r["fixture"]["date"]) for r in rows}
    for point in report.points:
        assert point.fixture_id not in point.prior_fixture_ids
        assert all(dates[ref] < point.starts_at for ref in point.prior_fixture_ids)
    frozen = deepcopy(rows)
    model.compare_retrospective_winner_quality(rows, 39, NOW, max_targets=10)
    assert rows == frozen


@pytest.mark.parametrize("value", [True, 0, 51])
def test_rolling_quality_target_bound_is_not_an_open_ended_sweep(value):
    with pytest.raises(model.ComparisonUnavailable):
        model.compare_retrospective_winner_quality(history(), 39, NOW, max_targets=value)


def test_four_year_old_result_does_not_enter_strength_or_form():
    rows = history(); old = deepcopy(rows[0]); old["fixture"]["id"] = 8888
    old["fixture"]["date"] = "2022-10-11T12:00:00+00:00"
    old["result_observed_at"] = "2022-10-11T14:00:00+00:00"
    assert model.compare_football_goal_strength(fixture(), rows+[old], NOW) == model.compare_football_goal_strength(fixture(), rows, NOW)


def test_rolling_runner_stops_a_large_generator_at_the_source_bound():
    consumed = []
    def source():
        for i in range(1300):
            consumed.append(i)
            yield history()[0]
    with pytest.raises(model.ComparisonUnavailable, match="1200"):
        model.compare_retrospective_winner_quality(source(), 39, NOW)
    assert len(consumed) == 1201


def test_rolling_runner_ignores_foreign_rows_without_a_local_fixture_shape():
    rows = history()
    expected = model.compare_retrospective_winner_quality(rows, 39, NOW)
    actual = model.compare_retrospective_winner_quality(rows+[{"league": {"id": 140}}], 39, NOW)
    assert actual == expected


def test_rolling_runner_excludes_a_legacy_rate_outside_the_existing_score_domain(monkeypatch):
    import challenge_engine
    monkeypatch.setattr(challenge_engine, "_fixture_model", lambda *args: {"active_lambdas": (9., 1.)})
    report = model.compare_retrospective_winner_quality(history(), 39, NOW)
    assert not report.points
    assert any("legacy goal rates exceed" in reason for _, reason in report.excluded)
    assert len(report.excluded) == report.attempted_targets


def test_future_receipt_revision_does_not_enter_the_legacy_paired_prefix(monkeypatch):
    import challenge_engine
    received = []
    def legacy(target, prior):
        received.append(deepcopy((target, prior)))
        return {"active_lambdas": (1.5, 1.)}
    monkeypatch.setattr(challenge_engine, "_fixture_model", legacy)
    rows = history()
    expected = model.compare_retrospective_winner_quality(rows, 39, NOW)
    revised = deepcopy(rows[0])
    revised["result_observed_at"] = (NOW+timedelta(hours=1)).isoformat()
    revised["goals"]["home"] = 99
    revised["challenge_stats"] = {"xg_home": 99., "xg_away": 99.}
    received.clear()
    assert model.compare_retrospective_winner_quality(rows+[revised], 39, NOW) == expected
    assert received
    assert all(row["goals"]["home"] != 99 and row.get("challenge_stats") != revised["challenge_stats"]
               for _, prior in received for row in prior)


def test_zero_realized_outcome_probability_is_infinite_loss_not_an_excluded_match():
    from itertools import combinations
    rows = []
    for cycle in range(8):
        for a, b in combinations(range(1, 7), 2):
            home, away = (a, b) if cycle % 2 == 0 else (b, a)
            row = fixture(len(rows)+1, home, away, start=NOW-timedelta(days=180-len(rows)),
                          challenge_neutral_venue=False)
            row["fixture"]["status"]["short"] = "FT"
            row["goals"] = {"home": 0, "away": 0}
            rows.append(row)
    rows[-1]["goals"]["home"] = 1
    report = model.compare_retrospective_winner_quality(rows, 39, NOW, max_targets=1)
    assert len(report.points) == 1 and not report.excluded
    assert report.points[0].legacy_probabilities[0] == 0
    assert report.legacy_log_loss == math.inf
    assert math.isfinite(report.experimental_log_loss)
    assert report.legacy_brier == pytest.approx(2.)
