"""Synthetic native receipts prove load mechanics, not predictive quality."""
from datetime import timedelta

import pytest

from context_models.contracts import canonical_timestamp
from context_observations import append_observation, observations_as_of
from context_sources.football import _record
from context_training_helpers import NOW


def event(fixture=9000, *, home=1, away=2, start=None):
    return dict(event_key=f"api-football:football:{fixture}", sport="football",
        competition="39", format="90min", home_id=f"api-football:team:{home}",
        away_id=f"api-football:team:{away}", scheduled_start=canonical_timestamp(start or NOW + timedelta(hours=5)),
        schedule_revision="s1", status="scheduled")


def appearance(tmp_path, fixture, team, minutes, *, player=7, days=2, received=None, ended=None):
    observed = received or NOW - timedelta(days=days) + timedelta(hours=3)
    ev = event(fixture, start=NOW - timedelta(days=days))
    payload = dict(player_id=f"api-football:player:{player}", team_id=f"api-football:team:{team}",
        fixture_id=ev["event_key"], minutes=minutes, regulation_minutes=minutes,
        exposure_kind="regulation_reported", started=True, role="M",
        result_observed_at=canonical_timestamp(observed), event_start=None,
        event_end=canonical_timestamp(ended) if ended else None, scheduled_start=ev["scheduled_start"],
        performance={key: None for key in ("goals", "shots", "passes", "tackles", "duels", "cards")})
    return receipt(tmp_path, ev, payload, kind="appearance", observed=observed,
                   schema="fixture-players-v3-context-v1", complete=minutes is not None)


def lineup(tmp_path, *, player=7, team=1, started=True):
    ev = event()
    payload = dict(player_id=f"api-football:player:{player}", team_id=f"api-football:team:{team}",
                   status="available", started=started, role="M", scheduled_start=ev["scheduled_start"])
    return receipt(tmp_path, ev, payload, kind="confirmed_lineup", observed=NOW,
                   schema="lineups-v3-context-v1", complete=True)


def receipt(tmp_path, ev, payload, *, kind, observed, schema, complete):
    from context_models.contracts import digest
    raw = _record(ev, payload["player_id"], kind, payload, observed_at=observed,
                  complete=complete, schema=schema)
    path = tmp_path / (digest(raw) + ".db")
    append_observation(path, raw, observed_at=observed)
    return observations_as_of(path, ev["event_key"], cutoff=observed, schedule_revision=ev["schedule_revision"])


def features(rows):
    from context_models.football_player_load import player_load_features
    return player_load_features(event(), rows, cutoff=NOW)


def test_native_player_combines_club_and_national_minutes_without_changing_club_role(tmp_path):
    rows = (appearance(tmp_path, 101, 1, 60, days=6)
            + appearance(tmp_path, 102, 100, 90, days=2) + lineup(tmp_path))
    got = features(rows)
    # Exactly 60 club + 90 national minutes; national 90 never changes the
    # confirmed club starter's expected role from 60 to an average of 75.
    assert got["values"]["load.home.reported_minutes_schedule_7d"] == 150.
    assert got["values"]["load.home.expected_minutes"] == 60.
    assert got["values"]["load.home.recovery_min_hours"] == 50.
    assert got["values"]["load.home.recovery_exact_hours"] is None
    refs = got["refs"]["load.home.reported_minutes_schedule_7d"]
    assert all(row["digest"] in refs for row in rows)
    assert got["states"]["load.away.reported_minutes_schedule_7d"] == "missing"


def test_repeated_receipt_counts_one_match_and_keeps_first_terminal_time(tmp_path):
    first = appearance(tmp_path, 102, 100, 90, days=2)
    recheck = appearance(tmp_path, 102, 100, 90, days=2, received=NOW - timedelta(hours=1))
    got = features(appearance(tmp_path, 101, 1, 60, days=6) + first + recheck + lineup(tmp_path))
    assert got["values"]["load.home.reported_minutes_schedule_7d"] == 150.
    assert got["values"]["load.home.recovery_min_hours"] == 50.
    assert first[0]["digest"] in got["refs"]["load.home.recovery_min_hours"]


