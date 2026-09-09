"""Synthetic native-envelope mechanics; no real-feed or model qualification."""
from copy import deepcopy
from datetime import date, timedelta
import json
import sqlite3
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from context_observations import append_observation
from context_sources import team_sports_status as status
from model_artifacts import canonical_bytes
from tests.test_team_sports_capture import NOW, SOURCES, completed_arguments, native_reply
from scanners.basketball_scanner import BasketballScanner


def request(provider="ESPN"):
    key, url, _, params = completed_arguments(BasketballScanner(), provider)
    return status.response_request(provider, url, params, phase="history", window=None,
        request_key=key, response=SimpleNamespace(status_code=200, history=[],
            url=url + ("?" + urlencode(params) if params else "")))


def game(payload, provider):
    if provider == "ESPN":
        return payload["events"][0]["competitions"][0]
    return payload["data"][0] if provider == "EuroLeague" else payload["gameWeek"][0]["games"][0]


def append(path, provider="ESPN", *, payload=None, clock=NOW):
    records, issues = status.normalize_team_sport_response(request(provider),
        native_reply(provider) if payload is None else payload, observed_at=clock)
    for row in records:
        append_observation(path, row, observed_at=clock)
    return records, issues


def selection(path, key=None, *, cutoff=NOW):
    rows = status.team_sport_observations_as_of(path, cutoff=cutoff)
    return status.select_team_sport_status(rows, cutoff=cutoff, event_key=key or rows[0]["event_key"])


def cancel(payload, provider):
    row = game(payload, provider)
    if provider == "ESPN":
        row["status"]["type"] = {"state": "post", "name": "STATUS_CANCELED", "completed": False}
    elif provider == "EuroLeague":
        row["cancelled"] = True
        row["played"] = False
    else:
        row["gameState"] = "CANC"


@pytest.mark.parametrize("provider", SOURCES)
def test_actual_sqlite_retains_final_cancellation_and_corrected_schedule_lineage(tmp_path, provider):
    path = tmp_path / "context_models.db"
    records, _ = append(path, provider)
    key = records[0]["event_key"]
    corrected = native_reply(provider)
    cancel(corrected, provider)
    row = game(corrected, provider)
    field = {"ESPN": "date", "EuroLeague": "utcDate", "NHL": "startTimeUTC"}[provider]
    row[field] = "2026-09-10T19:00:00Z"
    later = NOW + timedelta(microseconds=1)
    append(path, provider, payload=corrected, clock=later)
    assert selection(path, key)["rows"][0]["payload"]["projection"]["status"] == "completed"
    selected = selection(path, key, cutoff=later)
    assert selected["state"] == "available"
    assert selected["rows"][0]["payload"]["projection"]["status"] == "cancelled"
    full = status.team_sport_observations_as_of(path, cutoff=later)
    assert len(full) == 2 and len({r["schedule_revision"] for r in full}) == 2
    assert all(r["published_at"] is None and not r["complete"] for r in full)


@pytest.mark.parametrize("provider", SOURCES)
@pytest.mark.parametrize("bad", [{"future_code": "new"}, ["changed"], None, 0])
def test_known_event_unknown_native_status_withdraws_older_final(tmp_path, provider, bad):
    path = tmp_path / "context_models.db"
    records, _ = append(path, provider)
    payload = native_reply(provider)
    row = game(payload, provider)
    if provider == "ESPN":
        row["status"]["type"]["name"] = bad
    elif provider == "EuroLeague":
        row["played"] = bad
    else:
        row["gameState"] = bad
    later = NOW + timedelta(microseconds=1)
    corrections, _ = append(path, provider, payload=payload, clock=later)
    assert len(corrections) == 1, "known event correction must not disappear"
    current = selection(path, records[0]["event_key"], cutoff=later)
    assert current["state"] == "unknown"
    assert current["rows"][0]["observed_at"] == canonical_timestamp(later)


@pytest.mark.parametrize("provider", ["ESPN", "EuroLeague"])
def test_known_winner_contradiction_is_retained_but_not_available_status(tmp_path, provider):
    payload = native_reply(provider)
    row = game(payload, provider)
    if provider == "ESPN":
        row["competitors"][1]["winner"] = True
    else:
        row["winner"]["code"] = row["road"]["club"]["code"]
    records, _ = append(tmp_path / "context_models.db", provider, payload=payload)
    assert len(records) == 1
    assert "native-winner-conflict" in records[0]["payload"]["projection"]["issues"]
    assert selection(tmp_path / "context_models.db")["state"] == "unknown"


