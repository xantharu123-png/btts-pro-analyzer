from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from riskobet_candidates import adapt_tennis_shadow
from riskobet_domain import RiskRunSnapshot, RunStatus, stable_event_key
from riskobet_settlement import (
    Selection,
    SettlementStatus,
    TennisTermination,
    settle_market,
)
from riskobet_settlement_automation import SettlementRequest, tennis_result_loader
from riskobet_store import RiskBetStore
from scripts import tennis_daily
from tennis import shadow
from tennis_tab import _next_tennis_scan_date


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Prediction:
    player_a = "Alpha"
    player_b = "Beta"
    surface = "Hard"
    best_of = 3
    p_a_raw = 0.61
    p_a_cal = 0.60
    gates = []
    verdict = "KEINE WETTE"
    recommended_side = None
    recommended_edge = 0.0

    def market_summary(self):
        return {}


class _RecommendedPrediction(_Prediction):
    verdict = "WETTE"
    recommended_side = "A"
    recommended_edge = 0.12


def _sofascore_event(
    event_id,
    *,
    status_type,
    status_description,
    player_b="Beta",
    winner_code=None,
    home_sets=None,
    away_sets=None,
):
    event = {
        "id": event_id,
        "startTimestamp": int(
            datetime(2030, 1, 1, 12, tzinfo=timezone.utc).timestamp()
        ),
        "status": {
            "type": status_type,
            "description": status_description,
        },
        "tournament": {
            "name": "Test Open",
            "category": {"slug": "atp"},
        },
        "homeTeam": {"name": "Alpha"},
        "awayTeam": {"name": player_b},
    }
    if winner_code is not None:
        event["winnerCode"] = winner_code
    if home_sets is not None:
        event["homeScore"] = {"current": home_sets}
    if away_sets is not None:
        event["awayScore"] = {"current": away_sets}
    return event


def test_sofascore_fixture_keeps_event_and_start(monkeypatch):
    start = datetime(2030, 1, 1, 17, 30, tzinfo=timezone.utc)
    payload = {
        "events": [
            {
                "id": 1234,
                "startTimestamp": int(start.timestamp()),
                "status": {"type": "notstarted"},
                "tournament": {
                    "name": "Test Open",
                    "category": {"slug": "atp"},
                },
                "homeTeam": {"name": "Alpha"},
                "awayTeam": {"name": "Beta"},
            }
        ]
    }
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response(payload),
    )

    fixture = tennis_daily.fetch_fixtures_sofascore("2030-01-01")[0]
    assert fixture["provider_event_id"] == "1234"
    assert fixture["scheduled_start_utc"] == "2030-01-01T17:30:00Z"
    assert fixture["fixture_source"] == "SofaScore"
    assert fixture["match_date"] == "2030-01-01"


def test_sofascore_results_accept_only_explicit_terminal_statuses(monkeypatch):
    payload = {
        "events": [
            _sofascore_event(
                2001,
                status_type="finished",
                status_description="Ended",
                winner_code=1,
                home_sets=2,
                away_sets=1,
            ),
            _sofascore_event(
                2002,
                status_type="retired",
                status_description="Retired",
                winner_code=1,
                home_sets=1,
                away_sets=0,
            ),
            _sofascore_event(
                2003,
                status_type="canceled",
                status_description="Walkover",
                winner_code=1,
            ),
            _sofascore_event(
                2004,
                status_type="canceled",
                status_description="Defaulted",
            ),
            _sofascore_event(
                2005,
                status_type="finished",
                status_description="Abandoned",
                winner_code=1,
                home_sets=1,
                away_sets=0,
            ),
            _sofascore_event(
                2006,
                status_type="inprogress",
                status_description="Live",
                winner_code=1,
                home_sets=1,
                away_sets=0,
            ),
            _sofascore_event(
                2007,
                status_type="inprogress",
                status_description="Player retired",
            ),
            _sofascore_event(
                2008,
                status_type="notstarted",
                status_description="Walkover noted prematurely",
            ),
        ]
    }
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response(payload),
    )

    results = tennis_daily.fetch_results_sofascore("2030-01-01")

    assert {result["provider_event_id"] for result in results} == {
        "2001",
        "2002",
        "2003",
    }
    by_id = {result["provider_event_id"]: result for result in results}
    assert by_id["2001"]["termination"] == "normal"
    assert by_id["2001"]["winner"] == "Alpha"
    assert by_id["2001"]["winner_sets"] == 2
    assert by_id["2001"]["loser_sets"] == 1
    for event_id, termination in (("2002", "retirement"), ("2003", "walkover")):
        assert by_id[event_id]["termination"] == termination
        assert by_id[event_id]["winner"] is None
        assert by_id[event_id]["winner_sets"] is None
        assert by_id[event_id]["loser_sets"] is None


