"""Cross-league BH-FDR (Audit 2026-10-16, M5): the family is leagues x markets.

The per-league artifact (``challenge_engine._validation_metrics_from_records``)
adjusts its paired-loss p-values over its own market catalogue only.
``cross_league_fdr.apply_cross_league_fdr`` re-adjusts the same p-values once
over every (league, market) pair of one scan run and rewrites exactly the
fields the release gate reads.
"""
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

import challenge_15k
import challenge_engine
from challenge_engine import (
    CHALLENGE_PREDICTION_VERSION,
    MARKET_SPECS,
    VALIDATION_FDR_ALPHA,
    ValidationMetrics,
)
from cross_league_fdr import apply_cross_league_fdr, cross_league_fdr_summary
from model_loss_statistics import benjamini_hochberg_q_values

M = len(MARKET_SPECS)  # 96 configured markets per league
KEY_A = MARKET_SPECS[0].key
KEY_B = MARKET_SPECS[1].key
KEY_C = MARKET_SPECS[2].key


def _tested_metric(p_value, *, q_value, released, lower_bound=0.0418, passed=True):
    """A metric that satisfies ``_credible_validation`` like the 15K fixtures."""
    return ValidationMetrics(
        observations=300,
        brier_score=0.15,
        baseline_brier_score=0.20,
        relative_improvement=0.25,
        expected_calibration_error=0.04,
        passed=passed,
        calibration_bins=4,
        min_bin_size=30,
        max_calibration_error=0.06,
        max_error_bin_size=30,
        max_error_bin_mean_probability=0.70,
        raw_brier_score=0.16,
        paired_loss_mean=0.05,
        paired_loss_hac_standard_error=0.005,
        paired_loss_lower_confidence_bound=lower_bound,
        paired_loss_p_value=p_value,
        fdr_q_value=q_value,
        tested_hypotheses=M,
        statistical_release_passed=released,
        prediction_version=CHALLENGE_PREDICTION_VERSION,
    )


def _untested_metric():
    """What the engine stores for a market without observations."""
    return ValidationMetrics(
        0, None, None, None, None, False,
        tested_hypotheses=M,
        prediction_version=CHALLENGE_PREDICTION_VERSION,
    )


def _league(p_by_key, *, lower_bound=0.0418, passed=True):
    """Per-league map exactly as the engine's own BH over MARKET_SPECS yields it."""
    family = {spec.key: p_by_key.get(spec.key, 1.0) for spec in MARKET_SPECS}
    q_values = benjamini_hochberg_q_values(family)
    league = {}
    for spec in MARKET_SPECS:
        p_value = p_by_key.get(spec.key)
        if p_value is None:
            league[spec.key] = _untested_metric()
            continue
        q_value = round(q_values[spec.key], 10)
        league[spec.key] = _tested_metric(
            p_value,
            q_value=q_value,
            released=bool(passed and lower_bound > 0.0 and q_value <= VALIDATION_FDR_ALPHA),
            lower_bound=lower_bound,
            passed=passed,
        )
    return league


def test_two_leagues_hand_calculation_widens_the_family():
    # League 39 tests one market with p = 0.0004; league 78 tests nothing.
    # Per league (n = 96):        q = 0.0004 * 96 / 1  = 0.0384 <= 0.05 -> released.
    # Family  (n = 2 * 96 = 192): q = 0.0004 * 192 / 1 = 0.0768 >  0.05 -> lost.
    before = {39: _league({KEY_A: 0.0004}), 78: _league({})}
    assert before[39][KEY_A].fdr_q_value == pytest.approx(0.0004 * M)
    assert before[39][KEY_A].statistical_release_passed is True

    after = apply_cross_league_fdr(before)

    metric = after[39][KEY_A]
    assert metric.tested_hypotheses == 2 * M
    assert metric.fdr_q_value == pytest.approx(0.0004 * 2 * M)
    assert metric.statistical_release_passed is False
    for league_key in (39, 78):
        assert set(after[league_key]) == {spec.key for spec in MARKET_SPECS}
        for key, value in after[league_key].items():
            assert value.tested_hypotheses == 2 * M
            if (league_key, key) != (39, KEY_A):
                assert value.fdr_q_value is None
                assert value.statistical_release_passed is False


