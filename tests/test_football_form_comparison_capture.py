"""The paired measurement reuses prospective forecasts without changing them."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

import challenge_15k as scan
import challenge_engine as engine
import football_joint_calibration as joint
from tests.test_challenge_15k import fixture


def _match(kickoff=None, *, league=39):
    kickoff = kickoff or (datetime.now(timezone.utc) + timedelta(days=1))
    match = fixture(9001, kickoff, 10, 11, league_id=league)
    history = [fixture(i, kickoff - timedelta(days=i), 10 + i % 2, 11 - i % 2,
                       2, 1, league_id=league) for i in range(1, 37)]
    return match, history


def test_captures_the_exact_two_production_variants_without_changing_candidates(monkeypatch):
    match, history = _match()
    calibration = {"RESULT_HOME": lambda p: .1 + .8 * p}
    options = {"goal_model": engine.PRODUCTION_GOAL_MODEL}
    baseline = engine.build_fixture_candidates(match, history, {}, calibration, **options)
    computations = []
    original = engine.fixture_market_probabilities

    def observe(*args, **kwargs):
        model = original(*args, **kwargs)
        computations.append(model)
        return model

    monkeypatch.setattr(engine, "fixture_market_probabilities", observe)
    pairs = []
    before = datetime.now(timezone.utc)
    actual = engine.build_fixture_candidates(match, history, {}, calibration,
                                             form_comparison_capture=pairs.append, **options)
    after = datetime.now(timezone.utc)

    assert actual == baseline and actual
    model, = computations
    pair, = pairs
    captured = datetime.fromisoformat(pair["captured_at"])
    assert before <= captured <= after < datetime.fromisoformat(match["fixture"]["date"])
    assert captured.utcoffset() == timedelta(0)
    home, draw, away = (model["probabilities"][key] for key in ("RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY"))
    assert pair == {"fixture_id": 9001, "league_id": 39, "home_id": 10, "away_id": 11,
                    "kickoff": match["fixture"]["date"], "captured_at": captured.isoformat(),
                    "model_version": engine.CHALLENGE_PREDICTION_VERSION, "model_scope": "same_competition",
                    "with_form": (home[0], draw[0], away[0]), "without_form": (home[1], draw[1], away[1])}
    assert pair["with_form"][0] < pair["without_form"][0]
    assert sum(pair["with_form"]) == pytest.approx(1.)
    assert sum(pair["without_form"]) == pytest.approx(1.)


def test_capture_exception_warns_without_changing_product_candidates(caplog):
    match, history = _match()
    options = {"goal_model": engine.PRODUCTION_GOAL_MODEL}
    baseline = engine.build_fixture_candidates(match, history, {}, **options)

    def collector(_pair):
        raise RuntimeError("private collector detail")

    assert engine.build_fixture_candidates(
        match, history, {}, form_comparison_capture=collector, **options,
    ) == baseline and baseline
    warnings = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]
    assert any("form comparison" in message and "RuntimeError" in message for message in warnings)
    assert "private collector detail" not in caplog.text


def test_observer_does_not_hide_base_model_errors():
    match, history = _match()
    pairs = []
    with pytest.raises(ValueError, match="calibration target"):
        engine.build_fixture_candidates(match, history, {}, {"RESULT_HOME": lambda _p: -1.},
                                        goal_model=engine.PRODUCTION_GOAL_MODEL, form_comparison_capture=pairs.append)
    assert not pairs


@pytest.mark.parametrize("variant", ["active", "season"])
def test_failed_projection_of_either_arm_suppresses_the_pair(monkeypatch, variant):
    match, history = _match()
    real = joint.calibrate_joint_distribution
    call_in_goals = {"active": 0, "season": 1}[variant]
    calls = 0

    def fail_one(matrix, specs, *args, **kwargs):
        nonlocal calls
        projected, diag = real(matrix, specs, *args, **kwargs)
        if calls == call_in_goals:
            projected, diag = matrix, {**diag, "success": False, "status": "raw-fallback"}
        calls += 1
        return projected, diag

    monkeypatch.setattr(joint, "calibrate_joint_distribution", fail_one)
    pairs = []
    assert engine.build_fixture_candidates(match, history, {}, goal_model=engine.PRODUCTION_GOAL_MODEL,
                                           form_comparison_capture=pairs.append)
    assert not pairs


def test_unusable_pair_does_not_enter_the_capture_sink(monkeypatch):
    match, history = _match()
    compute = engine.fixture_market_probabilities

    def invalid_triplet(*args, **kwargs):
        model = compute(*args, **kwargs)
        active, _season, form = model["probabilities"]["RESULT_DRAW"]
        model["probabilities"]["RESULT_DRAW"] = (active, 0., form)
        return model

    monkeypatch.setattr(engine, "fixture_market_probabilities", invalid_triplet)
    pairs = []
    assert engine.build_fixture_candidates(match, history, {}, goal_model=engine.PRODUCTION_GOAL_MODEL,
                                           form_comparison_capture=pairs.append)
    assert not pairs


def test_club_transfer_retains_its_own_scope():
    match, history = _match(league=3)
    pairs = []
    scope = engine.MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST
    engine.build_fixture_candidates(match, history, {}, team_history=history, model_scope=scope,
                                    goal_model=engine.PRODUCTION_GOAL_MODEL, form_comparison_capture=pairs.append)
    pair, = pairs
    assert pair["model_scope"] == scope and pair["league_id"] == 3


@pytest.mark.parametrize("reason", ["late", "national_scope", "national_flag", "national_league",
                                     "legacy", "conflicting_timestamp", "naive_clock", "already_live"])
def test_does_not_capture_nonproduction_or_unproven_prematch_pairs(reason):
    kickoff = datetime.now(timezone.utc) + timedelta(days=-1 if reason == "late" else 1)
    match, history = _match(kickoff, league=5 if reason == "national_league" else 39)
    options = {"goal_model": engine.PRODUCTION_GOAL_MODEL}
    if reason == "national_scope":
        options["model_scope"] = engine.MODEL_SCOPE_SENIOR_NATIONAL
    elif reason == "national_flag":
        match["challenge_senior_national_team"] = True
    elif reason == "legacy":
        options["goal_model"] = engine.GOAL_MODEL_LEGACY
    elif reason == "conflicting_timestamp":
        match["fixture"]["timestamp"] = int(kickoff.timestamp()) - 100
    elif reason == "naive_clock":
        match["fixture"]["date"] = kickoff.replace(tzinfo=None).isoformat()
    elif reason == "already_live":
        match["fixture"]["status"]["short"] = "1H"
    pairs = []
    assert engine.build_fixture_candidates(match, history, {}, form_comparison_capture=pairs.append, **options)
    assert not pairs


def test_scan_passes_the_comparison_to_the_same_final_calc_without_extra_calls(monkeypatch):
    match, history = _match()
    kickoff = datetime.fromisoformat(match["fixture"]["date"])

    def provider():
        result = Mock(spec=scan.ChallengeDataProvider)
        result.errors = []
        result.upcoming_fixtures.return_value = [match]
        result.completed_history.return_value = history
        result.coverage.return_value = {}
        result.injuries_by_fixture.return_value = {}
        result.details_by_fixture.return_value = {}
        result.h2h.return_value = []
        return result

    monkeypatch.setattr(scan, "_cached_market_validation", lambda *args: {})
    monkeypatch.setattr(scan, "_cached_market_calibration", lambda *args: {})
    monkeypatch.setattr(scan, "annotate_history_xg", lambda *args, **kwargs: {"coverage": 1})
    plain_provider, paired_provider = provider(), provider()
    day = kickoff.astimezone(scan.CHALLENGE_TIMEZONE).date()
    options = {"candidate_profile": engine.CANDIDATE_PROFILE_WETTFINDER, "capture_live_goal_priors": False}
    plain = scan.scan_daily_challenge(plain_provider, [39], day, 20, **options)
    pairs = []
    paired = scan.scan_daily_challenge(paired_provider, [39], day, 20, form_comparison_capture=pairs.append, **options)
    pair, = pairs
    assert pair["fixture_id"] == 9001
    # Controlled equal all-venue forms: the baseline leagues' 2:1 goal rate
    # becomes 1.875:1.125 only under the existing 75/25 blend.
    assert pair["with_form"][0] == pytest.approx(.5488544729923877)
    assert pair["without_form"][0] == pytest.approx(.6057031411076684)
    assert paired["discovery_candidates"] == plain["discovery_candidates"]
    assert paired_provider.method_calls == plain_provider.method_calls