@pytest.mark.parametrize(
    ("status_type", "status_description", "expected_termination"),
    (
        ("retired", "Retired", "retirement"),
        ("finished", "Player retired", "retirement"),
        ("canceled", "Player retired", None),
        ("walkover", "Walkover", "walkover"),
        ("canceled", "Walkover", "walkover"),
        ("cancelled", "Walkover", "walkover"),
        ("finished", "Walkover", "walkover"),
        ("retired", "Walkover", None),
    ),
)
def test_sofascore_abnormal_status_type_combinations_fail_closed(
    monkeypatch,
    status_type,
    status_description,
    expected_termination,
):
    event = _sofascore_event(
        2010,
        status_type=status_type,
        status_description=status_description,
    )
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response({"events": [event]}),
    )

    results = tennis_daily.fetch_results_sofascore("2030-01-01")

    if expected_termination is None:
        assert results == []
    else:
        assert len(results) == 1
        assert results[0]["termination"] == expected_termination


@pytest.mark.parametrize("bad_event_id", (None, True, 0, -1, 12.5, "12", {}))
def test_sofascore_rejects_missing_or_non_integer_event_identity(
    monkeypatch,
    bad_event_id,
):
    scheduled = _sofascore_event(
        bad_event_id,
        status_type="notstarted",
        status_description="Not started",
    )
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response({"events": [scheduled]}),
    )
    assert tennis_daily.fetch_fixtures_sofascore("2030-01-01") == []

    terminal = _sofascore_event(
        bad_event_id,
        status_type="finished",
        status_description="Ended",
        winner_code=1,
        home_sets=2,
        away_sets=0,
    )
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response({"events": [terminal]}),
    )
    assert tennis_daily.fetch_results_sofascore("2030-01-01") == []


