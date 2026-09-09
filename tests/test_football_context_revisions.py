"""Permanent independent-review regressions through actual B1 storage."""
from copy import deepcopy
from datetime import timedelta

import pytest
import test_football_context_features as support
from context_models.contracts import ContextContractError, OBSERVATION_FIELDS
from context_models.contracts import digest, validate_base_distribution, validate_event
from context_models.football import expected_roster, football_features
from context_observations import append_observation, observations_as_of
from context_sources.football import normalize_football_context
from model_artifacts import put_artifact, load_artifact

NOW = support.NOW


def detail(fixture, players, *, completed=True):
    return {
        "fixture": {"id": fixture, "date": (NOW - timedelta(days=2) if completed else support.START).isoformat(),
                    "status": {"short": "FT" if completed else "NS"}},
        "league": {"id": 39}, "teams": {"home": {"id": 1}, "away": {"id": 2}},
        "lineups": [],
        "players": [{"team": {"id": 1}, "players": [
            {"player": {"id": player}, "statistics": [{"games": {
                "minutes": 60, "substitute": False, "position": "M"}}]} for player in players
        ]}],
    }


def ingest(tmp_path, revisions, *, kind):
    path = tmp_path / "review-observations.db"
    scopes = set()
    for observed, kwargs in revisions:
        records = normalize_football_context(support.event(), injuries=kwargs.get("injuries", []),
            lineups=kwargs.get("lineups", []), appearances=kwargs.get("appearances", []), observed_at=observed)
        for row in records:
            append_observation(path, row, observed_at=observed)
            scopes.add((row["event_key"], row["schedule_revision"]))
    return tuple(row for key, schedule in scopes for row in observations_as_of(
        path, key, cutoff=NOW, schedule_revision=schedule) if row["kind"] in kind)


def test_removed_player_cannot_survive_a_newer_full_appearance_envelope(tmp_path):
    old, corrected = detail(99, [7, 8]), detail(99, [8])
    past = ingest(tmp_path, [(NOW - timedelta(hours=3), {"appearances": [old]}),
                            (NOW - timedelta(hours=2), {"appearances": [corrected]})], kind={"appearance"})
    facts = support.availability(tmp_path, "available", kind="confirmed_lineup", started=True)
    facts += support.availability(tmp_path, "out", player=8)
    result = expected_roster(past, facts, cutoff=NOW)
    assert result["central_minutes"] is None or "api-football:player:7" not in result["central_minutes"], result


def test_removed_old_starter_cannot_override_current_absence_after_lineup_correction(tmp_path):
    first, corrected = detail(1, [], completed=False), detail(1, [], completed=False)
    for raw, players in ((first, range(7, 18)), (corrected, range(8, 19))):
        raw["lineups"] = [{"team": {"id": 1}, "startXI": [
            {"player": {"id": player, "pos": "M"}} for player in players], "substitutes": []}]
    injury = {"fixture": corrected["fixture"], "league": corrected["league"], "team": {"id": 1},
              "player": {"id": 7, "type": "Missing Fixture", "reason": "Knee injury"}}
    facts = ingest(tmp_path, [(NOW - timedelta(hours=3), {"lineups": [first]}),
                             (NOW - timedelta(hours=2), {"lineups": [corrected], "injuries": [injury]})],
                   kind={"confirmed_lineup", "availability"})
    past = ingest(tmp_path, [(NOW - timedelta(hours=4), {"appearances": [detail(99, range(7, 19))]})],
                  kind={"appearance"})
    result = expected_roster(past, facts, cutoff=NOW)
    assert result["central_minutes"] is None or result["central_minutes"].get("api-football:player:7") != 60., result


def test_not_yet_valid_appearance_cannot_lend_numeric_minutes(tmp_path):
    original = support.appearance(tmp_path, 60)[0]
    content = {key: original[key] for key in OBSERVATION_FIELDS}
    content["valid_from"] = (NOW + timedelta(days=1)).isoformat()
    path = tmp_path / "future-validity.db"
    append_observation(path, content, observed_at=NOW - timedelta(hours=2))
    selected = observations_as_of(path, original["event_key"], cutoff=NOW, schedule_revision=original["schedule_revision"])
    facts = support.availability(tmp_path, "available", kind="confirmed_lineup", started=True)
    try:
        result = expected_roster(selected, facts, cutoff=NOW)
    except ContextContractError:
        return
    assert result["central_minutes"] is None, result