def test_two_leagues_hand_calculation_step_up_keeps_strong_markets():
    # League 39: p = 0.0001 (rank 1); league 78: p = 0.0004 (rank 2); n = 192.
    # q(rank 2) = 0.0004 * 192 / 2 = 0.0384
    # q(rank 1) = min(0.0384, 0.0001 * 192 / 1 = 0.0192) = 0.0192
    before = {39: _league({KEY_A: 0.0001}), 78: _league({KEY_B: 0.0004})}

    after = apply_cross_league_fdr(before)

    assert after[39][KEY_A].fdr_q_value == pytest.approx(0.0001 * 2 * M)
    assert after[78][KEY_B].fdr_q_value == pytest.approx(0.0004 * 2 * M / 2)
    assert after[39][KEY_A].statistical_release_passed is True
    assert after[78][KEY_B].statistical_release_passed is True
    assert after[39][KEY_B].fdr_q_value is None
    assert after[78][KEY_A].fdr_q_value is None


def test_single_league_reproduces_the_per_league_artifact_exactly():
    # With one league the family equals MARKET_SPECS: nothing may change.
    before = {39: _league({KEY_A: 0.0004, KEY_B: 0.00001, KEY_C: 0.02})}

    after = apply_cross_league_fdr(before)

    for key, metric in before[39].items():
        assert asdict(after[39][key]) == asdict(metric)


def test_missing_tests_enter_the_family_with_p_one():
    # Three leagues: one tested market, one empty map, one partial map.
    # n = 3 * 96 = 288; p = 0.0002 at rank 1 -> q = 0.0576 > 0.05 (per league: 0.0192).
    partial = {
        KEY_B: _untested_metric(),
        KEY_C: _tested_metric(0.5, q_value=1.0, released=False),
    }
    before = {39: _league({KEY_A: 0.0002}), 78: {}, 140: partial}

    after = apply_cross_league_fdr(before)

    assert after[39][KEY_A].tested_hypotheses == 3 * M
    assert after[39][KEY_A].fdr_q_value == pytest.approx(0.0002 * 3 * M)
    assert after[39][KEY_A].statistical_release_passed is False
    # The same family computed by hand through the shared BH arithmetic.
    family = {
        f"{league}|{spec.key}": 1.0
        for league in (39, 78, 140)
        for spec in MARKET_SPECS
    }
    family[f"39|{KEY_A}"] = 0.0002
    family[f"140|{KEY_C}"] = 0.5
    expected = benjamini_hochberg_q_values(family)
    assert len(expected) == 3 * M
    assert after[39][KEY_A].fdr_q_value == pytest.approx(expected[f"39|{KEY_A}"])
    assert after[140][KEY_C].fdr_q_value == pytest.approx(expected[f"140|{KEY_C}"])
    # No metrics are fabricated for missing markets; untested ones stay untested.
    assert after[78] == {}
    assert set(after[140]) == {KEY_B, KEY_C}
    assert after[140][KEY_B].fdr_q_value is None
    assert after[140][KEY_B].tested_hypotheses == 3 * M


def test_only_the_release_fields_change_and_inputs_stay_untouched():
    before = {
        39: _league({KEY_A: 0.0004, KEY_B: 0.5}),
        78: _league({KEY_C: 0.0001}),
    }
    snapshot = {
        league: {key: asdict(metric) for key, metric in metrics.items()}
        for league, metrics in before.items()
    }
    changed = {"fdr_q_value", "tested_hypotheses", "statistical_release_passed"}

    after = apply_cross_league_fdr(before)

    for league_key, metrics in before.items():
        for key, metric in metrics.items():
            assert asdict(metric) == snapshot[league_key][key]  # pure function
            new = after[league_key][key]
            assert new is not metric
            old_fields = {k: v for k, v in asdict(metric).items() if k not in changed}
            new_fields = {k: v for k, v in asdict(new).items() if k not in changed}
            assert old_fields == new_fields
            assert new.tested_hypotheses == 2 * M
    # p-values rounded to 10 decimals keep p <= q as the engine gate demands.
    assert after[39][KEY_A].paired_loss_p_value <= after[39][KEY_A].fdr_q_value + 1e-9


def test_failed_base_validation_or_non_positive_lower_bound_never_releases():
    weak = {
        39: _league({KEY_A: 1e-9}, passed=False),
        78: _league({KEY_A: 1e-9}, lower_bound=-0.01),
    }

    adjusted = apply_cross_league_fdr(weak)

    # Ties at ranks 1 and 2: q = 1e-9 * 192 / 2 for both.
    assert adjusted[39][KEY_A].fdr_q_value == pytest.approx(1e-9 * 2 * M / 2, abs=1e-10)
    assert adjusted[39][KEY_A].statistical_release_passed is False
    assert adjusted[78][KEY_A].statistical_release_passed is False


