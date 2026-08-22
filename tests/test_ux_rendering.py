"""UX regression tests for the bet-decision rendering.

Nails down the three failures from the 2026-07-29 screenshot review:
1. A bare "Ja" must never appear as a standalone heading.
2. A blocked candidate keeps its quotenfreie forecast visible.
3. One clear overall verdict instead of repeated NICHT WETTEN fragments.

Note: AppTest.from_function extracts only the function body into a temp
script, so every run function below must be fully self-contained — no
module-level helpers, constants, or imports.
"""

from streamlit.testing.v1 import AppTest

import ui_components
from ui_components import _example_ticket_html, plain_german


def _run_zero_ready() -> None:
    from datetime import datetime, timedelta, timezone

    import pandas as pd
    from app import _render_prematch_results

    kickoff = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    frame = pd.DataFrame([{
        "_fixture_id": 123,
        "_fixture_date": kickoff,
        "Home": "Alpha",
        "Away": "Beta",
        "Date": kickoff,
        "League": "Test-Liga",
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
    }])
    _render_prematch_results(
        frame, 60, 60,
        scanned_at=datetime.now().astimezone().isoformat(),
        validated_model_available=False,
    )


def _run_one_ready() -> None:
    from datetime import datetime, timedelta, timezone

    import pandas as pd
    from app import _render_prematch_results

    kickoff = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    frame = pd.DataFrame([{
        "_fixture_id": 123,
        "_fixture_date": kickoff,
        "Home": "Alpha",
        "Away": "Beta",
        "Date": kickoff,
        "League": "Test-Liga",
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
    }])
    _render_prematch_results(
        frame, 60, 60,
        scanned_at=datetime.now().astimezone().isoformat(),
        validated_model_available=True,
    )


def _run_blocked_card() -> None:
    from datetime import datetime, timedelta, timezone

    import pandas as pd
    from bet_finder_ui import render_price_decision
    from football_recommendations import prematch_btts_candidate

    kickoff = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    frame = pd.DataFrame([{
        "_fixture_id": 123,
        "_fixture_date": kickoff,
        "Home": "Alpha",
        "Away": "Beta",
        "Date": kickoff,
        "League": "Test-Liga",
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
    }])
    candidate = prematch_btts_candidate(
        frame.iloc[0],
        snapshot_age_seconds=60,
        validated_model_available=False,
    )
    render_price_decision(candidate, key="ux_test_blocked")


def _run_shadow_playable_card() -> None:
    from datetime import datetime, timezone

    from bet_finder_ui import render_price_decision
    from market_consensus import MarketConsensus, QuotePoint
    from multi_sport_recommendations import EVIDENCE_SHADOW, RecommendationCandidate

    now = datetime.now(timezone.utc).isoformat()
    candidate = RecommendationCandidate(
        event_key="shadow-1",
        sport="Fußball",
        event_label="Alpha vs Beta",
        market="Beide treffen",
        selection="Ja",
        line=None,
        model_probability=65.0,
        risk_adjusted_probability=60.0,
        probability_haircut=5.0,
        fair_odds=1.538,
        minimum_odds=1.80,
        model_name="Testmodell",
        expected_total=3.0,
        evidence=("interne Prüfung",),
        evidence_stage=EVIDENCE_SHADOW,
    )
    quote = MarketConsensus(
        fixture_id=1,
        candidate_id="shadow-1",
        market_key="BTTS_YES",
        bet_name="Both Teams Score",
        value_name="Yes",
        consensus_odds=2.00,
        conservative_odds=2.00,
        lowest_odds=1.95,
        best_odds=2.10,
        bookmaker_count=3,
        quoted_at=now,
        fetched_at=now,
        source="test",
        points=(
            QuotePoint("A", 1.95),
            QuotePoint("B", 2.00),
            QuotePoint("C", 2.10),
        ),
    )
    render_price_decision(
        candidate,
        key="ux_shadow_playable",
        save_source="Test",
        reference_quote=quote,
    )


