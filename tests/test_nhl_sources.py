"""Real sampled native shapes plus explicitly synthetic adversarial mutations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from importlib import import_module
import json
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import ContextContractError, OBSERVATION_FIELDS, canonical_timestamp
from context_observations import freeze_named_receipts


SAMPLES = json.loads((Path(__file__).parent / "fixtures" / "nhl_boxscore_native_samples.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 16, 20, 3, 24, tzinfo=timezone.utc)


def source():
    return import_module("context_sources.nhl")


def sample(kind="completed"):
    return deepcopy(SAMPLES[kind])


def normalize(payload=None, **kwargs):
    payload = sample() if payload is None else payload
    return source().normalize_nhl_boxscore(payload, requested_game_id=kwargs.pop("requested_game_id", payload["id"]),
                                          observed_at=kwargs.pop("observed_at", NOW), **kwargs)


def goalie(payload):
    return payload["playerByGameStats"]["awayTeam"]["goalies"][0]


def players(row, team=16):
    return row["payload"]["data"]["teams"][f"nhl:ice_hockey:team:{team}"]["players"]


def test_real_sample_keeps_measured_toi_and_actual_historical_goalie_distinct_from_internal_exposure():
    raw = sample()
    row = normalize(raw)
    assert raw == SAMPLES["completed"]
    assert row["source_schema"] == "nhl-boxscore-measured-v1"
    assert row["kind"] == "native_boxscore" and row["complete"] is False
    assert set(row) == OBSERVATION_FIELDS
    data = row["payload"]["data"]
    assert data["total_toi_scope"] == "whole_game"
    assert data["actual_start"] is None and data["actual_end"] is None
    assert data["final_score"] == {"home": 3, "away": 2}
    assert data["regulation_score"] == {"home": 3, "away": 2}
    knight = next(p for p in players(row) if p["role"] == "goalie")
    assert knight["total_seconds"] == 3544 and knight["toi"] == "59:04"
    assert knight["actual_starter"] is True
    assert knight["regulation_seconds"] is None and knight["overtime_seconds"] is None
    assert knight["stats"] == {"shots_against": 37, "saves": 34, "goals_against": 3, "save_pctg": 0.918919}
    assert row["published_at"] is None and row["publication_proof"] is None
    assert row["payload"]["scope"]["neutral_site"] is None


def test_real_future_sample_has_no_measured_usage_injury_or_goalie_confirmation():
    row = normalize(sample("future"))
    data = row["payload"]["data"]
    assert row["payload"]["status"] == "scheduled"
    assert data["final_score"] == {"home": None, "away": None}
    assert data["regulation_score"] is None and data["terminal_phase"] is None
    assert all(team["players"] is None for team in data["teams"].values())
    assert all(team["availability"] is None and team["pregame_starter"] is None for team in data["teams"].values())
    assert row["complete"] is False


@pytest.mark.parametrize("phase", ["OT", "SO"])
def test_synthetic_ot_so_winner_goal_never_becomes_a_regulation_score_or_phase_toi(phase):
    raw = sample()
    raw["gameOutcome"]["lastPeriodType"] = phase
    raw["periodDescriptor"].update(number=4 if phase == "OT" else 5, periodType=phase)
    raw["homeTeam"]["score"], raw["awayTeam"]["score"] = 4, 3
    goalie(raw)["toi"] = "64:59"
    data = normalize(raw)["payload"]["data"]
    assert data["final_score"] == {"home": 4, "away": 3}
    assert data["regulation_score"] is None
    assert data["terminal_phase"] == phase
    assert players(normalize(raw))[-1]["regulation_seconds"] is None


@pytest.mark.parametrize("remaining", [300, 301])
def test_regular_season_ot_remaining_is_bounded_by_five_minutes(remaining):
    raw = sample()
    raw["gameOutcome"]["lastPeriodType"] = "OT"
    raw["periodDescriptor"].update(number=4, periodType="OT")
    raw["clock"]["secondsRemaining"] = remaining
    if remaining == 301:
        with pytest.raises(ContextContractError, match="remaining clock"):
            normalize(raw)
    else:
        assert normalize(raw)["payload"]["data"]["actual_end"] is None


@pytest.mark.parametrize("field", ["toi", "shifts", "goals", "assists", "points", "sog"])
def test_missing_skater_measurement_stays_none_not_zero(field):
    raw = sample()
    del raw["playerByGameStats"]["awayTeam"]["forwards"][0][field]
    item = next(p for p in players(normalize(raw)) if p["player_id"] == "nhl:ice_hockey:player:8477987")
    assert (item["total_seconds"] if field == "toi" else item["stats"][{"sog": "shots_on_goal"}.get(field, field)]) is None


@pytest.mark.parametrize("field", ["starter", "shotsAgainst", "saves", "goalsAgainst", "savePctg"])
def test_missing_goalie_measurement_or_confirmation_stays_unknown(field):
    raw = sample()
    del goalie(raw)[field]
    item = next(p for p in players(normalize(raw)) if p["role"] == "goalie")
    key = {"shotsAgainst": "shots_against", "goalsAgainst": "goals_against", "savePctg": "save_pctg"}.get(field, field)
    assert (item["actual_starter"] if field == "starter" else item["stats"][key]) is None


def test_real_unused_backup_is_not_invented_to_have_played_or_have_a_save_percentage():
    backup = next(p for p in players(normalize(), 13) if p["role"] == "goalie")
    assert backup["total_seconds"] == 0 and backup["actual_starter"] is False
    assert backup["stats"]["save_pctg"] is None


@pytest.mark.parametrize("missing", ["playerByGameStats", "awayTeam", "goalies"])
def test_missing_player_collection_is_incomplete_not_an_empty_complete_roster(missing):
    raw = sample()
    if missing == "playerByGameStats": del raw[missing]
    elif missing == "awayTeam": del raw["playerByGameStats"][missing]
    else: del raw["playerByGameStats"]["awayTeam"][missing]
    row = normalize(raw)
    team = row["payload"]["data"]["teams"]["nhl:ice_hockey:team:16"]
    assert row["complete"] is False
    assert (team["players"] is None if missing != "goalies" else "goalies" in team["missing_groups"])


@pytest.mark.parametrize("mutation", [
    "wrong-id", "bool-id", "bool-request", "wrong-season", "bool-season", "unknown-season", "wrong-type", "bool-type",
    "same-teams", "bool-team", "wrong-expected-teams", "cross-team-player", "duplicate-player", "bool-player", "foreign-player-team",
    "bad-toi", "negative-toi", "seconds-toi", "overlong-reg", "bool-toi", "bad-starter", "multiple-starters", "saves-too-high", "ga-mismatch", "pct-mismatch", "pct-nan", "negative-shifts", "bool-stat", "points-mismatch",
    "future-start", "equal-start", "naive-receipt", "receipt-string", "nonterminal-usage", "unknown-status", "bad-schedule", "tied-final", "missing-final", "unknown-phase", "period-conflict", "phase-number", "so-playoff", "ot-gap", "reg-extra-period", "nonzero-clock", "malformed-collection", "overlarge-roster",
])
def test_synthetic_contradictions_fail_closed_with_typed_error(mutation):
    raw, kwargs = sample(), {}
    if mutation == "wrong-id": kwargs["requested_game_id"] = 2025020002
    elif mutation == "bool-id": raw["id"] = True
    elif mutation == "bool-request": kwargs["requested_game_id"] = True
    elif mutation == "wrong-season": raw["season"] = 20262027
    elif mutation == "bool-season": raw["season"] = True
    elif mutation == "unknown-season": raw.update(id=2027020001, season=20272028)
    elif mutation == "wrong-type": raw["gameType"] = 3
    elif mutation == "bool-type": raw["gameType"] = True
    elif mutation == "same-teams": raw["awayTeam"]["id"] = 13
    elif mutation == "bool-team": raw["awayTeam"]["id"] = True
    elif mutation == "wrong-expected-teams": kwargs["expected_teams"] = (16, 13)
    elif mutation == "cross-team-player": raw["playerByGameStats"]["homeTeam"]["forwards"][0]["playerId"] = 8477987
    elif mutation == "duplicate-player": raw["playerByGameStats"]["awayTeam"]["forwards"].append(deepcopy(raw["playerByGameStats"]["awayTeam"]["forwards"][0]))
    elif mutation == "bool-player": goalie(raw)["playerId"] = True
    elif mutation == "foreign-player-team": goalie(raw)["teamId"] = 13
    elif mutation == "bad-toi": goalie(raw)["toi"] = "01:60"
    elif mutation == "negative-toi": goalie(raw)["toi"] = "-1:00"
    elif mutation == "seconds-toi": goalie(raw)["toi"] = 3544
    elif mutation == "overlong-reg": goalie(raw)["toi"] = "60:01"
    elif mutation == "bool-toi": goalie(raw)["toi"] = True
    elif mutation == "bad-starter": goalie(raw)["starter"] = "true"
    elif mutation == "multiple-starters":
        extra = deepcopy(goalie(raw)); extra["playerId"] = 9999999
        raw["playerByGameStats"]["awayTeam"]["goalies"].append(extra)
    elif mutation == "saves-too-high": goalie(raw)["saves"] = 38
    elif mutation == "ga-mismatch": goalie(raw)["goalsAgainst"] = 4
    elif mutation == "pct-mismatch": goalie(raw)["savePctg"] = .95
    elif mutation == "pct-nan": goalie(raw)["savePctg"] = float("nan")
    elif mutation == "negative-shifts": raw["playerByGameStats"]["awayTeam"]["forwards"][0]["shifts"] = -1
    elif mutation == "bool-stat": goalie(raw)["saves"] = True
    elif mutation == "points-mismatch": raw["playerByGameStats"]["awayTeam"]["forwards"][0]["points"] = 1
    elif mutation == "future-start": raw["startTimeUTC"] = (NOW+timedelta(seconds=1)).isoformat()
    elif mutation == "equal-start": raw["startTimeUTC"] = NOW.isoformat()
    elif mutation == "naive-receipt": kwargs["observed_at"] = NOW.replace(tzinfo=None)
    elif mutation == "receipt-string": kwargs["observed_at"] = NOW.isoformat()
    elif mutation == "nonterminal-usage": raw["gameState"] = "FUT"
    elif mutation == "unknown-status": raw["gameState"] = "new"
    elif mutation == "bad-schedule": raw["gameScheduleState"] = "new"
    elif mutation == "tied-final": raw["homeTeam"]["score"] = 2
    elif mutation == "missing-final": del raw["homeTeam"]["score"]
    elif mutation == "unknown-phase": raw["gameOutcome"]["lastPeriodType"] = "new"
    elif mutation == "period-conflict": raw["periodDescriptor"]["periodType"] = "OT"
    elif mutation == "phase-number": raw["periodDescriptor"]["number"] = True
    elif mutation == "so-playoff":
        raw.update(id=2025030111, gameType=3); raw["gameOutcome"]["lastPeriodType"] = "SO"
        raw["periodDescriptor"].update(number=5, periodType="SO")
    elif mutation == "ot-gap":
        raw["gameOutcome"]["lastPeriodType"] = "OT"; raw["periodDescriptor"].update(number=4, periodType="OT")
        raw["homeTeam"]["score"] = 5
    elif mutation == "reg-extra-period": raw["periodDescriptor"]["number"] = 4
    elif mutation == "nonzero-clock": raw["clock"]["secondsRemaining"] = 1
    elif mutation == "malformed-collection": raw["playerByGameStats"]["awayTeam"]["goalies"] = {}
    elif mutation == "overlarge-roster": raw["playerByGameStats"]["awayTeam"]["forwards"] *= 101
    with pytest.raises(ContextContractError): normalize(raw, **kwargs)


def test_unknown_optional_fields_and_prices_do_not_enter_retained_source_facts():
    raw = sample()
    raw.update(odds={"home": 1.2}, article="huge irrelevant source", career={"years": list(range(1000))})
    goalie(raw).update(odds=1.1, name={"default": "media label"})
    assert normalize(raw) == normalize()


def test_sampled_player_order_does_not_change_joint_source_content():
    raw = sample()
    raw["playerByGameStats"]["awayTeam"]["forwards"].append({"playerId": 9999999, "toi": None})
    a = normalize(raw)
    raw["playerByGameStats"]["awayTeam"]["forwards"].reverse()
    assert normalize(raw) == a


def test_invalid_unicode_scalar_is_a_typed_source_error_not_an_encoder_crash():
    raw = sample()
    goalie(raw)["toi"] = "\ud800"
    with pytest.raises(ContextContractError):
        normalize(raw)


def test_later_receipt_roundtrip_uses_real_existing_b1_content_deduplication(tmp_path):
    db = tmp_path / "context_models.db"
    later = NOW + timedelta(minutes=1)
    refs, retained_bytes = source().append_nhl_boxscore_batch(db, ((sample(), 2025020001, NOW), (sample(), 2025020001, later)), max_new_payload_bytes=65536)
    rows = freeze_named_receipts(db, refs)
    assert len(rows) == 2 and len(set(refs)) == 2
    assert rows[0]["content_digest"] == rows[1]["content_digest"]
    assert {r["observed_at"] for r in rows} == {canonical_timestamp(NOW), canonical_timestamp(later)}
    assert retained_bytes < 65536
    for row in rows:
        assert {key: row[key] for key in OBSERVATION_FIELDS} == normalize()
        assert source().validate_nhl_boxscore_receipt(row) == row["payload"]
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM context_contents").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM context_observations").fetchone() == (2,)
    again, new_bytes = source().append_nhl_boxscore_batch(db, ((sample(), 2025020001, NOW),), max_new_payload_bytes=0)
    assert again == (refs[0],) and new_bytes == 0


@pytest.mark.parametrize("mutation", ["total", "starter", "schema", "phase", "hash"])
def test_source_receipt_revalidation_rejects_altered_derived_or_native_facts(tmp_path, mutation):
    refs, _ = source().append_nhl_boxscore_batch(tmp_path / "context.db", ((sample(), 2025020001, NOW),), max_new_payload_bytes=65536)
    row = deepcopy(freeze_named_receipts(tmp_path / "context.db", refs)[0])
    if mutation == "total": players(row)[0]["total_seconds"] = 12
    elif mutation == "starter": players(row)[-1]["actual_starter"] = False
    elif mutation == "schema": row["payload"]["source_schema"] = "hockey-internal-context-v1"
    elif mutation == "phase": row["payload"]["data"]["terminal_phase"] = "SO"
    else: row["source_revision"] = "0"*64
    with pytest.raises(ContextContractError): source().validate_nhl_boxscore_receipt(row)


def test_batch_is_bounded_and_invalid_rows_do_not_partially_append(tmp_path):
    db = tmp_path / "context.db"
    bad = sample(); bad["season"] = True
    with pytest.raises(ContextContractError):
        source().append_nhl_boxscore_batch(db, ((sample(), 2025020001, NOW), (bad, 2025020001, NOW)), max_new_payload_bytes=65536)
    assert not db.exists()
    with pytest.raises(ContextContractError):
        source().append_nhl_boxscore_batch(db, ((sample(), 2025020001, NOW),)*513, max_new_payload_bytes=65536)
    assert not db.exists()
    from context_models.football_original_storage import StorageBudgetExceeded
    with pytest.raises(StorageBudgetExceeded):
        source().append_nhl_boxscore_batch(db, ((sample(), 2025020001, NOW),), max_new_payload_bytes=1)
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM context_contents").fetchone() == (0,)