def participation_payload():
    return {"schema": 1, "version": "football-doubtful-v1", "training_end": (NOW - timedelta(days=1)).isoformat(),
            "training_refs_hash": "c" * 64,
            "population": {"sport": "football", "competitions": ["39"], "formats": ["90min"],
                           "tours": [None], "surfaces": [None], "indoor": [None]},
            "feature_names": ["doubtful"], "base_probability": .25,
            "fit": {"link": "logit", "scale": [1.], "coef": [0.], "alpha": 1., "n_rows": 20}}


def test_real_a1_transport_can_supply_typed_participation_mechanics(tmp_path):
    path = tmp_path / "artifacts.db"
    identity = put_artifact(path, kind="football-participation-v1", payload=participation_payload(), created_at=NOW)
    envelope = load_artifact(path, identity)
    result = expected_roster(support.appearance(tmp_path, 60), support.availability(tmp_path, "doubtful"),
                             cutoff=NOW, participation={"digest": identity, **envelope})
    assert result["central_minutes"] == {"api-football:player:7": 15.}


@pytest.mark.parametrize("change", [{"training_end": (NOW + timedelta(seconds=1)).isoformat()}, {"schema": True}])
def test_hashed_participation_still_cannot_bypass_schema_or_future_training(tmp_path, change):
    payload = {**participation_payload(), **change}
    identity = put_artifact(tmp_path / "artifacts.db", kind="football-participation-v1", payload=payload, created_at=NOW)
    envelope = load_artifact(tmp_path / "artifacts.db", identity)
    with pytest.raises(ContextContractError):
        expected_roster(support.appearance(tmp_path, 60), support.availability(tmp_path, "doubtful"), cutoff=NOW,
                        participation={"digest": identity, **envelope})


def test_conflicting_simultaneous_full_rosters_do_not_merge_members(tmp_path):
    past = ingest(tmp_path, [(NOW - timedelta(hours=2), {"appearances": [detail(99, [7, 8]), detail(99, [8, 9])]})], kind={"appearance"})
    facts = support.availability(tmp_path, "available", kind="confirmed_lineup", started=True)
    facts += support.availability(tmp_path, "out", player=8) + support.availability(tmp_path, "out", player=9)
    result = expected_roster(past, facts, cutoff=NOW)
    assert result["central_minutes"] is None
    assert result["coverage"]["case"] == "conflicting"


def test_partial_new_collection_cannot_borrow_an_older_player_projection(tmp_path):
    past = ingest(tmp_path, [(NOW - timedelta(hours=2), {"appearances": [detail(99, [7, 8])]})], kind={"appearance"})
    only_player_seven = tuple(r for r in past if r["subject_id"].endswith(":7"))
    facts = support.availability(tmp_path, "available", kind="confirmed_lineup", started=True)
    result = expected_roster(only_player_seven, facts, cutoff=NOW)
    assert result["central_minutes"] is None


def test_earlier_cutoff_retains_original_roster_and_receipt(tmp_path):
    original = ingest(tmp_path, [(NOW - timedelta(hours=3), {"appearances": [detail(99, [7, 8])]})], kind={"appearance"})
    revised = ingest(tmp_path, [(NOW - timedelta(hours=2), {"appearances": [detail(99, [8])]})], kind={"appearance"})
    earlier = NOW - timedelta(hours=2, minutes=30)
    facts = support.availability(tmp_path, "available", kind="confirmed_lineup", started=True, observed=NOW - timedelta(hours=3))
    facts += support.availability(tmp_path, "out", player=8, observed=NOW - timedelta(hours=3))
    result = expected_roster(original + revised, facts, cutoff=earlier)
    assert result["central_minutes"]["api-football:player:7"] == 60.
    assert all(r["observed_at"] <= earlier.isoformat() for r in original)


def test_same_members_partial_revisions_cannot_become_one_fictional_roster(tmp_path):
    first, revised = detail(99, [7, 8]), detail(99, [7, 8])
    for row in revised["players"][0]["players"]:
        row["statistics"][0]["games"]["minutes"] = 20
    past = ingest(tmp_path, [(NOW - timedelta(hours=2), {"appearances": [first, revised]})], kind={"appearance"})
    mixed = tuple(row for row in past if row["subject_id"].startswith("api-football:player:") and (row["subject_id"], row["payload"]["minutes"]) in {
        ("api-football:player:7", 60), ("api-football:player:8", 20)})
    assert len(mixed) == 2
    facts = support.availability(tmp_path, "available", kind="confirmed_lineup", started=True)
    facts += support.availability(tmp_path, "out", player=8)
    result = expected_roster(mixed, facts, cutoff=NOW)
    assert result["central_minutes"] is None and result["coverage"]["case"] == "conflicting"