def test_foreign_values_pass_through_but_occupy_a_family_slot():
    mixed = {
        39: {KEY_A: "not a metric", KEY_B: _tested_metric(0.0004, q_value=0.0384, released=True)},
        78: {},
    }

    adjusted = apply_cross_league_fdr(mixed)

    assert adjusted[39][KEY_A] == "not a metric"
    assert adjusted[39][KEY_B].tested_hypotheses == 2 * M
    assert adjusted[39][KEY_B].fdr_q_value == pytest.approx(0.0004 * 2 * M)
    assert adjusted[39][KEY_B].statistical_release_passed is False


def test_alpha_validation_empty_input_and_summary():
    assert apply_cross_league_fdr({}) == {}
    for alpha in (0.0, 1.5, float("nan"), True):
        with pytest.raises(ValueError):
            apply_cross_league_fdr({39: _league({})}, alpha=alpha)

    # Lost: per league 0.0004 -> 0.0384 (released); family rank 1 -> 0.0768.
    #       78's 0.0009 fails both ways (0.0864).
    before = {39: _league({KEY_A: 0.0004}), 78: _league({KEY_C: 0.0009})}
    after = apply_cross_league_fdr(before)
    assert cross_league_fdr_summary(before, after) == {
        "leagues": 2,
        "released_before": 1,
        "released_after": 0,
        "lost": 1,
        "gained": 0,
    }

    # Gained: BH step-up over the true family can also release a market that
    # failed alone (0.0006 * 96 = 0.0576) when twenty stronger tests precede it
    # (0.0006 * 192 / 21 = 0.0055).  That is the family-wide procedure, not a
    # tuned threshold.
    strong = {spec.key: 1e-6 for spec in MARKET_SPECS[1:21]}
    before = {39: _league({KEY_A: 0.0006}), 78: _league(strong)}
    assert before[39][KEY_A].statistical_release_passed is False
    after = apply_cross_league_fdr(before)
    assert after[39][KEY_A].statistical_release_passed is True
    assert cross_league_fdr_summary(before, after) == {
        "leagues": 2,
        "released_before": 20,
        "released_after": 21,
        "lost": 0,
        "gained": 1,
    }


def test_switch_zero_keeps_per_league_metrics(monkeypatch):
    before = {(39, 2026): _league({KEY_A: 0.0004}), (78, 2026): _league({})}

    monkeypatch.setenv("BETBOY_CROSS_LEAGUE_FDR", "0")
    assert challenge_15k.cross_league_fdr_enabled() is False
    unchanged = challenge_15k._family_adjusted_validations(before)
    assert unchanged is before
    assert unchanged[(39, 2026)][KEY_A].tested_hypotheses == M
    assert unchanged[(39, 2026)][KEY_A].statistical_release_passed is True

    monkeypatch.delenv("BETBOY_CROSS_LEAGUE_FDR", raising=False)  # Default: active.
    assert challenge_15k.cross_league_fdr_enabled() is True
    adjusted = challenge_15k._family_adjusted_validations(before)
    assert adjusted is not before
    assert adjusted[(39, 2026)][KEY_A].tested_hypotheses == 2 * M
    assert adjusted[(39, 2026)][KEY_A].statistical_release_passed is False
    assert before[(39, 2026)][KEY_A].statistical_release_passed is True

    monkeypatch.setenv("BETBOY_CROSS_LEAGUE_FDR", " 0 ")
    assert challenge_15k.cross_league_fdr_enabled() is False
    monkeypatch.setenv("BETBOY_CROSS_LEAGUE_FDR", "1")
    assert challenge_15k.cross_league_fdr_enabled() is True
    assert challenge_15k._family_adjusted_validations({}) == {}


def test_release_gate_reads_the_rewritten_statistical_release_flag():
    before = {39: _league({KEY_A: 0.0004}), 78: _league({})}
    base_gate = challenge_engine._credible_validation
    release_gate = challenge_engine._credible_statistical_release_validation
    assert base_gate(before[39][KEY_A]) is True
    assert release_gate(before[39][KEY_A]) is True

    after = apply_cross_league_fdr(before)

    lost = after[39][KEY_A]
    assert lost.statistical_release_passed is False
    # `_credible_validation` reads no statistical field: unchanged.
    assert base_gate(lost) is True
    # The statistical release gate follows the rewritten flag, not only the
    # family size.
    assert release_gate(lost) is False
    assert release_gate(replace(lost, tested_hypotheses=M)) is False


