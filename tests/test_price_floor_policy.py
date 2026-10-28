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
    # Without a current quote the model guard decides (owner 25.10.2026): 68 % is withheld, 60 % stays unpriced.
    assert mc.wettfinder_reference_price_status(ancient, None, candidate=binding, now=NOW).code == "BELOW_FLOOR"
    unsure = surface.wettfinder_quote_binding_candidate(replace(signal, probability=0.60))
    assert mc.wettfinder_reference_price_status(ancient, None, candidate=unsure, now=NOW).code == "UNPRICED"
    # A quote bound to another candidate is no evidence either way.
    other = surface.wettfinder_quote_binding_candidate(
        replace(_signal(key="other", market_key="RESULT_HOME", selection="1"), probability=0.60))
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
    unpriced = surface.build_wettfinder_card(replace(signal, probability=0.60), None, now=NOW)
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
    rows = [playable, _ledger_row(2, probability=0.64), _ledger_row(3)]
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


def test_card_without_quote_is_floor_excluded_only_from_65_percent_or_below_1_20():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    assert surface.build_wettfinder_card(replace(signal, probability=0.60), None, now=NOW).quote_floor_excluded is False
    # Owner 25.10.2026: without any price evidence 65 % or more is withheld (model guard).
    guarded = surface.build_wettfinder_card(signal, None, now=NOW)
    assert guarded.price_code == "BELOW_FLOOR" and guarded.quote_floor_excluded is True
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


# --------------------------------------------------------------------------
# Three-stage floor check (owner 25.10.2026, docs/audits/2026-10-25-preispruefung-dreistufig.md)
# --------------------------------------------------------------------------

def test_floor_checks_the_median_price_not_the_best_book(monkeypatch):
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    binding = surface.wettfinder_quote_binding_candidate(signal)
    skewed = _quote(signal, odds=(1.15, 1.18, 1.35), fetched_at=NOW - timedelta(minutes=5))
    status = mc.wettfinder_reference_price_status(skewed, None, candidate=binding, now=NOW)
    assert status.code == "BELOW_FLOOR"  # best 1.35, median 1.18
    fair = _quote(signal, odds=(1.18, 1.22, 1.35), fetched_at=NOW - timedelta(minutes=5))
    status = mc.wettfinder_reference_price_status(fair, None, candidate=binding, now=NOW)
    assert status.code == "PLAYABLE" and status.usable_odds == 1.35  # execution stays a real best offer
    # Stored producer rows (multi-book API-Football quotes) and the RisikoBet/manual display rule agree.
    from datetime import datetime, timezone
    checked = datetime(2030, 1, 1, 10, 5, tzinfo=timezone.utc)
    low_row = _ledger_row(1, odds=("1.15", "1.18", "1.35"))
    fair_row = _ledger_row(1, odds=("1.18", "1.22", "1.35"))
    assert low_row["reference_price_status"] == "BELOW_FLOOR" and "reference_quote_executable_odds" not in low_row
    assert fair_row["reference_price_status"] == "PLAYABLE" and fair_row["reference_quote_executable_odds"] == 1.35
    assert mc.quote_below_publication_floor(low_row["reference_quote"], candidate=low_row, now=checked) is True
    assert mc.quote_below_publication_floor(fair_row["reference_quote"], candidate=fair_row, now=checked) is False
    monkeypatch.setenv(mc.PRICE_POLICY_FLAG, "gate")  # the old contract keeps the best offer
    assert mc.quote_below_publication_floor(low_row["reference_quote"], candidate=low_row, now=checked) is False


_LINE_OBSERVED = "2030-01-01T10:00:00+00:00"


