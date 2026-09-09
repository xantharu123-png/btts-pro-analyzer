"""Source mechanics; the saved provider sample is not historical prematch proof."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from context_models.contracts import ContextContractError, normalize_observation
from context_sources.football import normalize_football_context

NOW = datetime(2026, 9, 9, 8, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent / "fixtures/context/football/api-football-20260909.json"


def probe():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def event(detail):
    return {"event_key": f"api-football:football:{detail['fixture']['id']}",
            "sport": "football", "competition": str(detail["league"]["id"]),
            "format": "90min", "home_id": f"api-football:team:{detail['teams']['home']['id']}",
            "away_id": f"api-football:team:{detail['teams']['away']['id']}",
            "scheduled_start": detail["fixture"]["date"], "schedule_revision": "schema-test-v1",
            "status": "completed" if detail["fixture"]["status"]["short"] == "FT" else "scheduled"}


def normalize(current, *, injuries=None, lineups=None, appearances=None):
    return normalize_football_context(current, injuries=injuries or [], lineups=lineups or [],
                                      appearances=appearances or [], observed_at=NOW)


def test_actual_completed_player_rows_keep_missing_minutes_and_true_receipt():
    detail = probe()["calls"][0]["samples"][0]
    records = normalize(event(detail), appearances=[detail])
    players = [r for r in records if r["kind"] == "appearance"]
    assert len(players) == 46
    assert sum(r["payload"]["minutes"] is not None for r in players) == 32
    assert any(r["payload"]["minutes"] is None for r in players)
    for row in records:
        assert normalize_observation(row, observed_at=NOW) == row
        assert row["published_at"] is None
    assert all(r["payload"]["event_end"] is None for r in players)
    assert all(r["payload"]["result_observed_at"] == "2026-09-09T08:00:00.000000Z" for r in players)
    assert all(r["payload"]["exposure_kind"] == "regulation_reported" for r in players)


def test_real_nonmedical_absences_and_red_card_are_not_injury_effects():
    data = probe()
    detail = data["calls"][0]["samples"][0]
    rows = normalize(event(detail), injuries=data["calls"][1]["samples"])
    players = [r["payload"] for r in rows if r["subject_id"].startswith("api-football:player:")]
    by_id = {r["player_id"]: r for r in players}
    assert by_id["api-football:player:297311"]["status"] == "suspended"
    assert by_id["api-football:player:286593"]["absence_category"] == "selection"
    assert by_id["api-football:player:182639"]["absence_category"] == "inactive"
    assert by_id["api-football:player:48471"]["absence_category"] == "transfer"
    assert all("material_impact" not in r for r in players)
    assert all(not r["complete"] for r in rows if r["subject_id"].startswith("api-football:team:"))


def test_empty_future_source_does_not_assert_healthy_or_confirmed_lineup():
    detail = probe()["calls"][0]["samples"][1]
    records = normalize(event(detail), lineups=[detail], appearances=[detail])
    assert not any(r["subject_id"].startswith("api-football:player:") for r in records)
    assert len(records) == 4  # Two explicit empty-XI revisions plus unknown absence coverage.
    assert all(r["complete"] is False for r in records)


def test_direct_normalizer_cannot_relabel_native_regulation_as_another_format():
    detail = probe()["calls"][0]["samples"][0]
    with pytest.raises(ContextContractError):
        normalize({**event(detail), "format": "45min"}, lineups=[detail])


def test_lineup_requires_bound_fixture_and_distinct_eleven_not_bare_team_blob():
    detail = probe()["calls"][0]["samples"][0]
    rows = normalize(event(detail), lineups=[detail])
    assert sum(r["kind"] == "confirmed_lineup" for r in rows) == 46
    with pytest.raises(ContextContractError):
        normalize(event(detail), lineups=detail["lineups"])
    malformed = deepcopy(detail)
    malformed["lineups"][0]["startXI"][1] = malformed["lineups"][0]["startXI"][0]
    with pytest.raises(ContextContractError):
        normalize(event(detail), lineups=[malformed])


def test_native_collision_schedule_and_league_binding_are_not_name_matches():
    detail = probe()["calls"][0]["samples"][0]
    injury = deepcopy(probe()["calls"][1]["samples"][0])
    for path, value in [("team", 999), ("league", 999)]:
        changed = deepcopy(injury)
        changed[path]["id"] = value
        with pytest.raises(ContextContractError):
            normalize(event(detail), injuries=[changed])
    changed = deepcopy(injury)
    changed["fixture"]["date"] = "2026-08-23T15:00:00+00:00"
    with pytest.raises(ContextContractError):
        normalize(event(detail), injuries=[changed])
    changed = deepcopy(injury)
    changed["fixture"]["id"] = 999
    assert len(normalize(event(detail), injuries=[changed])) == 2


@pytest.mark.parametrize("minutes", [True, -1, 130, float("nan"), "90"])
def test_invalid_match_minutes_never_coerce_or_clip(minutes):
    detail = deepcopy(probe()["calls"][0]["samples"][0])
    detail["players"][0]["players"][0]["statistics"][0]["games"]["minutes"] = minutes
    with pytest.raises(ContextContractError):
        normalize(event(detail), appearances=[detail])


def test_extra_time_aggregate_stays_workload_not_regulation_exposure():
    detail = deepcopy(probe()["calls"][0]["samples"][0])
    detail["fixture"]["status"]["short"] = "AET"
    detail["fixture"]["status"]["elapsed"] = 120
    detail["players"][0]["players"][0]["statistics"][0]["games"]["minutes"] = 120
    rows = normalize({**event(detail), "status": "completed"}, appearances=[detail])
    player = next(r["payload"] for r in rows if r["kind"] == "appearance")
    assert player["minutes"] == 120
    assert player["regulation_minutes"] is None
    assert player["exposure_kind"] == "total_only"


def test_future_and_season_aggregate_cannot_be_old_appearance():
    detail = deepcopy(probe()["calls"][0]["samples"][0])
    detail["fixture"]["date"] = "2026-09-10T15:00:00+00:00"
    with pytest.raises(ContextContractError):
        normalize(event(detail), appearances=[detail])
    with pytest.raises(ContextContractError):
        normalize(event(probe()["calls"][0]["samples"][1]), appearances=[{"player": {"id": 1}, "season": 2026}])
