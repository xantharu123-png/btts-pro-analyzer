"""AppTest coverage for the tennis tab.

Self-contained run functions (AppTest extracts the body into a temp
script): each builds a temporary shadow DB, redirects the module-level
paths, then renders the page.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest


def _make_db(with_prediction: bool) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "test_shadow.db"
    from tennis import shadow

    shadow.DB_PATH = tmp  # redirect store for the test
    with sqlite3.connect(tmp) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_utc REAL, match_date TEXT, tour TEXT, tournament TEXT,
                provider_event_id TEXT, scheduled_start_utc TEXT,
                fixture_source TEXT,
                surface TEXT, best_of INTEGER, player_a TEXT, player_b TEXT,
                p_raw REAL, p_cal REAL, markets_json TEXT, gates_json TEXT,
                verdict TEXT, recommended_side TEXT, recommended_edge REAL,
                odds_a REAL, odds_b REAL, settled INTEGER DEFAULT 0,
                actual_winner TEXT, ret_flag INTEGER DEFAULT 0, ret_set INTEGER,
                closing_odds_a REAL, closing_odds_b REAL, pnl REAL,
                model_version TEXT, policy_version TEXT
            )
            """
        )
        if with_prediction:
            gates = {
                "Belag": {"passed": True, "detail": "Hard (erlaubt)"},
                "Erfahrung": {"passed": True, "detail": "400 / 300 Matches"},
                "Aufschlag-Daten": {"passed": True, "detail": "5000 / 4000"},
            }
            markets = {"expected_games": 24.1, "p_tiebreak": 0.4, "over_2_5_sets": 0.5}
            conn.execute(
                "INSERT INTO predictions (created_utc, match_date, tour, tournament,"
                " scheduled_start_utc, fixture_source, surface, best_of, player_a,"
                " player_b, p_raw, p_cal, markets_json, gates_json, model_version,"
                " policy_version, settled) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    1.0,
                    date.today().isoformat(),
                    "ATP",
                    "Test Open",
                    (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                    "Test",
                    "Hard",
                    3,
                    "Alpha A.",
                    "Beta B.",
                    0.72,
                    0.75,
                    json.dumps(markets),
                    json.dumps(gates),
                    shadow.TENNIS_MODEL_VERSION,
                    shadow.TENNIS_POLICY_VERSION,
                    0,
                ),
            )
    return tmp


def _run_empty() -> None:
    import tennis_tab
    from tennis import shadow
    from tests.test_tennis_tab import _make_db

    tmp = _make_db(with_prediction=False)
    shadow.DB_PATH = tmp
    tennis_tab.DB_PATH = tmp
    tennis_tab.render_tennis_page()


def _run_price_check() -> None:
    import tennis_tab
    from tennis import shadow
    from tests.test_tennis_tab import _make_db

    tmp = _make_db(with_prediction=True)
    shadow.DB_PATH = tmp
    tennis_tab.DB_PATH = tmp
    tennis_tab.render_tennis_page()


def _run_closing_capture() -> None:
    import sqlite3
    from datetime import datetime, timedelta, timezone

    import tennis_tab
    from tennis import shadow
    from tests.test_tennis_tab import _make_db

    tmp = _make_db(with_prediction=True)
    start = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    conn = sqlite3.connect(tmp)
    try:
        conn.execute(
            """
            UPDATE predictions
            SET scheduled_start_utc=?, verdict='WETTE',
                recommended_side='A', recommended_edge=0.20,
                odds_a=2.00, odds_b=4.00
            WHERE id=1
            """,
            (start,),
        )
        conn.commit()
    finally:
        conn.close()
    shadow.DB_PATH = tmp
    tennis_tab.DB_PATH = tmp
    tennis_tab.render_tennis_page()


def _run_blocked_card() -> None:
    import json
    import sqlite3

    import tennis_tab
    from tennis import shadow
    from tests.test_tennis_tab import _make_db

    tmp = _make_db(with_prediction=True)
    gates = {
        "Belag": {"passed": False, "detail": "Unbekannt"},
        "Erfahrung": {"passed": False, "detail": "0 / 335 Matches"},
        "Aufschlag-Daten": {"passed": False, "detail": "0 / 850"},
    }
    with sqlite3.connect(tmp) as conn:
        conn.execute(
            "UPDATE predictions SET gates_json=?, markets_json=? WHERE id=1",
            (json.dumps(gates), json.dumps({"p_a_cal": 0.05, "p_b_cal": 0.95})),
        )
    shadow.DB_PATH = tmp
    tennis_tab.DB_PATH = tmp
    tennis_tab.render_tennis_page()


def test_empty_db_shows_friendly_empty_state():
    at = AppTest.from_function(_run_empty)
    at.run(timeout=60)
    assert len(at.exception) == 0
    assert any("keine Tennis-Vorhersagen" in info.value for info in at.info)