def _line_row(fixture_id, market_key, *, over, under, observed=_LINE_OBSERVED, probability=0.60):
    """A ledger row of one over/under line with its exact multi-book quote and floor status."""
    import re
    from datetime import datetime
    from challenge_engine import MARKET_BY_KEY
    prefix, _, line = re.fullmatch(r"(HOME|AWAY|TOTAL)_(OVER|UNDER)_(\d)_5", market_key).groups()
    row = _ledger_row(fixture_id, probability=probability, statistical_release_passed=False,
                      candidate_id=f"{fixture_id}:{market_key}", market_key=market_key,
                      key=f"automatic-model-fussball-{fixture_id}-{market_key.lower()}",
                      selection=MARKET_BY_KEY[market_key].selection)
    bet = {"HOME": "Total - Home", "AWAY": "Total - Away", "TOTAL": "Goals Over/Under"}[prefix]
    payload = {"response": [{
        "fixture": {"id": fixture_id, "date": row["scheduled_start"]}, "update": observed,
        "bookmakers": [{"id": index, "name": f"Book {index}", "bets": [{"name": bet, "values": [
            {"value": f"Over {line}.5", "odd": str(o)}, {"value": f"Under {line}.5", "odd": str(u)}]}]}
            for index, (o, u) in enumerate(zip(over, under), start=1)],
    }]}
    quote = mc.parse_fixture_consensus(payload, [row], fetched_at=datetime.fromisoformat(observed))[row["candidate_id"]]
    row["reference_quote"] = quote.to_dict()
    status = mc.wettfinder_reference_price_status(quote, row["minimum_odds"], candidate=row,
                                                   now=datetime.fromisoformat(observed))
    row["reference_price_status"] = status.code
    for field in ("reference_quote_source", "reference_quote_executable_odds", "reference_quote_bookmaker",
                  "reference_quote_bookmaker_id", "reference_quote_observed_at"):
        row.pop(field, None)
    if status.code == "PLAYABLE":
        row.update(reference_quote_source=quote.source, reference_quote_executable_odds=status.usable_odds,
                   reference_quote_bookmaker=status.bookmaker, reference_quote_bookmaker_id=status.bookmaker_id,
                   reference_quote_observed_at=status.observed_at)
    return row


def _range_row(fixture_id, market_key, *, probability):
    from challenge_engine import MARKET_BY_KEY
    return _ledger_row(fixture_id, probability=probability, candidate_id=f"{fixture_id}:{market_key}",
                       market_key=market_key, key=f"automatic-model-fussball-{fixture_id}-{market_key.lower()}",
                       selection=MARKET_BY_KEY[market_key].selection)