def _run_released_playable_card() -> None:
    from datetime import datetime, timezone

    from bet_finder_ui import render_price_decision
    from market_consensus import MarketConsensus, QuotePoint
    from multi_sport_recommendations import EVIDENCE_RELEASED, RecommendationCandidate

    now = datetime.now(timezone.utc).isoformat()
    candidate = RecommendationCandidate(
        event_key="released-1",
        sport="Fußball",
        event_label="Alpha vs Beta",
        market="Beide treffen",
        selection="Ja",
        line=None,
        model_probability=65.0,
        risk_adjusted_probability=60.0,
        probability_haircut=5.0,
        fair_odds=1.538,
        minimum_odds=1.80,
        model_name="Testmodell",
        expected_total=3.0,
        evidence=("interne Prüfung",),
        evidence_stage=EVIDENCE_RELEASED,
    )
    quote = MarketConsensus(
        fixture_id=1,
        candidate_id="released-1",
        market_key="BTTS_YES",
        bet_name="Both Teams Score",
        value_name="Yes",
        consensus_odds=2.00,
        conservative_odds=2.00,
        lowest_odds=1.95,
        best_odds=2.10,
        bookmaker_count=3,
        quoted_at=now,
        fetched_at=now,
        source="test",
        points=(
            QuotePoint("A", 1.95),
            QuotePoint("B", 2.00),
            QuotePoint("C", 2.10),
        ),
    )
    render_price_decision(
        candidate,
        key="ux_released_playable",
        save_source="Test",
        reference_quote=quote,
    )


def _run_missing_price_card() -> None:
    from bet_finder_ui import render_price_decision
    from multi_sport_recommendations import EVIDENCE_RELEASED, RecommendationCandidate

    candidate = RecommendationCandidate(
        event_key="missing-1",
        sport="Fußball",
        event_label="Alpha vs Beta",
        market="Beide treffen",
        selection="Ja",
        line=None,
        model_probability=65.0,
        risk_adjusted_probability=60.0,
        probability_haircut=5.0,
        fair_odds=1.538,
        minimum_odds=1.80,
        model_name="Testmodell",
        expected_total=3.0,
        evidence=("interne Prüfung",),
        evidence_stage=EVIDENCE_RELEASED,
    )
    render_price_decision(candidate, key="ux_missing_price")


def _run_too_low_price_card() -> None:
    from datetime import datetime, timezone

    from bet_finder_ui import render_price_decision
    from market_consensus import MarketConsensus, QuotePoint
    from multi_sport_recommendations import EVIDENCE_RELEASED, RecommendationCandidate

    now = datetime.now(timezone.utc).isoformat()
    candidate = RecommendationCandidate(
        event_key="low-1",
        sport="Fußball",
        event_label="Alpha vs Beta",
        market="Beide treffen",
        selection="Ja",
        line=None,
        model_probability=65.0,
        risk_adjusted_probability=60.0,
        probability_haircut=5.0,
        fair_odds=1.538,
        minimum_odds=1.80,
        model_name="Testmodell",
        expected_total=3.0,
        evidence=("interne Prüfung",),
        evidence_stage=EVIDENCE_RELEASED,
    )
    quote = MarketConsensus(
        fixture_id=1,
        candidate_id="low-1",
        market_key="BTTS_YES",
        bet_name="Both Teams Score",
        value_name="Yes",
        consensus_odds=1.60,
        conservative_odds=1.60,
        lowest_odds=1.55,
        best_odds=1.70,
        bookmaker_count=3,
        quoted_at=now,
        fetched_at=now,
        source="test",
        points=(
            QuotePoint("A", 1.55),
            QuotePoint("B", 1.60),
            QuotePoint("C", 1.70),
        ),
    )
    render_price_decision(
        candidate,
        key="ux_too_low_price",
        save_source="Test",
        reference_quote=quote,
    )


def _run_partial_manual_scan_zero() -> None:
    from alternative_markets_tab_extended import _render_consumer_no_tip

    _render_consumer_no_tip(
        {
            "fixtures_found": 205,
            "fixtures_modeled": 144,
            "base_fixture_count": 21,
            "context_verified_fixtures": 20,
            "context_unchecked_fixtures": 1,
            "model_blocked_counts": {"Walk-forward-Gate": 5947},
        },
        day_label="Heute",
    )


