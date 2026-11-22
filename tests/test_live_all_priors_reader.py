"""The live reader consumes bounded, published fixture priors, not a market shortlist."""
from datetime import date, datetime, timezone
import json
import sys
from types import SimpleNamespace

import pytest

import ev_signal_sources
import live_football_priors as priors
from challenge_engine import MODEL_SCOPE_SAME_COMPETITION
from test_live_football_priors import case


START = "2026-11-22T21:00:00+00:00"
MODELED = "2026-11-21T20:00:00+00:00"
PUBLISHED = "2026-11-21T22:00:00+00:00"


@pytest.fixture
def files(tmp_path, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 22, 23, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(priors, "datetime", Clock)
    path = tmp_path / "wettfinder.json"
    monkeypatch.setattr(ev_signal_sources, "AUTOMATED_WETTFINDER_PATH", path)
    fixture, document, _ = case(datetime.fromisoformat(START))
    return path, fixture, document


def row(fid=81, **changes):
    return {
        "fixture_id": fid, "league_id": 39, "home_id": 1, "away_id": 2,
        "home_team": "1", "away_team": "2", "scheduled_start": START, "modeled_at": MODELED,
        "model_version": priors.PRIOR_MODEL, "model_scope": MODEL_SCOPE_SAME_COMPETITION,
        "expected_home_goals": 1.625, "expected_away_goals": .875, **changes,
    }


def compact(rows, **changes):
    return {"version": 1, "published_at": PUBLISHED, "rows": rows, **changes}


def read(files, section, *, group="football"):
    path, fixture, document = files
    document[group]["live_goal_priors"] = section
    path.write_text(json.dumps(document), encoding="utf-8")
    return priors.stored_goal_priors(fixture)


def test_all_27_modeled_fixture_ids_reachable_without_a_single_public_candidate(files):
    path, fixture, doc = files
    doc["football"]["candidates"] = []
    rows = [row(fid, home_id=fid + 500, home_team=f"Heim {fid}") for fid in range(81, 108)]
    doc["football"]["live_goal_priors"] = compact(rows)
    path.write_text(json.dumps(doc), encoding="utf-8")
    for fid in range(81, 108):
        fixture["fixture"]["id"] = fid
        fixture["teams"]["home"].update(id=fid + 500, name=f"Heim {fid}")
        assert priors.stored_goal_priors(fixture) == (1.625, .875), fid


@pytest.mark.parametrize("section", [
    None, {}, [], compact([], version=True), compact([row()], version=2),
    compact([row()], published_at=None), compact([row()], published_at="2026-11-21T22:00:00"),
    {"version": 1, "published_at": PUBLISHED, "rows": {}},
    compact([row(fid) for fid in range(81, 1282)]), compact([]),
], ids=["null", "missing", "not_map", "bool_version", "foreign_version", "missing_clock", "naive_clock",
        "not_list", "oversize", "empty"])
def test_new_section_is_authoritative_even_when_broken_or_empty(files, section):
    # files also has a valid legacy candidate for this same live fixture (81).
    assert read(files, section) is None


@pytest.mark.parametrize("changes", [
    {"modeled_at": "2026-11-21T20:00:00"}, {"modeled_at": "2026-11-21T22:00:01Z"},
    {"scheduled_start": "2026-11-22T22:00:00"}, {"scheduled_start": "2026-11-23T21:00:00Z"},
    {"model_version": "legacy"}, {"model_scope": "senior_national_pooled"},
    {"league_id": True}, {"home_id": True}, {"away_id": 1}, {"home_team": ""},
    {"away_team": "1"}, {"away_team": "2" * 201}, {"expected_home_goals": None},
    {"expected_away_goals": True}, {"expected_home_goals": "1.4"}, {"expected_away_goals": -0.1},
    {"expected_home_goals": 8.001}, {"expected_away_goals": float("nan")},
    {"expected_home_goals": float("inf")}, {"published_at": None},
    {"published_at": "2026-11-21T19:00:00Z"}, {"published_at": "2026-11-21T23:00:00Z"},
    {"home_id": 77}, {"away_team": "Different away"}, {"league_id": 78},
])
def test_bad_or_misbound_fixture_row_does_not_downgrade_to_legacy(files, changes):
    assert read(files, compact([row(**changes)])) is None


@pytest.mark.parametrize("duplicate", [row(), row(expected_home_goals=2.25), row(home_id=None), row(home_team="3")])
def test_ambiguous_fixture_id_is_quarantined_even_if_good_row_came_after_it(files, duplicate):
    assert read(files, compact([duplicate, row()])) is None


def test_corrupt_other_fixture_does_not_hide_supported_fixture(files):
    assert read(files, compact([row(82, away_team=None), row()])) == (1.625, .875)


def test_next_day_prior_does_not_require_any_public_preview_or_quote_decision(files):
    _, _, doc = files
    doc["football_next_day"] = doc.pop("football")
    doc.update(target_search_date="2026-11-21", generated_at="2026-11-21T19:00:00Z", decision_at="2026-11-22T22:00:00Z")
    assert read(files, compact([row()]), group="football_next_day") == (1.625, .875)


def test_disagreeing_next_day_marker_or_state_date_rejects_compact_group(files):
    _, _, doc = files
    doc["football_next_day"] = doc.pop("football")
    doc.update(target_search_date="2026-11-21", next_day_search_date="2026-11-23",
               generated_at="2026-11-21T19:00:00Z")
    assert read(files, compact([row()]), group="football_next_day") is None
    del doc["next_day_search_date"]
    doc["football_next_day"]["search_date"] = "2026-11-21"
    assert read(files, compact([row()]), group="football_next_day") is None


def test_post_kickoff_republication_keeps_only_an_authenticated_earlier_row_clock(files):
    _, _, doc = files
    doc["decision_at"] = MODELED  # even a pre-kickoff price time cannot witness first publication
    section = compact([row()], published_at=START)
    assert read(files, section) is None
    section["rows"][0]["published_at"] = START
    assert read(files, section) is None
    section["rows"][0]["published_at"] = PUBLISHED  # inherited from a previous publication
    assert read(files, section) == (1.625, .875)


def test_preexisting_format_still_reads_legacy_goals_until_new_state_is_published(files):
    path, fixture, doc = files
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert priors.stored_goal_priors(fixture) == (1.812, .942)
    assert read(files, compact([row()])) == (1.625, .875)


def test_publication_replay_gets_only_unique_projected_model_facts_and_first_clocks():
    replay = getattr(priors, "compact_goal_rows", None)
    assert callable(replay), "no validated carry-forward path for compact fixture priors"
    rows = [row(reference_quote=1.40), row(82, published_at=MODELED), row(83), row(83), row(84, away_id=True)]
    result = replay(compact(rows), date(2026, 11, 22))
    assert result == {81: row(published_at=PUBLISHED), 82: row(82, published_at=MODELED)}
    assert "published_at" not in rows[0] and "reference_quote" in rows[0]


def test_legacy_file_witness_cannot_override_new_sections_or_revive_poisoned_public_evidence(files, monkeypatch):
    path, fixture, doc = files
    # Only the independent legacy verification is substituted; exercise actual path, stat, index and match checks.
    def attest(document, *, stat, basis_factory, model):
        assert stat.st_size == path.stat().st_size
        assert model == priors.PRIOR_MODEL
        return {81: basis_factory(39, 1, 2, "1", "2", datetime.fromisoformat(START), None,
                                  datetime.fromisoformat(MODELED), (2.1, 0.7))}
    monkeypatch.setitem(sys.modules, "live_football_legacy_priors", SimpleNamespace(legacy_unpublished_priors=attest))
    state = doc["football"]
    old = state["candidates"].pop()
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert priors.stored_goal_priors(fixture) == (2.1, .7)
    state["candidates"] = [dict(old, model_scope="broken")]
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert priors.stored_goal_priors(fixture) is None
    state["candidates"] = []
    assert read(files, None) is None
