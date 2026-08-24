from types import SimpleNamespace

from challenge_engine import _injury_summary, candidate_context_summary


def _injury(team_id: int, player_id: int, name: str, *, verified=False):
    row = {
        "team": {"id": team_id},
        "player": {"id": player_id, "name": name, "type": "Missing Fixture"},
    }
    if verified:
        row["material_impact"] = {"verified": True, "veto": False}
    return row


def test_injury_coverage_distinguishes_observed_list_from_modeled_impact():
    passed, summary, reason = _injury_summary(
        [
            _injury(10, 101, "Home Player"),
            _injury(11, 201, "Away Player", verified=True),
        ],
        10,
        11,
        True,
    )

    assert passed is True
    assert reason is None
    assert summary["status"] == "observed"
    assert summary["reported_players"] == 2
    assert summary["impact_verified_players"] == 1
    assert summary["impact_assessment_complete"] is False
    assert summary["unassessed_player_names"] == ["Home Player"]


def test_empty_verified_injury_feed_has_complete_impact_coverage():
    passed, summary, reason = _injury_summary([], 10, 11, True)

    assert passed is True
    assert reason is None
    assert summary["reported_players"] == 0
    assert summary["impact_assessment_complete"] is True
    assert summary["reason"] == "Ausfallliste geprüft; keine Ausfälle gemeldet"


def test_malformed_relevant_injury_never_becomes_no_injuries_reported():
    passed, summary, reason = _injury_summary(
        [{"team": {"id": 10}, "player": {}}],
        10,
        11,
        True,
    )

    assert passed is None
    assert reason is None
    assert summary["status"] == "unavailable"
    assert summary["availability"] == "invalid"
    assert "Spieleridentität" in summary["reason"]


def test_unhashable_injury_player_id_fails_closed_instead_of_crashing():
    passed, summary, reason = _injury_summary(
        [
            {
                "team": {"id": 10},
                "player": {
                    "id": {"unexpected": "provider payload"},
                    "name": "Known Name",
                    "type": "Missing Fixture",
                },
            }
        ],
        10,
        11,
        True,
    )

    assert passed is None
    assert reason is None
    assert summary["status"] == "unavailable"
    assert summary["availability"] == "invalid"
    assert "Spieleridentität" in summary["reason"]


def test_injury_assigned_to_another_team_fails_closed():
    passed, summary, reason = _injury_summary(
        [_injury(99, 101, "Wrong Team Player")],
        10,
        11,
        True,
    )

    assert passed is None
    assert reason is None
    assert summary["status"] == "unavailable"
    assert summary["availability"] == "invalid"
    assert "keinem Spielteam" in summary["reason"]


def test_verified_injury_impact_requires_explicit_boolean_decision():
    row = _injury(10, 101, "Home Player")
    row["material_impact"] = {"verified": True}

    passed, summary, reason = _injury_summary([row], 10, 11, True)

    assert passed is True
    assert reason is None
    assert summary["impact_verified_players"] == 0
    assert summary["impact_assessment_complete"] is False
    assert summary["unassessed_player_names"] == ["Home Player"]


def test_verified_injury_impact_rejects_a_non_boolean_veto_decision():
    row = _injury(10, 101, "Home Player")
    row["material_impact"] = {"verified": True, "veto": "false"}

    passed, summary, reason = _injury_summary([row], 10, 11, True)

    assert passed is True
    assert reason is None
    assert summary["impact_verified_players"] == 0
    assert summary["impact_assessment_complete"] is False
    assert summary["unassessed_player_names"] == ["Home Player"]


def test_consumer_context_summary_never_calls_unmodeled_injuries_considered():
    candidate = SimpleNamespace(
        context={
            "h2h": {"status": "neutral"},
            "injuries": {
                "status": "observed",
                "reported_players": 2,
                "impact_assessment_complete": False,
                "unassessed_player_names": ["Home Player"],
            },
            "weather": {"status": "passed"},
            "lineups": {"status": "pending", "required": False},
        }
    )

    summary = candidate_context_summary(candidate)

    assert "Ausfälle Liste geprüft, Wirkung für 1 nicht modelliert" in summary
    assert "Ausfälle berücksichtigt" not in summary
    assert "Aufstellungen für vollständige Bestätigung noch offen" in summary


def test_consumer_context_summary_discloses_required_lineup_gap():
    candidate = SimpleNamespace(
        context={
            "h2h": {"status": "passed"},
            "injuries": {
                "status": "observed",
                "reported_players": 0,
                "impact_assessment_complete": True,
            },
            "weather": {"status": "unavailable"},
            "lineups": {"status": "required_missing", "required": True},
        }
    )

    summary = candidate_context_summary(candidate)

    assert "Ausfälle geprüft, keine gemeldet" in summary
    assert "Wetter nicht verfügbar" in summary
    assert "Aufstellungen fehlen (erforderlich)" in summary