def _run_complete_model_zero() -> None:
    from alternative_markets_tab_extended import _render_consumer_no_tip

    _render_consumer_no_tip(
        {
            "fixtures_found": 40,
            "fixtures_modeled": 40,
            "base_candidates": 0,
            "base_fixture_count": 0,
        },
        day_label="Heute",
    )


def test_zero_ready_keeps_best_price_independent_forecast_visible():
    at = AppTest.from_function(_run_zero_ready)
    at.run(timeout=60)
    assert len(at.warning) >= 1
    assert any("KEINE WETTE" in warning.value for warning in at.warning)
    # Die Quote darf eine gesperrte Modellprognose nicht unsichtbar machen.
    assert len(at.selectbox) == 1
    assert any(
        "PROGNOSE VORHANDEN" in warning.value for warning in at.warning
    )
    # Keine nackte Auswahl-Überschrift wie "Ja"
    assert all(header.value.strip() not in {"Ja", "Nein"} for header in at.subheader)


def test_ready_candidate_renders_market_and_selection_as_heading():
    at = AppTest.from_function(_run_one_ready)
    at.run(timeout=60)
    assert len(at.error) == 0
    assert len(at.success) >= 1
    assert "bestehen die Modellprüfung" in at.success[0].value
    assert "automatische Marktvergleich" in at.success[0].value
    headings = [header.value for header in at.subheader]
    assert any(":" in heading for heading in headings)
    assert all(heading.strip() != "Ja" for heading in headings)


def test_blocked_candidate_card_has_single_verdict_and_plain_reasons():
    at = AppTest.from_function(_run_blocked_card)
    at.run(timeout=60)
    assert len(at.error) == 0
    assert len(at.warning) == 1
    assert "PROGNOSE VORHANDEN" in at.warning[0].value
    headings = [header.value for header in at.subheader]
    assert all(heading.strip() != "Ja" for heading in headings)
    assert any(":" in heading for heading in headings)


def test_shadow_selection_with_good_price_is_never_labeled_or_saved_as_tip():
    at = AppTest.from_function(_run_shadow_playable_card)
    at.run(timeout=60)
    assert len(at.exception) == 0
    assert len(at.success) == 0
    assert any("PASSENDE QUOTE" in info.value for info in at.info)
    assert any("kein Einsatzvorschlag" in info.value for info in at.info)
    assert all("TIPP" not in info.value for info in at.info)
    assert all(button.label != "Tipp merken" for button in at.button)


def test_released_selection_with_good_price_is_a_playable_tip():
    at = AppTest.from_function(_run_released_playable_card)
    at.run(timeout=60)
    assert len(at.exception) == 0
    assert any("SPIELBARER TIPP" in success.value for success in at.success)
    assert any(button.label == "Tipp merken" for button in at.button)


def test_missing_quote_keeps_selection_visible_and_neutral():
    at = AppTest.from_function(_run_missing_price_card)
    at.run(timeout=60)
    assert len(at.exception) == 0
    assert len(at.error) == 0
    assert len(at.warning) == 0
    text = " ".join(info.value for info in at.info)
    assert "PREIS NOCH OFFEN" in text
    assert text.count("PREIS NOCH OFFEN") == 1
    assert "richtig oder falsch" in text


def test_low_quote_changes_only_price_not_model_selection():
    at = AppTest.from_function(_run_too_low_price_card)
    at.run(timeout=60)
    assert len(at.exception) == 0
    assert len(at.error) == 0
    assert len(at.warning) == 0
    text = " ".join(info.value for info in at.info)
    assert "QUOTE ZU NIEDRIG" in text
    assert "Prognose bleibt unverändert" in text
    assert "angebotene Preis ist zu niedrig" in text
    metric_labels = [metric.label for metric in at.metric]
    assert "Value-Grenze" in metric_labels
    assert "Mindestquote" not in metric_labels
    assert "keine erwartete Buchmacherquote" in text
    assert all(button.label != "Tipp merken" for button in at.button)


def test_partial_manual_scan_renders_bounded_claim_with_compact_evidence():
    at = AppTest.from_function(_run_partial_manual_scan_zero)
    at.run(timeout=60)

    assert len(at.exception) == 0
    assert len(at.error) == 0
    assert len(at.warning) == 1
    assert "Für 1 weiteres Spiel" in at.warning[0].value
    captions = " ".join(item.value for item in at.caption)
    assert "205 Spiele gefunden" in captions
    assert "144 modelliert" in captions
    assert "20 mit verfügbaren Kontextdaten geprüft" in captions
    visible = captions + " " + at.warning[0].value
    assert "Walk-forward" not in visible
    assert "5947" not in visible


