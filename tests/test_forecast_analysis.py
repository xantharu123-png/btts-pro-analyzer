from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from ev_signal_sources import ModelSignal
from forecast_analysis import (
    build_forecast_analysis,
    project_football_analysis,
    read_football_analysis,
)


NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)


def _row(market_key="RESULT_HOME", probability=0.46361):
    return {
        "candidate_id": f"81:{market_key}", "fixture_id": 81,
        "home_id": 11, "away_id": 12,
        "home_team": "Alpha", "away_team": "Beta",
        "market_key": market_key, "probability": probability,
        "scheduled_start": "2030-01-01T16:00:00+00:00",
        "modeled_at": "2030-01-01T10:00:00+00:00",
        "input_cutoff_at": "2030-01-01T09:59:00+00:00",
        "model_scope": "cross_competition_provisional_forecast",
        "context": {
            "checked_at": "2030-01-01T11:30:00+00:00",
            "injuries": {
                "status": "observed", "availability": "available",
                "coverage_available": True,
                "checked_at": "2030-01-01T11:30:00+00:00",
                "home_missing": 8, "away_missing": 2,
                "impact_assessment_complete": False,
                "home_names": ["NEVER DISPLAY PLAYER"],
                "reason": "NEVER DISPLAY PROVIDER REASON",
            },
            "lineups": {"status": "pending", "checked_at": "2030-01-01T11:30:00+00:00"},
            "probability_integration": {"applied": False},
        },
    }


def _basis(row):
    return {
        **row, "home_team_id": row["home_id"], "away_team_id": row["away_id"],
        "kickoff": row["scheduled_start"],
        "expected_home_goals": 1.527, "expected_away_goals": 1.133,
        "venue_samples": [12, 12], "form_samples": [6, 6],
        "expected_market_home": 5.1, "expected_market_away": 4.2,
        "expected_unit": "Ecken", "reasons": ["NEVER DISPLAY REASON"],
        "bookmaker_odds": 100,
    }


def _signal(row, *, evidence=True):
    return ModelSignal(
        key="card-81", label="Alpha vs Beta", probability=row["probability"],
        probability_haircut=0.08, evidence_stage="SHADOW", policy_version="test",
        detail="NEVER DISPLAY DETAIL", sport="Fußball", event_label="Alpha vs Beta",
        market="Endergebnis", selection="Heimsieg", market_key=row["market_key"],
        candidate_id=row["candidate_id"], fixture_id=row["fixture_id"],
        home_team=row["home_team"], away_team=row["away_team"],
        home_team_id=row["home_id"], away_team_id=row["away_id"],
        scheduled_start=row["scheduled_start"], modeled_at=row["modeled_at"],
        input_cutoff_at=row["input_cutoff_at"], model_scope=row["model_scope"],
        analysis_evidence=read_football_analysis(row) if evidence else None,
    )


def _analysis(row=None, basis=None):
    row = row or _row()
    row["analysis_evidence"] = project_football_analysis(row, model_basis=basis or _basis(row))
    return build_forecast_analysis(_signal(row), now=NOW)


def test_exact_recorded_porto_numbers_are_model_rates_not_score_or_observed_xg():
    row = _row()
    row.update(home_team="FC Porto", away_team="Manchester City")
    analysis = _analysis(row)
    assert "1,53" in analysis.basis and "1,13" in analysis.basis
    assert "für FC Porto höher" in analysis.basis
    assert "FC Porto" in analysis.basis and "Manchester City" in analysis.basis
    assert "Heimsieg" in analysis.basis and "46,4 %" in analysis.basis
    assert "12 Heimspiele" in analysis.samples and "12 Auswärtsspiele" in analysis.samples
    assert "je 6 letzte Spiele beider Teams" in analysis.samples
    assert "Remis oder Auswärtssieg: 53,6 %" in analysis.caution
    assert "unterschiedliche Stärke ihrer Ligen" in analysis.caution
    assert "nicht zuverlässig berücksichtigt" in analysis.caution
    assert "gemeldet" in analysis.caution and "8" in analysis.caution and "2" in analysis.caution
    assert "01.01. 12:30" in analysis.caution
    assert "nicht eingerechnet" in analysis.caution
    assert "Aufstellungen" in analysis.caution
    assert all(word not in (analysis.basis + analysis.caution) for word in (
        "xG", "Endstand", "wahrscheinlichster", "NEVER DISPLAY", "kein Veto", "unmodelliert",
    ))


