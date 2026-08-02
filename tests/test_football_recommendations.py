from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from alternative_markets_tab_extended import _strict_market_candidate
from football_recommendations import (
    live_football_candidate,
    prematch_btts_candidate,
    red_card_candidate,
)


def _prematch_row():
    return {
        "_fixture_id": 123,
        "_fixture_date": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
        "Home": "Alpha",
        "Away": "Beta",
        "BTTS_num": 71.0,
        "Quality_num": 82.0,
        "xG Total": "3.1",
        "_analysis": {
            "ml_probability": 71.0,
            "statistical_probability": 68.0,
            "details": {
                "ml_active": True,
                "evidence_breakdown": {
                    "samples": {
                        "home_venue_matches": 9,
                        "away_venue_matches": 8,
                        "home_form_matches": 6,
                        "away_form_matches": 6,
                    }
                },
            },
        },
    }


def test_prematch_candidate_requires_validated_active_model():
    approved = prematch_btts_candidate(
        _prematch_row(),
        snapshot_age_seconds=60,
        validated_model_available=True,
    )
    assert approved.model_ready is True
    assert approved.selection == "Ja"
    assert approved.risk_adjusted_probability < approved.model_probability
    assert approved.minimum_odds > approved.fair_odds

    blocked = prematch_btts_candidate(
        _prematch_row(),
        snapshot_age_seconds=60,
        validated_model_available=False,
    )
    assert blocked.model_ready is False
    assert any("validiert" in reason for reason in blocked.blockers)


def test_live_candidate_fails_closed_for_stale_snapshot():
    candidate = live_football_candidate(
        {
            "fixture_id": 77,
            "home_team": "Alpha",
            "away_team": "Beta",
            "minute": 54,
            "score": "1-0",
            "live_data_quality": "MEDIUM",
            "model_calibrated": True,
            "red_cards": {"supported": True, "status": "VERIFIED_NONE"},
        },
        market="Noch ein Tor",
        selection="Mindestens 1 weiteres Tor",
        probability=72.0,
        snapshot_age_seconds=121,
    )
    assert candidate.model_ready is False
    assert any("älter als zwei Minuten" in reason for reason in candidate.blockers)


def test_live_candidate_blocks_uncalibrated_model():
    candidate = live_football_candidate(
        {
            "fixture_id": 77,
            "home_team": "Alpha",
            "away_team": "Beta",
            "minute": 54,
            "score": "1-0",
            "live_data_quality": "MEDIUM",
            "red_cards": {"supported": True, "status": "VERIFIED_NONE"},
        },
        market="Noch ein Tor",
        selection="Mindestens 1 weiteres Tor",
        probability=72.0,
        snapshot_age_seconds=30,
    )

    assert candidate.model_ready is False
    assert any("Kalibrierungsnachweis" in reason for reason in candidate.blockers)


def test_red_card_candidate_selects_strongest_next_goal_outcome():
    candidate = red_card_candidate(
        {
            "home": "Alpha",
            "away": "Beta",
            "score": "0-1",
            "opponent": "Beta",
            "prediction_minute": 61,
            "fixture_red_card_count": 1,
            "card": {
                "card_id": "77_1_2_60_0",
                "team": "Alpha",
                "minute": 60,
            },
            "prediction": {
                "next_goal_by_opponent": 0.64,
                "next_goal_by_red_team": 0.14,
                "no_more_goals": 0.22,
                "data_quality": "MEDIUM",
                "too_late_for_signal": False,
                "calibrated": True,
                "actionable": True,
            },
        },
        snapshot_age_seconds=30,
    )
    assert candidate.model_ready is True
    assert candidate.selection == "Beta"
    assert candidate.model_probability == 64.0
    assert candidate.risk_adjusted_probability == 49.0


def test_red_card_candidate_blocks_uncalibrated_shadow_model():
    candidate = red_card_candidate(
        {
            "home": "Alpha",
            "away": "Beta",
            "score": "0-1",
            "opponent": "Beta",
            "prediction_minute": 61,
            "fixture_red_card_count": 1,
            "card": {"card_id": "card", "team": "Alpha", "minute": 60},
            "prediction": {
                "next_goal_by_opponent": 0.70,
                "next_goal_by_red_team": 0.10,
                "no_more_goals": 0.20,
                "data_quality": "MEDIUM",
                "too_late_for_signal": False,
                "calibrated": False,
                "actionable": False,
            },
        },
        snapshot_age_seconds=30,
    )

    assert candidate.model_ready is False
    assert any("Shadow-Evidenz" in reason for reason in candidate.blockers)


def test_red_card_candidate_blocks_multiple_dismissals():
    candidate = red_card_candidate(
        {
            "home": "Alpha",
            "away": "Beta",
            "score": "0-1",
            "opponent": "Beta",
            "prediction_minute": 61,
            "fixture_red_card_count": 2,
            "card": {"card_id": "card", "team": "Alpha", "minute": 60},
            "prediction": {
                "next_goal_by_opponent": 0.70,
                "next_goal_by_red_team": 0.10,
                "no_more_goals": 0.20,
                "data_quality": "MEDIUM",
                "too_late_for_signal": False,
            },
        },
        snapshot_age_seconds=30,
    )

    assert candidate.model_ready is False
    assert any("Mehrere Platzverweise" in reason for reason in candidate.blockers)


def test_strict_market_adapter_preserves_challenge_conservative_probability():
    challenge_candidate = SimpleNamespace(
        candidate_id="123:BTTS_YES",
        kickoff=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        home_team="Alpha",
        away_team="Beta",
        market="Beide Teams treffen",
        selection="Ja",
        probability=0.72,
        conservative_probability=0.54,
        probability_haircut_pp=12.0,
        evidence_score=80.0,
        model_spread_pp=6.0,
        expected_home_goals=1.4,
        expected_away_goals=1.2,
        reasons=["Konservatives Mehrmodell-Gate"],
        blocked_reasons=[],
        context={"passed": True, "h2h": {"matches": 5}, "blocked_reasons": []},
    )

    candidate = _strict_market_candidate(challenge_candidate)

    assert candidate.model_probability == 72.0
    assert candidate.probability_haircut == 18.0
    assert candidate.risk_adjusted_probability == 54.0
