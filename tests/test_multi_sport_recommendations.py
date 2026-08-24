import math
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from bet_finder_candidates import build_probability_candidate
from multi_sport_recommendations import (
    EVIDENCE_RELEASED,
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


def _esports_history(team_id, opponent_id, wins, losses, start_id):
    total = wins + losses
    return [
        {
            "match_id": start_id + index,
            "begin_at": f"2026-07-{1 + index:02d}T12:00:00Z",
            "end_at": f"2026-07-{1 + index:02d}T14:00:00Z",
            "opponent_id": opponent_id,
            # Interleaved results: avoids path artefacts of blocked
            # win-then-loss sequences in the ELO iteration.
            "won": (index * wins) % total < wins,
            "number_of_games": 3,
        }
        for index in range(total)
    ]


def _esports_match():
    return {
        "id": 55,
        "game": "CS2",
        "team1": "Alpha",
        "team2": "Beta",
        "team1_id": 7,
        "team2_id": 8,
        "team1_score": 1,
        "team2_score": 0,
        "series_type": 3,
        "team1_stats": {"matches": 20, "wins": 15},
        "team2_stats": {"matches": 20, "wins": 8},
        "team1_history": _esports_history(7, 100, 15, 5, 1000),
        "team2_history": _esports_history(8, 100, 8, 12, 2000),
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
    assert any("Lineup- und Verletzungsdaten" in note for note in candidate.evidence)


@pytest.mark.parametrize(
    ("sport", "payload"),
    [
        (
            "Basketball",
            {
                "status": "upcoming",
                "game_id": "nba-future",
                "home_team": "Alpha",
                "away_team": "Beta",
            },
        ),
        (
            "Eishockey",
            {
                "status": "upcoming",
                "game_id": "nhl-future",
                "home_team": "Alpha",
                "away_team": "Beta",
            },
        ),
    ],
)
def test_upcoming_live_only_sports_fail_closed(sport, payload):
    candidate = build_candidate(sport, payload, market_line=5.5)

    assert not candidate.model_ready
    assert candidate.model_probability is None
    assert any("Pre-Match-Modell" in reason for reason in candidate.blockers)


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
    candidate = replace(
        basketball_total_candidate(_basketball_game(), 225.5),
        evidence_stage=EVIDENCE_RELEASED,
    )

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
    assert accepted.metrics.risk_adjusted_expected_roi >= 3.0
    assert accepted.stake_amount == 10.0
    assert math.isclose(accepted.stake_fraction, 0.02)


def test_price_gate_rejects_short_odds_even_with_extreme_probability():
    candidate = build_probability_candidate(
        event_key="short-price",
        sport="Fussball",
        event_label="Alpha vs Beta",
        market="Teamtore",
        selection="Alpha ueber 0,5",
        model_probability=99.0,
        probability_haircut=0.0,
        model_name="Testmodell",
        evidence=("Test",),
        evidence_stage=EVIDENCE_RELEASED,
    )

    assert candidate.minimum_odds == pytest.approx(1.20)
    rejected = evaluate_candidate_price(
        candidate,
        1.19,
        bankroll=500,
        quote_confirmed=True,
    )
    accepted = evaluate_candidate_price(
        candidate,
        1.20,
        bankroll=500,
        quote_confirmed=True,
    )

    assert rejected.status == "NO_BET"
    assert accepted.status == "BET"


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
    assert any("Starting-Goalie" in note for note in candidate.evidence)


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
    assert decision.status == "SHADOW"
    assert decision.stake_amount == 0.0
    assert decision.metrics.kelly_fraction > 0.0


def test_esports_history_gate_blocks_small_samples():
    match = _esports_match()
    match["team1_history"] = match["team1_history"][:8]

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
    assert any("separaten Tennis-Prematch-Pipeline" in reason for reason in tennis.blockers)
    assert any("historischer Cricket-State" in reason for reason in cricket.blockers)


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


def test_esports_series_math_matches_closed_form_negative_binomial():
    """Unabhängiger Beweis: Rekursion == geschlossene Form (neg. Binomial)."""
    from multi_sport_recommendations import _series_win_probability

    def closed_form(p, a, b, n):
        m = n - a
        return sum(
            math.comb(m - 1 + k, k) * p**m * (1 - p) ** k
            for k in range(0, n - b)
        )

    for n in (1, 2, 3, 4):  # Bo1, Bo3, Bo5, Bo7
        for a in range(0, n):
            for b in range(0, n):
                for i in range(1, 10):
                    p = i / 10.0
                    assert _series_win_probability(p, a, b, n) == (
                        pytest.approx(closed_form(p, a, b, n), abs=1e-12)
                    )


def test_esports_series_map_roundtrip_is_exact():
    from multi_sport_recommendations import (
        _map_probability_from_series_probability,
        _series_win_probability,
    )

    for n in (1, 2, 3, 4):
        for i in range(5, 96):
            series_probability = i / 100.0
            map_probability = _map_probability_from_series_probability(
                series_probability, n
            )
            assert _series_win_probability(map_probability, 0, 0, n) == (
                pytest.approx(series_probability, abs=1e-9)
            )


def test_esports_prematch_candidate_scores_upcoming_series():
    match = _esports_match()
    match.update(
        {
            "team1_score": 0,
            "team2_score": 0,
            "status": "upcoming",
            "begin_at": "2026-08-01T18:00:00Z",
        }
    )

    candidate = esports_match_winner_candidate(
        match,
        now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )

    assert candidate.model_ready
    assert candidate.selection == "Alpha"
    assert 70.0 < candidate.model_probability < 99.5
    assert candidate.probability_haircut >= 5.0
    assert any("Pre-Match" in note for note in candidate.evidence)
    assert any("Rosterwechsel und Map-Veto" in note for note in candidate.evidence)


def test_esports_prematch_rejects_stale_or_missing_start_time():
    match = _esports_match()
    match.update(
        {
            "team1_score": 0,
            "team2_score": 0,
            "status": "upcoming",
            "begin_at": "2026-08-01T11:00:00Z",
        }
    )

    stale = esports_match_winner_candidate(
        match,
        now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )
    match.pop("begin_at")
    missing = esports_match_winner_candidate(
        match,
        now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )

    assert not stale.model_ready
    assert any("bereits begonnen" in reason for reason in stale.blockers)
    assert not missing.model_ready
    assert any("Startzeit" in reason for reason in missing.blockers)


def test_esports_prematch_drops_history_that_is_not_strictly_pre_event():
    match = _esports_match()
    match.update(
        {
            "team1_score": 0,
            "team2_score": 0,
            "status": "upcoming",
            "begin_at": "2026-07-19T18:00:00Z",
        }
    )

    candidate = esports_match_winner_candidate(
        match,
        now=datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
    )

    assert not candidate.model_ready
    assert any("vor Serienbeginn" in reason for reason in candidate.blockers)


def test_esports_prematch_never_reads_a_result_after_prediction_time():
    match = _esports_match()
    match.update(
        {
            "team1_score": 0,
            "team2_score": 0,
            "status": "upcoming",
            "begin_at": "2026-08-01T18:00:00Z",
        }
    )
    match["team1_history"][-1] = {
        **match["team1_history"][-1],
        "begin_at": "2026-08-01T15:00:00Z",
    }

    candidate = esports_match_winner_candidate(
        match,
        now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )

    assert not candidate.model_ready
    assert any("vor Serienbeginn" in reason for reason in candidate.blockers)


def test_esports_prematch_requires_result_completed_strictly_before_prediction():
    match = _esports_match()
    match.update(
        {
            "team1_score": 0,
            "team2_score": 0,
            "status": "upcoming",
            "begin_at": "2026-08-01T18:00:00Z",
        }
    )
    for key in ("team1_history", "team2_history"):
        match[key] = [
            {
                **row,
                "begin_at": "2026-08-01T10:00:00Z",
                "end_at": "2026-08-01T12:00:00Z",
            }
            for row in match[key]
        ]

    candidate = esports_match_winner_candidate(
        match,
        now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )

    assert not candidate.model_ready
    assert any("Abschlusszeitpunkt" in reason for reason in candidate.blockers)


def test_esports_prematch_selects_twenty_causal_results_before_aggregating():
    match = _esports_match()
    match.update(
        {
            "team1_score": 0,
            "team2_score": 0,
            "status": "upcoming",
            "begin_at": "2026-08-01T18:00:00Z",
        }
    )
    invalid_newest = {
        **match["team1_history"][-1],
        "match_id": 9999,
        "begin_at": "2026-07-31T12:00:00Z",
        "end_at": "",
        "won": False,
    }
    match["team1_history"] = [invalid_newest, *match["team1_history"]]
    match["team1_stats"] = {"matches": 20, "wins": 0}

    candidate = esports_match_winner_candidate(
        match,
        now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )

    assert candidate.model_ready
    assert any("Alpha 15/20" in note for note in candidate.evidence)


def test_esports_live_uses_only_the_newest_twenty_completed_results(monkeypatch):
    match = _esports_match()
    match["status"] = "live"
    match["team1_history"] = _esports_history(7, 100, 18, 7, 3000)
    match["team2_history"] = _esports_history(8, 100, 9, 16, 4000)
    match["team1_history"].append(
        {
            **match["team1_history"][-1],
            "match_id": 9999,
            "begin_at": "2026-08-01T10:00:00Z",
            "end_at": "2026-08-01T13:00:00Z",
        }
    )
    match["team1_stats"] = {"matches": 25, "wins": 18}
    match["team2_stats"] = {"matches": 25, "wins": 9}
    consumed = {}

    def fake_subgraph_ratings(history1, history2, team1_id, team2_id):
        consumed["team1"] = [row["match_id"] for row in history1]
        consumed["team2"] = [row["match_id"] for row in history2]
        assert (team1_id, team2_id) == (7, 8)
        return 1550.0, 1450.0, 40

    monkeypatch.setattr(
        "multi_sport_recommendations.subgraph_ratings",
        fake_subgraph_ratings,
    )

    candidate = esports_match_winner_candidate(
        match,
        now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )

    assert candidate.model_ready
    assert consumed["team1"] == list(range(3024, 3004, -1))
    assert consumed["team2"] == list(range(4024, 4004, -1))
    assert any("Alpha 15/20" in note for note in candidate.evidence)


def test_elo_fixed_point_matches_empirical_win_rate():
    """20 direct encounters, 75 % win rate: ELO converges to the
    fixed point delta = 400 * log10(0.75/0.25) ~= 191 points."""
    from esports_elo import expected_score, subgraph_ratings

    history_a = _esports_history(7, 8, 15, 5, 3000)
    history_b = _esports_history(8, 7, 5, 15, 3000)  # same match ids
    elo_a, elo_b, size = subgraph_ratings(history_a, history_b, 7, 8)

    assert size == 20  # direct encounters are deduplicated
    assert abs((elo_a - elo_b) - 190.8) < 60.0
    assert 0.70 < expected_score(elo_a, elo_b) < 0.82


def test_elo_prices_opponent_strength_from_shared_opponent():
    """A 16-4 vs C and B 4-16 vs C must rate A clearly above B even
    though no direct A-vs-B match exists in the subgraph."""
    from esports_elo import expected_score, subgraph_ratings

    elo_a, elo_b, _ = subgraph_ratings(
        _esports_history(7, 100, 16, 4, 4000),
        _esports_history(8, 100, 4, 16, 5000),
        7,
        8,
    )

    assert 0.85 < expected_score(elo_a, elo_b) < 0.99


def test_elo_bo1_results_move_ratings_less_than_bo3():
    from esports_elo import ELO_BO1_K_MULTIPLIER, ELO_BASE, subgraph_ratings

    one_bo3 = [
        {
            "match_id": 1,
            "begin_at": "2026-07-01T12:00:00Z",
            "opponent_id": 8,
            "won": True,
            "number_of_games": 3,
        }
    ]
    one_bo1 = [dict(one_bo3[0], number_of_games=1)]
    bo3_a, _, _ = subgraph_ratings(one_bo3, [], 7, 8, iterations=1)
    bo1_a, _, _ = subgraph_ratings(one_bo1, [], 7, 8, iterations=1)

    assert (bo1_a - ELO_BASE) == pytest.approx(
        (bo3_a - ELO_BASE) * ELO_BO1_K_MULTIPLIER
    )


def test_esports_candidate_uses_elo_not_raw_winrates():
    candidate = esports_match_winner_candidate(_esports_match())

    assert candidate.model_ready
    assert candidate.model_name == "Subgraph-ELO Series v3"
    assert any("ELO" in note for note in candidate.evidence)
