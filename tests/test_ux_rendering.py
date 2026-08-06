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


def test_empty_state_supports_sport_specific_escaped_example():
    rendered = _example_ticket_html(
        ("Spieler <A>", "Sieg & Satzvorsprung @ 2,10"),
    )
    assert "Spieler &lt;A&gt;" in rendered
    assert "Sieg &amp; Satzvorsprung" in rendered
    assert "Beide treffen" not in rendered