@pytest.mark.parametrize("provider", SOURCES)
@pytest.mark.parametrize("offset", [0, 1])
def test_impossible_started_or_terminal_clock_is_preserved_as_unknown(tmp_path, provider, offset):
    payload = native_reply(provider)
    row = game(payload, provider)
    field = {"ESPN": "date", "EuroLeague": "utcDate", "NHL": "startTimeUTC"}[provider]
    row[field] = canonical_timestamp(NOW + timedelta(microseconds=offset))
    records, _ = append(tmp_path / "context_models.db", provider, payload=payload)
    assert len(records) == 1
    assert "native-status-time-conflict" in records[0]["payload"]["projection"]["issues"]


@pytest.mark.parametrize("provider", SOURCES)
def test_equal_time_full_event_conflict_is_not_resolved_by_input_order(tmp_path, provider):
    path = tmp_path / "context_models.db"
    first, _ = append(path, provider)
    changed = native_reply(provider)
    cancel(changed, provider)
    second, _ = append(path, provider, payload=changed)
    assert first != second
    selected = selection(path)
    assert selected["state"] == "conflicting" and len(selected["receipt_refs"]) == 2
    rows = status.team_sport_observations_as_of(path, cutoff=NOW)
    assert selected == status.select_team_sport_status(tuple(reversed(rows)), cutoff=NOW, event_key=rows[0]["event_key"])


@pytest.mark.parametrize("provider", SOURCES)
def test_native_receipt_and_duplicate_identity_are_idempotent_not_newer_precedence(tmp_path, provider):
    path = tmp_path / "context_models.db"
    append(path, provider)
    append(path, provider)
    assert len(status.team_sport_observations_as_of(path, cutoff=NOW)) == 1
    later = NOW + timedelta(microseconds=1)
    append(path, provider, clock=later)
    assert len(status.team_sport_observations_as_of(path, cutoff=later)) == 2
    assert len(selection(path, cutoff=later)["rows"]) == 1


@pytest.mark.parametrize("provider", SOURCES)
@pytest.mark.parametrize("delta,expected", [(-1, 0), (0, 1), (1, 1)])
def test_actual_receipt_cutoff_is_inclusive_and_cannot_use_old_fixture_date(tmp_path, provider, delta, expected):
    path = tmp_path / "context_models.db"
    append(path, provider)
    rows = status.team_sport_observations_as_of(path, cutoff=NOW + timedelta(microseconds=delta))
    assert len(rows) == expected


@pytest.mark.parametrize("provider", SOURCES)
def test_no_missing_neutral_season_player_or_rule_fact_is_invented(tmp_path, provider):
    payload = native_reply(provider)
    row = game(payload, provider)
    row.pop({"ESPN": "neutralSite", "EuroLeague": "isNeutralVenue", "NHL": "neutralSite"}[provider], None)
    if provider == "NHL":
        row.pop("season")
        row.pop("gameType")
    records, _ = append(tmp_path / "context_models.db", provider, payload=payload)
    projection = records[0]["payload"]["projection"]
    assert projection["neutral_site"] is None
    assert projection["game_type"] is None
    if provider == "ESPN":
        assert projection["season"] == {}
    elif provider == "NHL":
        assert projection["season"] == {"event": None}
    assert not any(key in json.dumps(records) for key in ("completed_at", "minutes", "regulation_seconds", "confirmed_starter", "context_rules"))


def test_euroleague_gamecode_only_composite_uses_exact_received_request_season(tmp_path):
    payload = native_reply("EuroLeague")
    row = payload["data"][0]
    row.pop("id")
    row.pop("identifier")
    row["gameCode"] = 406
    records, _ = append(tmp_path / "context_models.db", "EuroLeague", payload=payload)
    assert records[0]["event_key"] == "euroleague:basketball:season:E2025:game:406"
    assert records[0]["payload"]["projection"]["aliases"] == [{"field": "gameCode", "value": 406, "scope": "request-season"}]
    assert "E2025_406" not in json.dumps(records)
    malformed = request("EuroLeague")
    malformed["request_season"] = None
    with pytest.raises(ContextContractError):
        status.normalize_team_sport_response(malformed, payload, observed_at=NOW)


def test_espn_distinct_outer_id_is_cooccurring_evidence_not_assumed_equal(tmp_path):
    payload = native_reply("ESPN")
    payload["events"][0]["id"] = "123"
    records, _ = append(tmp_path / "context_models.db", payload=payload)
    projection = records[0]["payload"]["projection"]
    assert projection["event_key"] == "espn:basketball:401810101"
    assert projection["aliases"] == [{"field": "competition.id", "value": "401810101", "scope": "source"},
                                     {"field": "event.id", "value": "123", "scope": "source"}]
    assert selection(tmp_path / "context_models.db", "espn:basketball:123")["state"] == "missing"


