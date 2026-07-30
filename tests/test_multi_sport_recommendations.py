import math

from multi_sport_recommendations import (
    basketball_total_candidate,
    build_candidate,
    esports_match_winner_candidate,
    evaluate_candidate_price,
    nhl_total_candidate,
)


def _basketball_game():
    return {
        "league": "NBA",
        "game_id": "nba-1",
        "home_team": "Alpha",
        "away_team": "Beta",
        "period": 3,
        "game_clock": "06:00",
        "home_score": 72,
        "away_score": 68,
        "source": "NBA.com",
    }


def _esports_match():
    return {
        "id": 55,
        "game": "CS2",
        "team1": "Alpha",
        "team2": "Beta",
        "team1_score": 1,
        "team2_score": 0,
        "series_type": 3,
        "team1_stats": {"matches": 20, "wins": 15},
        "team2_stats": {"matches": 20, "wins": 8},
    }


def test_basketball_model_is_created_before_a_bookmaker_quote_exists():
    candidate = basketball_total_candidate(_basketball_game(), 225.5)

    assert candidate.model_ready
    assert candidate.selection == "Unter 225.5 Gesamtpunkte"
    assert 50.0 < candidate.model_probability < 60.0
    assert candidate.risk_adjusted_probability < candidate.model_probability
    assert candidate.minimum_odds > candidate.fair_odds

    pending = evaluate_candidate_price(candidate, None, bankroll=100)
    assert pending.status == "PRICE_REQUIRED"
    assert pending.metrics is None

    unconfirmed = evaluate_candidate_price(candidate, 3.00, bankroll=100)
    assert unconfirmed.status == "PRICE_REQUIRED"
    assert unconfirmed.metrics is None


def test_total_models_reject_push_lines_instead_of_using_binary_ev_math():
    candidate = basketball_total_candidate(_basketball_game(), 225.0)

    assert not candidate.model_ready
    assert any("x,5" in blocker for blocker in candidate.blockers)


def test_basketball_model_rejects_stale_or_mistyped_lines():
    stale = basketball_total_candidate(_basketball_game(), 125.5)
    mistyped = basketball_total_candidate(_basketball_game(), 22.5)

    assert not stale.model_ready
    assert any("bereits erzielten" in blocker for blocker in stale.blockers)
    assert not mistyped.model_ready
    assert any("Ligabereich" in blocker for blocker in mistyped.blockers)


def test_price_gate_rejects_short_quote_and_accepts_only_sufficient_value():
    candidate = basketball_total_candidate(_basketball_game(), 225.5)

    rejected = evaluate_candidate_price(
        candidate,
        1.90,
        bankroll=500,
        quote_confirmed=True,
    )
    accepted = evaluate_candidate_price(
        candidate,
        3.00,
        bankroll=500,
        quote_confirmed=True,
    )

    assert rejected.status == "NO_BET"
    assert rejected.stake_amount == 0
    assert accepted.status == "BET"
    assert accepted.metrics.risk_adjusted_edge >= 4.0
    assert accepted.metrics.risk_adjusted_expected_roi >= 3.0
    assert accepted.stake_amount == 10.0
    assert math.isclose(accepted.stake_fraction, 0.02)


def test_nhl_model_uses_regulation_clock_and_explicit_risk_haircut():
    candidate = nhl_total_candidate(
        {
            "game_id": 1,
            "home_team": "MTL",
            "away_team": "TOR",
            "period": 2,
            "game_clock": "10:00",
            "home_score": 2,
            "away_score": 1,
        },
        5.5,
    )

    assert candidate.model_ready
    assert candidate.selection == "Über 5.5 Tore"
    assert candidate.market == "Gesamttore reguläre Spielzeit"
    assert candidate.probability_haircut == 10.0
    assert candidate.expected_total > 5.5


def test_nhl_overtime_is_never_priced_as_a_regulation_market():
    candidate = nhl_total_candidate(
        {
            "game_id": 2,
            "home_team": "MTL",
            "away_team": "TOR",
            "period": 4,
            "game_clock": "04:30",
            "home_score": 3,
            "away_score": 3,
        },
        6.5,
    )

    assert not candidate.model_ready
    assert any("Verlängerung" in blocker for blocker in candidate.blockers)


def test_esports_live_series_uses_history_uncertainty_before_price_gate():
    candidate = esports_match_winner_candidate(_esports_match())

    assert candidate.model_ready
    assert candidate.selection == "Alpha"
    assert candidate.model_probability > candidate.risk_adjusted_probability
    assert candidate.probability_haircut >= 5.0
    assert candidate.minimum_odds > 1.0

    decision = evaluate_candidate_price(
        candidate,
        candidate.minimum_odds,
        bankroll=500,
        quote_confirmed=True,
    )
    assert decision.status == "BET"
    assert decision.stake_amount > 2.0


def test_esports_history_gate_blocks_small_samples():
    match = _esports_match()
    match["team1_stats"] = {"matches": 8, "wins": 6}

    candidate = esports_match_winner_candidate(match)

    assert not candidate.model_ready
    assert any("20" in blocker for blocker in candidate.blockers)


def test_tennis_and_cricket_return_no_bet_instead_of_fake_probabilities():
    tennis = build_candidate(
        "Tennis",
        {"match_id": 1, "player1": "A", "player2": "B"},
    )
    cricket = build_candidate(
        "Cricket",
        {"match_id": 2, "team1": "A", "team2": "B"},
    )

    assert not tennis.model_ready
    assert tennis.model_probability is None
    assert not cricket.model_ready
    assert cricket.model_probability is None


def test_near_certain_probability_is_display_capped_and_flagged():
    from multi_sport_recommendations import (
        HIGH_PROBABILITY_DISPLAY_CAP,
        format_fair_odds,
        format_probability_percent,
    )

    game = _basketball_game()
    game.update({"period": 4, "game_clock": "06:00", "home_score": 110, "away_score": 105})
    candidate = basketball_total_candidate(game, 216.5)

    assert candidate.model_probability >= HIGH_PROBABILITY_DISPLAY_CAP
    assert format_probability_percent(candidate.model_probability) == "> 99.5 %"
    assert not format_probability_percent(candidate.model_probability).startswith("100")
    assert format_fair_odds(candidate.fair_odds).startswith("<")
    assert any("Eingangsdaten" in note for note in candidate.evidence)

    assert format_probability_percent(58.34) == "58.3 %"
    assert format_probability_percent(None) == "k. A."
    assert format_fair_odds(1.83) == "1.830"
    assert format_fair_odds(None) == "k. A."