def test_espn_fixture_keeps_competition_id_and_local_date(monkeypatch):
    payload = {
        "events": [
            {
                "name": "Test Open",
                "groupings": [
                    {
                        "grouping": {"slug": "mens-singles"},
                        "competitions": [
                            {
                                "id": "espn-42",
                                "date": "2030-01-01T23:30:00Z",
                                "status": {"type": {"state": "pre"}},
                                "competitors": [
                                    {"athlete": {"displayName": "Alpha"}},
                                    {"athlete": {"displayName": "Beta"}},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response(payload),
    )

    fixture = tennis_daily.fetch_fixtures_espn("2030-01-01")[0]
    assert fixture["provider_event_id"] == "espn-42"
    assert fixture["scheduled_start_utc"] == "2030-01-01T23:30:00Z"
    assert fixture["fixture_source"] == "ESPN"
    assert fixture["match_date"] == "2030-01-02"


def test_espn_results_accept_only_explicit_terminal_statuses(monkeypatch):
    normal = {
        "id": "normal-1",
        "date": "2030-01-01T12:00:00Z",
        "status": {
            "type": {
                "state": "post",
                "completed": True,
                "name": "STATUS_FINAL",
                "detail": "Final",
            }
        },
        "notes": [{"text": "Alpha bt Beta 6-4 3-6 6-2"}],
        "competitors": [
            {
                "winner": True,
                "athlete": {"displayName": "Alpha"},
                "linescores": [
                    {"winner": True},
                    {"winner": False},
                    {"winner": True},
                ],
            },
            {
                "winner": False,
                "athlete": {"displayName": "Beta"},
                "linescores": [
                    {"winner": False},
                    {"winner": True},
                    {"winner": False},
                ],
            },
        ],
    }
    retired = {
        **normal,
        "id": "retired-1",
        "notes": [{"text": "Alpha bt Beta - retired"}],
    }
    walkover = {
        **normal,
        "id": "walkover-1",
        "notes": [{"text": "Alpha advances by walkover"}],
    }
    defaulted = {
        **normal,
        "id": "defaulted-1",
        "notes": [{"text": "Match defaulted"}],
    }
    payload = {
        "events": [
            {
                "groupings": [
                    {
                        "grouping": {"slug": "mens-singles"},
                        "competitions": [normal, retired, walkover, defaulted],
                    }
                ]
            }
        ]
    }
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response(payload),
    )

    results = tennis_daily.fetch_results_espn("2030-01-01", "ATP")
    assert {result["provider_event_id"] for result in results} == {
        "normal-1",
        "retired-1",
        "walkover-1",
    }
    by_id = {result["provider_event_id"]: result for result in results}
    assert by_id["normal-1"]["termination"] == "normal"
    assert by_id["normal-1"]["winner"] == "Alpha"
    assert by_id["normal-1"]["winner_sets"] == 2
    assert by_id["normal-1"]["loser_sets"] == 1
    for event_id, termination in (
        ("retired-1", "retirement"),
        ("walkover-1", "walkover"),
    ):
        assert by_id[event_id]["termination"] == termination
        assert by_id[event_id]["winner"] is None
        assert by_id[event_id]["winner_sets"] is None
        assert by_id[event_id]["loser_sets"] is None
    observed_at = datetime.fromisoformat(by_id["normal-1"]["result_observed_at"])
    assert observed_at.tzinfo is not None
    assert observed_at.utcoffset() == timedelta(0)


def test_default_scan_date_uses_zurich_calendar():
    now = datetime(2030, 1, 1, 23, 30, tzinfo=timezone.utc)
    assert tennis_daily._default_scan_date(now) == "2030-01-03"


def test_national_bank_open_resolves_to_current_montreal_hardcourt():
    surfaces = {
        "montreal": ("Hard", 3, "Omnium Banque National", False),
    }
    assert tennis_daily.resolve_surface(
        "National Bank Open presented by Rogers", surfaces
    ) == ("Hard", 3, "Omnium Banque National", False)


def test_provider_surface_parses_explicit_court_and_environment():
    assert tennis_daily.provider_surface("Hardcourt outdoor") == ("Hard", False)
    assert tennis_daily.provider_surface("Red clay indoor") == ("Clay", True)
    assert tennis_daily.provider_surface(None) == (None, None)


def test_surface_sources_fail_closed_on_conflict():
    assert tennis_daily.merge_surface("Hard", "Hard") == "Hard"
    assert tennis_daily.merge_surface(None, "Clay") == "Clay"
    assert tennis_daily.merge_surface("Hard", "Clay") is None


def test_tennis_empty_state_uses_exact_next_scan_date():
    assert _next_tennis_scan_date(today_value="2030-01-02").isoformat() == "2030-01-03"


def test_duplicate_scan_backfills_fixture_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    first = shadow.store_prediction(
        "2030-01-02",
        "ATP",
        "Test Open",
        _Prediction(),
    )
    duplicate = shadow.store_prediction(
        "2030-01-02",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="espn-42",
        scheduled_start_utc="2030-01-02T12:00:00Z",
        fixture_source="ESPN",
    )
    rescheduled = shadow.store_prediction(
        "2030-01-03",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="espn-42",
        scheduled_start_utc="2030-01-03T13:00:00Z",
        fixture_source="ESPN",
    )

    assert first > 0
    assert duplicate == -1
    assert rescheduled == -1
    row = shadow.pending_predictions()[0]
    assert row["provider_event_id"] == "espn-42"
    assert row["match_date"] == "2030-01-03"
    assert row["scheduled_start_utc"] == "2030-01-03T13:00:00Z"
    assert row["fixture_source"] == "ESPN"


def test_espn_duplicate_cannot_rewrite_published_sofascore_identity(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    row_id = shadow.store_prediction(
        "2030-01-01",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="4101",
        scheduled_start_utc="2030-01-01T12:00:00Z",
        fixture_source="SofaScore",
    )
    as_of = datetime.now(timezone.utc) + timedelta(seconds=1)
    adapted = adapt_tennis_shadow(
        shadow.DB_PATH,
        as_of=as_of,
        window_end=datetime(2030, 1, 2, tzinfo=timezone.utc),
    )
    assert len(adapted) == 1
    run = RiskRunSnapshot(
        started_at=as_of,
        completed_at=as_of,
        status=RunStatus.COMPLETE,
        snapshots=(adapted[0].snapshot,),
        candidates=adapted[0].candidates,
    )
    risk_store = RiskBetStore(
        tmp_path / "riskobet.db",
        tmp_path / "riskobet_latest.json",
    )
    risk_store.append_run(run)
    risk_store.publish_latest(run.run_id)
    published = risk_store.read_latest()
    frozen_event_key = stable_event_key("tennis", "SofaScore", "4101")
    assert published["snapshots"][0]["event_key"] == frozen_event_key

    duplicate = shadow.store_prediction(
        "2030-01-01",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="espn-should-not-replace",
        scheduled_start_utc="2030-01-01T12:15:00Z",
        fixture_source="ESPN",
    )
    assert duplicate > 0 and duplicate != row_id
    rows = {row["id"]: row for row in shadow.pending_predictions()}
    assert len(rows) == 2
    row = rows[row_id]
    assert row["provider_event_id"] == "4101"
    assert row["fixture_source"] == "SofaScore"
    assert row["scheduled_start_utc"] == "2030-01-01T12:00:00Z"
    assert rows[duplicate]["provider_event_id"] == "espn-should-not-replace"
    assert rows[duplicate]["scheduled_start_utc"] == "2030-01-01T12:15:00Z"

    monkeypatch.setattr(
        tennis_daily,
        "fetch_results_sofascore",
        lambda date: [
            {
                "provider_event_id": "4101",
                "player_a": "Alpha",
                "player_b": "Beta",
                "winner": "Alpha",
                "winner_sets": 2,
                "loser_sets": 0,
                "termination": "normal",
                "result_observed_at": "2030-01-01T13:00:00Z",
            }
        ],
    )
    assert tennis_daily.auto_settle_completed(today="2030-01-02") == 1

    published_snapshot = published["snapshots"][0]
    published_candidates = [
        candidate
        for candidate in published["candidates"]
        if candidate["snapshot_id"] == published_snapshot["snapshot_id"]
    ]
    request = SettlementRequest(
        sport="tennis",
        event_key=published_snapshot["event_key"],
        event_label=published_snapshot["event_label"],
        starts_at=datetime.fromisoformat(published_snapshot["starts_at"]),
        snapshot_id=published_snapshot["snapshot_id"],
        factors=tuple(published_snapshot["factors"]),
        candidate_ids=tuple(
            candidate["candidate_id"] for candidate in published_candidates
        ),
    )
    loaded = tennis_result_loader(shadow.DB_PATH)(
        (request,),
        datetime(2030, 1, 1, 14, tzinfo=timezone.utc),
    )
    assert loaded.issues == ()
    assert len(loaded.results) == 1
    assert loaded.results[0].event_key == frozen_event_key
    assert loaded.results[0].result.winner is Selection.HOME


def test_shadow_schema_additively_migrates_result_bridge_columns(
    tmp_path,
    monkeypatch,
):
    db = tmp_path / "legacy-tennis.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE predictions (id INTEGER PRIMARY KEY, player_a TEXT, "
            "player_b TEXT, settled INTEGER)"
        )
        connection.execute(
            "INSERT INTO predictions VALUES (7, 'Legacy A', 'Legacy B', 1)"
        )
    monkeypatch.setattr(shadow, "DB_PATH", db)

    shadow.ensure_schema()

    with sqlite3.connect(db) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(predictions)")
        }
        legacy_row = connection.execute(
            "SELECT player_a, player_b, settled, termination, "
            "result_observed_at, player_a_sets, player_b_sets "
            "FROM predictions WHERE id=7"
        ).fetchone()
    assert {
        "termination",
        "result_observed_at",
        "player_a_sets",
        "player_b_sets",
    } <= columns
    assert legacy_row == ("Legacy A", "Legacy B", 1, None, None, None, None)


def test_shadow_settlement_validates_and_normalizes_result_evidence(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    row_id = shadow.store_prediction(
        "2030-01-01",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="espn-strict",
        scheduled_start_utc="2030-01-01T12:00:00Z",
        fixture_source="ESPN",
    )

    with pytest.raises(ValueError, match="include a timezone"):
        shadow.settle(
            row_id,
            "Alpha",
            result_observed_at="2030-01-01T13:00:00",
            player_a_sets=2,
            player_b_sets=1,
        )
    with pytest.raises(ValueError, match="provided together"):
        shadow.settle(
            row_id,
            "Alpha",
            result_observed_at="2030-01-01T13:00:00Z",
            player_a_sets=2,
        )
    with pytest.raises(ValueError, match="does not prove"):
        shadow.settle(
            row_id,
            "Alpha",
            result_observed_at="2030-01-01T13:00:00Z",
            player_a_sets=1,
            player_b_sets=2,
        )
    with pytest.raises(ValueError, match="cannot include"):
        shadow.settle(
            row_id,
            "Alpha",
            termination="walkover",
            result_observed_at="2030-01-01T13:00:00Z",
        )

    shadow.settle(
        row_id,
        "Alpha",
        result_observed_at="2030-01-01T15:05:00+02:00",
        player_a_sets=2,
        player_b_sets=1,
    )

    with sqlite3.connect(shadow.DB_PATH) as connection:
        stored = connection.execute(
            "SELECT termination, result_observed_at, "
            "player_a_sets, player_b_sets "
            "FROM predictions WHERE id=?",
            (row_id,),
        ).fetchone()
    assert stored == ("normal", "2030-01-01T13:05:00+00:00", 2, 1)
    with pytest.raises(ValueError, match="already settled"):
        shadow.settle(row_id, "Alpha")

    retirement_id = shadow.store_prediction(
        "2030-01-02",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="espn-retirement",
        scheduled_start_utc="2030-01-02T12:00:00Z",
        fixture_source="ESPN",
    )
    shadow.settle(
        retirement_id,
        "Beta",
        ret=True,
        ret_set=1,
        result_observed_at="2030-01-02T13:00:00Z",
    )
    with sqlite3.connect(shadow.DB_PATH) as connection:
        retirement = connection.execute(
            "SELECT termination, ret_flag, player_a_sets, player_b_sets "
            "FROM predictions WHERE id=?",
            (retirement_id,),
        ).fetchone()
    assert retirement == ("retirement", 1, None, None)


def test_new_model_version_is_not_hidden_by_legacy_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    first = shadow.store_prediction(
        "2030-01-02",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="espn-42",
        fixture_source="ESPN",
    )
    with shadow._connect() as conn:
        conn.execute(
            "UPDATE predictions SET model_version='legacy-model' WHERE id=?",
            (first,),
        )

    assert not shadow.already_stored("2030-01-02", "Alpha", "Beta")
    current = shadow.store_prediction(
        "2030-01-02",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="espn-42",
        fixture_source="ESPN",
    )

    assert current > 0
    assert current != first
    assert shadow.already_stored("2030-01-02", "Alpha", "Beta")
    assert len(shadow.pending_predictions()) == 2


def test_shadow_summary_reports_clv_and_brier(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    start = datetime.now(timezone.utc) + timedelta(minutes=30)
    row_id = shadow.store_prediction(
        start.date().isoformat(),
        "ATP",
        "Test Open",
        _RecommendedPrediction(),
        odds_a=2.20,
        odds_b=1.80,
        scheduled_start_utc=start.isoformat(),
    )
    shadow.record_entry_prices(row_id, 2.20, 1.80)
    captured = datetime.now(timezone.utc).timestamp()
    shadow.record_closing_prices(
        row_id,
        2.00,
        1.90,
        captured_utc=captured,
    )
    import pytest

    with pytest.raises(ValueError, match="already frozen"):
        shadow.record_closing_prices(
            row_id,
            2.05,
            1.85,
            captured_utc=captured,
        )
    shadow.settle(row_id, "Alpha")

    summary = shadow.summary()
    assert summary["recommended_bets"] == 1
    assert summary["clv_samples"] == 1
    assert summary["clv"] == 0.10
    assert summary["brier_samples"] == 1
    assert summary["brier"] == 0.16
    assert summary["benchmark_samples"] == 1
    assert summary["benchmark_model_brier"] == 0.16
    assert summary["benchmark_market_brier"] == 0.263


def test_shadow_summary_excludes_legacy_model_from_every_metric(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    start = datetime.now(timezone.utc) + timedelta(minutes=30)
    row_id = shadow.store_prediction(
        start.date().isoformat(),
        "ATP",
        "Test Open",
        _RecommendedPrediction(),
        odds_a=2.20,
        odds_b=1.80,
        scheduled_start_utc=start.isoformat(),
    )
    with shadow._connect() as conn:
        conn.execute(
            "UPDATE predictions SET model_version='legacy-model' WHERE id=?",
            (row_id,),
        )

    summary = shadow.summary()

    assert summary["predictions"] == 0
    assert summary["recommended_bets"] == 0
    assert summary["clv_samples"] == 0
    assert summary["brier_samples"] == 0
    assert summary["model_version"] == shadow.TENNIS_MODEL_VERSION


def test_sofascore_preferred_scan_writer_and_loader_normal_final(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    scheduled_payload = {
        "events": [
            _sofascore_event(
                3101,
                status_type="notstarted",
                status_description="Not started",
            )
        ]
    }
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response(scheduled_payload),
    )
    fixture = tennis_daily.fetch_fixtures_sofascore("2030-01-01")[0]
    row_id = shadow.store_prediction(
        fixture["match_date"],
        fixture["tour"],
        fixture["tournament"],
        _RecommendedPrediction(),
        odds_a=2.20,
        odds_b=1.80,
        provider_event_id=fixture["provider_event_id"],
        scheduled_start_utc=fixture["scheduled_start_utc"],
        fixture_source=fixture["fixture_source"],
    )
    side_id = shadow.store_side_bet(
        row_id,
        "over_2_5_sets",
        0.55,
        2.10,
        0.074,
    )
    terminal_payload = {
        "events": [
            _sofascore_event(
                3101,
                status_type="finished",
                status_description="Ended",
                winner_code=1,
                home_sets=2,
                away_sets=1,
            )
        ]
    }
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response(terminal_payload),
    )

    assert tennis_daily.auto_settle_completed(today="2030-01-02") == 1
    with sqlite3.connect(shadow.DB_PATH) as connection:
        row = connection.execute(
            "SELECT actual_winner, termination, result_observed_at, "
            "player_a_sets, player_b_sets FROM predictions WHERE id=?",
            (row_id,),
        ).fetchone()
    assert row[0] == "Alpha"
    assert row[1] == "normal"
    assert datetime.fromisoformat(row[2]).utcoffset() == timedelta(0)
    assert row[3:] == (2, 1)
    side_bet = shadow.side_bets_for([row_id])[0]
    assert side_bet["id"] == side_id
    assert side_bet["result"] == "2:1"
    assert side_bet["won"] == 1

    event_key = stable_event_key("tennis", "SofaScore", "3101")
    request = SettlementRequest(
        sport="tennis",
        event_key=event_key,
        event_label="Alpha vs Beta",
        starts_at=datetime(2030, 1, 1, 12, tzinfo=timezone.utc),
        snapshot_id="snapshot-sofascore-normal",
        factors=({"factor_key": f"tennis_prediction_id:{row_id}"},),
        candidate_ids=("candidate-sofascore-normal",),
    )
    loaded = tennis_result_loader(shadow.DB_PATH)(
        (request,),
        datetime(2030, 1, 1, 14, tzinfo=timezone.utc),
    )
    assert loaded.issues == ()
    assert len(loaded.results) == 1
    observation = loaded.results[0]
    assert observation.event_key == event_key
    assert observation.result.winner is Selection.HOME
    assert observation.result.home_sets == 2
    assert observation.result.away_sets == 1


@pytest.mark.parametrize(
    (
        "event_id",
        "status_type",
        "status_description",
        "termination",
        "expected_ret_flag",
        "expected_termination",
    ),
    (
        (
            3201,
            "retired",
            "Retired",
            "retirement",
            1,
            TennisTermination.RETIREMENT,
        ),
        (
            3202,
            "canceled",
            "Walkover",
            "walkover",
            0,
            TennisTermination.WALKOVER,
        ),
    ),
)
def test_sofascore_preferred_scan_abnormal_terminal_is_void_end_to_end(
    tmp_path,
    monkeypatch,
    event_id,
    status_type,
    status_description,
    termination,
    expected_ret_flag,
    expected_termination,
):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    scheduled = _sofascore_event(
        event_id,
        status_type="notstarted",
        status_description="Not started",
    )
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response({"events": [scheduled]}),
    )
    fixture = tennis_daily.fetch_fixtures_sofascore("2030-01-01")[0]
    row_id = shadow.store_prediction(
        fixture["match_date"],
        fixture["tour"],
        fixture["tournament"],
        _RecommendedPrediction(),
        odds_a=2.20,
        odds_b=1.80,
        provider_event_id=fixture["provider_event_id"],
        scheduled_start_utc=fixture["scheduled_start_utc"],
        fixture_source=fixture["fixture_source"],
    )
    side_id = shadow.store_side_bet(
        row_id,
        "over_2_5_sets",
        0.55,
        2.10,
        0.074,
    )
    terminal = _sofascore_event(
        event_id,
        status_type=status_type,
        status_description=status_description,
        winner_code=1,
        home_sets=1,
        away_sets=0,
    )
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response({"events": [terminal]}),
    )

    assert tennis_daily.auto_settle_completed(today="2030-01-02") == 1
    with sqlite3.connect(shadow.DB_PATH) as connection:
        row = connection.execute(
            "SELECT actual_winner, ret_flag, termination, result_observed_at, "
            "player_a_sets, player_b_sets, pnl FROM predictions WHERE id=?",
            (row_id,),
        ).fetchone()
    assert row[0] is None
    assert row[1] == expected_ret_flag
    assert row[2] == termination
    assert datetime.fromisoformat(row[3]).utcoffset() == timedelta(0)
    assert row[4:] == (None, None, 0.0)
    side_bet = shadow.side_bets_for([row_id])[0]
    assert side_bet["id"] == side_id
    assert side_bet["result"] == "ret"
    assert side_bet["won"] is None
    assert side_bet["pnl"] == 0.0

    event_key = stable_event_key("tennis", "SofaScore", str(event_id))
    request = SettlementRequest(
        sport="tennis",
        event_key=event_key,
        event_label="Alpha vs Beta",
        starts_at=datetime(2030, 1, 1, 12, tzinfo=timezone.utc),
        snapshot_id=f"snapshot-sofascore-{termination}",
        factors=({"factor_key": f"tennis_prediction_id:{row_id}"},),
        candidate_ids=(f"candidate-sofascore-{termination}",),
    )
    loaded = tennis_result_loader(shadow.DB_PATH)(
        (request,),
        datetime(2030, 1, 1, 14, tzinfo=timezone.utc),
    )
    assert loaded.issues == ()
    assert len(loaded.results) == 1
    observation = loaded.results[0]
    assert observation.result.termination is expected_termination
    assert observation.result.winner is None
    assert observation.result.home_sets is None
    assert observation.result.away_sets is None
    decision = settle_market(
        sport="tennis",
        market="match_winner",
        selection="away",
        result=observation.result,
    )
    assert decision.status is SettlementStatus.VOID


def test_auto_settlement_matches_event_and_settles_side_market(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    row_id = shadow.store_prediction(
        "2030-01-01",
        "ATP",
        "Test Open",
        _RecommendedPrediction(),
        odds_a=2.20,
        odds_b=1.80,
        provider_event_id="espn-42",
        scheduled_start_utc="2030-01-01T12:00:00Z",
        fixture_source="ESPN",
    )
    side_id = shadow.store_side_bet(
        row_id,
        "over_2_5_sets",
        0.55,
        2.10,
        0.074,
    )
    monkeypatch.setattr(
        tennis_daily,
        "fetch_results_espn",
        lambda date, tour: [
            {
                "provider_event_id": "espn-42",
                "player_a": "Alpha",
                "player_b": "Beta",
                "winner": "Alpha",
                "winner_sets": 2,
                "loser_sets": 1,
                "termination": "normal",
                "result_observed_at": "2030-01-01T15:05:00+02:00",
            }
        ],
    )

    assert tennis_daily.auto_settle_completed(today="2030-01-02") == 1
    assert shadow.pending_predictions() == []
    bet = shadow.side_bets_for([row_id])[0]
    assert bet["id"] == side_id
    assert bet["settled"] == 1
    assert bet["result"] == "2:1"
    assert bet["won"] == 1
    with sqlite3.connect(shadow.DB_PATH) as connection:
        result_row = connection.execute(
            "SELECT termination, result_observed_at, "
            "player_a_sets, player_b_sets "
            "FROM predictions WHERE id=?",
            (row_id,),
        ).fetchone()
    assert result_row == (
        "normal",
        "2030-01-01T13:05:00+00:00",
        2,
        1,
    )

    event_key = stable_event_key("tennis", "ESPN", "espn-42")
    request = SettlementRequest(
        sport="tennis",
        event_key=event_key,
        event_label="Alpha vs Beta",
        starts_at=datetime(2030, 1, 1, 12, tzinfo=timezone.utc),
        snapshot_id="snapshot-tennis-writer",
        factors=({"factor_key": f"tennis_prediction_id:{row_id}"},),
        candidate_ids=("candidate-tennis-writer",),
    )
    loaded = tennis_result_loader(shadow.DB_PATH)(
        (request,),
        datetime(2030, 1, 1, 14, tzinfo=timezone.utc),
    )
    assert loaded.issues == ()
    assert len(loaded.results) == 1
    observation = loaded.results[0]
    assert observation.event_key == event_key
    assert observation.observed_at == datetime(
        2030, 1, 1, 13, 5, tzinfo=timezone.utc
    )
    assert observation.result.winner is Selection.HOME
    assert observation.result.home_sets == 2
    assert observation.result.away_sets == 1


@pytest.mark.parametrize(
    ("termination", "expected_ret_flag", "expected_termination"),
    (
        ("retirement", 1, TennisTermination.RETIREMENT),
        ("walkover", 0, TennisTermination.WALKOVER),
    ),
)
def test_auto_abnormal_terminal_writer_loader_and_market_are_void(
    tmp_path,
    monkeypatch,
    termination,
    expected_ret_flag,
    expected_termination,
):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    provider_id = f"espn-{termination}"
    row_id = shadow.store_prediction(
        "2030-01-01",
        "ATP",
        "Test Open",
        _RecommendedPrediction(),
        odds_a=2.20,
        odds_b=1.80,
        provider_event_id=provider_id,
        scheduled_start_utc="2030-01-01T12:00:00Z",
        fixture_source="ESPN",
    )
    side_id = shadow.store_side_bet(
        row_id,
        "over_2_5_sets",
        0.55,
        2.10,
        0.074,
    )
    monkeypatch.setattr(
        tennis_daily,
        "fetch_results_espn",
        lambda date, tour: [
            {
                "provider_event_id": provider_id,
                "player_a": "Alpha",
                "player_b": "Beta",
                "winner": None,
                "winner_sets": None,
                "loser_sets": None,
                "termination": termination,
                "result_observed_at": "2030-01-01T13:05:00Z",
            }
        ],
    )

    assert tennis_daily.auto_settle_completed(today="2030-01-02") == 1
    with sqlite3.connect(shadow.DB_PATH) as connection:
        result_row = connection.execute(
            "SELECT actual_winner, ret_flag, termination, result_observed_at, "
            "player_a_sets, player_b_sets, pnl FROM predictions WHERE id=?",
            (row_id,),
        ).fetchone()
    assert result_row == (
        None,
        expected_ret_flag,
        termination,
        "2030-01-01T13:05:00+00:00",
        None,
        None,
        0.0,
    )
    side_bet = shadow.side_bets_for([row_id])[0]
    assert side_bet["id"] == side_id
    assert side_bet["settled"] == 1
    assert side_bet["result"] == "ret"
    assert side_bet["won"] is None
    assert side_bet["pnl"] == 0.0

    event_key = stable_event_key("tennis", "ESPN", provider_id)
    request = SettlementRequest(
        sport="tennis",
        event_key=event_key,
        event_label="Alpha vs Beta",
        starts_at=datetime(2030, 1, 1, 12, tzinfo=timezone.utc),
        snapshot_id=f"snapshot-{termination}",
        factors=({"factor_key": f"tennis_prediction_id:{row_id}"},),
        candidate_ids=(f"candidate-{termination}",),
    )
    loaded = tennis_result_loader(shadow.DB_PATH)(
        (request,),
        datetime(2030, 1, 1, 14, tzinfo=timezone.utc),
    )
    assert loaded.issues == ()
    assert len(loaded.results) == 1
    observation = loaded.results[0]
    assert observation.result.termination is expected_termination
    assert observation.result.winner is None
    assert observation.result.home_sets is None
    assert observation.result.away_sets is None
    decision = settle_market(
        sport="tennis",
        market="match_winner",
        selection="away",
        result=observation.result,
    )
    assert decision.status is SettlementStatus.VOID


@pytest.mark.parametrize(
    ("result_event_id", "result_player_b"),
    (
        ("espn-collision", "Gamma"),
        ("espn-other-event", "Beta"),
    ),
)
def test_auto_settlement_requires_exact_event_and_participants(
    tmp_path,
    monkeypatch,
    result_event_id,
    result_player_b,
):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    row_id = shadow.store_prediction(
        "2030-01-01",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="espn-collision",
        scheduled_start_utc="2030-01-01T12:00:00Z",
        fixture_source="ESPN",
    )
    monkeypatch.setattr(
        tennis_daily,
        "fetch_results_espn",
        lambda date, tour: [
            {
                "provider_event_id": result_event_id,
                "player_a": "Alpha",
                "player_b": result_player_b,
                "winner": "Alpha",
                "winner_sets": 2,
                "loser_sets": 0,
                "termination": "normal",
                "result_observed_at": "2030-01-01T13:00:00Z",
            }
        ],
    )

    assert tennis_daily.auto_settle_completed(today="2030-01-02") == 0
    assert [row["id"] for row in shadow.pending_predictions()] == [row_id]
    with sqlite3.connect(shadow.DB_PATH) as connection:
        result = connection.execute(
            "SELECT settled, termination, result_observed_at "
            "FROM predictions WHERE id=?",
            (row_id,),
        ).fetchone()
    assert result == (0, None, None)


@pytest.mark.parametrize(
    ("result_event_id", "result_player_b"),
    (
        ("sofa-frozen", "Gamma"),
        ("sofa-other-event", "Beta"),
    ),
)
def test_sofascore_auto_settlement_requires_exact_event_and_participants(
    tmp_path,
    monkeypatch,
    result_event_id,
    result_player_b,
):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    row_id = shadow.store_prediction(
        "2030-01-01",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="sofa-frozen",
        scheduled_start_utc="2030-01-01T12:00:00Z",
        fixture_source="SofaScore",
    )
    monkeypatch.setattr(
        tennis_daily,
        "fetch_results_sofascore",
        lambda date: [
            {
                "provider_event_id": result_event_id,
                "player_a": "Alpha",
                "player_b": result_player_b,
                "winner": "Alpha",
                "winner_sets": 2,
                "loser_sets": 0,
                "termination": "normal",
                "result_observed_at": "2030-01-01T13:00:00Z",
            }
        ],
    )

    assert tennis_daily.auto_settle_completed(today="2030-01-02") == 0
    assert [row["id"] for row in shadow.pending_predictions()] == [row_id]


def test_sofascore_defaulted_exact_event_stays_open(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    row_id = shadow.store_prediction(
        "2030-01-01",
        "ATP",
        "Test Open",
        _Prediction(),
        provider_event_id="3401",
        scheduled_start_utc="2030-01-01T12:00:00Z",
        fixture_source="SofaScore",
    )
    terminal = _sofascore_event(
        3401,
        status_type="canceled",
        status_description="Defaulted",
    )
    monkeypatch.setattr(
        tennis_daily.requests,
        "get",
        lambda *args, **kwargs: _Response({"events": [terminal]}),
    )

    assert tennis_daily.auto_settle_completed(today="2030-01-02") == 0
    assert [row["id"] for row in shadow.pending_predictions()] == [row_id]
    with sqlite3.connect(shadow.DB_PATH) as connection:
        result = connection.execute(
            "SELECT settled, termination, result_observed_at "
            "FROM predictions WHERE id=?",
            (row_id,),
        ).fetchone()
    assert result == (0, None, None)


def test_closing_capture_rejects_hindsight_and_early_prices(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "tennis.db")
    row_id = shadow.store_prediction(
        "2030-01-02",
        "ATP",
        "Test Open",
        _RecommendedPrediction(),
        odds_a=2.20,
        odds_b=1.80,
        scheduled_start_utc="2030-01-02T12:00:00Z",
    )
    too_early = datetime(2030, 1, 2, 10, 59, tzinfo=timezone.utc).timestamp()
    after_start = datetime(2030, 1, 2, 12, 1, tzinfo=timezone.utc).timestamp()

    import pytest

    with pytest.raises(ValueError, match="final 60 minutes"):
        shadow.record_closing_prices(
            row_id,
            2.00,
            1.90,
            captured_utc=too_early,
        )
    with pytest.raises(ValueError, match="after scheduled start"):
        shadow.record_closing_prices(
            row_id,
            2.00,
            1.90,
            captured_utc=after_start,
        )
    with pytest.raises(ValueError, match="greater than"):
        shadow.record_closing_prices(
            row_id,
            float("nan"),
            1.90,
            captured_utc=after_start,
        )