@pytest.mark.parametrize("provider", SOURCES)
def test_price_and_unreviewed_extra_fields_do_not_enter_native_identity(provider):
    payload = native_reply(provider)
    expected, _ = status.normalize_team_sport_response(request(provider), payload, observed_at=NOW)
    payload["unknownPriceField"] = {"market": "999"}
    row = game(payload, provider)
    row.update(odds=100, bestPrice=0, futureBookmaker={"secret": "not context"})
    actual, _ = status.normalize_team_sport_response(request(provider), payload, observed_at=NOW)
    assert canonical_bytes(actual) == canonical_bytes(expected)


@pytest.mark.parametrize("mutation", ["event_key", "schedule_revision", "source", "subject_id", "kind", "observed_at", "payload", "missing_content"])
def test_known_physical_corruption_cannot_hide_before_event_or_cutoff_filter(tmp_path, mutation):
    path = tmp_path / "context_models.db"
    append(path)
    with sqlite3.connect(path) as connection:
        if mutation == "payload":
            connection.execute("UPDATE context_contents SET payload=?", (b"{}",))
        elif mutation == "missing_content":
            connection.execute("DELETE FROM context_contents")
        else:
            connection.execute(f"UPDATE context_observations SET {mutation}=?", ("wrong",))
    with pytest.raises(ContextIntegrityError):
        status.team_sport_observations_as_of(path, cutoff=NOW - timedelta(days=500))


@pytest.mark.parametrize("field,value", [("complete", True), ("format", "regulation"), ("source", "nhl"),
    ("published_at", "2026-01-01T00:00:00Z"), ("valid_from", "2026-01-01T00:00:00Z")])
def test_rehashed_claimed_native_envelope_requires_owning_reconstruction(tmp_path, field, value):
    path = tmp_path / "context_models.db"
    records, _ = status.normalize_team_sport_response(request(), native_reply("ESPN"), observed_at=NOW)
    records[0][field] = value
    append_observation(path, records[0], observed_at=NOW)
    with pytest.raises(ContextIntegrityError):
        status.team_sport_observations_as_of(path, cutoff=NOW)


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "context_models.db"
    assert status.team_sport_observations_as_of(path, cutoff=NOW) == ()
    assert not path.exists()


@pytest.mark.parametrize("digits", [5000, 1000])
def test_huge_malformed_score_does_not_drop_known_event_correction(tmp_path, digits):
    payload = native_reply("ESPN")
    game(payload, "ESPN")["competitors"][0]["score"] = "9" * digits
    records, _ = append(tmp_path / "context_models.db", payload=payload)
    assert len(records) == 1
    assert "invalid-terminal-score" in records[0]["payload"]["projection"]["issues"]


@pytest.mark.parametrize("provider", SOURCES)
@pytest.mark.parametrize("side", ["home", "away"])
def test_incomplete_participant_change_does_not_resurrect_old_whole_event(tmp_path, provider, side):
    path = tmp_path / "context_models.db"
    records, _ = append(path, provider)
    original_key = records[0]["event_key"]
    changed = native_reply(provider)
    row = game(changed, provider)
    if provider == "ESPN":
        row["competitors"] = [p for p in row["competitors"] if p["homeAway"] != side]
    elif provider == "EuroLeague":
        row.pop("local" if side == "home" else "road")
    else:
        row.pop(side + "Team")
    later = NOW + timedelta(microseconds=1)
    append(path, provider, payload=changed, clock=later)
    current = selection(path, original_key, cutoff=later)
    assert current["state"] == "unknown"
    assert current["rows"][0]["payload"]["projection"][side + "_id"] is None
    returned = later + timedelta(microseconds=1)
    append(path, provider, clock=returned)
    assert selection(path, original_key, cutoff=returned)["state"] == "available"
    assert len(status.team_sport_observations_as_of(path, cutoff=returned)) == 3


def test_actual_sqlite_euroleague_cross_id_alias_conflicts_remain_in_full_native_pool(tmp_path):
    path = tmp_path / "context_models.db"
    first, _ = append(path, "EuroLeague")
    changed = native_reply("EuroLeague")
    changed["data"][0]["id"] = "other-native-uuid"
    changed["data"][0]["local"]["club"]["code"] = "Other"
    cancel(changed, "EuroLeague")
    later = NOW + timedelta(microseconds=1)
    second, _ = append(path, "EuroLeague", payload=changed, clock=later)
    rows = status.team_sport_observations_as_of(path, cutoff=later)
    assert len(rows) == 2 and first[0]["event_key"] != second[0]["event_key"]
    aliases = [r["payload"]["projection"]["aliases"] for r in rows]
    shared = {"field": "identifier", "value": "E2025_406", "scope": "source"}
    assert all(shared in a for a in aliases)
    # No mapping helper is allowed to manufacture a third event or equate IDs.
    assert status.select_team_sport_status(rows, cutoff=later,
        event_key="euroleague:basketball:E2025_406")["state"] == "missing"


