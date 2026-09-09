"""Pure selected-market copy from a worker-verified context result.

No prediction, source lookup, statistical approval, price or markup belongs
here. This projection checks its display contract, not empirical/source truth.
Owning adapters supply explicit feature groups; unknown names are never guessed
into a medical or numerical explanation. Only static labels enter public text.
"""
from copy import deepcopy

from context_models.contracts import (
    ContextContractError, DATA_STATES, MODEL_ROLES, require_list,
    require_number, require_object, require_text, validate_markets,
)


_LABELS = {
    "injuries": ("Ausfälle", "Ausfalldaten"),
    "roster": ("Besetzung", "Besetzungsdaten"),
    "workload": ("Belastung", "Belastungsdaten"),
    "recovery": ("Erholung", "Erholungsdaten"),
    "weather": ("Wetter", "Wetterdaten"),
}
_REQUIRED = {"role", "factor_roles", "factor_states", "selected_market",
    "base_markets", "used_markets", "comparison_markets", "delta_pp", "limitations"}
_OPTIONAL = {"event_key", "base_hash", "effect_hash", "feature_refs", "base_params",
    "comparison_params", "used_params", "approval_hash", "certified_markets", "factor_groups"}
_RANK = {"not_applied": 0, "experimental": 1, "applied": 2}


def public_context_summary(result: dict) -> dict:
    """Project exactly the selected market; technical details stay admin-only.

    An applied group with only some modeled members is labelled partial. Total
    change is not attributed to individual groups: effects may cancel/interact.
    Display-precision zero never overwrites the exact stored probability/delta.
    """
    require_object(result, _REQUIRED, optional=_OPTIONAL, label="context display input")
    role = result["role"]
    if type(role) is not str or role not in MODEL_ROLES:
        raise ContextContractError("unknown display model role")
    base, used = (validate_markets(result[key]) for key in ("base_markets", "used_markets"))
    if set(base) != set(used):
        raise ContextContractError("display distributions have different markets")
    market = require_text(result["selected_market"], "selected market", code=True)
    if market not in used:
        raise ContextContractError("selected display market is outside the actual distribution")
    comparison = result["comparison_markets"]
    if comparison is not None:
        comparison = validate_markets(comparison)
        if set(comparison) != set(base):
            raise ContextContractError("display comparison has different markets")
    if used != (comparison if role == "applied" else base):
        raise ContextContractError("display distribution contradicts its model role")
    require_object(result["delta_pp"], set(used), label="display deltas")
    for key, value in result["delta_pp"].items():
        require_number(value, "actual displayed delta", minimum=-100, maximum=100)
        if value != 100*(used[key]-base[key]):
            raise ContextContractError("display delta does not equal the actual selected change")
    roles, states = result["factor_roles"], result["factor_states"]
    if type(roles) is not dict:
        raise ContextContractError("factor roles must be a mapping")
    require_object(states, set(roles), label="display factor states")
    for name, state in states.items():
        require_text(name, "factor name", code=True)
        if type(state) is not str or state not in DATA_STATES:
            raise ContextContractError("unknown factor data state")
        if type(roles[name]) is not str or roles[name] not in MODEL_ROLES or _RANK[roles[name]] > _RANK[role]:
            raise ContextContractError("factor role exceeds the actual overall role")
        if roles[name] != "not_applied" and state != "available":
            raise ContextContractError("unavailable factor cannot claim a modeled effect")
    limitations = require_list(result["limitations"], "display limitations")
    for limitation in limitations:
        require_text(limitation, "admin limitation")
    groups = result.get("factor_groups")
    if groups is None:
        groups = {name: [name] for name in roles if name in _LABELS}
    if type(groups) is not dict or not set(groups) <= set(_LABELS):
        raise ContextContractError("unknown public factor grouping")
    for members in groups.values():
        require_list(members, "factor group members")
        if not members or any(type(name) is not str or name not in roles for name in members) or len(set(members)) != len(members):
            raise ContextContractError("factor group must bind existing distinct members")

    applied, known, missing = [], [], []
    for group in _LABELS:
        members = groups.get(group)
        if not members:
            continue
        label, data_label = _LABELS[group]
        active = [name for name in members if roles[name] == "applied"]
        available = [name for name in members if states[name] == "available"]
        if active:
            applied.append(label + (" eingerechnet" if len(active) == len(members) else " teilweise eingerechnet"))
        elif len(available) == len(members):
            known.append(label + " bekannt; Wirkung offen")
        if len(available) != len(members):
            missing.append(data_label + (" unvollständig" if available else " fehlen"))
    pieces = (applied + known)[:2]
    if missing:
        pieces.append(missing[0])
    if not pieces:
        pieces = ["Kontext eingerechnet" if role == "applied" else
                  "Zusätzliche Kontextwirkung offen" if any(state == "available" for state in states.values())
                  else "Zusätzliche Kontextdaten fehlen"]
    if role == "applied" and result["delta_pp"][market] == 0:
        pieces.append("Gesamtprognose unverändert")
    return {"summary": " · ".join(pieces), "base_probability": base[market],
        "used_probability": used[market], "delta_pp": result["delta_pp"][market],
        "missing": missing, "admin_details": deepcopy({"role": role,
            "selected_market": market, "factor_roles": roles, "factor_states": states,
            "factor_groups": groups, "limitations": limitations})}
