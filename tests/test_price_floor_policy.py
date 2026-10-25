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


def test_esports_attach_stores_the_floor_status_and_execution_fields(tmp_path, monkeypatch):
    # 25.10.2026: the attach stored the gate code OBSERVED under every policy and the
    # app loader, recomputing PLAYABLE under floor, rejected the whole daily document.
    import json
    import esports_prices as prices
    from tests.test_esports_prices import NOW as ESPORTS_NOW, document, event, row
    cache = tmp_path / "esports_quotes.json"
    cache.write_text(json.dumps(document(event())), encoding="utf-8")
    priced, = prices.attach_cached_esports_prices([row()], now=ESPORTS_NOW, path=cache)
    assert priced["reference_price_status"] == "PLAYABLE"
    assert priced["reference_quote_executable_odds"] == 2.5
    assert priced["reference_quote_bookmaker"] in {"pinnacle", "1xbet"}
    assert priced["reference_quote_source"] == mc.ESPORTS_PRICE_SOURCE and priced["reference_quote_observed_at"]
    cache.write_text(json.dumps(document(event(first=1.10))), encoding="utf-8")
    below, = prices.attach_cached_esports_prices([row()], now=ESPORTS_NOW, path=cache)
    assert below["reference_price_status"] == "BELOW_FLOOR"
    assert not any(field.startswith("reference_quote_") for field in below)
    unknown, = prices.attach_cached_esports_prices([row(competition="Unknown")], now=ESPORTS_NOW, path=cache)
    assert unknown["reference_price_status"] == "UNAVAILABLE" and unknown["reference_quote"] is None
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    cache.write_text(json.dumps(document(event())), encoding="utf-8")
    gated, = prices.attach_cached_esports_prices([row()], now=ESPORTS_NOW, path=cache)
    assert gated["reference_price_status"] == "OBSERVED"
    assert not any(field.startswith("reference_quote_") for field in gated)


def test_consumer_loader_accepts_legacy_observed_rows_but_never_playable_without_execution_fields(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone
    import ev_signal_sources as ev
    from tests.test_ev_signal_sources import _automatic_document, _model_overlay, _playable_automatic_candidate
    generated = datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc)
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    path = tmp_path / "wettfinder_latest.json"

    def load(row):
        path.write_text(json.dumps(_automatic_document([row]) | {"bookmaker_data_used": True}), encoding="utf-8")
        return ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE)

    legacy = _model_overlay(_playable_automatic_candidate())
    for field in ev._REFERENCE_EXECUTION_FIELDS:
        legacy.pop(field, None)
    legacy["reference_price_status"] = "OBSERVED"  # written by the E-sport attach before 25.10.2026
    assert load(legacy) is not None

    def withheld(row):  # since 25.10.2026 the row is withheld, the document stays readable
        loaded = load(row)
        return loaded is not None and loaded[0]["model_candidates"] == [] and loaded[0]["price_inconsistent_rows"] == 1

    assert withheld({**legacy, "reference_price_status": "PLAYABLE"})  # playable needs execution fields
    assert withheld({**legacy, "reference_quote_executable_odds": 2.06})  # legacy code with an execution field
    # The fixed producer stores the floor status with the floor's own execution fields.
    fixed = _model_overlay(_playable_automatic_candidate())
    quote = mc.MarketConsensus.from_dict(fixed["reference_quote"])
    status = mc.wettfinder_reference_price_status(quote, fixed["minimum_odds"], candidate=fixed, now=generated)
    assert status.code == "PLAYABLE"
    fixed.update(reference_price_status=status.code, reference_quote_source=quote.source,
                 reference_quote_executable_odds=status.usable_odds, reference_quote_bookmaker=status.bookmaker,
                 reference_quote_bookmaker_id=status.bookmaker_id, reference_quote_observed_at=status.observed_at)
    assert load(fixed) is not None
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    assert load(legacy) is None


def _ledger_row(index, *, kickoff="2030-01-01T15:00:00+00:00", odds=None, probability=None,
                quoted_at="2030-01-01T10:00:00+00:00", **overrides):
    """A release-eligible football model row of the stored ledger (UNPRICED unless odds are given)."""
    import ev_signal_sources as ev
    from tests.test_ev_signal_sources import _model_automatic_candidate, _model_overlay, _playable_automatic_candidate
    row = (_model_overlay(_playable_automatic_candidate(odds=odds, generated_at=quoted_at)) if odds
           else _model_automatic_candidate())
    row.update(_release_row(tested_hypotheses=96))
    row.update(candidate_id=f"{index}:BTTS_YES", fixture_id=index, key=f"automatic-model-fussball-{index}",
               event=f"Spiel {index}", event_identity=f"football:{index}", scheduled_start=kickoff)
    if probability is not None:
        haircut = row["probability_haircut"]
        row.update(probability=probability, conservative_probability=round(probability - haircut, 10),
                   minimum_odds=ev._minimum_odds(probability, haircut))
    row.update(overrides)
    return row