@pytest.mark.parametrize(("key", "basis_fragment", "risk"), [
    ("RESULT_AWAY", "Auswärtssieg", "Heimsieg oder Remis"),
    ("RESULT_DRAW", "Remis", "Heim- oder Auswärtssieg"),
    ("BTTS_YES", "beide Teams treffen", "mindestens ein Team ohne Tor"),
    ("BTTS_NO", "mindestens ein Team ohne Tor", "beide Teams treffen"),
    ("TOTAL_OVER_2_5", "mindestens 3 Tore insgesamt", "höchstens 2 Tore insgesamt"),
    ("TOTAL_UNDER_2_5", "höchstens 2 Tore insgesamt", "mindestens 3 Tore insgesamt"),
    ("HOME_UNDER_1_5", "höchstens 1 Tor für Alpha", "mindestens 2 Tore für Alpha"),
    ("AWAY_OVER_1_5", "mindestens 2 Tore für Beta", "höchstens 1 Tor für Beta"),
    ("DC_X2", "Remis oder Auswärtssieg", "Heimsieg"),
    ("CORNERS_OVER_8_5", "mindestens 9 Ecken insgesamt", "höchstens 8 Ecken insgesamt"),
    ("AWAY_CORNERS_UNDER_4_5", "höchstens 4 Ecken für Beta", "mindestens 5 Ecken für Beta"),
])
def test_market_sides_have_exact_contracts_and_complements(key, basis_fragment, risk):
    analysis = _analysis(_row(key, 0.63))
    assert basis_fragment in analysis.basis
    assert risk in analysis.caution and "37,0 %" in analysis.caution
    if "CORNERS" in key:
        assert "1,53" not in analysis.basis and "Tore" not in analysis.basis
        assert "5,1" in analysis.basis or "4,2" in analysis.basis


def test_yellow_cards_use_only_matching_separate_count_model():
    row = _row("YELLOW_UNDER_3_5", 0.63)
    basis = _basis(row)
    basis.update(expected_unit="Gelbe Karten", expected_market_home=1.1, expected_market_away=1.4)
    analysis = _analysis(row, basis)
    assert "2,5 Gelbe Karten" in analysis.basis
    assert "höchstens 3 Gelbe Karten" in analysis.basis
    assert "1,53" not in analysis.basis
    mismatch = _analysis(_row("YELLOW_UNDER_3_5", 0.63))
    assert "Modellgrundlagen fehlen" in mismatch.basis
    assert "9,3" not in mismatch.basis


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, -1, "1.527"])
def test_invalid_numerical_evidence_has_truthful_fallback(bad):
    row = _row()
    basis = _basis(row)
    basis["expected_home_goals"] = bad
    analysis = _analysis(row, basis)
    assert "Modellgrundlagen fehlen" in analysis.basis
    assert "1,13" not in analysis.basis
    assert "nan" not in analysis.basis.lower()


@pytest.mark.parametrize(("field", "bad"), [
    ("candidate_id", "other"), ("fixture_id", 99), ("home_id", 99),
    ("away_id", 99), ("home_team", "Wrong"), ("away_team", "Wrong"),
    ("market_key", "RESULT_AWAY"), ("probability", 0.47),
    ("scheduled_start", "2030-01-01T17:00:00+00:00"),
    ("modeled_at", "2030-01-01T10:01:00+00:00"),
    ("input_cutoff_at", "2030-01-01T09:58:00+00:00"),
    ("model_scope", "same_competition"),
])
def test_persisted_evidence_is_exact_bound_to_identity_and_model_revision(field, bad):
    row = _row()
    row["analysis_evidence"] = project_football_analysis(row, model_basis=_basis(row))
    row[field] = bad
    assert read_football_analysis(row) is None


def test_projection_declines_mismatched_native_candidate_and_whitelists_facts():
    row = _row()
    basis = _basis(row)
    basis["home_team_id"] = 99
    assert project_football_analysis(row, model_basis=basis) is None
    evidence = project_football_analysis(row, model_basis=_basis(row))
    assert "NEVER DISPLAY" not in str(evidence)
    assert "bookmaker" not in str(evidence)
    assert evidence["identity"]["modeled_at"] == row["modeled_at"]
    assert evidence["identity"]["input_cutoff_at"] == row["input_cutoff_at"]


@pytest.mark.parametrize("age", [timedelta(minutes=76), timedelta(hours=2), timedelta(minutes=-1)])
def test_stale_or_future_context_never_describes_current_missing_players(age):
    row = _row()
    clock = (NOW - age).isoformat()
    for axis in ("injuries", "lineups"):
        row["context"][axis]["checked_at"] = clock
    analysis = _analysis(row)
    assert "gemeldet" not in analysis.caution
    assert "aktueller Kaderstand nicht belegt" in analysis.caution
    assert "gesund" not in analysis.caution


@pytest.mark.parametrize("field", ["status", "availability", "checked_at", "home_missing"])
def test_partial_unchecked_or_malformed_context_never_becomes_an_advantage(field):
    row = _row()
    row["context"]["injuries"].pop(field)
    analysis = _analysis(row)
    assert "8/2" not in analysis.caution
    assert "Vorteil" not in analysis.caution
    assert "aktueller Kaderstand nicht belegt" in analysis.caution


def test_legacy_missing_and_unknown_sport_evidence_remains_visible_and_price_neutral():
    row = _row()
    signal = _signal(row, evidence=False)
    analysis = build_forecast_analysis(signal, now=NOW)
    assert "Modellgrundlagen fehlen" in analysis.basis
    assert "46,4 %" in analysis.basis and "53,6 %" in analysis.caution
    assert "unterschiedliche Stärke ihrer Ligen" in analysis.caution
    assert analysis == build_forecast_analysis(replace(signal, minimum_odds=7.5), now=NOW)
    unknown = replace(signal, sport="Tennis", market_key="H2H", market="Match Winner", selection="Alpha")
    assert "Modellgrundlagen fehlen" in build_forecast_analysis(unknown, now=NOW).basis


