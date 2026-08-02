from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts import tennis_daily
from tennis import shadow


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


def test_espn_results_accept_only_complete_normal_finals(monkeypatch):
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
    payload = {
        "events": [
            {
                "groupings": [
                    {
                        "grouping": {"slug": "mens-singles"},
                        "competitions": [normal, retired],
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
    assert len(results) == 1
    assert results[0]["provider_event_id"] == "normal-1"
    assert results[0]["winner"] == "Alpha"
    assert results[0]["winner_sets"] == 2
    assert results[0]["loser_sets"] == 1


def test_default_scan_date_uses_zurich_calendar():
    now = datetime(2030, 1, 1, 23, 30, tzinfo=timezone.utc)
    assert tennis_daily._default_scan_date(now) == "2030-01-03"


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
