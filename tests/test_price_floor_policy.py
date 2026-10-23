"""Price policy since 23.10.2026: only the 1.20 floor, checked in the background.

Owner decision (docs/audits/2026-10-23-preisregel-1-20.md): public tips follow the
model and the context gates; bookmaker quotes are neither shown nor a release
gate. ``BETBOY_PRICE_POLICY=gate`` restores the previous execution contract,
which the older suites keep documenting (tests/conftest.py pins it for them).
"""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

import market_consensus as mc
import wettfinder_automation as automation
import wettfinder_surface as surface
from daily3_selection import Daily3Choice, reservation_minimum_odds
from multi_sport_recommendations import evaluate_candidate_price
from tests.test_wettfinder_surface import NOW, _quote, _signal


@pytest.fixture(autouse=True)
def floor_policy(monkeypatch):
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "floor")


def test_policy_defaults_to_floor_and_gate_restores_the_old_contract(monkeypatch):
    monkeypatch.delenv(mc.PRICE_POLICY_FLAG, raising=False)
    assert mc.price_policy() == "floor" and mc.floor_only_pricing()
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    assert mc.price_policy() == "gate" and not mc.floor_only_pricing()
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "anything-else")
    assert mc.floor_only_pricing()


def test_floor_status_ignores_freshness_and_model_minimum_but_withholds_below_1_20():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    binding = surface.wettfinder_quote_binding_candidate(signal)
    assert mc.floor_price_status(None, now=NOW).code == "UNPRICED"
    aged = _quote(signal, odds=(1.76, 1.80, 1.84), fetched_at=NOW - timedelta(hours=5))
    status = mc.wettfinder_reference_price_status(aged, 2.5, candidate=binding, now=NOW)
    assert status.code == "PLAYABLE" and status.usable_odds == 1.84 and status.bookmaker
    assert mc.reference_price_status(aged, 2.5, now=NOW).code == "PLAYABLE"
    low = _quote(signal, odds=(1.10, 1.15, 1.18), fetched_at=NOW - timedelta(minutes=5))
    assert mc.wettfinder_reference_price_status(low, None, candidate=binding, now=NOW).code == "BELOW_FLOOR"
    ancient = _quote(signal, odds=(1.76, 1.80, 1.84), fetched_at=NOW - timedelta(hours=25))
    assert mc.wettfinder_reference_price_status(ancient, None, candidate=binding, now=NOW).code == "UNPRICED"
    # A quote bound to another candidate is no evidence either way.
    other = surface.wettfinder_quote_binding_candidate(_signal(key="other", market_key="RESULT_HOME", selection="1"))
    assert mc.wettfinder_reference_price_status(aged, None, candidate=other, now=NOW).code == "UNPRICED"


def test_gate_policy_still_marks_a_five_hour_old_quote_stale(monkeypatch):
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    aged = _quote(signal, fetched_at=NOW - timedelta(hours=5))
    status = mc.wettfinder_reference_price_status(
        aged, 1.5, candidate=surface.wettfinder_quote_binding_candidate(signal), now=NOW)
    assert status.code == "STALE"


def test_floor_playable_rows_keep_unpriced_forecasts_and_drop_only_below_floor():
    rows = [
        {"candidate_id": "a", "status": "MODEL_SELECTION", "reference_price_status": "UNAVAILABLE"},
        {"candidate_id": "b", "status": "MODEL_SELECTION", "reference_price_status": "UNPRICED"},
        {"candidate_id": "c", "status": "MODEL_SELECTION", "reference_price_status": "PLAYABLE"},
        {"candidate_id": "d", "status": "MODEL_SELECTION", "reference_price_status": "BELOW_FLOOR"},
        "not-a-row",
    ]
    playable = automation._floor_playable_rows(rows)
    assert [row["candidate_id"] for row in playable] == ["a", "b", "c"]
    assert all(row["status"] == "PRICE_REQUIRED" for row in playable)
    assert rows[0]["status"] == "MODEL_SELECTION"  # the catalog itself is untouched


def test_daily3_reservation_uses_only_the_1_20_floor(monkeypatch):
    assert reservation_minimum_odds(SimpleNamespace(minimum_odds=2.5)) == 1.2
    assert reservation_minimum_odds(SimpleNamespace(minimum_odds=None)) == 1.2
    blocked = Daily3Choice.price_blocked.fget
    assert blocked(SimpleNamespace(minimum_odds=1.2, offer_odds=None)) is False
    assert blocked(SimpleNamespace(minimum_odds=1.2, offer_odds=1.15)) is True
    assert blocked(SimpleNamespace(minimum_odds=1.2, offer_odds=1.25)) is False
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    assert reservation_minimum_odds(SimpleNamespace(minimum_odds=2.5)) == 2.5
    assert blocked(SimpleNamespace(minimum_odds=2.5, offer_odds=None)) is True


