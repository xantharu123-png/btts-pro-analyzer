"""D2 paired event-loss assembly, not the experiment/activation authority.

Inputs are normalized price-free model comparisons with D1-resolved native
identity. Final shared-cohort intersection, frozen hypotheses, distribution
scoring, calibration and linked approval remain separate mandatory checks.
"""
from __future__ import annotations

from fractions import Fraction

from context_models.contracts import (
    ContextContractError, _is_price_name, canonical_timestamp, require_native_key,
    require_number, require_object, require_text, require_sport,
)


def _targets(values):
    if type(values) is not tuple or not values:
        raise ContextContractError("fixed target markets require a nonempty tuple")
    for value in values:
        require_text(value, "target market", code=True)
        if _is_price_name(value):
            raise ContextContractError("price fields are not model target markets")
    if values != tuple(sorted(set(values))):
        raise ContextContractError("fixed target markets must be canonical sorted unique names")
    return values


def event_loss_coverage(rows: tuple[dict, ...], *, target_markets: tuple[str, ...]) -> dict:
    """Return fixed-target event means and explicit missing-target exclusions.

    Malformed/duplicate/conflicting rows are errors, never favorable coverage
    exclusions. Missing a declared target excludes the complete event from
    this paired input. D2 must intersect these inputs across the frozen ready
    cohort and distribution losses; this routine does NOT choose that cohort.
    """
    targets = _targets(target_markets)
    if type(rows) is not tuple:
        raise ContextContractError("paired loss inventory must be an explicit tuple")
    groups = {}
    fields = {"event_key", "market_key", "decision_at", "block", "p_base", "p_context", "outcome"}
    for value in rows:
        require_object(value, fields, label="paired market loss row")
        event = require_native_key(value["event_key"])
        require_sport(event.split(":", 2)[1])
        market = require_text(value["market_key"], "market key", code=True)
        if market not in targets:
            raise ContextContractError("unregistered target market in paired loss rows")
        if type(value["decision_at"]) is not str:
            raise ContextContractError("paired decision must be an aware JSON timestamp string")
        decision = canonical_timestamp(value["decision_at"])
        block = require_text(value["block"], "frozen test block", code=True)
        if type(value["outcome"]) is not int or value["outcome"] not in (0, 1):
            raise ContextContractError("market outcome must be actual integer zero or one")
        for name in ("p_base", "p_context"):
            require_number(value[name], name, minimum=0, maximum=1)
        group = groups.setdefault(event, {"decision_at": decision, "block": block, "rows": {}})
        if (decision, block) != (group["decision_at"], group["block"]):
            raise ContextContractError("one native event has conflicting decision or block")
        if market in group["rows"]:
            raise ContextContractError("duplicate native event/market in paired loss rows")
        group["rows"][market] = (value["p_base"], value["p_context"], value["outcome"])
    events, excluded = [], []
    for event, group in sorted(groups.items(), key=lambda item: (item[1]["decision_at"], item[0])):
        missing = sorted(set(targets)-set(group["rows"]))
        if missing:
            excluded.append({"event_key": event, "reason": "missing-target-markets", "missing": missing})
            continue
        ordered = [group["rows"][key] for key in targets]
        base = sum((p_base-outcome)**2 for p_base, _, outcome in ordered)/len(ordered)
        context = sum((p_context-outcome)**2 for _, p_context, outcome in ordered)/len(ordered)
        events.append({"event_key": event, "decision_at": group["decision_at"], "block": group["block"],
                       "base_brier": base, "context_brier": context, "advantage": base-context})
    return {"events": tuple(events), "excluded": tuple(excluded)}


def aggregate_event_losses(rows: tuple[dict, ...], *, target_markets: tuple[str, ...]) -> tuple[dict, ...]:
    """One chronologically ordered mean loss per canonical event, not per card.

    Use event_loss_coverage when constructing reports so missing-target reasons
    are carried forward. This convenience projection contains no approval flag.
    """
    return event_loss_coverage(rows, target_markets=target_markets)["events"]


