from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from context_models.contracts import ContextContractError, digest
from context_models.football import roster_delta, expected_roster, football_features
from context_observations import append_observation, observations_as_of
from context_sources.football import _record

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
START = NOW + timedelta(hours=5)


def event(fixture=1, *, start=START):
    return {"event_key": f"api-football:football:{fixture}", "sport": "football", "competition": "39",
            "format": "90min", "home_id": "api-football:team:1", "away_id": "api-football:team:2",
            "scheduled_start": start.isoformat(), "schedule_revision": "s1", "status": "scheduled"}


def selected(tmp_path, payload, *, kind, fixture=1, observed=NOW, player=7, complete=True):
    row = _record(event(fixture), f"api-football:player:{player}", kind, payload, observed_at=observed,
                  complete=complete, schema=("fixture-players-v3-context-v1" if kind == "appearance" else
                  "lineups-v3-context-v1" if kind == "confirmed_lineup" else "injuries-v3-context-v1"))
    path = tmp_path / f"data-{digest(row)[:16]}.db"
    append_observation(path, row, observed_at=observed)
    return observations_as_of(path, row["event_key"], cutoff=NOW, schedule_revision="s1")


def appearance(tmp_path, minutes, *, player=7, fixture=99, started=True, team=1):
    return selected(tmp_path, {"player_id": f"api-football:player:{player}", "team_id": f"api-football:team:{team}",
                    "fixture_id": f"api-football:football:{fixture}", "minutes": minutes,
                    "regulation_minutes": minutes, "exposure_kind": "regulation_reported", "started": started,
                    "role": "M", "result_observed_at": (NOW - timedelta(days=1)).isoformat(),
                    "event_start": None, "event_end": None, "scheduled_start": (NOW - timedelta(days=2)).isoformat(),
                    "performance": {k: None for k in ("goals", "shots", "passes", "tackles", "duels", "cards")}},
                    kind="appearance", fixture=fixture, player=player, observed=NOW - timedelta(hours=2))


def availability(tmp_path, status, *, player=7, kind="availability", started=None, observed=NOW, team=1):
    payload = {"player_id": f"api-football:player:{player}", "team_id": f"api-football:team:{team}", "status": status}
    if kind == "confirmed_lineup":
        payload.update(started=started, role="M")
    else:
        payload.update(reported_type="Doubtful" if status == "doubtful" else "Missing Fixture",
                       reported_reason=None, absence_category="unspecified")
    return selected(tmp_path, payload, kind=kind, observed=observed, player=player)


def test_reference_roster_prevents_double_absence_deduction():
    reference = {"starter": 0., "replacement": 90.}
    assert roster_delta(reference, reference) == {"starter": 0., "replacement": 0.}
    assert roster_delta(reference, {"starter": 60., "replacement": 30.}) == {"starter": 2 / 3, "replacement": -2 / 3}


@pytest.mark.parametrize("value", [True, -1, 91, float("nan"), "20", None])
def test_roster_delta_requires_known_regulation_minutes(value):
    with pytest.raises(ContextContractError):
        roster_delta({"player": value}, {"player": 0})
    with pytest.raises(ContextContractError):
        roster_delta({"player": 0}, {"player": value})


def test_roster_delta_requires_same_complete_identities():
    with pytest.raises(ContextContractError):
        roster_delta({"player": 0}, {"another": 90})


def test_expected_roster_out_is_zero_not_generic_percent_penalty(tmp_path):
    rows = appearance(tmp_path, 75)
    result = expected_roster(rows, availability(tmp_path, "out"), cutoff=NOW)
    assert result["central_minutes"] == {"api-football:player:7": 0.}
    assert result["coverage"]["case"] == "reported_players"
    assert result["refs"]


def test_confirmed_start_uses_starter_history_not_ninety_and_overrides_doubt(tmp_path):
    past = appearance(tmp_path, 60) + appearance(tmp_path, 80, fixture=98) + appearance(tmp_path, 20, fixture=97, started=False)
    facts = availability(tmp_path, "doubtful") + availability(tmp_path, "available", kind="confirmed_lineup", started=True)
    result = expected_roster(past, facts, cutoff=NOW)
    assert result["central_minutes"] == {"api-football:player:7": 70.}
    assert not result["scenarios"]