def test_price_check_edge_paths():
    at = AppTest.from_function(_run_price_check)
    at.run(timeout=60)
    assert len(at.exception) == 0

    # Ein guter Preis bleibt eine Shadow-Auswahl und wird nie zum Nutzertipp.
    at.number_input(key="odds_a_1").set_value(2.00)
    at.number_input(key="odds_b_1").set_value(4.00)
    at.run(timeout=60)
    at.button(key="check_1").click().run(timeout=60)
    assert any("PASSENDE QUOTE" in info.value for info in at.info)
    assert len(at.success) == 0
    visible = " ".join(info.value for info in at.info)
    assert "keinen Einsatzvorschlag" in visible

    # Eine zu niedrige Quote ändert nur den Preisstatus.
    at.number_input(key="odds_a_1").set_value(1.40)
    at.button(key="check_1").click().run(timeout=60)
    assert any("QUOTE ZU NIEDRIG" in info.value for info in at.info)
    assert len(at.error) == 0


def test_match_card_shows_plain_gates_and_markets():
    at = AppTest.from_function(_run_price_check)
    at.run(timeout=60)
    # market metrics visible without any click
    labels = [m.label for m in at.metric]
    assert "Modell" in labels
    assert "Vorsichtige Prognose" in labels


def test_blocked_card_hides_raw_probability_and_price_controls():
    at = AppTest.from_function(_run_blocked_card)
    at.run(timeout=60)
    assert len(at.exception) == 0
    assert any("KEINE BELASTBARE TENNIS-AUSWAHL" in warning.value for warning in at.warning)
    assert len(at.error) == 0
    assert len(at.number_input) == 0
    visible_text = " ".join(
        element.value
        for collection in (at.markdown, at.caption, at.error, at.info)
        for element in collection
    )
    assert "95" not in visible_text


def test_daily_scan_propagates_nonzero_exit_code():
    import tennis_tab

    failed = SimpleNamespace(returncode=2, stdout="out", stderr="boom")
    with patch.object(tennis_tab.subprocess, "run", return_value=failed):
        with pytest.raises(RuntimeError, match="Code 2"):
            tennis_tab._run_daily_scan()


def test_tennis_worker_scans_every_day_in_selected_window():
    import tennis_tab

    calls = []
    updates = []
    with patch.object(
        tennis_tab,
        "_run_daily_scan",
        side_effect=lambda value=None: calls.append(value) or f"scan {value}",
    ):
        output = tennis_tab._run_tennis_scan_worker(
            "2030-01-01",
            "2030-01-04",
            progress_cb=lambda fraction, text: updates.append((fraction, text)),
        )

    assert calls == [
        "2030-01-01",
        "2030-01-02",
        "2030-01-03",
        "2030-01-04",
    ]
    assert "scan 2030-01-04" in output
    assert updates[-1] == (1.0, "Fertig")


def test_tennis_worker_rejects_more_than_fourteen_days():
    import tennis_tab

    with pytest.raises(ValueError, match="höchstens 14 Tage"):
        tennis_tab._run_tennis_scan_worker("2030-01-01", "2030-01-16")


def test_shadow_closing_capture_is_not_exposed_to_consumer():
    at = AppTest.from_function(_run_closing_capture)
    at.run(timeout=60)
    assert len(at.exception) == 0
    assert all(button.key != "closing_capture_btn_1" for button in at.button)


def test_prematch_visibility_is_fail_closed():
    import tennis_tab

    now = datetime(2030, 1, 1, 18, 25, tzinfo=timezone.utc)
    base = {"settled": 0}

    assert tennis_tab._prematch_visibility(
        {**base, "scheduled_start_utc": "2030-01-01T18:30:00Z"},
        now,
    )[0]
    assert not tennis_tab._prematch_visibility(
        {**base, "scheduled_start_utc": "2030-01-01T18:25:00Z"},
        now,
    )[0]
    assert not tennis_tab._prematch_visibility(
        {**base, "scheduled_start_utc": None},
        now,
    )[0]
    assert not tennis_tab._prematch_visibility(
        {**base, "settled": 1, "scheduled_start_utc": "2030-01-02T18:25:00Z"},
        now,
    )[0]


def test_failed_model_gate_cannot_be_stored_as_recommendation():
    import tennis_tab
    from tennis import shadow

    tmp = _make_db(with_prediction=True)
    shadow.DB_PATH = tmp
    tennis_tab.DB_PATH = tmp

    result = tennis_tab._update_price_check(1, 2.0, 4.0, 0.75, False)
    assert result["verdict"] == "KEINE WETTE"
    assert not result["side"]
    with sqlite3.connect(tmp) as conn:
        verdict, side = conn.execute(
            "SELECT verdict, recommended_side FROM predictions WHERE id=1"
        ).fetchone()
    assert verdict == "KEINE WETTE"
    assert side is None
