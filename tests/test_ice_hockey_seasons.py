"""Explicit current NHL scope; synthetic records never certify a real feed."""
from copy import deepcopy

import pytest

from context_models.contracts import ContextContractError, canonical_bytes
from context_models import ice_hockey
from tests.test_ice_hockey_context import NOW, base, event, inputs, scope
from tests.test_ice_hockey_effects import fitted_artifact
from tests.test_ice_hockey_features import features, historical
from tests.test_ice_hockey_sources import raw


def current_scope():
    return dict(season=20262027, game_type=2, neutral_site=False,
                rule_version="nhl-2026-27-rule84")


def current_event():
    return {**event(), "event_key": "nhl:ice_hockey:2026029999"}


def current_base():
    import sports_prematch
    target, history = inputs()
    for row in [target, *history]:
        row.update(season=20262027, context_rule_version="nhl-2026-27-rule84")
        row["provider_event_id"] = row["provider_event_id"].replace("2025", "2026", 1)
    return sports_prematch.hockey_base_distribution(target, history, NOW,
        context_event=current_event(), scope=current_scope())


@pytest.mark.parametrize("season,rule", [(20252026, "nhl-2025-26-rule84"),
                                       (20262027, "nhl-2026-27-rule84")])
@pytest.mark.parametrize("format_code,game_type", [("nhl_reg60_regular_ot_so", 2),
                                                ("nhl_reg60_playoff_ot", 3)])
def test_reviewed_native_scope_preserves_explicit_season_and_phase(season, rule, format_code, game_type):
    declaration = dict(season=season, rule_version=rule, game_type=game_type, neutral_site=False)
    original = deepcopy(declaration)
    assert ice_hockey.hockey_scope(declaration, {**event(), "format": format_code}) == original
    assert declaration == original


@pytest.mark.parametrize("season,rule", [(20262027, "nhl-2025-26-rule84"),
    (20252026, "nhl-2026-27-rule84"), (20272028, "nhl-2027-28-rule84"),
    (20262026, "nhl-2026-27-rule84"), (True, "nhl-2026-27-rule84"),
    (20262027.0, "nhl-2026-27-rule84"), (20262027, None)])
def test_calendar_year_or_old_rule_label_cannot_self_qualify_scope(season, rule):
    with pytest.raises(ContextContractError):
        ice_hockey.hockey_scope({**current_scope(), "season": season, "rule_version": rule}, current_event())


def test_current_season_exports_own_provenance_without_changing_legacy_law_or_old_record():
    legacy = base()
    frozen = canonical_bytes(legacy)
    current = current_base()
    assert current["reference_weights"]["scope"] == current_scope()
    assert current["reference_weights"]["raw_target"]["season"] == 20262027
    assert len(current["history_refs"]) == len(legacy["history_refs"]) == 84
    assert canonical_bytes(current["params"]) == canonical_bytes(legacy["params"])
    assert canonical_bytes(current["markets"]) == canonical_bytes(legacy["markets"])
    assert current["model_hash"] != legacy["model_hash"]
    assert canonical_bytes(base()) == frozen


def test_current_features_cannot_inherit_old_season_effect_or_exposure_vocabulary():
    from tests.test_ice_hockey_features import full_inputs
    old, old_inputs = full_inputs()
    old_features = features(old_inputs, old)
    old_effect = fitted_artifact(old_features)
    current = current_base()
    observations = [*historical(current), *(raw(kind, ev=current_event())
                    for kind in ("projection", "starter", "availability"))]
    for item in observations:
        item["scope"] = current_scope()
    current_features = features(observations, current, current=current_event())
    assert current_features["coverage"] != old_features["coverage"]
    assert any("/20262027/" in name for name in current_features["values"])
    assert not any("/20252026/" in name for name in current_features["values"])
    with pytest.raises(ContextContractError):
        ice_hockey.apply_hockey_effect(current, current_features, old_effect, event=current_event())
    assert old["reference_weights"]["scope"] == scope()


def test_reviewed_season_inventory_is_not_a_mutable_runtime_override():
    with pytest.raises(TypeError):
        ice_hockey.SEASON_RULES[20272028] = "nhl-2027-28-rule84"
