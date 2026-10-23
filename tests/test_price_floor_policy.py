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


def test_card_shows_neither_bookmaker_quote_nor_minimum_quote():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    card = surface.build_wettfinder_card(signal, _quote(signal, fetched_at=NOW - timedelta(hours=4)), now=NOW)
    assert card.value_threshold == 1.2 and card.price_code == "PLAYABLE"
    assert card.evidence_label == "Modell geprüft"
    html = surface.render_editorial_card_html(card)
    assert "se-number-quote" not in html and "se-price-status" not in html
    # Owner 23.10.2026 (evening): the 1.20 floor works only in the background.
    assert "Mindestquote" not in html and "se-number-threshold" not in html
    unpriced = surface.build_wettfinder_card(signal, None, now=NOW)
    assert unpriced.price_code == "UNPRICED" and unpriced.evidence_label == "Modell geprüft"
    assert "Mindestquote" not in surface.render_editorial_card_html(unpriced)
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


def test_model_view_shows_no_minimum_quote_hint(monkeypatch):
    import bet_finder_ui as ui
    from tests.test_bet_finder_ui import _binding, _candidate, _quote
    shown = []
    for name in ("subheader", "write", "caption", "info"):
        monkeypatch.setattr(ui.st, name, lambda value, _shown=shown: _shown.append(str(value)))
    monkeypatch.setattr(ui, "evaluate_reference_price",
                        lambda *args, **kwargs: pytest.fail("model view must not evaluate a quote"))
    quote = _quote()
    ui.render_model_selection(_candidate(), reference_quote=quote, reference_binding_candidate=_binding(quote))
    copy = " ".join(shown)
    assert "Modell: 65.0 %" in copy
    assert "Mindestquote" not in copy and "1,20" not in copy and "1.80" not in copy


def test_daily3_reservation_shows_no_minimum_quote_hint(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from tests.test_daily3_ui import _render_priced
    monkeypatch.delenv("BETBOY_DAILY3_RESERVATION_MINIMUM", raising=False)
    app = AppTest.from_function(_render_priced, args=(str(tmp_path / "floor.db"), 2.0, 1.8)).run(timeout=30)
    assert not app.exception
    assert any("Heimteam 1" in item.value for item in app.markdown)
    texts = [item.value for group in (app.caption, app.warning, app.info, app.markdown) for item in group]
    assert not any("Mindestquote" in text for text in texts)


def test_tennis_card_shows_neither_last_quote_nor_minimum_quote_hint():
    from streamlit.testing.v1 import AppTest
    from tests.test_tennis_tab import _run_price_check
    at = AppTest.from_function(_run_price_check)
    at.run(timeout=60)
    assert len(at.exception) == 0
    labels = [metric.label for metric in at.metric]
    assert "Modell" in labels and "Letzte Quote" not in labels
    assert not any("Mindestquote" in item.value for item in at.caption)


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


def test_consumer_loader_accepts_unpriced_public_tips_under_the_floor_policy(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone
    import ev_signal_sources as ev
    from tests.test_ev_signal_sources import _automatic_document, _model_automatic_candidate
    from wettfinder_automation import AUTOMATED_FOOTBALL_RELEASE_CONTRACT
    model_row = _model_automatic_candidate()  # UNAVAILABLE: never price-checked (no bookmaker market)
    strict_row = {**model_row, "status": "RECOMMENDED", "evidence_stage": "RELEASED",
                  "release_contract": AUTOMATED_FOOTBALL_RELEASE_CONTRACT}
    document = _automatic_document([model_row], candidates=[strict_row], challenge_release_candidates=[])
    document["bookmaker_data_used"] = True
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    loaded = ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE)
    assert loaded is not None
    snapshot = ev.automated_wettfinder_snapshot(path, now=now)
    assert snapshot.status is not None and len(snapshot.forecasts) == 1
    # A published row with an execution field but no playable price is still inconsistent.
    broken = {**strict_row, "reference_quote_executable_odds": 2.0}
    path.write_text(json.dumps(_automatic_document([model_row], candidates=[broken], challenge_release_candidates=[])
                               | {"bookmaker_data_used": True}), encoding="utf-8")
    assert ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE) is None
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    path.write_text(json.dumps(document), encoding="utf-8")
    assert ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE) is None
