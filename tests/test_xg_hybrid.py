"""Tests für das xG-Hybrid-Modul (challenge_engine) und den xG-Backfill."""

from __future__ import annotations

import sys
import unittest
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from challenge_engine import (  # noqa: E402
    XG_BLEND_WEIGHT,
    XG_MIN_COVERAGE,
    _fixture_model,
    _fixture_xg,
    _hybrid_strength,
    _shrunk_mean,
    _team_observations,
    build_fixture_candidates,
)
from xg_backfill import (  # noqa: E402
    annotate_history,
    cached_stats,
    cached_xg,
    fetch_missing_xg,
    season_fixture_index,
)

BASE = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _row(fixture_id, day, home_id, away_id, home_goals, away_goals, xg=None,
         home_name=None, away_name=None):
    fixture = {
        "fixture": {
            "id": fixture_id,
            "date": (BASE + timedelta(days=day)).isoformat(),
        },
        "league": {"id": 78, "season": 2025},
        "teams": {
            "home": {"id": home_id, "name": home_name or f"Team {home_id}"},
            "away": {"id": away_id, "name": away_name or f"Team {away_id}"},
        },
        "goals": {"home": home_goals, "away": away_goals},
        "challenge_stats": {},
    }
    if xg is not None:
        fixture["challenge_stats"]["xg_home"] = xg[0]
        fixture["challenge_stats"]["xg_away"] = xg[1]
    return fixture


def _league_history(days=40, xg_for_team_1=None, xg_default=None):
    """40 Spieltage à 4 Spiele; Team 1 heim vs. Team 3, Team 2 auswärts bei Team 4."""
    history = []
    fixture_id = 1
    for day in range(days):
        pairings = ((1, 3), (4, 2), (5, 6), (7, 8))
        for home_id, away_id in pairings:
            xg = xg_default
            if home_id == 1 and xg_for_team_1 is not None:
                xg = xg_for_team_1(day)
            history.append(_row(fixture_id, day, home_id, away_id, 2, 1, xg=xg))
            fixture_id += 1
    return history


def _kickoff_fixture():
    return _row(99999, 45, 1, 2, 0, 0)


class FixtureXgParsingTest(unittest.TestCase):
    def test_reads_valid_pair(self):
        fixture = _row(1, 0, 1, 2, 2, 1, xg=("2.35", 0.9))
        self.assertEqual(_fixture_xg(fixture), (2.35, 0.9))

    def test_rejects_missing_or_invalid(self):
        self.assertIsNone(_fixture_xg(_row(1, 0, 1, 2, 2, 1)))
        self.assertIsNone(_fixture_xg(_row(1, 0, 1, 2, 2, 1, xg=(None, 1.0))))
        self.assertIsNone(_fixture_xg(_row(1, 0, 1, 2, 2, 1, xg=(2.0, -0.5))))
        self.assertIsNone(_fixture_xg(_row(1, 0, 1, 2, 2, 1, xg=(13.0, 1.0))))
        self.assertIsNone(_fixture_xg(_row(1, 0, 1, 2, 2, 1, xg=("abc", 1.0))))
        self.assertIsNone(_fixture_xg(_row(1, 0, 1, 2, 2, 1, xg=(True, 1.0))))


class TeamObservationsXgTest(unittest.TestCase):
    def test_xg_from_team_perspective(self):
        history = [
            _row(1, 0, 1, 2, 3, 0, xg=(2.8, 0.4)),
            _row(2, 1, 3, 1, 1, 1, xg=(1.2, 1.9)),
        ]
        rows = _team_observations(history, 1, BASE + timedelta(days=5), venue=None, limit=6)
        self.assertEqual(len(rows), 2)
        # Neuestes zuerst: Spiel 2 (Team 1 auswärts) -> xG 1.9 / xGA 1.2
        self.assertEqual(rows[0][0:3], (1.0, 1.0, rows[0][2]))
        self.assertEqual((rows[0][3], rows[0][4]), (1.9, 1.2))
        # Spiel 1 (Team 1 heim) -> xG 2.8 / xGA 0.4
        self.assertEqual((rows[1][3], rows[1][4]), (2.8, 0.4))

    def test_respects_kickoff_cutoff(self):
        history = [_row(1, 10, 1, 2, 2, 0, xg=(2.0, 0.5))]
        rows = _team_observations(history, 1, BASE + timedelta(days=5), venue=None, limit=6)
        self.assertEqual(rows, [])


