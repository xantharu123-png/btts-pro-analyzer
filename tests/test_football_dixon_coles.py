from datetime import datetime, timedelta, timezone
import math
import random

import numpy as np
import pytest

import challenge_engine as engine
from football_dixon_coles import (
    DixonColesMatch, DixonColesUnavailable, RHO_BOUNDS, decay_weights, dixon_coles_score_matrix,
    fit_dixon_coles, fit_for_fixture, matches_from_fixtures, negative_log_likelihood, tau_correction,
)
from test_market_benchmark import synthetic_league

START = datetime(2023, 8, 1, 14, tzinfo=timezone.utc)
TRUE = dict(intercept=math.log(1.3), home=0.25, rho=-0.12)


def _true_strengths(teams=10, seed=11):
    generator = random.Random(seed)
    attack = [generator.gauss(0.0, 0.30) for _ in range(teams)]
    defence = [generator.gauss(0.0, 0.25) for _ in range(teams)]
    centre = lambda values: [v - sum(values) / len(values) for v in values]  # noqa: E731
    return centre(attack), centre(defence)


def _sample_matches(*, teams=10, double_round_robins=12, seed=11):
    """Exact Dixon-Coles sampling from the rho-corrected score law."""
    attack, defence = _true_strengths(teams, seed)
    generator = random.Random(seed + 1)
    rows, day = [], 0
    for cycle in range(double_round_robins):
        for home in range(teams):
            for away in range(teams):
                if home == away:
                    continue
                lam = math.exp(TRUE["intercept"] + attack[home] + defence[away] + TRUE["home"])
                mu = math.exp(TRUE["intercept"] + attack[away] + defence[home])
                law = dixon_coles_score_matrix(lam, mu, TRUE["rho"], max_goals=10)
                cells, weights = zip(*law.items())
                home_goals, away_goals = generator.choices(cells, weights=weights)[0]
                rows.append(DixonColesMatch(len(rows) + 1, START + timedelta(days=day), 100 + home, 100 + away,
                                            home_goals, away_goals, True))
                day += 0.25
    return rows, attack, defence


def test_fit_recovers_the_generating_parameters_on_exact_dixon_coles_samples():
    rows, attack, defence = _sample_matches()
    cutoff = max(row.played_at for row in rows) + timedelta(days=1)
    fit = fit_dixon_coles(rows, cutoff, half_life_days=1e9, max_history_days=10_000)
    assert fit.converged and fit.matches == len(rows)
    assert abs(fit.home_advantage - TRUE["home"]) < 0.08
    assert abs(fit.rho - TRUE["rho"]) < 0.06
    assert abs(fit.intercept - TRUE["intercept"]) < 0.10
    fitted_attack = np.array(fit.attack)
    fitted_defence = np.array(fit.defence)
    assert np.corrcoef(fitted_attack, np.array(attack))[0, 1] > 0.9
    assert np.corrcoef(fitted_defence, np.array(defence))[0, 1] > 0.9
    assert abs(fitted_attack.mean()) < 1e-9 and abs(fitted_defence.mean()) < 1e-9  # Centred after the fit.


def test_analytic_gradient_matches_finite_differences():
    rows, _, _ = _sample_matches(teams=5, double_round_robins=3, seed=3)
    cutoff = max(row.played_at for row in rows) + timedelta(days=1)
    from football_dixon_coles import _design
    teams, home, away, x, y, known, weights = _design(tuple(rows), cutoff, 90.0)
    generator = np.random.default_rng(5)
    params = np.concatenate(([0.2, 0.3, -0.1], generator.normal(0, 0.3, 2 * len(teams))))
    value, gradient = negative_log_likelihood(params, home, away, x, y, known, weights, len(teams))
    numeric = np.zeros_like(params)
    for index in range(len(params)):
        step = np.zeros_like(params)
        step[index] = 1e-6
        up, _ = negative_log_likelihood(params + step, home, away, x, y, known, weights, len(teams))
        down, _ = negative_log_likelihood(params - step, home, away, x, y, known, weights, len(teams))
        numeric[index] = (up - down) / 2e-6
    assert np.allclose(gradient, numeric, rtol=1e-4, atol=1e-5)
    assert math.isfinite(value)


