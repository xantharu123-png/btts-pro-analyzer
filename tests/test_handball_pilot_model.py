import pytest


def _game(home: int, away: int, margin: int) -> tuple[int, int, int, int]:
    return (home, away, 30 + margin, 30)


def _balanced_history(margin: int = 0) -> list[tuple[int, int, int, int]]:
    return [_game(home, away, margin) for _ in range(4) for home in range(1, 5)
            for away in range(1, 5) if home != away]


def test_equal_teams_include_the_rounded_normal_draw_mass():
    from handball_pilot_model import predict_1x2

    chances = predict_1x2(iter(_balanced_history()), home_id=1, away_id=2)
    # At zero expected margin, a goal-scale standard deviation of four gives
    # P(-0.5 <= margin <= 0.5) = 2 * Phi(0.125) - 1.
    assert chances == pytest.approx({"home": 0.4502617752, "draw": 0.0994764497, "away": 0.4502617752})
    assert sum(chances.values()) == pytest.approx(1.0)


def test_home_advantage_does_not_become_a_team_strength_difference():
    from handball_pilot_model import predict_1x2

    history = _balanced_history(3)
    # A persistent three-goal home edge means P(margin > 0.5) = Phi(0.625).
    expected_home = 0.734014471
    assert predict_1x2(history, home_id=1, away_id=2)["home"] == pytest.approx(expected_home)
    assert predict_1x2(history, home_id=2, away_id=1)["home"] == pytest.approx(expected_home)


def test_stronger_opponents_explain_why_team_with_no_wins_is_favoured():
    from handball_pilot_model import predict_1x2

    history = [row for _ in range(8) for row in (
        _game(1, 3, -6), _game(3, 1, 6),  # Team 1 loses every match vs. strong 3.
        _game(2, 4, 6), _game(4, 2, -6),  # Team 2 beats weak 4 in every match.
        _game(3, 4, 16), _game(4, 3, -16),  # Direct bridge shows the gap.
    )]
    chances = predict_1x2(history, home_id=1, away_id=2)
    assert chances["home"] > chances["away"]
    assert predict_1x2(history, home_id=2, away_id=1) == pytest.approx({
        "home": chances["away"], "draw": chances["draw"], "away": chances["home"],
    })


def test_no_forecast_below_league_or_team_sample_floor():
    from handball_pilot_model import predict_1x2

    assert predict_1x2(_balanced_history()[:39], home_id=1, away_id=2) is None
    history = _balanced_history() + [_game(5, 1, 0)] * 7
    assert predict_1x2(history, home_id=5, away_id=2) is None
    assert predict_1x2(history + [_game(1, 5, 0)], home_id=5, away_id=2) is not None


def test_does_not_compare_teams_from_disconnected_schedules():
    from handball_pilot_model import predict_1x2

    history = _balanced_history() + [_game(5, 6, 0)] * 40
    assert predict_1x2(history, home_id=1, away_id=5) is None


@pytest.mark.parametrize("invalid_row", [
    (True, 2, 30, 30), (1, 2, 30.0, 30), (1, 2, -1, 30), (2, 2, 30, 30), (1, 2, 30),
])
def test_invalid_training_row_does_not_get_silently_ignored(invalid_row):
    from handball_pilot_model import predict_1x2

    assert predict_1x2(_balanced_history() + [invalid_row], home_id=1, away_id=2) is None