def _refreshed_document(rows, *, published):
    from tests.test_ev_signal_sources import _automatic_document
    strict = [{**row, "status": "RECOMMENDED", "evidence_stage": "RELEASED",
               "release_contract": automation.AUTOMATED_FOOTBALL_RELEASE_CONTRACT} for row in published]
    document = _automatic_document(rows, candidates=strict, challenge_release_candidates=[])
    # A price refresh clears both strict lists before the republication runs (unchanged behaviour).
    document["candidates"] = []
    document["challenge_release_candidates"] = []
    document["bookmaker_data_used"] = True
    return document


def test_price_refresh_refills_public_tips_after_a_tip_falls_below_the_floor(tmp_path):
    import json
    from datetime import datetime, timezone
    import ev_signal_sources as ev
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    below = _ledger_row(1, odds=("1.10", "1.12", "1.14", "1.16"))  # the refresh found this tip below 1.20
    assert below["reference_price_status"] == "BELOW_FLOOR"
    rows = [below, _ledger_row(2), _ledger_row(3), _ledger_row(4)]
    document = _refreshed_document(rows, published=rows[:3])
    automation._republish_floor_candidates(document, now=now)
    assert [row["candidate_id"] for row in document["candidates"]] == ["2:BTTS_YES", "3:BTTS_YES", "4:BTTS_YES"]
    assert all(row["status"] == "RECOMMENDED" and row["evidence_stage"] == "RELEASED"
               and row["release_contract"] == automation.AUTOMATED_FOOTBALL_RELEASE_CONTRACT
               for row in document["candidates"])
    assert document["sources"]["football"]["published_recommendation_count"] == 3
    assert all(row["evidence_stage"] == "SHADOW" for row in document["model_candidates"])  # ledger untouched
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    snapshot = ev.automated_wettfinder_snapshot(path, now=now)
    assert snapshot.status is not None and len(snapshot.signals) == 3 and len(snapshot.forecasts) == 4


def test_price_refresh_republication_skips_started_games_and_unreleased_rows():
    from datetime import datetime, timezone
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    started = _ledger_row(1, kickoff="2030-01-01T10:30:00+00:00")
    unreleased = _ledger_row(4, statistical_release_passed=False)
    rows = [started, _ledger_row(2), _ledger_row(3), unreleased, _ledger_row(5)]
    document = _refreshed_document(rows, published=rows[:3])
    automation._republish_floor_candidates(document, now=now)
    assert [row["candidate_id"] for row in document["candidates"]] == ["2:BTTS_YES", "3:BTTS_YES", "5:BTTS_YES"]
    # An unverified fixture context or a football run with errors publishes nothing.
    document["football"]["context_fixture_statuses"]["5"] = "data_incomplete"
    automation._republish_floor_candidates(document, now=now)
    assert [row["candidate_id"] for row in document["candidates"]] == ["2:BTTS_YES", "3:BTTS_YES"]
    document["football"]["operational_error_count"] = 1
    automation._republish_floor_candidates(document, now=now)
    assert document["candidates"] == [] and document["sources"]["football"]["published_recommendation_count"] == 0


def test_price_refresh_fills_the_15k_list_only_with_playable_corridor_rows(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone
    import ev_signal_sources as ev
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    playable = _ledger_row(1, odds=("2.00", "2.02", "2.04", "2.06"), probability=0.65)
    assert playable["reference_price_status"] == "PLAYABLE"
    rows = [playable, _ledger_row(2, probability=0.65), _ledger_row(3)]
    document = _refreshed_document(rows, published=[])
    automation._republish_floor_candidates(document, now=now)
    assert [row["candidate_id"] for row in document["candidates"]] == ["1:BTTS_YES", "2:BTTS_YES", "3:BTTS_YES"]
    assert [row["candidate_id"] for row in document["challenge_release_candidates"]] == ["1:BTTS_YES"]
    assert document["sources"]["football"]["challenge_release_candidate_count"] == 1
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE) is not None
    # The old contract keeps the cleared lists: a release needed a fresh executable price.
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    gated = _refreshed_document(rows, published=rows[:1])
    automation._republish_floor_candidates(gated, now=now)
    assert gated["candidates"] == [] and gated["challenge_release_candidates"] == []