@pytest.mark.parametrize("identifier", ["Native", "native", "NATIVE"])
def test_native_case_is_not_casefolded_or_joined_via_labels(tmp_path, identifier):
    payload = native_reply("EuroLeague")
    row = payload["data"][0]
    row["id"] = identifier
    row["local"]["club"]["code"] = "ClubAbC"
    records, _ = append(tmp_path / "context_models.db", "EuroLeague", payload=payload)
    assert records[0]["event_key"] == "euroleague:basketball:" + identifier
    assert records[0]["payload"]["projection"]["home_id"] == "euroleague:basketball:team:ClubAbC"


@pytest.mark.parametrize("provider", ["ESPN", "NHL"])
@pytest.mark.parametrize("identifier", [True, 42.0, "042", " 42", "４２", None])
def test_unsupported_native_id_does_not_become_sanitized_numeric_alias(provider, identifier):
    payload = native_reply(provider)
    game(payload, provider)["id"] = identifier
    if provider == "ESPN":
        payload["events"][0]["id"] = identifier
    records, issues = status.normalize_team_sport_response(request(provider), payload, observed_at=NOW)
    assert records == () and "native-event-id-unavailable" in issues


@pytest.mark.parametrize("provider", SOURCES)
@pytest.mark.parametrize("field,value", [("source", "other"), ("sport", "cricket"), ("competition", "wrong"),
    ("request_season", "E2099"), ("request_key", "wrong"), ("search_window", {"start": "2026-01-01", "end": "2026-01-02"})])
def test_request_provenance_cannot_be_freely_relabelled(provider, field, value):
    claimed = request(provider)
    claimed[field] = value
    with pytest.raises(ContextContractError):
        status.normalize_team_sport_response(claimed, native_reply(provider), observed_at=NOW)


@pytest.mark.parametrize("provider", SOURCES)
def test_pending_native_content_is_detached_from_provider_mutations(provider):
    payload = native_reply(provider)
    records, _ = status.normalize_team_sport_response(request(provider), payload, observed_at=NOW)
    before = canonical_bytes(records)
    cancel(payload, provider)
    game(payload, provider).clear()
    assert canonical_bytes(records) == before


@pytest.mark.parametrize("mutation", ["schema", "derived_id", "neutral_default", "price", "extra"])
def test_rehashed_native_payload_cannot_claim_other_projection_or_unknown_fields(tmp_path, mutation):
    path = tmp_path / "context_models.db"
    records, _ = status.normalize_team_sport_response(request(), native_reply("ESPN"), observed_at=NOW)
    row = records[0]
    if mutation == "schema":
        # Claiming another known source inside the exact typed native envelope.
        row["payload"]["request"]["provider"] = "NHL"
    elif mutation == "derived_id":
        row["payload"]["projection"]["home_id"] = "espn:basketball:team:999"
    elif mutation == "neutral_default":
        row["payload"]["native"]["competition"].pop("neutralSite")
    else:
        row["payload"]["native"]["competition"]["odds" if mutation == "price" else "extra"] = 2
    row["source_revision"] = digest(row["payload"])
    if mutation == "price":
        with pytest.raises(ContextContractError):
            append_observation(path, row, observed_at=NOW)
    else:
        append_observation(path, row, observed_at=NOW)
        with pytest.raises(ContextIntegrityError):
            status.team_sport_observations_as_of(path, cutoff=NOW)


def test_unencodable_native_label_does_not_erase_known_status(tmp_path):
    payload = native_reply("ESPN")
    game(payload, "ESPN")["competitors"][0]["team"]["abbreviation"] = "\ud800"
    records, _ = append(tmp_path / "context_models.db", payload=payload)
    assert len(records) == 1
    assert records[0]["payload"]["native"]["competition"]["competitors"][0]["team"]["abbreviation"] == {"invalid_shape": "string"}


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_claimed_selected_row_is_typed_integrity_error_before_filter(tmp_path, value):
    path = tmp_path / "context_models.db"
    append(path)
    rows = status.team_sport_observations_as_of(path, cutoff=NOW)
    rows[0]["payload"]["projection"]["scores"]["home"] = value
    with pytest.raises(ContextIntegrityError):
        status.select_team_sport_status(rows, cutoff=NOW, event_key="espn:basketball:123")