def test_complete_model_zero_explains_that_no_quote_was_checked():
    at = AppTest.from_function(_run_complete_model_zero)
    at.run(timeout=60)

    assert len(at.exception) == 0
    assert len(at.error) == 0
    assert len(at.warning) == 0
    assert len(at.info) == 1
    assert "Quote wurde deshalb noch nicht geprüft" in at.info[0].value
    assert "40 Spiele gefunden" in " ".join(item.value for item in at.caption)


def test_plain_german_replaces_model_jargon():
    assert "Prüfkriterien" in plain_german("bestehen die Modellgates")
    assert "validierte" in plain_german("Das chronologisch validierte BTTS-Modell")
    assert "Walk-forward-Prüfung" in plain_german("Walk-forward-Gate fehlt")
    # Artikel muss mit dem Genus von "Prüfung" mitwandern
    assert "die Walk-forward-Prüfung" in plain_german(
        "Markt hat das Walk-forward-Gate nicht bestanden"
    )
    assert "das Walk-forward-Prüfung" not in plain_german(
        "Markt hat das Walk-forward-Gate nicht bestanden"
    )
    assert plain_german("normaler Text") == "normaler Text"


def test_shared_scan_progress_shows_percentage_phase_and_elapsed_time(
    monkeypatch,
):
    rendered = {}
    monkeypatch.setattr(
        ui_components.st,
        "progress",
        lambda value, text=None: rendered.update(value=value, text=text),
    )
    monkeypatch.setattr(
        ui_components.st,
        "caption",
        lambda text: rendered.update(caption=text),
    )

    ui_components.render_scan_progress(
        {
            "progress": 0.39,
            "progress_text": "Liga 5/51",
            "started_at": "2026-08-03T06:00:00+00:00",
        },
        "Markt-Scan",
    )

    assert rendered["value"] == 0.39
    assert rendered["text"] == "39 % · Markt-Scan: Liga 5/51"
    assert "Laufzeit" in rendered["caption"]
    assert "Seitenwechsel" in rendered["caption"]


def test_shared_scan_progress_shows_explicit_completion(monkeypatch):
    rendered = {}
    monkeypatch.setattr(
        ui_components.st,
        "progress",
        lambda value, text=None: rendered.update(value=value, text=text),
    )
    monkeypatch.setattr(
        ui_components.st,
        "caption",
        lambda text: rendered.update(caption=text),
    )

    ui_components.render_scan_progress(
        {
            "state": "done",
            "progress": 1.0,
            "progress_text": "Abgeschlossen",
        },
        "Markt-Scan",
    )

    assert rendered["value"] == 1.0
    assert rendered["text"] == "100 % · Markt-Scan: Abgeschlossen"
    assert rendered["caption"].startswith("Markt-Scan abgeschlossen")


def test_consumer_scan_progress_hides_internal_worker_phase(monkeypatch):
    rendered = {}
    monkeypatch.setattr(
        ui_components.st,
        "progress",
        lambda value, text=None: rendered.update(value=value, text=text),
    )
    monkeypatch.setattr(
        ui_components.st,
        "caption",
        lambda text: rendered.update(caption=text),
    )

    ui_components.render_scan_progress(
        {
            "progress": 0.55,
            "progress_text": "Walk-forward-Gate und UEFA-Transfergate",
        },
        "Fußball-Suche",
        show_internal_detail=False,
    )

    assert rendered["text"] == "55 % · Fußball-Suche"
    assert "Walk-forward" not in rendered["text"]
    assert "Transfergate" not in rendered["text"]


def test_empty_state_supports_sport_specific_escaped_example():
    rendered = _example_ticket_html(
        ("Spieler <A>", "Sieg & Satzvorsprung @ 2,10"),
    )
    assert "Spieler &lt;A&gt;" in rendered
    assert "Sieg &amp; Satzvorsprung" in rendered
    assert "Beide treffen" not in rendered