def test_goal_range_without_quote_is_judged_by_the_team_lines():
    from datetime import datetime, timezone
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    # Hammarby case: "away 1-4 goals" has no quote; "away over 0.5" sits far below 1.20.
    sure = _line_row(7, "AWAY_OVER_0_5", over=(1.08, 1.10, 1.11, 1.12), under=(6.5, 7.0, 6.8, 7.2))
    hammarby = _range_row(7, "AWAY_RANGE_1_4", probability=0.60)
    bound = mc.derive_range_price_bound(hammarby, {"AWAY_OVER_0_5": sure}, now=now)
    assert bound["basis"] == "upper_bound" and bound["sources"] == ["AWAY_OVER_0_5"] and bound["probability"] > 0.85
    status = mc.wettfinder_reference_price_status(None, None, candidate={**hammarby, "reference_price_bound": bound}, now=now)
    assert status.code == "BELOW_FLOOR" and status.market_basis == mc.FLOOR_BASIS_DERIVED  # 60 % alone would pass
    # "away 2-4 goals" from the 1.5 under line (team lines end at 2.5, so a team range is always
    # an upper bound): a range priced above 1.20 passes although the model sees 80 %.
    under = _line_row(8, "AWAY_UNDER_1_5", over=(2.40, 2.45, 2.50, 2.42), under=(1.55, 1.52, 1.50, 1.56))
    wide = _range_row(8, "AWAY_RANGE_2_4", probability=0.80)
    bound = mc.derive_range_price_bound(wide, {"AWAY_UNDER_1_5": under}, now=now)
    assert bound["basis"] == "upper_bound" and bound["sources"] == ["AWAY_UNDER_1_5"]
    assert 0.35 < bound["probability"] < 0.45
    status = mc.wettfinder_reference_price_status(None, None, candidate={**wide, "reference_price_bound": bound}, now=now)
    assert status.code == "UNPRICED" and status.market_basis == mc.FLOOR_BASIS_DERIVED
    # Match ranges have both lines: "1-3 goals" = P(over 0.5) - P(over 3.5).
    some = _line_row(9, "TOTAL_OVER_0_5", over=(1.06, 1.07, 1.05, 1.06), under=(9.0, 8.5, 9.5, 9.0))
    many = _line_row(9, "TOTAL_OVER_3_5", over=(3.20, 3.10, 3.25, 3.30), under=(1.33, 1.35, 1.32, 1.33))
    middle = mc.derive_range_price_bound(_range_row(9, "TOTAL_RANGE_1_3", probability=0.70),
                                         {"TOTAL_OVER_0_5": some, "TOTAL_OVER_3_5": many}, now=now)
    assert middle["basis"] == "line_difference" and middle["sources"] == ["TOTAL_OVER_0_5", "TOTAL_OVER_3_5"]
    assert 0.55 < middle["probability"] < 0.70
    # A stale line is no evidence: the model guard decides again.
    late = datetime(2030, 1, 2, 10, 30, tzinfo=timezone.utc)
    assert mc.derive_range_price_bound(wide, {"AWAY_UNDER_1_5": under}, now=late) is None
    stale = mc.wettfinder_reference_price_status(None, None, candidate={**wide, "reference_price_bound": bound}, now=late)
    assert stale.code == "BELOW_FLOOR" and stale.market_basis == mc.FLOOR_BASIS_MODEL
    # A bound belongs to exactly one range market; anything else is ignored.
    assert mc.valid_price_bound(bound, "AWAY_RANGE_1_4") is None and mc.valid_price_bound(bound, "AWAY_RANGE_2_4")
    assert mc.derive_range_price_bound(_range_row(9, "HOME_RANGE_1_3", probability=0.6), {}, now=now) is None


def test_model_guard_withholds_unpriced_selections_from_65_percent():
    from datetime import datetime, timezone
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    for probability, expected in ((0.6499, "UNPRICED"), (0.65, "BELOW_FLOOR"), (0.87, "BELOW_FLOOR")):
        row = _ledger_row(1, probability=probability)
        assert mc.wettfinder_reference_price_status(None, None, candidate=row, now=now).code == expected
    # Candidates that carry the probability in percent are scaled, not misread.
    assert mc.wettfinder_reference_price_status(
        None, None, candidate={**_ledger_row(1), "probability": 79.7}, now=now).code == "BELOW_FLOOR"


