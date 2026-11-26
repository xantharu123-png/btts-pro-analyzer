"""Price-free comparison of verified live chance creation against a neutral split."""

import math

import pytest

import live_market_comparison as comparison
from scanners.ultra_live_scanner_v3 import UltraLiveScanner


def _snapshot(xg=(2.4, .12), *, red=0, minute=60, phase="2H", extra=None):
    return {
        "model_version": "live-restspiel-xg-neutral-split-v1", "live_data_quality": "LOW",
        "fixture_id": 81, "home_team_id": 1, "away_team_id": 2,
        "home_team": "Viktoria Plzeň", "away_team": "Benfica", "home_score": 1, "away_score": 0,
        "minute": minute,
        "phase_data": UltraLiveScanner._regulation_clock({"short": phase, "elapsed": minute, "extra": extra}),
        "xg_data": {"home_xg": xg[0], "away_xg": xg[1]},
        "red_cards": UltraLiveScanner._red_card_state(
            {"red_cards_home": 0, "red_cards_away": red}, home_score=1, away_score=0,
            minute=minute, red_card_minute=50 if red else None,
        ),
    }


def _btts_no(picks):
    return next(pick for pick in picks if (pick.market, pick.side) == ("ft_btts", "no"))


def test_live_xg_differential_supports_open_team_markets_not_pure_totals():
    snapshot = _snapshot()
    picks = comparison.compare_live_markets(snapshot)
    assert picks
    # After 60 minutes, 2.52 combined xG gives .63 reference rest goals per side.
    # The guest's .12 observed xG and .63 symmetric pseudo-xG give .25 rest goals.
    selected = _btts_no(picks)
    assert selected.probability == pytest.approx(math.exp(-.25))
    assert selected.reference == pytest.approx(math.exp(-.63))
    assert selected.has_clear_lift and selected.probability >= .55
    assert not any(pick.market in {"next_goal", "ft_total"} for pick in picks)
    with_quote = dict(snapshot, odds=4000., reference_odds=.01, breakdown={"remaining_away_mean": 98.})
    with_quote["xg_data"] = dict(snapshot["xg_data"], home_prior=None, away_prior=None)
    assert comparison.compare_live_markets(with_quote) == picks


@pytest.mark.parametrize("xg", [(0., 0.), (.84, .84)])
def test_zero_or_symmetric_xg_does_not_turn_a_lopsided_score_into_a_signal(xg):
    snapshot = dict(_snapshot(xg), home_score=4)
    assert comparison.compare_live_markets(snapshot) == []


def test_confirmed_dismissal_affects_only_the_unobserved_smoothing_component():
    snapshot = _snapshot(red=1)
    selected = _btts_no(comparison.compare_live_markets(snapshot))
    # At 50' trailing by one: .4 x .93 (score) x .75 (shock) x .95 (away).
    expected = math.exp(-(.12 + .63 * (.4 * .93 * .75 * .95)) / 3)
    assert selected.probability == pytest.approx(expected)
    assert selected.reference == pytest.approx(math.exp(-.63))
    assert selected.probability > _btts_no(comparison.compare_live_markets(_snapshot())).probability


@pytest.mark.parametrize("container, field, value", [
    (None, "prematch_prior_source", "any legacy source"),
    (None, "live_data_quality", "MEDIUM"),
    (None, "away_team_id", 1),
    (None, "home_score", True),
    ("xg_data", "home_xg", None),
    ("xg_data", "away_xg", float("inf")),
    ("xg_data", "home_prior", 0.),
    ("phase_data", "elapsed_minutes", 61),
    ("phase_data", "remaining_minutes", True),
    ("phase_data", "extra", 2),
    ("red_cards", "supported", False),
    ("red_cards", "home_factor", 1.25),
    ("red_cards", "away_count", 1),
])
def test_mixed_basis_uncertain_inputs_or_incompatible_clocks_fail_closed(container, field, value):
    snapshot = _snapshot()
    (snapshot[container] if container else snapshot)[field] = value
    assert comparison.compare_live_markets(snapshot) is None


@pytest.mark.parametrize("phase, minute, extra", [("1H", 45, 5), ("1H", 50, None), ("HT", 45, 5), ("HT", 46, 0)])
def test_frozen_first_half_chances_preserve_ranking_across_stoppage_and_halftime(phase, minute, extra):
    halftime = comparison.compare_live_markets(_snapshot(phase="HT", minute=45, extra=0))
    assert halftime
    # 45 regulation minutes played and 45 remaining, for either display clock.
    # Guest xG .12 and pooled pseudo-xG .84 give .576 modeled rest goals.
    assert _btts_no(halftime).probability == pytest.approx(math.exp(-.576))
    assert comparison.compare_live_markets(_snapshot(phase=phase, minute=minute, extra=extra)) == halftime


@pytest.mark.parametrize("phase, minute, extra", [("HT", 46, 40), ("1H", 50, 5), ("2H", 60, 2)])
def test_nonboundary_stoppage_cannot_duplicate_elapsed_time(phase, minute, extra):
    snapshot = _snapshot(phase=phase, minute=minute, extra=extra)
    assert comparison.compare_live_markets(snapshot) is None


@pytest.mark.parametrize("factor", [None, 0., float("nan"), 20.])
def test_bad_dismissal_factors_cannot_leak_into_a_tip(factor):
    snapshot = _snapshot(red=1)
    snapshot["red_cards"]["away_factor"] = factor
    assert comparison.compare_live_markets(snapshot) is None