def test_unknown_starter_minutes_cannot_use_bench_history(tmp_path):
    result = expected_roster(appearance(tmp_path, 20, started=False),
                             availability(tmp_path, "available", kind="confirmed_lineup", started=True), cutoff=NOW)
    assert result["central_minutes"] is None


def test_doubtful_player_has_named_extremes_not_fifty_fifty(tmp_path):
    result = expected_roster(appearance(tmp_path, 60), availability(tmp_path, "doubtful"), cutoff=NOW)
    assert result["central_minutes"] is None
    assert result["scenarios"] == {"all_doubtful_present": {"api-football:player:7": 60.},
                                   "all_doubtful_absent": {"api-football:player:7": 0.}}


def test_absent_report_stale_or_missing_does_not_assert_full_squad_health(tmp_path):
    past = appearance(tmp_path, 80)
    assert expected_roster(past, (), cutoff=NOW)["central_minutes"] is None
    result = expected_roster(past, availability(tmp_path, "out", observed=NOW - timedelta(hours=7)), cutoff=NOW)
    assert result["central_minutes"] is None
    assert result["coverage"]["case"] == "incomplete"


def test_late_or_tampered_appearance_cannot_create_an_expected_player(tmp_path):
    rows = appearance(tmp_path, 80)
    changed = deepcopy(rows)
    changed[0]["payload"]["regulation_minutes"] = 0
    with pytest.raises(ContextContractError):
        expected_roster(changed, availability(tmp_path, "out"), cutoff=NOW)


def test_same_receipt_conflict_is_unknown_not_first_row_wins(tmp_path):
    facts = availability(tmp_path, "out") + availability(tmp_path, "doubtful")
    result = expected_roster(appearance(tmp_path, 80), facts, cutoff=NOW)
    assert result["central_minutes"] is None
    assert result["coverage"]["case"] == "conflicting"


def test_unverified_participation_dictionary_cannot_make_a_central_forecast(tmp_path):
    with pytest.raises(ContextContractError):
        expected_roster(appearance(tmp_path, 80), availability(tmp_path, "doubtful"), cutoff=NOW,
                        participation={"probability": .5})


def reference_base():
    # A synthetic closed provenance object, not a real reconstructed base.
    from test_context_contracts import football_reference_base
    base = football_reference_base()
    return {**base, "event_key": event()["event_key"], "cutoff": NOW.isoformat()}


def test_features_use_component_sample_support_without_deducting_league_prior(tmp_path):
    past = appearance(tmp_path, 75) + appearance(tmp_path, 90, player=8, team=2)
    facts = availability(tmp_path, "out") + availability(tmp_path, "available", player=8, team=2,
                                                       kind="confirmed_lineup", started=True)
    features = football_features(event(), past + facts, reference_base(), cutoff=NOW)
    key = "home.venue_attack.goals.api-football:player:7"
    assert features["values"][key] == pytest.approx((0 - 75) / 90 * .25 * .75 * .5)
    assert features["states"][key] == "available"
    assert features["refs"][key]
    assert features["values"]["away.venue_attack.goals.api-football:player:8"] == 0.


def test_unresolved_reference_or_missing_regulation_exposure_keeps_features_unknown(tmp_path):
    base = reference_base()
    base["history_refs"][0]["roster_join"] = "unresolved"
    features = football_features(event(), appearance(tmp_path, 80) + availability(tmp_path, "out"), base, cutoff=NOW)
    assert not any(value is not None for value in features["values"].values())
    assert not any(features["refs"].values())


def test_feature_identity_scope_and_cutoff_cannot_migrate_to_another_match(tmp_path):
    with pytest.raises(ContextContractError):
        football_features(event(2), (), reference_base(), cutoff=NOW)
    with pytest.raises(ContextContractError):
        football_features(event(), (), reference_base(), cutoff=NOW - timedelta(hours=1))


def test_new_football_features_never_claim_doubtful_central_or_price_support(tmp_path):
    past = appearance(tmp_path, 80) + appearance(tmp_path, 90, player=8, team=2)
    facts = availability(tmp_path, "doubtful") + availability(tmp_path, "out", player=8, team=2)
    feature = football_features(event(), past + facts, reference_base(), cutoff=NOW)
    assert not any(value is not None for value in feature["values"].values())
    assert feature["coverage"]["case"] == "doubtful_scenarios"
    with pytest.raises(ContextContractError):
        football_features({**event(), "current_odds": 3.4}, past + facts, reference_base(), cutoff=NOW)