def test_rho_zero_is_exactly_the_engine_poisson_law_and_negative_rho_moves_low_score_mass():
    independent = engine.score_matrix(1.45, 1.05)
    assert dixon_coles_score_matrix(1.45, 1.05, 0.0) == pytest.approx(independent, abs=1e-12)
    assert engine.score_matrix(1.45, 1.05, rho=0.0) == independent  # Byte-identical default path.
    corrected = engine.score_matrix(1.45, 1.05, rho=-0.12)
    assert math.isclose(sum(corrected.values()), 1.0, abs_tol=1e-12)
    assert corrected[(0, 0)] > independent[(0, 0)] and corrected[(1, 1)] > independent[(1, 1)]
    assert corrected[(1, 0)] < independent[(1, 0)] and corrected[(0, 1)] < independent[(0, 1)]
    assert corrected[(2, 2)] == pytest.approx(independent[(2, 2)] * (1.0 / sum(
        independent[c] * tau_correction(c[0], c[1], 1.45, 1.05, -0.12) for c in independent)), rel=1e-9)
    with pytest.raises(ValueError):
        engine.score_matrix(1.45, 1.05, rho=1.5)


def test_decay_weights_and_fail_closed_thresholds():
    assert decay_weights(np.array([0.0, 120.0, 240.0]), 120.0) == pytest.approx([1.0, 0.5, 0.25])
    with pytest.raises(ValueError):
        decay_weights(np.array([1.0]), 0.0)
    rows, _, _ = _sample_matches(teams=4, double_round_robins=1, seed=2)  # 12 matches only.
    with pytest.raises(DixonColesUnavailable):
        fit_dixon_coles(rows, max(r.played_at for r in rows) + timedelta(days=1))
    with pytest.raises(ValueError):
        fit_dixon_coles(rows, datetime(2024, 1, 1))  # Naive clock refused.


def test_engine_default_path_is_unchanged_and_the_opt_in_path_is_fail_closed():
    fixtures = synthetic_league(rounds=6)
    assert engine._walk_forward_market_records(fixtures) == engine._walk_forward_market_records(fixtures, goal_model="legacy")
    history, target = fixtures[:-1], fixtures[-1]
    legacy = engine.fixture_market_probabilities(target, history, None, _validation_only=True)
    explicit = engine.fixture_market_probabilities(target, history, None, _validation_only=True, goal_model="legacy")
    assert legacy["probabilities"] == explicit["probabilities"] and "goal_model" not in legacy
    dixon = engine.fixture_market_probabilities(target, history, None, _validation_only=True, goal_model="dixon_coles")
    assert dixon is not None and dixon["goal_model"] == "dixon_coles"
    assert RHO_BOUNDS[0] <= dixon["rho"] <= RHO_BOUNDS[1] and dixon["dixon_coles"]["converged"] is True
    # The projection step rewrites the active means from the effective matrix;
    # the raw fitted rates are shared by all three variants (spread = 0).
    assert dixon["raw_active_lambdas"] == dixon["season_lambdas"] == dixon["form_lambdas"]
    assert dixon["raw_active_lambdas"] != legacy["raw_active_lambdas"]
    home, draw, away = (dixon["probabilities"][k][0] for k in ("RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY"))
    assert math.isclose(home + draw + away, 1.0, abs_tol=1e-9)
    over, under = (dixon["probabilities"][k][0] for k in ("TOTAL_OVER_2_5", "TOTAL_UNDER_2_5"))
    assert math.isclose(over + under, 1.0, abs_tol=1e-9)
    # Since 22.10.2026 an ORIGINAL may capture a non-legacy basis; it names that basis.
    captured = []
    assert engine.fixture_market_probabilities(target, history, None, goal_model="dixon_coles",
                                              original_capture=captured.append) is not None
    assert captured[0].to_dict()["goal_model"]["goal_model"] == "dixon_coles"
    with pytest.raises(ValueError):
        engine.fixture_market_probabilities(target, history, None, goal_model="something_else")
    assert engine.fixture_market_probabilities(target, history[:10], None, _validation_only=True, goal_model="dixon_coles") is None


def test_fit_for_fixture_uses_only_matches_before_the_kickoff_day():
    fixtures = synthetic_league(rounds=6)
    target = fixtures[-1]
    rows = matches_from_fixtures(fixtures)
    assert len(rows) == len(fixtures) and all(row.home_effect_known for row in rows)
    fit = fit_for_fixture(target, fixtures)  # The target itself is in the list but after the cutoff.
    kickoff = datetime.fromisoformat(target["fixture"]["date"])
    assert fit.cutoff == kickoff.replace(hour=0, minute=0, second=0, microsecond=0)
    assert fit.matches == sum(1 for row in rows if row.played_at < fit.cutoff)
    assert fit_for_fixture(target, fixtures) is fit  # Cached per league, day and history.


