"""AppTest coverage for the tennis tab.

Self-contained run functions (AppTest extracts the body into a temp
script): each builds a temporary shadow DB, redirects the module-level
paths, then renders the page.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import date
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
                surface TEXT, best_of INTEGER, player_a TEXT, player_b TEXT,
                p_raw REAL, p_cal REAL, markets_json TEXT, gates_json TEXT,
                verdict TEXT, recommended_side TEXT, recommended_edge REAL,
                odds_a REAL, odds_b REAL, settled INTEGER DEFAULT 0,
                actual_winner TEXT, ret_flag INTEGER DEFAULT 0, ret_set INTEGER,
                closing_odds_a REAL, closing_odds_b REAL, pnl REAL
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
                " surface, best_of, player_a, player_b, p_raw, p_cal, markets_json,"
                " gates_json, settled) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
                (
                    1.0,
                    date.today().isoformat(),
                    "ATP",
                    "Test Open",
                    "Hard",
                    3,
                    "Alpha A.",
                    "Beta B.",
                    0.72,
                    0.75,
                    json.dumps(markets),
                    json.dumps(gates),
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


def test_empty_db_shows_friendly_empty_state():
    at = AppTest.from_function(_run_empty)
    at.run(timeout=60)
    assert len(at.exception) == 0
    assert any("keine Tennis-Vorhersagen" in info.value for info in at.info)


def test_price_check_edge_paths():
    at = AppTest.from_function(_run_price_check)
    at.run(timeout=60)
    assert len(at.exception) == 0

    # gift price on the 75% side -> WETTE
    at.number_input(key="odds_a_1").set_value(2.00)
    at.button(key="check_1").click().run(timeout=60)
    assert any("WETTE" in s.value for s in at.success)

    # fair price -> KEINE WETTE (edge below 12% threshold)
    at.number_input(key="odds_a_1").set_value(1.40)
    at.button(key="check_1").click().run(timeout=60)
    assert any("KEINE WETTE" in e.value for e in at.error)


def test_match_card_shows_plain_gates_and_markets():
    at = AppTest.from_function(_run_price_check)
    at.run(timeout=60)
    # market metrics visible without any click
    labels = [m.label for m in at.metric]
    assert any("Vorhersagen gesamt" in label for label in labels)


def test_daily_scan_propagates_nonzero_exit_code():
    import tennis_tab

    failed = SimpleNamespace(returncode=2, stdout="out", stderr="boom")
    with patch.object(tennis_tab.subprocess, "run", return_value=failed):
        with pytest.raises(RuntimeError, match="Code 2"):
            tennis_tab._run_daily_scan()