def test_mutated_signal_cannot_reuse_another_event_or_native_side_analysis():
    row = _row()
    row["analysis_evidence"] = project_football_analysis(row, model_basis=_basis(row))
    signal = _signal(row)
    for altered in (replace(signal, home_team="Beta", away_team="Alpha"), replace(signal, home_team_id=99)):
        assert "Modellgrundlagen fehlen" in build_forecast_analysis(altered, now=NOW).basis


def test_hostile_text_is_not_interpreted_or_copied_from_context():
    row = _row()
    row["home_team"] = '<script>alert("x")</script>'
    analysis = _analysis(row)
    # The pure copy remains text; the sole HTML rendering layer escapes it.
    assert row["home_team"] in analysis.basis
    assert "NEVER DISPLAY" not in analysis.basis + analysis.caution


def test_result_comparison_follows_the_selected_native_side_without_inventing_superiority():
    home = _analysis(_row("RESULT_HOME"))
    away = _analysis(_row("RESULT_AWAY"))
    assert "für Alpha höher" in home.basis
    assert "für Beta niedriger" in away.basis
    reversed_row = _row("RESULT_AWAY")
    reversed_row.update(home_team="Beta", away_team="Alpha", home_id=12, away_id=11)
    reversed_basis = _basis(reversed_row)
    reversed_basis.update(expected_home_goals=1.133, expected_away_goals=1.527)
    reversed_analysis = _analysis(reversed_row, reversed_basis)
    assert "für Alpha höher" in reversed_analysis.basis
    assert "Heimsieg oder Remis: 53,6 %" in reversed_analysis.caution
    equal_row = _row()
    equal_basis = _basis(equal_row)
    equal_basis.update(expected_away_goals=1.527)
    assert "höher" not in _analysis(equal_row, equal_basis).basis


@pytest.mark.parametrize("bad", [[], {}, True, None])
def test_malformed_typed_context_and_unit_fail_soft_without_erasing_probability(bad):
    row = _row("CORNERS_OVER_8_5")
    basis = _basis(row)
    basis["expected_unit"] = bad
    row["context"]["injuries"]["status"] = bad
    row["context"]["lineups"]["status"] = bad
    analysis = _analysis(row, basis)
    assert "Modellgrundlagen fehlen" in analysis.basis and "46,4 %" in analysis.basis
    assert "gemeldet" not in analysis.caution


def test_confirmation_due_is_not_silently_treated_as_confirmed_lineup():
    row = _row()
    row["context"]["lineups"]["status"] = "confirmation_due"
    assert "Aufstellungen noch offen" in _analysis(row).caution


def test_boolean_in_untrusted_identity_cannot_equal_native_integer_one():
    row = _row()
    row["fixture_id"] = 1
    row["analysis_evidence"] = project_football_analysis(row, model_basis=_basis(row))
    row["analysis_evidence"]["identity"]["fixture_id"] = True
    assert read_football_analysis(row) is None


def test_out_of_range_context_clock_fails_soft():
    row = _row()
    row["context"]["injuries"]["checked_at"] = "0001-01-01T00:00:00+01:00"
    assert "gemeldet" not in _analysis(row).caution


@pytest.mark.parametrize("bad", [True, 0, "false", None])
def test_explicit_stale_or_untyped_stale_flag_cannot_override_context_clock(bad):
    row = _row()
    row["analysis_evidence"] = project_football_analysis(row, model_basis=_basis(row))
    row["context_stale"] = bad
    analysis = build_forecast_analysis(_signal(row), now=NOW)
    assert "gemeldet" not in analysis.caution


@pytest.mark.parametrize("bad", [True, -1, float("nan"), "8"])
def test_bad_absence_or_sample_counts_are_not_claimed(bad):
    row = _row()
    row["context"]["injuries"]["home_missing"] = bad
    basis = _basis(row)
    basis["venue_samples"] = [bad, 12]
    basis["form_samples"] = [6, bad]
    analysis = _analysis(row, basis)
    assert "gemeldet" not in analysis.caution and analysis.samples == ""


def test_all_configured_football_markets_remain_explainable_with_their_own_unit():
    from challenge_engine import MARKET_BY_KEY

    for key, spec in MARKET_BY_KEY.items():
        row = _row(key, 0.63)
        basis = _basis(row)
        if "yellow" in spec.kind:
            basis["expected_unit"] = "Gelbe Karten"
        analysis = _analysis(row, basis)
        assert "Modellgrundlagen fehlen" not in analysis.basis, key
        assert "63,0 %" in analysis.basis and "37,0 %" in analysis.caution, key
        if spec.kind in {"corner_total", "team_corners", "yellow_total", "team_yellow"}:
            assert "Tore" not in analysis.basis, key