def test_release_gate_accepts_a_family_survivor_once_it_accepts_the_family_size():
    before = {39: _league({KEY_A: 0.00001}), 78: _league({})}

    after = apply_cross_league_fdr(before)

    survivor = after[39][KEY_A]
    assert survivor.statistical_release_passed is True
    assert survivor.fdr_q_value == pytest.approx(0.00001 * 2 * M)  # 0.00192
    release_gate = challenge_engine._credible_statistical_release_validation
    # Every other gate rule holds for the survivor.
    assert release_gate(replace(survivor, tested_hypotheses=M)) is True
    # The engine accepts the leagues x markets family (whole multiple of the catalog).
    assert release_gate(survivor) is True
    assert release_gate(replace(survivor, tested_hypotheses=M + 1)) is False


def _fixture(fixture_id, played_at, home_id, away_id, home_goals=None, away_goals=None, *, league_id):
    return {
        "fixture": {
            "id": fixture_id,
            "date": played_at.astimezone(timezone.utc).isoformat(),
            "status": {"short": "FT" if home_goals is not None else "NS"},
            "venue": {"city": "London"},
            "referee": "R Test",
        },
        "league": {"id": league_id, "name": f"League {league_id}", "country": "Test"},
        "teams": {
            "home": {"id": home_id, "name": f"Team {home_id}"},
            "away": {"id": away_id, "name": f"Team {away_id}"},
        },
        "goals": {"home": home_goals, "away": away_goals},
        "challenge_stats": {},
    }


def test_scan_binds_the_family_before_candidates_are_built(monkeypatch):
    monkeypatch.delenv("BETBOY_CROSS_LEAGUE_FDR", raising=False)
    target_day = date(2030, 8, 4)
    kickoff = datetime(2030, 8, 4, 18, tzinfo=timezone.utc)
    upcoming = {
        39: _fixture(900, kickoff, 100, 101, league_id=39),
        78: _fixture(901, kickoff, 200, 201, league_id=78),
    }
    histories = {
        league_id: [
            _fixture(
                league_id * 1000 + index,
                kickoff - timedelta(days=200 - index),
                base + index % 6,
                base + (index + 1) % 6,
                1 + index % 3,
                index % 2,
                league_id=league_id,
            )
            for index in range(30)
        ]
        for league_id, base in ((39, 100), (78, 200))
    }
    per_league = {39: _league({KEY_A: 0.0004}), 78: _league({})}

    provider = Mock()
    provider.errors = []
    provider.upcoming_fixtures.side_effect = lambda league_id, season, day: [upcoming[league_id]]
    provider.completed_history.side_effect = lambda league_id, season, fixtures: histories[league_id]
    provider.coverage.return_value = {"injuries": False, "lineups": False}
    provider.injuries_by_fixture.return_value = {900: [], 901: []}
    provider.details_by_fixture.return_value = {900: upcoming[39], 901: upcoming[78]}
    provider.h2h.return_value = []
    provider.weather.return_value = {
        "temperature_c": 20.0,
        "wind_kmh": 5.0,
        "precipitation_mm": 0.0,
    }

    seen = []
    real_build = challenge_15k.build_fixture_candidates

    def spy(fixture, history, validation, calibration, **kwargs):
        seen.append(validation)
        return real_build(fixture, history, validation, calibration, **kwargs)

    with patch(
        "challenge_15k._cached_market_validation",
        side_effect=lambda league_id, season, history: per_league[league_id],
    ), patch("challenge_15k._cached_market_calibration", return_value={}), patch(
        "challenge_15k.annotate_history_xg", return_value={"coverage": 1.0}
    ), patch("challenge_15k.build_fixture_candidates", side_effect=spy):
        snapshot = challenge_15k.scan_daily_challenge(provider, [39, 78], target_day, 8)

    assert snapshot["fixtures_found"] == 2
    assert len(seen) == 2
    assert {metric.tested_hypotheses for validation in seen for metric in validation.values()} == {2 * M}
    lost = [validation[KEY_A] for validation in seen if validation[KEY_A].paired_loss_p_value == 0.0004]
    assert len(lost) == 1
    assert lost[0].fdr_q_value == pytest.approx(0.0004 * 2 * M)
    assert lost[0].statistical_release_passed is False
    # The per-league artifacts handed to the scan were not mutated.
    assert per_league[39][KEY_A].statistical_release_passed is True
    assert per_league[39][KEY_A].tested_hypotheses == M