def test_rho_is_projected_into_the_range_valid_for_extreme_rates():
    from football_dixon_coles import clamp_rho, valid_rho_range
    lower, upper = valid_rho_range(5.0, 0.8)
    assert lower == pytest.approx(-0.2, abs=1e-5) and upper == pytest.approx(0.25, abs=1e-5)
    assert clamp_rho(-0.25, 5.0, 0.8) == pytest.approx(lower)
    assert clamp_rho(-0.05, 5.0, 0.8) == -0.05
    law = engine.score_matrix(5.0, 0.8, rho=clamp_rho(-0.25, 5.0, 0.8))
    assert math.isclose(sum(law.values()), 1.0, abs_tol=1e-12) and all(v >= 0 for v in law.values())
    with pytest.raises(ValueError):
        engine.score_matrix(5.0, 0.8, rho=-0.25)


def test_level_prior_matches_the_unweighted_scoring_level_of_the_window():
    import numpy as np
    rows, _, _ = _sample_matches(teams=8, double_round_robins=6, seed=9)
    cutoff = max(row.played_at for row in rows) + timedelta(days=1)
    pinned = fit_dixon_coles(rows, cutoff, half_life_days=30.0, max_history_days=10_000, level_prior=True)
    free = fit_dixon_coles(rows, cutoff, half_life_days=30.0, max_history_days=10_000)
    def mean_predicted(fit):
        return np.mean([sum(fit.rates(r.home_id, r.away_id)) for r in rows])
    observed = np.mean([r.home_goals + r.away_goals for r in rows])
    assert mean_predicted(pinned) == pytest.approx(observed, rel=1e-6)
    assert pinned.version.endswith("-level") and not free.version.endswith("-level")
    assert pinned.converged and pinned.rho == free.rho and pinned.attack == free.attack  # Only the level moves.
    assert abs(sum(pinned.attack)) < 1e-9 and abs(sum(pinned.defence)) < 1e-9


def test_engine_accepts_every_registered_variant_and_keeps_the_default_identical():
    fixtures = synthetic_league(rounds=6)
    history, target = fixtures[:-1], fixtures[-1]
    baseline = engine.fixture_market_probabilities(target, history, None, _validation_only=True)
    for name, options in engine.GOAL_MODEL_OPTIONS.items():
        result = engine.fixture_market_probabilities(target, history, None, _validation_only=True, goal_model=name)
        assert result is not None and result["goal_model"] == name
        assert result["dixon_coles"]["half_life_days"] == options["half_life_days"]
        assert result["dixon_coles"]["version"].endswith("-level") is options["level_prior"]
    again = engine.fixture_market_probabilities(target, history, None, _validation_only=True)
    assert again["probabilities"] == baseline["probabilities"] and "goal_model" not in again


def _sample_venue_matches(*, teams=8, double_round_robins=10, seed=21):
    """Teams score differently at home and away: separate venue strengths."""
    generator = random.Random(seed)
    att_h = [generator.gauss(0.0, 0.3) for _ in range(teams)]
    att_a = [generator.gauss(0.0, 0.3) for _ in range(teams)]
    dfc = [generator.gauss(0.0, 0.2) for _ in range(teams)]
    rows, day = [], 0
    for _ in range(double_round_robins):
        for home in range(teams):
            for away in range(teams):
                if home == away:
                    continue
                lam = math.exp(math.log(1.4) + att_h[home] + dfc[away] + 0.2)
                mu = math.exp(math.log(1.4) + att_a[away] + dfc[home])
                law = dixon_coles_score_matrix(lam, mu, -0.1, max_goals=10)
                cells, weights = zip(*law.items())
                hg, ag = generator.choices(cells, weights=weights)[0]
                rows.append(DixonColesMatch(len(rows) + 1, START + timedelta(days=day), 200 + home, 200 + away, hg, ag, True))
                day += 0.25
    return rows, att_h, att_a


