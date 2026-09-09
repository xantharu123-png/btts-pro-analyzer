"""Synthetic-only D1/B7 numerical law tests; real tennis replay is unsupported.

These intentionally do not manufacture source receipts or a native/name join.
They exercise the internal already-resolved mathematical seam; a public fit
with these objects must remain rejected.
"""
from copy import deepcopy
from datetime import timedelta
import math

import numpy as np
import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from context_models.training import _fit_cohort
from context_models.training_cases import _case_rows
from context_models.tennis import tennis_reference_hash
from context_models.tennis_effect import SERVE_VARIANT, WINNER_VARIANT, SERVE_BASE_VERSION
from context_training_helpers import NOW, envelope
from test_context_training_contracts import winner_config
from test_tennis_context_model import base, features, event


def cohort(family):
    serve = family == "tennis:serve"
    config = winner_config()
    names = ["observed_sets_1d_a", "observed_sets_1d_b", "observed_sets_1d_delta"] if serve else ["observed_sets_1d_delta"]
    config.update(family=family, feature_names=names, model_variant=SERVE_VARIANT if serve else WINNER_VARIANT,
        base_versions=[SERVE_BASE_VERSION if serve else "tennis-winner-predecision-tour-state-v1"],
        head_links={"hold_a": "logit", "hold_b": "logit"} if serve else {"winner": "logit"}, groups={"workload": names},
        outcome_contract="tennis-completed-serve-v1" if serve else "tennis-completed-winner-v1",
        train_end=canonical_timestamp(NOW-timedelta(days=5)), tune_end=canonical_timestamp(NOW-timedelta(days=1)))
    cases, rows = [], []
    for index, (days, a, b) in enumerate(((9, 5., 2.), (8, 2., 5.), (7, 4., 3.), (6, 3., 4.), (4, 4., 2.), (3, 2., 4.))):
        decision = NOW-timedelta(days=days)
        ev = event(event_key=f"espn:tennis:ATP:match:{100+index}", scheduled_start=canonical_timestamp(decision+timedelta(hours=1)))
        original = base(family=family, p=.5, hold_a=.75, hold_b=.75)
        original.update(version=config["base_versions"][0], event_key=ev["event_key"], cutoff=canonical_timestamp(decision))
        feats = features(original, ev=ev, load_a=a, load_b=b)
        feats.update(cutoff=original["cutoff"], reference_hash=tennis_reference_hash(original, ev))
        home_wins = a < b
        result = {"winner_id": ev["home_id"] if home_wins else ev["away_id"]}
        if serve:
            result.update(set_scores=[{"home": 6 if home_wins else 4, "away": 4 if home_wins else 6}] * 2,
                held_games_home=8 if home_wins else 6, service_games_home=10,
                held_games_away=6 if home_wins else 8, service_games_away=10)
        # NOT a B1 receipt: explicit unit data for the internal arithmetic seam.
        outcome = {"digest": digest({"synthetic_case": index}), "observed_at": canonical_timestamp(decision+timedelta(hours=4)),
                   "payload": {"result": result}}
        case = envelope("context-training-case-v1", {"schema": 1, "event": ev, "base": original, "features": feats,
            "replay_ref": "a"*64, "outcome_ref": outcome["digest"], "event_identity_hash": "c"*64,
            "family_config_hash": digest(config), "preprocessing_refs": []})
        resolved = {"case": case, "artifacts": {}, "observations": (outcome,)}
        rows.extend(_case_rows(resolved, config))
        cases.append(resolved)
    return tuple(rows), tuple(cases), config


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
def test_actual_d1_numeric_fit_respects_b7_law_without_claiming_real_source(family):
    from context_models.tennis_effect import apply_tennis_effect
    from context_models.training import fit_family
    rows, cases, config = cohort(family)
    report = _fit_cohort(rows, cases, config, exclusions=())
    assert report["status"] == "fitted" and report["training_events"] == 4 and report["tuning_events"] == 2
    artifact = report["artifact"]
    expected_head_rows = 8 if family == "tennis:serve" else 4
    assert {head["n_rows"] for head in artifact["heads"].values()} == {expected_head_rows}
    left, right = cases[-2]["case"]["payload"], cases[-1]["case"]["payload"]
    a = apply_tennis_effect(left["base"], left["features"], artifact, event=left["event"])
    b = apply_tennis_effect(right["base"], right["features"], artifact, event=right["event"])
    assert a["markets"]["winner_a"] + b["markets"]["winner_a"] == pytest.approx(1., abs=1e-12)
    real_report = fit_family((), config, cases=cases)
    assert real_report["status"] == "unsupported" and real_report["artifact"] is None
    assert {row["reason"] for row in real_report["exclusions"]} == {"native_to_state_key_source_resolver_unavailable"}


def test_serve_uses_exactly_one_joint_train_fit_per_alpha_and_derived_mirrored_head(monkeypatch):
    import context_models.offset as offset
    rows, cases, config = cohort("tennis:serve")
    calls = []
    actual = offset.fit_offset
    def counted(x, base, y, **kwargs):
        calls.append((x.copy(), base.copy(), y.copy(), deepcopy(kwargs)))
        return actual(x, base, y, **kwargs)
    monkeypatch.setattr(offset, "fit_offset", counted)
    report = _fit_cohort(rows, cases, config, exclusions=())
    assert report["status"] == "fitted" and len(calls) == 5
    assert all(x.shape == (8, 3) and options["trials"].tolist() == [10.]*8 for x, _, _, options in calls)
    for artifact in report["candidate_artifacts"].values():
        a, b = artifact["heads"]["hold_a"], artifact["heads"]["hold_b"]
        assert b["coef"] == [a["coef"][1], a["coef"][0], -a["coef"][2]]
        assert b["scale"] == [a["scale"][1], a["scale"][0], a["scale"][2]]


def test_observed_set_contracts_are_scored_from_actual_result_not_probability():
    from context_models.training import case_market_targets
    _, cases, _ = cohort("tennis:serve")
    targets = case_market_targets(cases[-1], ["winner_a", "winner_b", "exact_2_sets", "over_2_5_sets",
        "under_2_5_sets", "correct_score_2_0", "set_handicap_a_minus_1_5", "over_19.5_games",
        "under_19.5_games", "game_handicap_a_minus_3_5", "tiebreak_yes", "tiebreak_no"])
    assert targets == {"winner_a": 1, "winner_b": 0, "exact_2_sets": 1, "over_2_5_sets": 0,
        "under_2_5_sets": 1, "correct_score_2_0": 1, "set_handicap_a_minus_1_5": 1, "over_19.5_games": 1,
        "under_19.5_games": 0, "game_handicap_a_minus_3_5": 1, "tiebreak_yes": 0, "tiebreak_no": 1}


def test_fitting_cannot_round_inexact_json_integer_before_b2_validation():
    from context_models.training import _array
    with pytest.raises(ContextContractError, match="exactly"):
        _array([[2**53+1]])
    assert _array([[2**54]]).tolist() == [[2**54]]