def test_republication_loader_and_card_apply_all_three_stages(tmp_path):
    import json
    from datetime import datetime, timezone
    import ev_signal_sources as ev
    now = datetime(2030, 1, 1, 11, 0, tzinfo=timezone.utc)
    rows = [
        _range_row(7, "AWAY_RANGE_1_4", probability=0.60),  # lines say below 1.20: withheld
        _line_row(7, "AWAY_OVER_0_5", over=(1.08, 1.10, 1.11, 1.12), under=(6.5, 7.0, 6.8, 7.2)),
        _range_row(8, "AWAY_RANGE_2_4", probability=0.80),  # lines say above 1.20: public
        _line_row(8, "AWAY_UNDER_1_5", over=(2.40, 2.45, 2.50, 2.42), under=(1.55, 1.52, 1.50, 1.56)),
        _ledger_row(9, probability=0.70),  # no price evidence, 70 %: withheld by the guard
        _ledger_row(10, probability=0.60),  # no price evidence, 60 %: public
    ]
    assert rows[1]["reference_price_status"] == "BELOW_FLOOR" and rows[3]["reference_price_status"] == "PLAYABLE"
    for row in rows:
        if row.get("reference_quote") is None:
            row["reference_price_status"] = "UNAVAILABLE"
    automation._attach_floor_price_bounds(rows, now=now)
    assert rows[0]["reference_price_bound"]["probability"] > 0.85
    assert rows[2]["reference_price_bound"]["sources"] == ["AWAY_UNDER_1_5"]
    assert "reference_price_bound" not in rows[4] and "reference_price_bound" not in rows[1]
    assert [row["reference_price_status"] for row in rows] == [
        "UNAVAILABLE", "BELOW_FLOOR", "UNAVAILABLE", "PLAYABLE", "UNAVAILABLE", "UNAVAILABLE"]
    document = _refreshed_document(rows, published=[])
    automation._republish_floor_candidates(document, now=now)
    assert [row["candidate_id"] for row in document["candidates"]] == ["8:AWAY_RANGE_2_4", "10:BTTS_YES"]
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    snapshot = ev.automated_wettfinder_snapshot(path, now=now)
    assert snapshot.status.price_inconsistent_rows == 0
    assert [signal.candidate_id for signal in snapshot.signals] == ["8:AWAY_RANGE_2_4", "10:BTTS_YES"]
    forecasts = {signal.candidate_id: signal for signal in snapshot.forecasts}
    assert forecasts["8:AWAY_RANGE_2_4"].reference_price_bound["basis"] == "upper_bound"
    excluded = {cid: surface.build_wettfinder_card(forecasts[cid], None, now=now).quote_floor_excluded
                for cid in ("7:AWAY_RANGE_1_4", "8:AWAY_RANGE_2_4", "9:BTTS_YES", "10:BTTS_YES")}
    assert excluded == {"7:AWAY_RANGE_1_4": True, "8:AWAY_RANGE_2_4": False, "9:BTTS_YES": True, "10:BTTS_YES": False}
    # A published unpriced tip that a later evaluation withholds costs only that row.
    # (strict lists follow the ledger order, so the stale tip sits between the two others)
    document["candidates"] = [document["candidates"][0], _strict(rows[4]), document["candidates"][1]]
    path.write_text(json.dumps(document), encoding="utf-8")
    snapshot = ev.automated_wettfinder_snapshot(path, now=now)
    assert snapshot.status.price_inconsistent_rows == 1
    assert [signal.candidate_id for signal in snapshot.signals] == ["8:AWAY_RANGE_2_4", "10:BTTS_YES"]


def test_15k_ticket_prices_the_fresh_consensus_not_an_older_best_offer(tmp_path):
    """The floor reads quotes of the last 24 hours, the 15K ledger persists only the fresh
    consensus. A 46-minute-old 9.99 offer must neither crash the ticket ("ticket odds must
    lie inside the quoted market range") nor become its price (Audit 25.10.2026 D5)."""
    from datetime import datetime, timezone

    from challenge_15k import _automatic_challenge_ticket
    from challenge_engine import ticket_stake
    from challenge_store import ChallengeLedger
    from tests.test_challenge_15k import candidate, reference_quote_for

    now = datetime.now(timezone.utc)
    item = candidate("1:BTTS", 1, 0.60, kickoff=now + timedelta(days=1))
    quote = reference_quote_for(item, now)
    stale = replace(quote.points[0], odds=9.99, observed_at=(now - timedelta(minutes=46)).isoformat())
    raw = replace(quote, points=(stale, *quote.points[1:]), best_odds=9.99)

    ticket, statuses, approved = _automatic_challenge_ticket([item], {item.candidate_id: raw}, now=now)

    assert statuses[item.candidate_id].code == "PLAYABLE"
    evidence = approved[item.candidate_id]
    assert stale.bookmaker_id not in {point.bookmaker_id for point in evidence.points}
    assert ticket is not None
    assert ticket.legs[0].odds == pytest.approx(evidence.executable_point.odds) and ticket.legs[0].odds < 9.99
    ledger = ChallengeLedger(tmp_path / "challenge.db")
    ledger.set_stake_fraction(0.25)
    ticket_id = ledger.place_ticket(now.date().isoformat(), ticket, ticket_stake(ticket, 100.0, 0.25),
                                    now.isoformat(), reference_quote_evidence={item.candidate_id: evidence.to_dict()})
    assert ledger.get_ticket(ticket_id)["legs"][0]["odds"] == pytest.approx(ticket.legs[0].odds)


