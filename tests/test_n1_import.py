from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import zipfile

import pytest
from streamlit.testing.v1 import AppTest

from n1_import import (
    N1ImportError,
    N1ImportTarget,
    N1WidgetBinding,
    apply_imported_widget_value,
    match_imported_quotes,
    parse_import_snapshot,
)
from n1_import_component import extension_archive


NOW = datetime(2026, 8, 6, 18, 30, tzinfo=timezone.utc)


def _payload(*records, captured_at: datetime = NOW):
    return {
        "version": 1,
        "bookmaker": "N1Bet",
        "capturedAt": captured_at.isoformat(),
        "pageUrl": "https://bet.n1bet.com/sportsbook/football",
        "records": list(records),
        "diagnostics": {"pages": 1, "scannedElements": 12},
    }


def _record(
    *,
    record_id="quote-1",
    odds=2.05,
    event="France vs Spain",
    market="Both Teams To Score",
    selection="Yes",
    context="France vs Spain Both Teams To Score Yes 2.05 No 1.70",
    captured_at: datetime = NOW,
    line=None,
    live=False,
):
    return {
        "id": record_id,
        "odds": odds,
        "event": event,
        "market": market,
        "selection": selection,
        "context": context,
        "capturedAt": captured_at.isoformat(),
        "sourcePage": "https://bet.n1bet.com/sportsbook/football/event/123",
        "line": line,
        "live": live,
    }


def test_snapshot_accepts_only_valid_n1_records():
    snapshot = parse_import_snapshot(
        _payload(
            _record(),
            _record(record_id="bad", odds=1.0),
            {**_record(record_id="wrong-host"), "sourcePage": "https://example.com"},
        ),
        now=NOW,
    )
    assert len(snapshot.quotes) == 1
    assert snapshot.quotes[0].decimal_odds == 2.05
    assert snapshot.page_count == 1


def test_snapshot_rejects_wrong_bookmaker_and_future_timestamp():
    wrong = _payload(_record())
    wrong["bookmaker"] = "OtherBet"
    with pytest.raises(N1ImportError):
        parse_import_snapshot(wrong, now=NOW)

    with pytest.raises(N1ImportError):
        parse_import_snapshot(
            _payload(_record(), captured_at=NOW + timedelta(minutes=5)),
            now=NOW,
        )


def test_matches_exact_football_event_market_and_selection():
    snapshot = parse_import_snapshot(_payload(_record()), now=NOW)
    target = N1ImportTarget(
        key="fr-es-btts",
        sport="Fußball",
        event_name="Frankreich vs Spanien",
        market="Beide Teams treffen",
        selection="Ja",
        participants=("France", "Spain"),
    )
    matches = match_imported_quotes((target,), snapshot, now=NOW)
    assert matches[target.key].quote.decimal_odds == 2.05


def test_matches_tennis_winner_by_both_players_and_exact_selection():
    snapshot = parse_import_snapshot(
        _payload(
            _record(
                odds=2.60,
                event="Shang Juncheng vs Luciano Darderi",
                market="Match Winner",
                selection="Luciano Darderi",
                context="Shang Juncheng vs Luciano Darderi Match Winner Luciano Darderi 2.60",
            )
        ),
        now=NOW,
    )
    target = N1ImportTarget(
        key="tennis-darderi",
        sport="Tennis",
        event_name="Shang Juncheng vs Luciano Darderi",
        market="Match-Sieger",
        selection="Luciano Darderi",
        participants=("Shang Juncheng", "Luciano Darderi"),
    )
    assert match_imported_quotes((target,), snapshot, now=NOW)[target.key].quote.decimal_odds == 2.60


def test_total_line_must_match_exactly():
    snapshot = parse_import_snapshot(
        _payload(
            _record(
                odds=1.91,
                market="Total Goals",
                selection="Over 3.5",
                context="France vs Spain Total Goals Over 3.5 1.91",
                line=3.5,
            )
        ),
        now=NOW,
    )
    target = N1ImportTarget(
        key="total-25",
        sport="Fußball",
        event_name="France vs Spain",
        market="Gesamttore",
        selection="Über 2,5",
        participants=("France", "Spain"),
        line=2.5,
    )
    assert match_imported_quotes((target,), snapshot, now=NOW) == {}


def test_team_total_requires_the_correct_team_scope():
    snapshot = parse_import_snapshot(
        _payload(
            _record(
                odds=1.83,
                market="France Total Goals",
                selection="Over 1.5",
                context="France vs Spain France Total Goals Over 1.5 1.83",
                line=1.5,
            )
        ),
        now=NOW,
    )
    home_target = N1ImportTarget(
        key="france-total",
        sport="Fußball",
        event_name="France vs Spain",
        market="Team 1 Gesamttore",
        selection="Über 1,5",
        participants=("France", "Spain"),
        line=1.5,
    )
    away_target = N1ImportTarget(
        key="spain-total",
        sport="Fußball",
        event_name="France vs Spain",
        market="Team 2 Gesamttore",
        selection="Über 1,5",
        participants=("France", "Spain"),
        line=1.5,
    )
    matches = match_imported_quotes((home_target, away_target), snapshot, now=NOW)
    assert home_target.key in matches
    assert away_target.key not in matches