def test_venue_specific_fit_separates_home_and_away_attack():
    import numpy as np
    rows, att_h, att_a = _sample_venue_matches()
    cutoff = max(r.played_at for r in rows) + timedelta(days=1)
    fit = fit_dixon_coles(rows, cutoff, half_life_days=1e9, max_history_days=10_000, venue_specific=True)
    assert fit.converged and fit.venue_specific and fit.version.endswith("-venue")
    assert np.corrcoef(np.array(fit.attack), np.array(att_h))[0, 1] > 0.8
    assert np.corrcoef(np.array(fit.attack_away), np.array(att_a))[0, 1] > 0.8
    assert abs(sum(fit.attack)) < 1e-9 and abs(sum(fit.attack_away)) < 1e-9
    assert 0.05 < fit.home_advantage < 0.4  # Generated with 0.2.
    plain = fit_dixon_coles(rows, cutoff, half_life_days=1e9, max_history_days=10_000)
    assert not plain.venue_specific and plain.attack_away is None
    assert fit.log_likelihood > plain.log_likelihood  # More parameters fit the venue data better.
    # Analytic gradient of the venue likelihood matches finite differences.
    from football_dixon_coles import _design
    teams, home, away, x, y, known, weights = _design(tuple(rows[:120]), cutoff, 90.0)
    params = np.concatenate(([0.3, 0.0, -0.1], np.random.default_rng(2).normal(0, 0.2, 4 * len(teams))))
    _, grad = negative_log_likelihood(params, home, away, x, y, known, weights, len(teams), venue_specific=True)
    numeric = np.zeros_like(params)
    for i in range(len(params)):
        step = np.zeros_like(params); step[i] = 1e-6
        up, _ = negative_log_likelihood(params + step, home, away, x, y, known, weights, len(teams), venue_specific=True)
        down, _ = negative_log_likelihood(params - step, home, away, x, y, known, weights, len(teams), venue_specific=True)
        numeric[i] = (up - down) / 2e-6
    assert np.allclose(grad, numeric, rtol=1e-4, atol=1e-5)


def test_hybrid_matrix_keeps_the_legacy_total_law_and_the_dixon_coles_split():
    from football_dixon_coles import reweight_totals
    legacy = engine.score_matrix(1.6, 1.2)
    dixon = engine.score_matrix(1.9, 0.9, rho=-0.1)
    hybrid = reweight_totals(legacy, dixon)
    assert math.isclose(sum(hybrid.values()), 1.0, abs_tol=1e-12)
    def totals(matrix):
        out = {}
        for (h, a), p in matrix.items():
            out[h + a] = out.get(h + a, 0.0) + p
        return out
    for total, mass in totals(legacy).items():
        assert math.isclose(totals(hybrid)[total], mass, abs_tol=1e-12)
    # Within a total line the split follows Dixon-Coles, not legacy.
    assert math.isclose(hybrid[(2, 0)] / hybrid[(0, 2)], dixon[(2, 0)] / dixon[(0, 2)], rel_tol=1e-9)
    assert hybrid[(2, 0)] / hybrid[(0, 2)] > legacy[(2, 0)] / legacy[(0, 2)]


def test_engine_hybrid_variant_uses_the_override_and_keeps_totals_at_legacy():
    fixtures = synthetic_league(rounds=6)
    history, target = fixtures[:-1], fixtures[-1]
    legacy = engine.fixture_market_probabilities(target, history, None, _validation_only=True)
    hybrid = engine.fixture_market_probabilities(target, history, None, _validation_only=True, goal_model="dixon_coles_hl365_hybrid")
    assert hybrid["goal_model"] == "dixon_coles_hl365_hybrid" and hybrid.get("goal_matrix_override") is not None
    for key in ("TOTAL_OVER_2_5", "TOTAL_UNDER_1_5", "BTTS_YES"):
        if key in ("TOTAL_OVER_2_5", "TOTAL_UNDER_1_5"):
            assert hybrid["raw_probabilities"][key][0] == pytest.approx(legacy["raw_probabilities"][key][0], abs=1e-9)
    assert hybrid["raw_probabilities"]["RESULT_HOME"][0] != pytest.approx(legacy["raw_probabilities"]["RESULT_HOME"][0], abs=1e-6)
    venue = engine.fixture_market_probabilities(target, history, None, _validation_only=True, goal_model="dixon_coles_venue")
    assert venue is not None and venue["dixon_coles"]["venue_specific"] is True
