"""Public model-context projection; all cases are synthetic, not effect evidence."""
from copy import deepcopy

import pytest

from context_models.contracts import ContextContractError


def result(role="experimental", state="available", used=.6):
    return {"role": role, "factor_roles": {"injuries": role},
        "selected_market": "home", "base_markets": {"home": .6},
        "used_markets": {"home": used}, "comparison_markets": {"home": used if role == "applied" else .54},
        "delta_pp": {"home": 100*(used-.6)}, "limitations": [],
        "factor_states": {"injuries": state}}


def render(value):
    from context_copy import public_context_summary
    return public_context_summary(value)


def test_known_absence_not_advertised_as_applied():
    card = render(result())
    assert card["used_probability"] == .6 and card["base_probability"] == .6
    assert card["delta_pp"] == 0
    assert "Wirkung offen" in card["summary"]
    assert "eingerechnet" not in card["summary"]


@pytest.mark.parametrize("state", ["missing", "stale", "conflicting", "not_applicable"])
def test_unavailable_absence_cannot_be_called_known_or_applied(state):
    card = render(result("not_applied", state))
    assert "bekannt" not in card["summary"] and "eingerechnet" not in card["summary"]
    assert card["missing"] and "Ausfalldaten" in card["missing"][0]


@pytest.mark.parametrize("delta", [-.08, 0., 1e-12, .05])
def test_applied_values_retain_exact_signed_change(delta):
    raw = result("applied", used=.6+delta)
    card = render(raw)
    assert card["used_probability"] == raw["used_markets"]["home"]
    assert card["delta_pp"] == raw["delta_pp"]["home"]
    assert "eingerechnet" in card["summary"]
    assert "Wirkung offen" not in card["summary"]


@pytest.mark.parametrize("mutation", ["unknown-market", "bad-number", "bad-delta", "different-used", "missing-state", "bad-role", "price", "fake-group", "bad-state", "html-feature", "html-group"])
def test_corrupt_projection_is_not_a_public_context_claim(mutation):
    raw = result()
    if mutation == "unknown-market": raw["selected_market"] = "away"
    elif mutation == "bad-number": raw["used_markets"]["home"] = True
    elif mutation == "bad-delta": raw["delta_pp"]["home"] = 1.
    elif mutation == "different-used": raw["used_markets"]["home"] = .5
    elif mutation == "missing-state": raw["factor_states"] = {}
    elif mutation == "bad-role": raw["factor_roles"]["injuries"] = "verified"
    elif mutation == "price": raw["quote"] = 2.
    elif mutation == "fake-group": raw["factor_groups"] = {"injuries": ["unknown_feature"]}
    elif mutation == "bad-state": raw["factor_states"]["injuries"] = "partial"
    elif mutation == "html-feature": raw["factor_roles"] = raw["factor_states"] = {"<script>": "available"}
    elif mutation == "html-group": raw["factor_groups"] = {"<script>": ["injuries"]}
    with pytest.raises(ContextContractError):
        render(raw)


def test_owning_groups_bind_exact_feature_names_and_do_not_call_all_data_available():
    raw = result("applied", used=.55)
    raw["factor_roles"] = {"home.roster": "applied", "away.roster": "not_applied", "heat": "not_applied"}
    raw["factor_states"] = {"home.roster": "available", "away.roster": "missing", "heat": "missing"}
    raw["factor_groups"] = {"roster": ["home.roster", "away.roster"], "weather": ["heat"]}
    card = render(raw)
    assert "Besetzung teilweise eingerechnet" in card["summary"]
    assert "Wetterdaten fehlen" in card["missing"]


def test_user_projection_keeps_technical_details_outside_summary_and_is_detached():
    raw = result()
    raw["limitations"] = ["provider-secret-diagnostic<script>bad</script>"]
    frozen = deepcopy(raw)
    card = render(raw)
    assert "provider" not in card["summary"] and "<script>" not in card["summary"]
    assert card["admin_details"]["limitations"] == raw["limitations"]
    card["admin_details"]["limitations"].clear()
    assert raw == frozen


def test_technical_feature_without_explicit_group_never_invents_public_reason():
    raw = result()
    raw["factor_roles"] = {"home.injury_reference": "experimental"}
    raw["factor_states"] = {"home.injury_reference": "available"}
    card = render(raw)
    assert "injury" not in card["summary"] and "Ausfälle bekannt" not in card["summary"]


def test_market_projection_uses_selected_orientation_not_first_probability():
    raw = result("applied", used=.55)
    raw["base_markets"]["away"] = .4
    raw["used_markets"]["away"] = .45
    raw["comparison_markets"]["away"] = .45
    raw["delta_pp"]["away"] = 100*(.45-.4)
    raw["selected_market"] = "away"
    card = render(raw)
    assert card["base_probability"] == .4 and card["used_probability"] == .45
    assert card["delta_pp"] == raw["delta_pp"]["away"]


def test_applied_technical_group_does_not_get_a_fictitious_public_cause():
    raw = result("applied", used=.57)
    raw["factor_roles"] = {"unmapped.reference": "applied"}
    raw["factor_states"] = {"unmapped.reference": "available"}
    card = render(raw)
    assert card["summary"] == "Kontext eingerechnet"
    assert "Ausfälle" not in card["summary"] and "Wirkung offen" not in card["summary"]


@pytest.mark.parametrize("mutation", ["applied-unavailable", "factor-overall", "comparison", "extra-comparison", "duplicate-group", "extra-state"])
def test_partial_grouping_does_not_relax_owning_role_or_probability_contract(mutation):
    raw = result("applied", used=.55)
    if mutation == "applied-unavailable": raw["factor_states"]["injuries"] = "stale"
    elif mutation == "factor-overall": raw["role"] = "experimental"
    elif mutation == "comparison": raw["comparison_markets"] = None
    elif mutation == "extra-comparison": raw["comparison_markets"]["other"] = .5
    elif mutation == "duplicate-group": raw["factor_groups"] = {"injuries": ["injuries", "injuries"]}
    elif mutation == "extra-state": raw["factor_states"]["other"] = "available"
    with pytest.raises(ContextContractError):
        render(raw)


def test_fixed_short_group_order_and_nonadditive_total_change():
    raw = result("applied", used=.6)
    raw["factor_roles"] = {name: "applied" for name in ("weather", "recovery", "injuries", "workload")}
    raw["factor_states"] = {name: "available" for name in raw["factor_roles"]}
    card = render(raw)
    assert card["summary"] == "Ausfälle eingerechnet · Belastung eingerechnet · Gesamtprognose unverändert"
    assert "Ausfälle ohne Wirkung" not in card["summary"]


def test_no_available_context_has_a_short_truthful_baseline_caveat():
    raw = result("not_applied")
    raw["factor_roles"], raw["factor_states"] = {}, {}
    card = render(raw)
    assert card["summary"] == "Zusätzliche Kontextdaten fehlen"
    assert card["used_probability"] == card["base_probability"]