class HybridStrengthTest(unittest.TestCase):
    def _rows(self, xg_share):
        rows = []
        for index in range(10):
            xg = (3.0, 0.5) if index < round(10 * xg_share) else None
            rows.append((2.0, 1.0, BASE + timedelta(days=index),
                         xg[0] if xg else None, xg[1] if xg else None))
        return rows

    def test_full_coverage_blends_60_40(self):
        rows = self._rows(1.0)
        value, coverage = _hybrid_strength(rows, scored=True, prior_mean=1.5)
        goals_part = _shrunk_mean([2.0] * 10, 1.5)
        xg_part = _shrunk_mean([3.0] * 10, 1.5)
        self.assertAlmostEqual(
            value, XG_BLEND_WEIGHT * xg_part + (1 - XG_BLEND_WEIGHT) * goals_part
        )
        self.assertEqual(coverage, 1.0)
        self.assertGreater(value, goals_part)

    def test_low_coverage_falls_back_to_goals(self):
        rows = self._rows(XG_MIN_COVERAGE - 0.1)
        value, _ = _hybrid_strength(rows, scored=True, prior_mean=1.5)
        self.assertAlmostEqual(value, _shrunk_mean([2.0] * 10, 1.5))

    def test_empty_rows_use_prior(self):
        value, coverage = _hybrid_strength([], scored=True, prior_mean=1.4)
        self.assertEqual((value, coverage), (1.4, 0.0))


class FixtureModelXgTest(unittest.TestCase):
    def test_xg_shifts_lambdas(self):
        # Team 1 schießt 2 Tore/Heimspiel, spielt aber 3.5 xG -> Angriff stärker.
        history = _league_history(xg_for_team_1=lambda day: (3.5, 1.0))
        kickoff = _kickoff_fixture()
        with_xg = _fixture_model(kickoff, history)
        without_xg = _fixture_model(
            kickoff, [{**fixture, "challenge_stats": {}} for fixture in history]
        )
        self.assertIsNotNone(with_xg)
        self.assertIsNotNone(without_xg)
        self.assertGreater(with_xg["active_lambdas"][0], without_xg["active_lambdas"][0])
        # xG nur bei Team-1-Heimspielen -> Abdeckung über alle Fenster gemischt.
        self.assertEqual(with_xg["xg_coverage"], 0.0)
        self.assertEqual(without_xg["xg_coverage"], 0.0)
        # Auswärtsteam (kein xG-Eingriff) bleibt identisch.
        self.assertAlmostEqual(
            with_xg["active_lambdas"][1], without_xg["active_lambdas"][1], places=9
        )

    def test_full_coverage_reports_one(self):
        history = _league_history(
            xg_for_team_1=lambda day: (3.5, 1.0), xg_default=(1.5, 1.1)
        )
        model = _fixture_model(_kickoff_fixture(), history)
        self.assertIsNotNone(model)
        self.assertEqual(model["xg_coverage"], 1.0)

    def test_partial_coverage_below_threshold_ignored(self):
        history = _league_history()
        for fixture in history:
            day = (fixture["fixture"]["id"] - 1) // 4
            if fixture["teams"]["home"]["id"] == 1 and day % 4 == 0:  # 25 % Abdeckung
                fixture["challenge_stats"] = {"xg_home": 3.5, "xg_away": 1.0}
        kickoff = _kickoff_fixture()
        with_sparse = _fixture_model(kickoff, history)
        plain = _fixture_model(
            kickoff, [{**fixture, "challenge_stats": {}} for fixture in history]
        )
        self.assertAlmostEqual(
            with_sparse["active_lambdas"][0], plain["active_lambdas"][0], places=9
        )


class FakeProvider:
    """Fake fetch_list: liefert Saisonindex + statistics aus dem Speicher."""

    def __init__(self, index, statistics, stats_without_xg=()):
        self.index = index
        self.statistics = statistics
        self.stats_without_xg = set(stats_without_xg)
        self.calls = []

    def __call__(self, path, params, label):
        self.calls.append((path, dict(params)))
        if path == "fixtures":
            return self.index
        if path == "fixtures/statistics":
            fixture_id = params["fixture"]
            if fixture_id in self.stats_without_xg:
                return [
                    {"team": {"id": 1}, "statistics": [{"type": "Ball Possession", "value": 50}]},
                    {"team": {"id": 2}, "statistics": [{"type": "Ball Possession", "value": 50}]},
                ]
            return self.statistics.get(fixture_id)
        return None


