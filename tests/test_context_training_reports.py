"""FitResult is separate closed evidence; it is never an approval payload."""
from copy import deepcopy

import pytest

from context_models.contracts import ContextContractError
from context_models.training import _fit_cohort
from test_context_training_tennis_math import cohort


@pytest.fixture(scope="module")
def fitted():
    rows, cases, config = cohort("tennis:winner")
    return _fit_cohort(rows, cases, config, exclusions=()), config


def test_closed_fit_result_preserves_all_alpha_artifacts_and_train_only_identity(fitted):
    from context_models.training_contracts import validate_fit_result
    report, config = deepcopy(fitted)
    assert validate_fit_result(report, config=config) == report


@pytest.mark.parametrize("change", ["schema", "count", "selected", "effect", "candidate", "alpha", "score",
                                    "training_end", "extra", "config", "scope", "training_refs"])
def test_fit_status_cannot_hide_corrupted_coefficient_or_selection_provenance(fitted, change):
    from context_models.training_contracts import validate_fit_result
    report, config = deepcopy(fitted)
    if change == "schema":
        report["schema"] = True
    elif change == "count":
        report["training_events"] = True
    elif change == "selected":
        report["selected_alpha"] = -1
    elif change == "effect":
        report["effect_hash"] = "e"*64
    elif change == "candidate":
        report["candidate_artifacts"].pop(next(iter(report["candidate_artifacts"])))
    elif change == "alpha":
        report["alpha_scores"][0]["alpha"] = True
    elif change == "score":
        report["alpha_scores"][0]["mean_brier"] = float("nan")
    elif change == "training_end":
        report["artifact"]["training_end"] = config["tune_end"]
    elif change == "extra":
        report["approved"] = True
    elif change == "config":
        report["family_config_hash"] = "f"*64
    elif change == "scope":
        report["artifact"]["population"]["tours"] = ["WTA"]
    else:
        report["training_rows_hash"] = "b"*64
    with pytest.raises(ContextContractError):
        validate_fit_result(report, config=config)


@pytest.mark.parametrize("change", ["unreported", "overlap", "duplicate", "orphan", "status"])
def test_every_requested_case_has_exactly_one_reported_destination(fitted, change):
    from context_models.training_contracts import validate_fit_result
    report, config = deepcopy(fitted)
    omitted = "f" * 64
    exclusion = {"event_key": "espn:tennis:ATP:match:999", "case_hash": omitted,
                 "status": "unsupported", "reason": "source_resolver_unavailable"}
    if change == "unreported":
        report["case_hashes"] = sorted(report["case_hashes"] + [omitted])
    elif change == "overlap":
        exclusion["case_hash"] = report["training_case_hashes"][0]
        report["exclusions"] = [exclusion]
    elif change == "duplicate":
        report["case_hashes"] = sorted(report["case_hashes"] + [omitted])
        report["exclusions"] = [exclusion, deepcopy(exclusion)]
    elif change == "orphan":
        report["exclusions"] = [exclusion]
    else:
        report["case_hashes"] = sorted(report["case_hashes"] + [omitted])
        exclusion["status"] = "approved"
        report["exclusions"] = [exclusion]
    with pytest.raises(ContextContractError):
        validate_fit_result(report, config=config)


def test_an_explicit_unavailable_case_remains_in_the_full_fit_inventory(fitted):
    from context_models.training_contracts import validate_fit_result
    report, config = deepcopy(fitted)
    omitted = "f" * 64
    report["case_hashes"] = sorted(report["case_hashes"] + [omitted])
    report["exclusions"] = [{"event_key": "espn:tennis:ATP:match:999", "case_hash": omitted,
                             "status": "unsupported", "reason": "source_resolver_unavailable"}]
    assert validate_fit_result(report, config=config) == report