def test_two_same_squad_lineup_revisions_cannot_assemble_twelve_starters(tmp_path):
    first, revised = detail(1, [], completed=False), detail(1, [], completed=False)
    for raw, starters, bench in ((first, range(7, 18), [18]), (revised, range(8, 19), [7])):
        raw["lineups"] = [{"team": {"id": 1}, "startXI": [
            {"player": {"id": player, "pos": "M"}} for player in starters],
            "substitutes": [{"player": {"id": player, "pos": "M"}} for player in bench]}]
    facts = ingest(tmp_path, [(NOW - timedelta(hours=1), {"lineups": [first, revised]})], kind={"confirmed_lineup"})
    mixed = tuple(row for row in facts if row["subject_id"].startswith("api-football:player:") and row["payload"]["started"] is True)
    assert len({row["subject_id"] for row in mixed}) == 12
    assert len({row["payload"]["collection_hash"] for row in mixed}) == 2
    past = ingest(tmp_path, [(NOW - timedelta(hours=2), {"appearances": [detail(99, range(7, 19))]})], kind={"appearance"})
    result = expected_roster(past, mixed, cutoff=NOW)
    assert result["central_minutes"] is None and result["coverage"]["case"] == "conflicting"


def test_feature_reference_binds_original_base_and_complete_event_revision():
    event, base = support.event(), support.reference_base()
    original = football_features(event, (), base, cutoff=NOW)
    assert original["version"] == "football-roster-components-v2"
    assert original["reference_hash"] == digest({"version": "football-context-reference-v2",
        "base_hash": digest(validate_base_distribution(base)), "event_hash": digest(validate_event(event)), "preprocessing": []})
    changed = {**event, "scheduled_start": (support.START + timedelta(days=1)).isoformat(), "schedule_revision": "revised-v2"}
    assert football_features(changed, (), base, cutoff=NOW)["reference_hash"] != original["reference_hash"]


def _full_lineup():
    row = detail(1, [], completed=False)
    row["lineups"] = [{"team": {"id": 1}, "startXI": [
        {"player": {"id": player, "pos": "M"}} for player in range(7, 18)], "substitutes": []}]
    return row


def test_fresh_empty_lineup_withdraws_old_numeric_starters_without_rewriting_history(tmp_path):
    first, withdrawn = _full_lineup(), _full_lineup()
    withdrawn["lineups"] = []
    past = ingest(tmp_path, [(NOW - timedelta(hours=4), {"appearances": [detail(99, range(7, 18))]})], kind={"appearance"})
    facts = ingest(tmp_path, [(NOW - timedelta(hours=2), {"lineups": [first]}),
                             (NOW - timedelta(hours=1), {"lineups": [withdrawn]})], kind={"confirmed_lineup"})
    result = expected_roster(past, facts, cutoff=NOW)
    assert result["central_minutes"] is None
    earlier = expected_roster(past, facts, cutoff=NOW - timedelta(hours=1, minutes=30))
    assert earlier["central_minutes"] == {f"api-football:player:{p}": 60. for p in range(7, 18)}


@pytest.mark.parametrize("whole_array", [True, False])
def test_empty_history_collection_withdraws_older_minutes(tmp_path, whole_array):
    first, withdrawn = detail(99, [7]), detail(99, [7])
    if whole_array:
        withdrawn["players"] = []
    else:
        withdrawn["players"][0]["players"] = []
    past = ingest(tmp_path, [(NOW - timedelta(hours=3), {"appearances": [first]}),
                            (NOW - timedelta(hours=2), {"appearances": [withdrawn]})], kind={"appearance"})
    facts = support.availability(tmp_path, "available", kind="confirmed_lineup", started=True)
    assert expected_roster(past, facts, cutoff=NOW)["central_minutes"] is None


def test_simultaneous_empty_and_nonempty_lineup_are_conflicting_not_latest_wins(tmp_path):
    first, withdrawn = _full_lineup(), _full_lineup()
    withdrawn["lineups"] = []
    past = ingest(tmp_path, [(NOW - timedelta(hours=3), {"appearances": [detail(99, range(7, 18))]})], kind={"appearance"})
    facts = ingest(tmp_path, [(NOW - timedelta(hours=1), {"lineups": [withdrawn, first]})], kind={"confirmed_lineup"})
    result = expected_roster(past, facts, cutoff=NOW)
    assert result["central_minutes"] is None and result["coverage"]["case"] == "conflicting"