def _index_entry(fixture_id, day, home_id, away_id, home_name, away_name):
    """Rohdaten im API-Shape (so kommt es vom fixtures-Endpunkt)."""
    return {
        "fixture": {
            "id": fixture_id,
            "date": (BASE + timedelta(days=day, hours=15)).isoformat(),
        },
        "teams": {
            "home": {"id": home_id, "name": home_name},
            "away": {"id": away_id, "name": away_name},
        },
    }


def _stats_payload(home_id, away_id, xg_home, xg_away):
    return [
        {"team": {"id": away_id}, "statistics": [{"type": "expected_goals", "value": str(xg_away)}]},
        {"team": {"id": home_id}, "statistics": [{"type": "expected_goals", "value": str(xg_home)}]},
    ]


def _full_stats_payload(home_id, away_id):
    entries = [
        ("expected_goals", "1.75", "0.90"),
        ("Corner Kicks", "6", "3"),
        ("Yellow Cards", "2", "4"),
    ]
    home_stats = [{"type": kind, "value": hv} for kind, hv, _ in entries]
    away_stats = [{"type": kind, "value": av} for kind, _, av in entries]
    return [
        {"team": {"id": away_id}, "statistics": away_stats},
        {"team": {"id": home_id}, "statistics": home_stats},
    ]