def test_combined_market_cannot_match_a_plain_total_price():
    snapshot = parse_import_snapshot(
        _payload(
            _record(
                odds=1.70,
                market="Total Goals",
                selection="Under 3.5",
                context="France vs Spain Total Goals Under 3.5 1.70",
                line=3.5,
            )
        ),
        now=NOW,
    )
    target = N1ImportTarget(
        key="combined",
        sport="Fußball",
        event_name="France vs Spain",
        market="Resultat & Gesamttore 3,5",
        selection="1X und Unter 3,5",
        participants=("France", "Spain"),
        line=3.5,
    )
    assert match_imported_quotes((target,), snapshot, now=NOW) == {}


def test_live_and_stale_prices_do_not_fill_prematch_target():
    target = N1ImportTarget(
        key="prematch",
        sport="Fußball",
        event_name="France vs Spain",
        market="Beide Teams treffen",
        selection="Ja",
        participants=("France", "Spain"),
    )
    live_snapshot = parse_import_snapshot(_payload(_record(live=True)), now=NOW)
    assert match_imported_quotes((target,), live_snapshot, now=NOW) == {}

    stale_time = NOW - timedelta(minutes=11)
    stale_snapshot = parse_import_snapshot(
        _payload(_record(captured_at=stale_time), captured_at=stale_time),
        now=NOW,
    )
    assert match_imported_quotes((target,), stale_snapshot, now=NOW) == {}


def test_conflicting_equal_matches_are_rejected():
    snapshot = parse_import_snapshot(
        _payload(
            _record(record_id="a", odds=1.90),
            _record(record_id="b", odds=2.10),
        ),
        now=NOW,
    )
    target = N1ImportTarget(
        key="ambiguous",
        sport="Fußball",
        event_name="France vs Spain",
        market="Beide Teams treffen",
        selection="Ja",
        participants=("France", "Spain"),
    )
    assert match_imported_quotes((target,), snapshot, now=NOW) == {}


def test_import_never_overwrites_manual_widget_value():
    snapshot = parse_import_snapshot(_payload(_record()), now=NOW)
    target = N1ImportTarget(
        key="target",
        sport="Fußball",
        event_name="France vs Spain",
        market="Beide Teams treffen",
        selection="Ja",
        participants=("France", "Spain"),
    )
    match = match_imported_quotes((target,), snapshot, now=NOW)[target.key]
    binding = N1WidgetBinding(target, "odds", "text")
    state = {"odds": "1.88"}
    assert apply_imported_widget_value(state, binding, match) is False
    assert state["odds"] == "1.88"

    empty_state = {}
    assert apply_imported_widget_value(empty_state, binding, match) is True
    assert empty_state["odds"] == "2.05"


def test_download_archive_contains_a_valid_manifest_and_bridge_scripts():
    with zipfile.ZipFile(io.BytesIO(extension_archive())) as archive:
        names = set(archive.namelist())
    prefix = "betboy-n1bet-importer/"
    assert prefix + "manifest.json" in names
    assert prefix + "n1bet-content.js" in names
    assert prefix + "betboy-content.js" in names
    assert prefix + "background.js" in names


def _run_imported_price_card() -> None:
    from datetime import datetime, timedelta, timezone

    import n1_import_ui
    from bet_finder_ui import render_price_decision
    from multi_sport_recommendations import RecommendationCandidate

    captured_at = datetime.now(timezone.utc)
    n1_import_ui.render_bridge = lambda **_kwargs: {
        "status": "OK",
        "syncNonce": 0,
        "snapshot": {
            "version": 1,
            "bookmaker": "N1Bet",
            "capturedAt": captured_at.isoformat(),
            "pageUrl": "https://bet.n1bet.com/sportsbook/tennis",
            "records": [
                {
                    "id": "darderi",
                    "odds": 2.60,
                    "event": "Shang Juncheng vs Luciano Darderi",
                    "market": "Match Winner",
                    "selection": "Luciano Darderi",
                    "context": (
                        "Shang Juncheng vs Luciano Darderi Match Winner "
                        "Luciano Darderi 2.60"
                    ),
                    "capturedAt": captured_at.isoformat(),
                    "sourcePage": "https://bet.n1bet.com/sportsbook/tennis/event/1",
                    "live": False,
                }
            ],
        },
    }
    candidate = RecommendationCandidate(
        event_key="tennis-1",
        sport="Tennis",
        event_label="Shang Juncheng vs Luciano Darderi",
        market="Match-Sieger",
        selection="Luciano Darderi",
        line=None,
        model_probability=61.0,
        risk_adjusted_probability=56.0,
        probability_haircut=5.0,
        fair_odds=1.639,
        minimum_odds=1.84,
        model_name="Testmodell",
        expected_total=None,
        evidence=("Test",),
        blockers=(),
    )
    render_price_decision(candidate, key="imported_test")


def test_shared_tip_ui_no_longer_depends_on_browser_import():
    app = AppTest.from_function(_run_imported_price_card)
    app.run(timeout=30)
    assert len(app.exception) == 0
    assert len(app.text_input) == 0
    assert any("KEINE WETTFREIGABE" in info.value for info in app.info)
    visible_text = " ".join(
        element.value
        for collection in (app.caption, app.info, app.success, app.warning)
        for element in collection
    )
    assert "N1Bet" not in visible_text
