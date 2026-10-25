"""Published-candidate record in the shadow (Gesamtaudit 25.10.2026, Massnahme 2).

The legacy ledger logs the shadow's own pick with a Bet365 quote; the app
publishes the statistically released rows in ledger order, also unpriced.
``shadow_published`` keeps exactly what was published (public tips and the
15K list), its price status and, when playable, the opening odds, and settles
the goal markets from the full-time score. Corners and cards stay unsettled.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import shadow_clv_automation as shadow


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    db_path = tmp_path / "shadow.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE shadow_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    monkeypatch.setattr(shadow, "SHADOW_DB", db_path)
    shadow._connect().close()  # creates shadow_published like the runner does
    shadow.errors.clear()
    return SimpleNamespace(db_path=db_path, now=datetime(2030, 1, 1, 9, 30, tzinfo=timezone.utc),
                           today=date(2030, 1, 1))


def _row(candidate_id, fixture_id, market_key, *, status="UNPRICED", odds=None, source="football_challenge",
         kickoff="2030-01-01T15:00:00+00:00"):
    row = {
        "candidate_id": candidate_id, "fixture_id": fixture_id, "market_key": market_key, "selection": "x",
        "probability": 0.61, "reference_price_status": status, "model_version": "challenge:v1",
        "policy_version": "p1", "scheduled_start": kickoff, "source": source,
    }
    if odds is not None:
        row.update(reference_quote_executable_odds=odds, reference_quote_bookmaker="Bet365")
    return row


def _document(path, public, challenge, *, day="2030-01-01"):
    path.write_text(json.dumps({
        "target_search_date": day, "generated_at": "2030-01-01T02:35:00+00:00",
        "candidates": public, "challenge_release_candidates": challenge,
    }), encoding="utf-8")
    return path


def _published(db_path):
    with sqlite3.connect(db_path) as connection:
        return connection.execute(
            "SELECT candidate_id, kind, price_status, opening_odds, kickoff, result FROM shadow_published "
            "ORDER BY kind, candidate_id").fetchall()


def test_record_keeps_the_published_rows_with_their_price_status_once(ledger, tmp_path):
    path = _document(
        tmp_path / "wettfinder_latest.json",
        [_row("1:BTTS_YES", 1, "BTTS_YES", status="PLAYABLE", odds=1.85), _row("2:RESULT_HOME", 2, "RESULT_HOME")],
        [_row("3:CORNERS_OVER_9_5", 3, "CORNERS_OVER_9_5", status="PLAYABLE", odds=1.9,
              kickoff="2030-01-01T16:00:00+01:00"),
         _row("t:1", 9, "MATCH_WINNER", source="tennis_shadow"),  # football only
         _row("", 4, "BTTS_YES"), _row("5:BTTS_YES", 0, "BTTS_YES")],  # no identity, no fixture
    )
    assert shadow.step_record_published(ledger.now, ledger.today, document_path=path) == {
        "seen": 3, "recorded": 3, "recorded_with_quote": 2}
    assert _published(ledger.db_path) == [
        ("3:CORNERS_OVER_9_5", "challenge_15k", "PLAYABLE", 1.9, "2030-01-01T15:00:00+00:00", None),
        ("1:BTTS_YES", "public_tip", "PLAYABLE", 1.85, "2030-01-01T15:00:00+00:00", None),
        ("2:RESULT_HOME", "public_tip", "UNPRICED", None, "2030-01-01T15:00:00+00:00", None),
    ]
    # First sighting wins: a quote found later on the same published row does not rewrite the record.
    _document(path, [_row("2:RESULT_HOME", 2, "RESULT_HOME", status="PLAYABLE", odds=2.1)], [])
    assert shadow.step_record_published(ledger.now + timedelta(hours=3), ledger.today, document_path=path) == {
        "seen": 1, "recorded": 0, "recorded_with_quote": 0}
    assert _published(ledger.db_path)[2][2:4] == ("UNPRICED", None)
    with sqlite3.connect(ledger.db_path) as connection:
        stored = connection.execute(
            "SELECT model_probability, bookmaker, model_version, policy_version, document_generated_at, first_seen_at "
            "FROM shadow_published WHERE candidate_id = '1:BTTS_YES'").fetchone()
    assert stored == (0.61, "Bet365", "challenge:v1", "p1", "2030-01-01T02:35:00+00:00", "2030-01-01T09:30:00+00:00")


def test_record_ignores_a_document_of_another_day_or_a_missing_file(ledger, tmp_path):
    nothing = {"seen": 0, "recorded": 0, "recorded_with_quote": 0}
    path = _document(tmp_path / "wettfinder_latest.json", [_row("1:BTTS_YES", 1, "BTTS_YES")], [], day="2029-12-31")
    assert shadow.step_record_published(ledger.now, ledger.today, document_path=path) == nothing
    assert shadow.step_record_published(ledger.now, ledger.today, document_path=tmp_path / "missing.json") == nothing
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert shadow.step_record_published(ledger.now, ledger.today, document_path=tmp_path / "broken.json") == nothing
    assert _published(ledger.db_path) == []


class _Provider:
    def __init__(self, fixtures):
        self.fixtures = fixtures
        self.requested = []

    def fixtures_by_ids(self, ids):
        self.requested.append(list(ids))
        return [fixture for fixture in self.fixtures if fixture["fixture"]["id"] in ids]


def _fixture(fixture_id, home, away, status="FT"):
    return {"fixture": {"id": fixture_id, "status": {"short": status}}, "goals": {"home": home, "away": away}}


def test_settlement_uses_the_full_time_score_for_goal_markets_only(ledger, tmp_path):
    path = _document(
        tmp_path / "wettfinder_latest.json",
        [_row("1:BTTS_YES", 1, "BTTS_YES", status="PLAYABLE", odds=1.85), _row("2:RESULT_HOME", 2, "RESULT_HOME"),
         _row("4:TOTAL_OVER_2_5", 4, "TOTAL_OVER_2_5")],
        [_row("3:CORNERS_OVER_9_5", 3, "CORNERS_OVER_9_5", status="PLAYABLE", odds=1.9),
         _row("1:BTTS_YES", 1, "BTTS_YES", status="PLAYABLE", odds=1.85)],
    )
    shadow.step_record_published(ledger.now, ledger.today, document_path=path)
    provider = _Provider([_fixture(1, 1, 1), _fixture(2, 1, 1), _fixture(4, 2, 1, status="2H")])
    later = datetime(2030, 1, 1, 18, 0, tzinfo=timezone.utc)  # grace period after the 15:00 kick-offs is over
    assert shadow.step_settle_published(provider, later) == 3
    assert provider.requested == [[1, 2, 4]]  # the corner market is never queried
    assert _published(ledger.db_path) == [
        ("1:BTTS_YES", "challenge_15k", "PLAYABLE", 1.85, "2030-01-01T15:00:00+00:00", "Won"),
        ("3:CORNERS_OVER_9_5", "challenge_15k", "PLAYABLE", 1.9, "2030-01-01T15:00:00+00:00", None),
        ("1:BTTS_YES", "public_tip", "PLAYABLE", 1.85, "2030-01-01T15:00:00+00:00", "Won"),
        ("2:RESULT_HOME", "public_tip", "UNPRICED", None, "2030-01-01T15:00:00+00:00", "Lost"),
        ("4:TOTAL_OVER_2_5", "public_tip", "UNPRICED", None, "2030-01-01T15:00:00+00:00", None),
    ]
    assert shadow.step_settle_published(provider, later) == 0 and provider.requested[-1] == [4]  # still running
    assert shadow.step_settle_published(provider, datetime(2030, 1, 1, 16, 30, tzinfo=timezone.utc)) == 0
    assert len(provider.requested) == 2  # inside the grace period nothing is queried
    assert shadow.errors == []
    statistics = shadow._published_statistics()
    assert statistics["kinds"]["public_tip"] == {
        "recorded": 3, "with_quote": 1, "settled": 2, "won": 1, "lost": 1, "avg_opening_odds": 1.85, "hit_rate": 0.5}
    assert statistics["kinds"]["challenge_15k"] == {
        "recorded": 2, "with_quote": 2, "settled": 1, "won": 1, "lost": 0, "avg_opening_odds": 1.875, "hit_rate": 1.0}
    assert statistics["minimum_settled"] == shadow.SHADOW_REVIEW_MIN_CLV_BETS


def test_settlement_without_open_rows_never_calls_the_provider(ledger):
    provider = _Provider([])
    assert shadow.step_settle_published(provider, ledger.now) == 0 and provider.requested == []
    assert shadow._published_statistics() == {"kinds": {}, "minimum_settled": shadow.SHADOW_REVIEW_MIN_CLV_BETS}