class CountStatsExtractionTest(unittest.TestCase):
    def test_extracts_corners_and_yellow(self):
        import tempfile

        from xg_backfill import _extract_fixture_stats

        extracted = _extract_fixture_stats(_full_stats_payload(11, 12), 11, 12)
        self.assertEqual(extracted["xg"], (1.75, 0.90))
        self.assertEqual(extracted["corners"], (6, 3))
        self.assertEqual(extracted["yellow"], (2, 4))

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [_index_entry(601, 0, 11, 12, "VfL Wolfsburg", "FC Augsburg")]
            provider = FakeProvider(index, {601: _full_stats_payload(11, 12)})
            history = [_row(601, 0, 11, 12, 1, 2)]
            result = annotate_history(history, 78, 2025, provider, db, max_new_calls=5)
            stats = history[0]["challenge_stats"]
            self.assertEqual(result["annotated"], 1)
            self.assertEqual(stats["corners_home"], 6)
            self.assertEqual(stats["corners_away"], 3)
            self.assertEqual(stats["yellow_cards_home"], 2)
            self.assertEqual(stats["yellow_cards_away"], 4)

    def test_existing_csv_values_are_not_overwritten(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [_index_entry(602, 0, 11, 12, "VfL Wolfsburg", "FC Augsburg")]
            provider = FakeProvider(index, {602: _full_stats_payload(11, 12)})
            history = [_row(602, 0, 11, 12, 1, 2)]
            history[0]["challenge_stats"] = {"corners_home": 9, "corners_away": 1}
            annotate_history(history, 78, 2025, provider, db, max_new_calls=5)
            stats = history[0]["challenge_stats"]
            self.assertEqual((stats["corners_home"], stats["corners_away"]), (9, 1))
            self.assertEqual(stats["xg_home"], 1.75)
            self.assertEqual(stats["yellow_cards_away"], 4)


class XgBackfillTest(unittest.TestCase):
    def test_annotate_csv_rows_via_name_mapping(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [_index_entry(501, 0, 11, 12, "VfL Wolfsburg", "FC Augsburg")]
            provider = FakeProvider(index, {501: _stats_payload(11, 12, 2.1, 0.8)})
            history = [
                _row(-777, 0, -11, -12, 2, 1, home_name="Wolfsburg", away_name="Augsburg")
            ]
            result = annotate_history(history, 78, 2025, provider, db, max_new_calls=5)
            self.assertEqual(result["annotated"], 1)
            self.assertEqual(result["fetched"], 1)
            self.assertEqual(history[0]["challenge_stats"]["xg_home"], 2.1)
            self.assertEqual(history[0]["challenge_stats"]["xg_away"], 0.8)
            self.assertEqual(cached_xg(db)[501], (2.1, 0.8))

    def test_api_rows_use_direct_fixture_id(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [_index_entry(601, 0, 11, 12, "VfL Wolfsburg", "FC Augsburg")]
            provider = FakeProvider(index, {601: _stats_payload(11, 12, 1.4, 1.9)})
            history = [_row(601, 0, 11, 12, 1, 2)]
            result = annotate_history(history, 78, 2025, provider, db, max_new_calls=5)
            self.assertEqual(result["annotated"], 1)
            self.assertEqual(history[0]["challenge_stats"]["xg_away"], 1.9)

    def test_max_new_calls_is_respected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [
                _index_entry(700 + day, day, 11, 12, "VfL Wolfsburg", "FC Augsburg")
                for day in range(6)
            ]
            statistics = {
                700 + day: _stats_payload(11, 12, 1.5, 1.0) for day in range(6)
            }
            provider = FakeProvider(index, statistics)
            history = [
                _row(-900 - day, day, -11, -12, 1, 1,
                     home_name="Wolfsburg", away_name="Augsburg")
                for day in range(6)
            ]
            result = annotate_history(history, 78, 2025, provider, db, max_new_calls=2)
            stats_calls = [c for c in provider.calls if c[0] == "fixtures/statistics"]
            self.assertEqual(len(stats_calls), 2)
            self.assertEqual(result["fetched"], 2)
            self.assertEqual(result["annotated"], 2)

    def test_missing_xg_is_marked_and_not_refetched(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [
                {
                    "id": 801,
                    "date": BASE.isoformat(),
                    "home_id": 11,
                    "away_id": 12,
                    "home_name": "VfL Wolfsburg",
                    "away_name": "FC Augsburg",
                }
            ]
            provider = FakeProvider([], {}, stats_without_xg={801})
            stats = fetch_missing_xg(index, provider, db, max_calls=5, pause_seconds=0)
            self.assertEqual(stats["unavailable"], 1)
            self.assertEqual(cached_xg(db), {})
            provider.calls.clear()
            stats = fetch_missing_xg(index, provider, db, max_calls=5, pause_seconds=0)
            self.assertEqual(stats["unavailable"], 0)
            self.assertEqual(provider.calls, [])

    def test_stale_missing_marker_is_retried(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [{
                "id": 802,
                "date": BASE.isoformat(),
                "home_id": 11,
                "away_id": 12,
                "home_name": "VfL Wolfsburg",
                "away_name": "FC Augsburg",
            }]
            provider = FakeProvider([], {}, stats_without_xg={802})
            fetch_missing_xg(index, provider, db, max_calls=5, pause_seconds=0)
            connection = sqlite3.connect(db)
            try:
                connection.execute(
                    "UPDATE xg_missing SET fetched_at='2000-01-01T00:00:00+00:00'"
                )
                connection.commit()
            finally:
                connection.close()
            provider.stats_without_xg.clear()
            provider.statistics[802] = _full_stats_payload(11, 12)
            provider.calls.clear()

            stats = fetch_missing_xg(
                index,
                provider,
                db,
                max_calls=5,
                pause_seconds=0,
            )

            self.assertEqual(stats["fetched"], 1)
            self.assertEqual(cached_xg(db)[802], (1.75, 0.90))
            self.assertEqual(len(provider.calls), 1)

    def test_stale_partial_row_is_retried_without_losing_existing_xg(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [{
                "id": 803,
                "date": BASE.isoformat(),
                "home_id": 11,
                "away_id": 12,
                "home_name": "VfL Wolfsburg",
                "away_name": "FC Augsburg",
            }]
            provider = FakeProvider([], {803: _stats_payload(11, 12, 1.4, 0.8)})
            fetch_missing_xg(index, provider, db, max_calls=5, pause_seconds=0)
            connection = sqlite3.connect(db)
            try:
                connection.execute(
                    "UPDATE xg_values SET fetched_at='2000-01-01T00:00:00+00:00'"
                )
                connection.commit()
            finally:
                connection.close()
            full = _full_stats_payload(11, 12)
            for block in full:
                block["statistics"] = [
                    item
                    for item in block["statistics"]
                    if item["type"] != "expected_goals"
                ]
            provider.statistics[803] = full
            provider.calls.clear()

            stats = fetch_missing_xg(
                index,
                provider,
                db,
                max_calls=5,
                pause_seconds=0,
            )

            self.assertEqual(stats["fetched"], 1)
            combined = cached_stats(db)[803]
            self.assertEqual(combined["xg"], (1.4, 0.8))
            self.assertEqual(combined["corners"], (6.0, 3.0))
            self.assertEqual(combined["yellow"], (2.0, 4.0))

    def test_season_index_is_cached(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            index = [_index_entry(901, 0, 11, 12, "VfL Wolfsburg", "FC Augsburg")]
            provider = FakeProvider(index, {})
            first = season_fixture_index(78, 2025, provider, db)
            second = season_fixture_index(78, 2025, provider, db)
            self.assertEqual(first, second)
            fixture_calls = [c for c in provider.calls if c[0] == "fixtures"]
            self.assertEqual(len(fixture_calls), 1)

    def test_candidates_carry_xg_reason(self):
        history = _league_history(days=40, xg_default=(1.5, 1.1))
        kickoff = _kickoff_fixture()
        candidates = build_fixture_candidates(kickoff, history, {})
        self.assertTrue(candidates)
        self.assertTrue(
            any("xG-Hybrid" in reason for reason in candidates[0].reasons),
            msg=f"kein xG-Hinweis in {candidates[0].reasons}",
        )


class TailStatsTopupTest(unittest.TestCase):
    """Frische API-Tail-Zeilen bekommen Stats auch ohne (stale) Index-Eintrag."""

    def test_tail_fixture_not_in_index_is_fetched_and_annotated(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            # Index kennt das Tail-Spiel 700 NICHT (z. B. 6h-Cache noch alt).
            index = [_index_entry(699, 1, 13, 14, "Team 13", "Team 14")]
            provider = FakeProvider(
                index,
                {
                    699: _full_stats_payload(13, 14),
                    700: _full_stats_payload(11, 12),
                },
            )
            history = [
                _row(699, 1, 13, 14, 0, 0),
                _row(700, 0, 11, 12, 2, 1),  # frischer Tail, echte API-ID
            ]

            result = annotate_history(history, 78, 2025, provider, db, max_new_calls=5)

            stats = history[1]["challenge_stats"]
            self.assertEqual((stats["corners_home"], stats["corners_away"]), (6, 3))
            self.assertEqual((stats["yellow_cards_home"], stats["yellow_cards_away"]), (2, 4))
            self.assertEqual((stats["xg_home"], stats["xg_away"]), (1.75, 0.90))
            fetched_ids = {
                params["fixture"]
                for path, params in provider.calls
                if path == "fixtures/statistics"
            }
            self.assertIn(700, fetched_ids)
            self.assertGreaterEqual(result["fetched"], 1)

    def test_budget_cap_blocks_tail_fetch(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            provider = FakeProvider([], {700: _full_stats_payload(11, 12)})
            history = [_row(700, 0, 11, 12, 2, 1)]

            annotate_history(history, 78, 2025, provider, db, max_new_calls=0)

            self.assertEqual(history[0]["challenge_stats"], {})
            stat_calls = [c for c in provider.calls if c[0] == "fixtures/statistics"]
            self.assertEqual(stat_calls, [])

    def test_rows_with_complete_stats_are_not_refetched(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            provider = FakeProvider([], {700: _full_stats_payload(11, 12)})
            history = [_row(700, 0, 11, 12, 2, 1)]
            history[0]["challenge_stats"] = {
                "xg_home": 1.0,
                "corners_home": 5,
                "yellow_cards_home": 1,
            }

            annotate_history(history, 78, 2025, provider, db, max_new_calls=5)

            stat_calls = [c for c in provider.calls if c[0] == "fixtures/statistics"]
            self.assertEqual(stat_calls, [])
            self.assertEqual(history[0]["challenge_stats"]["corners_home"], 5)

    def test_pseudo_id_rows_never_take_the_direct_path(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            provider = FakeProvider([], {700: _full_stats_payload(11, 12)})
            history = [_row(-123456, 0, 11, 12, 2, 1)]  # CSV-Pseudo-ID

            annotate_history(history, 78, 2025, provider, db, max_new_calls=5)

            stat_calls = [c for c in provider.calls if c[0] == "fixtures/statistics"]
            self.assertEqual(stat_calls, [])
            self.assertEqual(history[0]["challenge_stats"], {})

    def test_invalid_tail_rows_are_skipped(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "xg.db"
            provider = FakeProvider([], {})
            rows = [
                _row(701, 0, True, 12, 1, 0),          # bool-Team-ID
                _row(702, 0, 11, 11, 1, 0),            # gleiche Teams
                _row(703, 0, -5, 12, 1, 0),            # negative Team-ID
            ]
            rows.append(_row(704, 0, 11, 12, 1, 0))
            rows[3]["fixture"]["date"] = "kein-datum"  # ungültiges Datum

            entries = annotate_history(rows, 78, 2025, provider, db, max_new_calls=5)

            stat_calls = [c for c in provider.calls if c[0] == "fixtures/statistics"]
            self.assertEqual(stat_calls, [])
            self.assertEqual(entries["fetched"], 0)


if __name__ == "__main__":
    unittest.main()