def test_opponent_and_other_player_never_enter_target_players_load(tmp_path):
    got = features(appearance(tmp_path, 101, 1, 60, days=6)
        + appearance(tmp_path, 102, 100, 90, days=2, player=99) + lineup(tmp_path))
    assert got["values"]["load.home.reported_minutes_schedule_7d"] == 60.


def test_late_receipt_cannot_enter_earlier_load(tmp_path):
    got = features(appearance(tmp_path, 101, 1, 60, days=6)
        + appearance(tmp_path, 102, 100, 90, days=2, received=NOW + timedelta(minutes=1)) + lineup(tmp_path))
    assert got["values"]["load.home.reported_minutes_schedule_7d"] == 60.


def test_unknown_reported_minutes_do_not_become_zero_or_a_healthy_load(tmp_path):
    got = features(appearance(tmp_path, 101, 1, 60, days=6)
        + appearance(tmp_path, 102, 100, None, days=2) + lineup(tmp_path))
    assert got["values"]["load.home.reported_minutes_schedule_7d"] is None
    assert got["states"]["load.home.reported_minutes_schedule_7d"] == "missing"
    assert got["values"]["load.home.recovery_min_hours"] is None


def test_conflicting_minutes_cannot_choose_convenient_first_revision(tmp_path):
    got = features(appearance(tmp_path, 101, 1, 60, days=6)
        + appearance(tmp_path, 102, 100, 90, days=2)
        + appearance(tmp_path, 102, 100, 20, days=2) + lineup(tmp_path))
    assert got["values"]["load.home.reported_minutes_schedule_7d"] is None
    assert got["states"]["load.home.reported_minutes_schedule_7d"] == "conflicting"


def test_missing_recent_match_does_not_prove_zero_minutes_in_a_window(tmp_path):
    got = features(appearance(tmp_path, 101, 1, 60, days=10) + lineup(tmp_path))
    assert got["values"]["load.home.reported_minutes_schedule_7d"] is None
    assert got["values"]["load.home.reported_minutes_schedule_14d"] == 60.


def test_actual_end_stays_distinct_from_terminal_receipt_bound(tmp_path):
    got = features(appearance(tmp_path, 101, 1, 60, days=6)
        + appearance(tmp_path, 102, 100, 90, days=2, ended=NOW - timedelta(days=2) + timedelta(hours=2))
        + lineup(tmp_path))
    assert got["values"]["load.home.recovery_min_hours"] == 51.
    assert got["values"]["load.home.recovery_exact_hours"] == 51.


def test_missing_current_role_cannot_use_international_role_as_club_lineup(tmp_path):
    got = features(appearance(tmp_path, 102, 100, 90, days=2) + lineup(tmp_path))
    assert got["values"]["load.home.expected_minutes"] is None
    assert got["values"]["load.home.reported_minutes_schedule_7d"] is None


def test_scheduled_order_never_overstates_recovery_when_an_older_fixture_ends_later(tmp_path):
    got = features(appearance(tmp_path, 101, 1, 60, days=6, received=NOW - timedelta(hours=1))
        + appearance(tmp_path, 102, 100, 90, days=2) + lineup(tmp_path))
    assert got["values"]["load.home.recovery_min_hours"] == 6.
    assert got["values"]["load.home.recovery_exact_hours"] is None


def test_exact_rest_requires_known_end_to_dominate_other_unknown_terminal_bounds(tmp_path):
    got = features(appearance(tmp_path, 101, 1, 60, days=6, received=NOW - timedelta(hours=1))
        + appearance(tmp_path, 102, 100, 90, days=2, ended=NOW - timedelta(days=2) + timedelta(hours=2))
        + lineup(tmp_path))
    assert got["values"]["load.home.recovery_min_hours"] == 6.
    assert got["values"]["load.home.recovery_exact_hours"] is None