def test_wettfinder_bet_is_priced_at_the_fresh_consensus_offer():
    """The floor reads points up to one minute ahead and 24 hours back; the card validator
    expects a BET at the fresh consensus offer. A point the consensus discards must not price
    the BET, otherwise the card actions fail with "provenance mismatch" (Audit 25.10.2026 D5)."""
    from copy import deepcopy

    import bet_finder_ui as ui
    from tests.test_bet_finder_ui import _candidate
    from tests.test_daily3_selection import NOW as DAILY3_NOW, football
    from tests.test_publication_odds_floor import priced

    signal = priced(football(), (1.25, 1.25, 1.50))
    quote = deepcopy(signal.reference_quote)
    quote.pop("executable_quote", None)
    quote["points"][-1]["observed_at"] = quote["quoted_at"] = (DAILY3_NOW + timedelta(seconds=1)).isoformat()

    evaluation = ui.evaluate_reference_price(_candidate(), quote, bankroll=100,
                                             reference_binding_candidate=signal, now=DAILY3_NOW)

    assert evaluation.status.code == "PLAYABLE"
    assert ui._validate_precomputed_reference_evaluation(evaluation, _candidate()) is evaluation
    assert evaluation.status.usable_odds == evaluation.quote.executable_point.odds == 1.25


def test_run_without_any_bookmaker_quote_keeps_its_unpriced_tips(tmp_path):
    """A quote provider outage leaves ``bookmaker_data_used`` False. Under the floor an unpriced
    tip stays visible (23.10.2026); the loader must not reject the whole document for it."""
    from datetime import datetime, timezone

    from config_loader import AppConfig
    from ev_signal_sources import automated_wettfinder_forecasts, automated_wettfinder_signals
    from tests.test_wettfinder_automation import _football_snapshot

    now = datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc)
    snapshot = _football_snapshot(now)
    # Below 65 % the three-stage check keeps a tip without any price evidence visible.
    tip = replace(snapshot["shortlist"][0], probability=0.45, conservative_probability=0.38,
                  probability_haircut_pp=7.0, model_price=1.0 / 0.38)
    snapshot.update(shortlist=[], wettfinder_candidates=[tip], discovery_candidates=[tip])
    artifact = tmp_path / "no-quotes.json"
    document = automation.run_wettfinder(
        now=now, state_path=artifact, config=AppConfig(api_football_key="test"),
        football_scanner=lambda _day: snapshot, football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [])

    assert document["bookmaker_data_used"] is False and document["candidates"]
    assert automated_wettfinder_forecasts(artifact, now=now)
    assert [signal.key for signal in automated_wettfinder_signals(artifact, now=now)] == [
        row["key"] for row in document["candidates"]]


def test_public_admission_checks_the_median_for_every_consumer():
    """Daily3, RisikoBet, the manual search and the 15K page admit offers through
    ``publication_quote``; since 25.10.2026 the floor compares the median, as the card does."""
    from daily3_selection import daily3_choices
    from quote_publication import publication_quote
    from tests.test_daily3_selection import NOW as DAILY3_NOW, football
    from tests.test_publication_odds_floor import priced

    best_only = priced(football(), (1.10, 1.12, 1.20))
    assert publication_quote(best_only.reference_quote, candidate=best_only, now=DAILY3_NOW) is None
    assert not daily3_choices([best_only], now=DAILY3_NOW)
    median_ok = priced(football(), (1.15, 1.20, 1.25))
    admitted = publication_quote(median_ok.reference_quote, candidate=median_ok, now=DAILY3_NOW)
    assert admitted is not None and max(point.odds for point in admitted.points) == 1.25
