from datetime import date, datetime, timezone
import json

import wettfinder_automation as auto


DAY = date(2026, 11, 22)


def at(hour):
    return datetime(2026, 11, 22, hour, tzinfo=timezone.utc)


def record(i, hour=18, home_rate=1.37):
    return dict(fixture_id=i, league_id=39, home_id=i+100, away_id=i+200,
                home_team=f"H{i}", away_team=f"A{i}", scheduled_start=at(hour).isoformat(),
                modeled_at=at(3).isoformat(), model_version=auto.CHALLENGE_PREDICTION_VERSION,
                model_scope="same_competition", expected_home_goals=home_rate, expected_away_goals=1.11)


def state(rows):
    return auto._football_state_from_snapshot({"live_goal_priors": {"version": 1, "rows": rows}},
                                             attempted_at=at(3), search_date=DAY)


def final(state_, prev, hour):
    from football_live_publication import publish_live_bases
    publish_live_bases(state_, prev, day=DAY, now=at(hour))
    return state_["live_goal_priors"]


def previous(state_, *, tomorrow=False):
    return {"version": auto.AUTOMATION_VERSION, "target_search_date": "2026-11-21" if tomorrow else str(DAY),
            "football_next_day" if tomorrow else "football": json.loads(json.dumps(state_))}


def test_daily_publication_not_gated_by_markets_or_limit_and_no_backdating():
    rows = [record(i) for i in range(1, 36)] + [record(36, hour=4)]
    rows[-1]["published_at"] = at(3).isoformat()  # a raw field cannot prove publication
    s = state(rows)
    section = final(s, {}, 5)
    assert [r["fixture_id"] for r in section["rows"]] == list(range(1, 36))
    assert all(r["published_at"] == at(5).isoformat() for r in section["rows"])
    assert s["approved_candidates"] == 0


def test_day_transition_keeps_frozen_evening_and_night_values_and_original_clock():
    first = state([record(1, hour=5), record(2)])
    final(first, {}, 4)
    s = state([record(2, home_rate=7), record(3)])
    rows = {r["fixture_id"]:r for r in final(s, previous(first, tomorrow=True), 6)["rows"]}
    assert rows[1]["published_at"] == rows[2]["published_at"] == at(4).isoformat()
    assert rows[2]["expected_home_goals"] == 1.37
    assert rows[3]["published_at"] == at(6).isoformat()


def test_never_issue_on_refresh_from_unsealed_or_cross_day_json():
    restored = json.loads(json.dumps(state([record(1)])))
    assert not final(restored, previous(restored), 4)["rows"]
    first = state([record(2)])
    final(first, {}, 4)
    wrong = previous(first, tomorrow=True)
    wrong["target_search_date"] = "2026-11-20"
    assert not final(state([]), wrong, 6)["rows"]


def test_real_daily_writer_persists_today_and_tomorrow_without_public_football_markets(tmp_path):
    from live_football_priors import _project_index
    from tests.test_wettfinder_next_day import _run, _today_snapshot, TODAY, TOMORROW

    def scan(day):
        snapshot = _today_snapshot()
        snapshot.update(shortlist=[], wettfinder_candidates=[], discovery_candidates=[], base_candidates=0,
                        base_fixture_count=0, context_verified_fixtures=0, context_fixtures=0,
                        context_fixture_statuses={}, fixture_kickoffs=[])
        rows = [{**record(i), "modeled_at": "2020-01-01T03:00:00+00:00",
                 "scheduled_start": f"{day}T18:00:00+00:00"} for i in
                (range(1, 31) if day == TODAY else range(31, 62))]
        snapshot["live_goal_priors"] = {"version": 1, "rows": rows}
        return snapshot

    artifact, doc = _run(tmp_path, scan, football_next_day=True)
    written = json.loads(artifact.read_text(encoding="utf-8"))
    assert written["model_candidates"] == [] and "next_day_search_date" not in written
    assert written["football_next_day"]["search_date"] == str(TOMORROW)
    assert set(_project_index(written)) == set(range(1, 62)) == set(_project_index(doc))


def test_fresh_conflicting_or_invalid_capture_is_not_replaced_by_older_pair():
    s = state([record(1), record(2), record(3)])
    final(s, {}, 4)
    changed = state([record(1), record(1, home_rate=3), record(2, home_rate=True),
                     {**record(3, home_rate=6), "scheduled_start": at(18).isoformat().replace("+00:00", "Z")}])
    rows = final(changed, previous(s), 6)["rows"]
    assert [(r["fixture_id"], r["expected_home_goals"]) for r in rows] == [(3, 1.37)]


def test_first_atomic_write_finishes_after_kickoff_but_an_earlier_receipt_survives(tmp_path, monkeypatch):
    class DiskClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return at(6)

    monkeypatch.setattr(auto, "datetime", DiskClock)
    early = state([record(1, hour=5)])
    final(early, {}, 3)
    s = state([record(2, hour=5), record(3, hour=18)])
    final(s, previous(early), 4)
    path = tmp_path / "state.json"
    auto.write_state({"football": s}, path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert [r["fixture_id"] for r in loaded["football"]["live_goal_priors"]["rows"]] == [1, 3]
    assert loaded["football"]["live_goal_priors"]["rows"][0]["published_at"] == at(3).isoformat()


def test_failed_new_day_discovery_retains_yesterdays_proven_nightgame_but_no_market_rows():
    first = state([record(1, hour=5)])
    final(first, {}, 4)
    failed = auto._failed_football_state({}, attempted_at=at(6), search_date=DAY, error="offline")
    assert final(failed, previous(first, tomorrow=True), 6)["rows"][0]["fixture_id"] == 1
    assert failed["status"] == "degraded" and failed["candidates"] == []