def test_unpriced_public_tips_stay_signals_as_long_as_the_model_document(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timedelta, timezone
    import ev_signal_sources as ev
    rows = [_ledger_row(index, kickoff="2030-01-01T20:00:00+00:00") for index in (1, 2, 3)]
    document = _refreshed_document(rows, published=[])
    generated = datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc)
    automation._republish_floor_candidates(document, now=generated)
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    # Six hours after the scan (far beyond the old 150-minute price limit) the tips are still public.
    snapshot = ev.automated_wettfinder_snapshot(path, now=generated + timedelta(hours=6))
    assert snapshot.status is not None and len(snapshot.signals) == 3
    assert all(signal.evidence_stage == "RELEASED" and signal.reference_quote is None for signal in snapshot.signals)
    # Started games leave the public tips; an aged-out model document publishes nothing.
    assert ev.automated_wettfinder_snapshot(path, now=generated + timedelta(hours=10, minutes=1)).signals == ()
    assert ev.automated_wettfinder_snapshot(path, now=generated + timedelta(hours=24, minutes=1)).status is None
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    assert ev.automated_wettfinder_snapshot(path, now=generated + timedelta(hours=6)).signals == ()


def test_refilled_playable_tips_are_judged_at_their_price_clock_not_the_scan_clock(tmp_path):
    # 25.10.2026 09:15: the refresh published tips whose quotes were observed after the
    # 03:53 scan; the loader recomputed them at the scan clock, got UNPRICED and rejected
    # the whole document (website empty again).
    import json
    from datetime import datetime, timezone
    import ev_signal_sources as ev
    now = datetime(2030, 1, 1, 13, 0, tzinfo=timezone.utc)
    later_quote = _ledger_row(1, odds=("2.00", "2.02", "2.04", "2.06"), quoted_at="2030-01-01T12:00:00+00:00",
                              reference_price_evaluated_at="2030-01-01T12:05:00+00:00")
    assert later_quote["reference_price_status"] == "PLAYABLE"
    rows = [later_quote, _ledger_row(2), _ledger_row(3)]
    document = _refreshed_document(rows, published=[])
    automation._republish_floor_candidates(document, now=now)
    assert [row["candidate_id"] for row in document["candidates"]][0] == "1:BTTS_YES"
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    snapshot = ev.automated_wettfinder_snapshot(path, now=now)
    assert snapshot.status is not None and len(snapshot.signals) == 3
    # Without its evaluation clock a quote observed after the scan is withheld (row, not document).
    for row in document["model_candidates"] + document["candidates"] + document["challenge_release_candidates"]:
        row.pop("reference_price_evaluated_at", None)
    path.write_text(json.dumps(document), encoding="utf-8")
    loaded = ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE)
    assert loaded is not None and loaded[0]["price_inconsistent_rows"] == 1
    assert "1:BTTS_YES" not in [row["candidate_id"] for row in loaded[0]["model_candidates"]]
    assert [row["candidate_id"] for row in loaded[2]] == ["2:BTTS_YES", "3:BTTS_YES"]


def test_card_without_quote_is_not_floor_excluded_only_a_quote_below_1_20_is():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    assert surface.build_wettfinder_card(signal, None, now=NOW).quote_floor_excluded is False
    assert surface.build_wettfinder_card(signal, _quote(signal, odds=(1.76, 1.80, 1.84)), now=NOW).quote_floor_excluded is False
    below = surface.build_wettfinder_card(signal, _quote(signal, odds=(1.10, 1.12, 1.14)), now=NOW)
    assert below.price_code == "BELOW_FLOOR" and below.quote_floor_excluded is True


def _strict(row):
    return {**row, "status": "RECOMMENDED", "evidence_stage": "RELEASED",
            "release_contract": automation.AUTOMATED_FOOTBALL_RELEASE_CONTRACT}


def test_loader_withholds_inconsistent_rows_instead_of_the_whole_document(tmp_path, monkeypatch):
    # Gesamtaudit 25.10.2026, Massnahme 1: two outages on one day came from single rows.
    import json
    from datetime import datetime, timezone
    import ev_signal_sources as ev
    from tests.test_ev_signal_sources import _automatic_document
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    clean = _ledger_row(1)
    broken = _ledger_row(2, odds=("2.00", "2.02", "2.04", "2.06"))
    for field in ev._REFERENCE_EXECUTION_FIELDS:
        broken.pop(field, None)  # PLAYABLE without its execution record is inconsistent
    other = _ledger_row(3)
    document = _automatic_document([clean, broken, other], candidates=[_strict(clean), _strict(broken)],
                                   challenge_release_candidates=[])
    document["bookmaker_data_used"] = True
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    loaded = ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE)
    assert loaded is not None
    projected, _generated, strict = loaded
    assert [row["candidate_id"] for row in projected["model_candidates"]] == ["1:BTTS_YES", "3:BTTS_YES"]
    assert [row["candidate_id"] for row in strict] == ["1:BTTS_YES"]
    snapshot = ev.automated_wettfinder_snapshot(path, now=now)
    assert snapshot.status.price_inconsistent_rows == 1
    assert len(snapshot.forecasts) == 2 and len(snapshot.signals) == 1
    # A structural defect still fails closed for the whole document.
    structural = {**document, "model_candidates": [clean, {**other, "status": "PRICE_REQUIRED"}], "candidates": []}
    path.write_text(json.dumps(structural), encoding="utf-8")
    assert ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE) is None
    # The old contract keeps rejecting the whole document.
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    path.write_text(json.dumps(document), encoding="utf-8")
    assert ev._load_automated_wettfinder_document(path, now=now, max_age=ev.AUTOMATED_MODEL_MAX_AGE) is None


