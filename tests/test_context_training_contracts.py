"""Closed, price-free D1/D2 configuration. The fixture is not a fitted effect."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from context_models.contracts import ContextContractError, digest


def winner_config():
    return json.loads((Path(__file__).parent / "fixtures/context/training/tennis-winner-family-v1.json").read_text(encoding="utf-8"))


def test_shared_config_is_detached_canonical_and_hashes_plain_payload():
    from context_models.training_contracts import validate_family_config
    value = winner_config()
    original = deepcopy(value)
    normalized = validate_family_config(value)
    assert normalized == value and normalized is not value
    assert digest(normalized) != digest({"kind": "context-family-config-v1", "payload": normalized})
    normalized["feature_names"].reverse()
    assert value == original


@pytest.mark.parametrize("key,value", [
    ("schema", True), ("schema", 2), ("sport", "cricket"), ("family", "tennis:serve"),
    ("feature_version", "tennis-performed-load-v1"), ("feature_names", []),
    ("feature_names", ["odds"]), ("feature_names", ["observed_sets_1d_a"]),
    ("model_variant", "unconstrained-v1"), ("base_versions", []),
    ("base_versions", ["tennis-context-comparison-v1"]), ("head_links", {"winner": "log_rate"}),
    ("reference_version", "tennis-context-reference-v1"),
    ("preprocessing_artifacts", {"future": "a" * 64}),
    ("groups", {"workload": ["observed_sets_1d_delta"]}),
    ("groups", {"workload": ["observed_recovery_exact_hours_delta"], "recovery": ["observed_sets_1d_delta"]}),
    ("joint_calibration", {"kind": "old_winner_curve"}),
    ("target_markets", ["winner_a", "total_games"]), ("target_markets", ["winner_b", "winner_a"]),
    ("outcome_contract", "tennis-completed-serve-v1"),
    ("train_end", "2026-09-01T00:00:00Z"), ("train_end", "2026-08-01"),
    ("alpha_grid", [0.01, .1, 1., 10.]), ("alpha_grid", [0.01, .1, True, 10., 100.]),
])
def test_unreviewed_or_ambiguous_family_contract_is_not_fitted(key, value):
    from context_models.training_contracts import validate_family_config
    config = winner_config()
    config[key] = value
    with pytest.raises(ContextContractError):
        validate_family_config(config)


def test_fixed_tennis_population_does_not_mix_tours_surfaces_or_environment():
    from context_models.training_contracts import validate_family_config
    for key, values in (("tours", ["ATP", "WTA"]), ("surfaces", ["Clay", "Hard"]), ("indoor", [False, True])):
        config = winner_config()
        config["population"][key] = values
        with pytest.raises(ContextContractError):
            validate_family_config(config)


def test_unknown_fields_never_silently_change_a_frozen_experiment():
    from context_models.training_contracts import validate_family_config
    config = winner_config()
    config["price_threshold"] = 1.5
    with pytest.raises(ContextContractError):
        validate_family_config(config)


@pytest.mark.parametrize("field", ["family", "feature_version", "reference_version", "model_variant", "coverage"])
@pytest.mark.parametrize("value", [None, [], {}, True])
def test_malformed_json_type_uses_the_owning_contract_error(field, value):
    from context_models.training_contracts import validate_family_config
    config = winner_config()
    config[field] = value
    with pytest.raises(ContextContractError):
        validate_family_config(config)


@pytest.mark.parametrize("value", [None, [], {}, True])
def test_malformed_coverage_member_type_uses_the_owning_contract_error(value):
    from context_models.training_contracts import validate_family_config
    config = winner_config()
    config["coverage"]["case"] = value
    with pytest.raises(ContextContractError):
        validate_family_config(config)