def test_price_decision_bets_a_released_tip_at_any_odds_from_1_20(monkeypatch):
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    candidate = replace(surface.wettfinder_recommendation_candidate(signal), minimum_odds=2.5, blockers=())
    decision = evaluate_candidate_price(candidate, 1.5, bankroll=100.0, quote_confirmed=True)
    assert decision.status == "BET" and decision.stake_fraction >= 0.0
    assert not any("1,20" in reason or "Value" in reason for reason in decision.reasons)
    below = evaluate_candidate_price(candidate, 1.15, bankroll=100.0, quote_confirmed=True)
    assert below.status == "NO_BET" and any("1,20" in reason for reason in below.reasons)
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    gated = evaluate_candidate_price(candidate, 1.5, bankroll=100.0, quote_confirmed=True)
    assert gated.status == "NO_BET"


def test_card_shows_no_bookmaker_quote_and_only_the_1_20_floor():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    card = surface.build_wettfinder_card(signal, _quote(signal, fetched_at=NOW - timedelta(hours=4)), now=NOW)
    assert card.value_threshold == 1.2 and card.price_code == "PLAYABLE"
    assert card.evidence_label == "Modell geprüft"
    html = surface.render_editorial_card_html(card)
    assert "se-number-quote" not in html and "se-price-status" not in html
    assert "Mindestquote</span><strong>1.20" in html
    unpriced = surface.build_wettfinder_card(signal, None, now=NOW)
    assert unpriced.price_code == "UNPRICED" and unpriced.evidence_label == "Modell geprüft"
    assert "Mindestquote</span><strong>1.20" in surface.render_editorial_card_html(unpriced)
    top = surface.render_top_card_html(card) if hasattr(surface, "render_top_card_html") else ""
    assert "Risikopreis ab" not in top


def _release_row(**overrides):
    row = {
        "prediction_version": "challenge-engine:coherent-joint-calibration-v14",
        "validation_prediction_version": "challenge-engine:coherent-joint-calibration-v14",
        "model_scope": "same_competition", "context_stale": False, "statistical_release_passed": True,
        "tested_hypotheses": 864,  # nine leagues x 96 markets (cross-league FDR)
        "paired_loss_mean": 0.05, "paired_loss_hac_standard_error": 0.005,
        "paired_loss_lower_confidence_bound": 0.04, "paired_loss_p_value": 0.00001, "fdr_q_value": 0.0009,
        "context": {"passed": True, "forecast_passed": True, "release_context_complete": False,
                    "release_context_limitations": ["Beide bestätigten Startaufstellungen fehlen"],
                    "release_eligible": False, "release_eligible_without_lineups": True,
                    "model_transfer": {"status": "passed"}},
    }
    row.update(overrides)
    return row


def test_release_needs_validated_model_and_passed_context_not_confirmed_lineups(monkeypatch):
    import challenge_engine as engine
    from ev_signal_sources import _football_recommendation_release_eligible
    row = _release_row()
    assert automation._football_record_release_eligible(row)
    assert _football_recommendation_release_eligible(row)
    assert engine.context_release_eligible(row["context"])
    # A context veto or a failed model transfer still blocks.
    assert not engine.context_release_eligible({**row["context"], "passed": False})
    assert not engine.context_release_eligible({**row["context"], "release_eligible_without_lineups": False})
    legacy_context = {"passed": True, "model_transfer": {"status": "passed"}}  # rows persisted before the flag
    assert engine.context_release_eligible(legacy_context)
    assert not engine.context_release_eligible({"passed": True, "model_transfer": {"status": "provisional"}})
    # The hypothesis family is the catalog or a whole multiple of it, never another catalog.
    assert engine.hypothesis_count_is_catalog_multiple(96) and engine.hypothesis_count_is_catalog_multiple(864)
    assert not engine.hypothesis_count_is_catalog_multiple(89) and not engine.hypothesis_count_is_catalog_multiple(True)
    assert not automation._football_record_release_eligible(_release_row(tested_hypotheses=89))
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    assert not automation._football_record_release_eligible(row)  # the old contract wants confirmed line-ups
    assert automation._football_record_release_eligible(_release_row(context={
        **row["context"], "release_context_complete": True, "release_eligible": True}))