def test_price_refresh_classifies_a_retained_quote_under_the_floor_policy(monkeypatch):
    from datetime import datetime, timezone
    from tests.test_ev_signal_sources import _model_automatic_candidate, _model_overlay, _playable_automatic_candidate
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    previous = _model_overlay(_playable_automatic_candidate())  # last run observed 2.00-2.06 at 10:00
    model_row = _model_automatic_candidate()                    # this run: the market is no longer offered
    price_row = dict(model_row)
    _counts, playable = automation._apply_reference_quotes([model_row], [price_row], {}, now=now,
                                                           previous_rows=[previous], price_evaluated_at=now)
    assert model_row["reference_quote"] is not None
    assert model_row["reference_price_status"] == "PLAYABLE"
    assert model_row["reference_price_evaluated_at"] == now.isoformat()
    assert model_row["reference_quote_executable_odds"] == 2.06
    assert [row["candidate_id"] for row in playable] == [model_row["candidate_id"]]
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    model_row = _model_automatic_candidate()
    automation._apply_reference_quotes([model_row], [dict(model_row)], {}, now=now,
                                       previous_rows=[previous], price_evaluated_at=now)
    assert model_row["reference_quote"] is not None and model_row["reference_price_status"] == "UNAVAILABLE"
    assert "reference_price_evaluated_at" not in model_row and "reference_quote_executable_odds" not in model_row


def test_15k_release_quote_uses_the_row_clock_and_the_floor_status(monkeypatch):
    from datetime import datetime, timezone
    generated = datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc)
    refilled = _strict(_ledger_row(1, odds=("2.00", "2.02", "2.04", "2.06"), quoted_at="2030-01-01T12:00:00+00:00",
                                   reference_price_evaluated_at="2030-01-01T12:05:00+00:00"))
    quote = automation._challenge_release_quote(refilled, generated_at=generated)
    assert quote is not None and quote.best_odds == 2.06
    below = _strict(_ledger_row(2, odds=("1.10", "1.12", "1.14", "1.16")))
    assert automation._challenge_release_quote(below, generated_at=generated) is None
    assert automation._challenge_release_quote(_strict(_ledger_row(3)), generated_at=generated) is None  # a stake needs odds
    backdated = {**refilled, "reference_price_evaluated_at": "2030-01-01T09:00:00+00:00"}
    assert automation._challenge_release_quote(backdated, generated_at=generated) is None
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")
    assert automation._challenge_release_quote(refilled, generated_at=generated) is None


def test_price_refresh_republication_follows_the_source_error_counter_the_loader_checks():
    from datetime import datetime, timezone
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    rows = [_ledger_row(1), _ledger_row(2)]
    document = _refreshed_document(rows, published=[])
    document["sources"]["football"]["operational_error_count"] = 1  # a degraded scan
    automation._republish_floor_candidates(document, now=now)
    assert document["candidates"] == [] and document["sources"]["football"]["published_recommendation_count"] == 0
    document["sources"]["football"]["operational_error_count"] = 0
    automation._republish_floor_candidates(document, now=now)
    assert [row["candidate_id"] for row in document["candidates"]] == ["1:BTTS_YES", "2:BTTS_YES"]


def test_football_price_refresh_does_not_count_budget_protection_as_operational_error(tmp_path):
    import json
    from tests.test_price_refresh_schedule import NOW as REFRESH_NOW, _football, _state
    row, _quote_unused = _football()
    path, _original = _state(tmp_path, [row])
    result = automation.refresh_prices_only(state_path=path, now=REFRESH_NOW,
                                            quote_loader=lambda *args, **kwargs: ({}, ["Fussball: APIBudgetExceeded"]))
    assert result["errors"] == 1
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["sources"]["football"]["quote_operational_error_count"] == 0