def _test_windows(values):
    if type(values) is not tuple or len(values) < 3:
        raise ContextContractError("at least three fixed consecutive test blocks required")
    blocks = []
    for value in values:
        if type(value) is not tuple or len(value) != 2 or any(type(v) is not str for v in value):
            raise ContextContractError("test block requires two aware JSON timestamps")
        start, end = map(canonical_timestamp, value)
        if start >= end or (blocks and start != blocks[-1][1]):
            raise ContextContractError("test blocks must have positive consecutive durations")
        blocks.append((start, end))
    return tuple(blocks)


def _representable_fraction(value, name):
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ContextContractError(f"{name} is not representable") from exc
    if value and result == 0.:
        raise ContextContractError(f"{name} is not representable (nonzero underflow)")
    require_number(result, name)
    return result


def _finite_mean(values):
    if not values:
        return None
    # Mean finite JSON numbers before their single display rounding. Neither
    # dividing each subnormal first nor summing huge values in float64 is safe.
    return _representable_fraction(sum(map(Fraction, values), Fraction())/len(values), "loss mean")


def paired_cohort_metrics(
    rows: tuple[dict, ...], distribution_losses: tuple[dict, ...], *,
    target_markets: tuple[str, ...], test_blocks: tuple[tuple[str, str], ...],
    outcome_contract: str, tail_policy: str,
) -> dict:
    """Score one already intersected, fixed comparable cohort without approval.

    The experiment owner must resolve identity/source evidence, intersect every
    ready comparable hypothesis and record exclusions BEFORE this call. This
    CPU helper neither reads labels nor grants approval/chooses a population.
    A missing target or a second distribution subset is an error here. All
    registered hypotheses still need a single joint BH pass outside this API.
    Distribution losses must come from the declared joint PMF/PDF, never from
    multiplying overlapping market probabilities. This helper validates the
    transport; the owning scorer/provenance resolver proves that derivation.
    """
    from challenge_engine import (
        _calibration_diagnostics, adaptive_bin_threshold, MIN_CALIBRATION_BINS,
        MIN_CALIBRATION_BIN_SIZE, MAX_EXPECTED_CALIBRATION_ERROR,
        MIN_RELATIVE_BRIER_IMPROVEMENT,
    )
    from model_loss_statistics import paired_advantage_statistics

    blocks = _test_windows(test_blocks)
    for name, value in (("outcome contract", outcome_contract), ("tail policy", tail_policy)):
        require_text(value, name, code=True)
        if _is_price_name(value):
            raise ContextContractError("price policy cannot define a model outcome")
    coverage = event_loss_coverage(rows, target_markets=target_markets)
    if coverage["excluded"]:
        raise ContextContractError("incomplete target set in final paired cohort")
    events = coverage["events"]
    by_event = {row["event_key"]: row for row in events}
    for row in events:
        actual_block = next((f"test:{i}" for i, (start, end) in enumerate(blocks)
                             if start <= row["decision_at"] < end), None)
        if actual_block != row["block"]:
            raise ContextContractError("event decision does not match its frozen test block")
    if type(distribution_losses) is not tuple:
        raise ContextContractError("distribution losses require an explicit tuple")
    fields = {"event_key", "decision_at", "block", "outcome_contract", "base_logloss", "context_logloss", "tail_policy"}
    distribution = {}
    for value in distribution_losses:
        require_object(value, fields, label="paired distribution loss")
        event = require_native_key(value["event_key"])
        if event in distribution:
            raise ContextContractError("duplicate native distribution event")
        if type(value["decision_at"]) is not str:
            raise ContextContractError("distribution decision must be an aware JSON timestamp")
        decision = canonical_timestamp(value["decision_at"])
        if value["outcome_contract"] != outcome_contract or value["tail_policy"] != tail_policy:
            raise ContextContractError("distribution outcome or tail policy differs from frozen comparison")
        if event not in by_event:
            raise ContextContractError("distribution and Brier must use the same exact events")
        if (decision, value["block"]) != (by_event[event]["decision_at"], by_event[event]["block"]):
            raise ContextContractError("distribution decision or block differs from paired event")
        distribution[event] = tuple(require_number(value[k], k) for k in ("base_logloss", "context_logloss"))
    if set(distribution) != set(by_event):
        raise ContextContractError("distribution and Brier must use the same exact events")

    def losses(values):
        base = _finite_mean([v["base_brier"] for v in values])
        context = _finite_mean([v["context_brier"] for v in values])
        base_log = _finite_mean([distribution[v["event_key"]][0] for v in values])
        context_log = _finite_mean([distribution[v["event_key"]][1] for v in values])
        # Compare the paired losses BEFORE rounding their absolute means.
        # JSON integers may carry more precision than float64. Fraction also
        # preserves mixed int/float differences; a +1 degradation beside 1e16
        # must not disappear through cancellation or turn into +2.
        delta = (_representable_fraction(sum((Fraction(distribution[v["event_key"]][1])
                                              - Fraction(distribution[v["event_key"]][0]) for v in values), Fraction())/len(values),
                                         "paired distribution difference") if values else None)
        if delta is not None:
            require_number(delta, "paired distribution difference")
        return {"event_count": len(values), "base_brier": base, "context_brier": context,
                "base_logloss": base_log, "context_logloss": context_log, "distribution_delta": delta}

    report = losses(events)
    mean, se, lower, p = paired_advantage_statistics([r["advantage"] for r in events])
    relative = ((report["base_brier"]-report["context_brier"])/report["base_brier"]
                if report["base_brier"] is not None and report["base_brier"] > 0 else None)
    if relative is not None:
        require_number(relative, "relative event Brier improvement")
    report.update(relative_improvement=relative, mean_advantage=mean, hac_standard_error=se,
                  hac_lower=lower, p_value=1. if p is None else p)
    report["event_inventory"] = [{k: r[k] for k in ("event_key", "decision_at", "block")} for r in events]
    report["blocks"] = [{"block": f"test:{i}", "start": start, "end": end,
                         **losses([r for r in events if r["block"] == f"test:{i}"])}
                        for i, (start, end) in enumerate(blocks)]
    failures = []
    if len(events) < 200:
        failures.append("insufficient-events")
    if any(b["event_count"] == 0 for b in report["blocks"]):
        failures.append("unrepresented-test-block")
    if relative is None or relative < MIN_RELATIVE_BRIER_IMPROVEMENT:
        failures.append("insufficient-relative-improvement")
    if lower is None or lower <= 0:
        failures.append("nonpositive-paired-lower-bound")
    if report["distribution_delta"] is None or report["distribution_delta"] > 0:
        failures.append("worse-distribution-logloss")
    market_rows = {m: {} for m in target_markets}
    for row in rows:
        market_rows[row["market_key"]][row["event_key"]] = row
    report["calibration"] = {}
    for market in target_markets:
        ordered = [market_rows[market][r["event_key"]] for r in events]
        ece, count, minimum, worst, worst_size, worst_mean = _calibration_diagnostics(
            [r["p_context"] for r in ordered], [r["outcome"] for r in ordered])
        threshold = adaptive_bin_threshold(worst_mean, worst_size)
        report["calibration"][market] = {
            "ece": ece, "supported_bins": count, "min_bin_size": minimum, "worst_deviation": worst,
            "worst_bin_size": worst_size, "worst_mean": worst_mean, "adaptive_threshold": threshold}
        if (count < MIN_CALIBRATION_BINS or minimum < MIN_CALIBRATION_BIN_SIZE
                or ece > MAX_EXPECTED_CALIBRATION_ERROR or worst is None or worst > threshold):
            failures.append(f"market-calibration:{market}")
    report["pre_multiplicity_failures"] = failures
    return report
