"""D1 immutable event splits and receipt-bound, train-only fitting mechanics.

The owning case resolver establishes original native Event and receipt evidence;
free arrays or caller evidence labels cannot establish causal provenance. This
module neither writes datasets nor opens final labels, and grants no activation.
"""
from __future__ import annotations

from datetime import datetime

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, validate_training_row,
)


def split_windows(*, train_end: datetime, tune_end: datetime,
                  test_blocks: tuple[tuple[datetime, datetime], ...]) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Validate and canonicalize half-open windows, including empty inventories."""
    train, tune = canonical_timestamp(train_end), canonical_timestamp(tune_end)
    if train >= tune:
        raise ContextContractError("training and tuning cutoffs must strictly increase")
    if type(test_blocks) is not tuple or len(test_blocks) < 3:
        raise ContextContractError("at least three fixed consecutive test blocks required")
    blocks = []
    for block in test_blocks:
        if type(block) is not tuple or len(block) != 2:
            raise ContextContractError("test block requires an immutable start/end pair")
        start, end = (canonical_timestamp(value) for value in block)
        if start >= end:
            raise ContextContractError("test block must have positive duration")
        if start < tune or (blocks and start < blocks[-1][1]):
            raise ContextContractError("test blocks overlap tuning or another block")
        if blocks and start != blocks[-1][1]:
            raise ContextContractError("test blocks must be contiguous")
        blocks.append((start, end))
    return train, tune, tuple(blocks)


def split_rows(rows: tuple[dict, ...], *, train_end: datetime, tune_end: datetime,
               test_blocks: tuple[tuple[datetime, datetime], ...]) -> dict[str, tuple[dict, ...]]:
    """Split normalized, already canonicalized rows as whole native events.

    If any head's result is late, the event stays excluded from that earlier
    fitting window; it cannot migrate into tune merely because its label is
    known there. A retrospective head likewise cannot lend a partial causal
    event. Result receipts may follow final blocks because evaluation observes
    later results, but the D2 evaluation cutoff is a separate required check.

    Row ``block`` is retained audit data, never authority for this split. The
    returned dict key is the computed destination. Callers must explicitly bind
    final block identities in the frozen experiment, not trust incoming labels.
    """
    train, tune, blocks = split_windows(train_end=train_end, tune_end=tune_end, test_blocks=test_blocks)
    if type(rows) is not tuple:
        raise ContextContractError("training inventory must be an explicit tuple")
    groups = {}
    unique = set()
    for value in rows:
        row = validate_training_row(value)
        group = groups.setdefault(row["event_key"], [])
        if group and row["decision_at"] != group[0]["decision_at"]:
            raise ContextContractError("one native event cannot have two training decision revisions")
        # A head is sampled once for each declared family/feature/scope variant.
        # Different target/offset/base revisions do not create independent data.
        identity = digest({key: row[key] for key in (
            "event_key", "family", "head", "feature_names", "population", "coverage")})
        if identity in unique:
            raise ContextContractError("duplicate or contradictory native event head")
        unique.add(identity)
        group.append(row)
    output = {name: [] for name in ("train", "tune", *(f"test:{index}" for index in range(len(blocks))),
                                     "late_results", "retrospective", "outside")}
    for event_rows in sorted(groups.values(), key=lambda values: (values[0]["decision_at"], values[0]["event_key"])):
        decision = event_rows[0]["decision_at"]
        last_result = max(row["result_observed_at"] for row in event_rows)
        if any(row["evidence_class"] == "retrospective" for row in event_rows):
            destination = "retrospective"
        elif decision < train:
            destination = "train" if last_result <= train else "late_results"
        elif decision < tune:
            destination = "tune" if last_result <= tune else "late_results"
        else:
            destination = next((f"test:{index}" for index, (start, end) in enumerate(blocks)
                                if start <= decision < end), "outside")
        output[destination].extend(sorted(event_rows, key=lambda row: (row["family"], row["head"], digest(row))))
    return {name: tuple(values) for name, values in output.items()}


class TrainingUnavailable(ContextContractError):
    """Artifact-only projection cannot return an unavailable or failed fit."""

    def __init__(self, report: dict):
        self.report = report
        super().__init__(report["reason"] or report["status"])


def _array(numbers):
    """Validate JSON scalars BEFORE conversion can round an integer or bool."""
    import numpy as np
    from context_models.contracts import require_number
    def check(values):
        for value in values:
            if type(value) is list:
                check(value)
            else:
                require_number(value, "training numeric value")
                if type(value) is int and int(float(value)) != value:
                    raise ContextContractError("training integer is not exactly representable in float64")
    check(numbers)
    return np.array(numbers, dtype=np.float64)


def _fit_heads(rows, config, alpha):
    from copy import deepcopy
    from context_models.offset import fit_offset
    names = config["feature_names"]
    if config["family"] != "tennis:serve":
        result = {}
        for name, link in sorted(config["head_links"].items()):
            selected = [row for row in rows if row["head"] == name]
            result[name] = fit_offset(_array([row["x"] for row in selected]),
                _array([row["offset"] for row in selected]), _array([row["target"] for row in selected]),
                link=link, alpha=alpha, trials=None if link == "log_rate" else _array([row["trials"] for row in selected]))
        return result
    from context_models.tennis_effect import _FEATURES
    mirror = []
    for name in names:
        root, side, _ = _FEATURES[name]
        counterpart = root + ("_b" if side == "a" else "_a" if side == "b" else "_delta")
        mirror.append((names.index(counterpart), -1 if side == "delta" else 1))
    x, offsets, targets, trials = [], [], [], []
    for row in rows:
        x.append(row["x"] if row["head"] == "hold_a" else [sign*row["x"][index] for index, sign in mirror])
        offsets.append(row["offset"])
        targets.append(row["target"])
        trials.append(row["trials"])
    shared = fit_offset(_array(x), _array(offsets), _array(targets), trials=_array(trials), link="logit", alpha=alpha)
    opposing = {**deepcopy(shared), "coef": [sign*shared["coef"][index] for index, sign in mirror],
                 "scale": [shared["scale"][index] for index, _ in mirror]}
    return {"hold_a": shared, "hold_b": opposing}


def case_market_targets(resolved: dict, target_markets: list[str]) -> dict[str, int]:
    """Owning final-outcome projection, after explicit case/source resolution."""
    import re
    payload = resolved["case"]["payload"]
    event, base = payload["event"], payload["base"]
    record = next(row for row in resolved["observations"] if row["digest"] == payload["outcome_ref"])
    result = record["payload"]["result"]
    if base["family"] == "football:goals:90min":
        from challenge_engine import MARKET_SPECS, market_outcome
        from context_models.football_effect import GOAL_KINDS
        specs = {spec.key: spec for spec in MARKET_SPECS if spec.kind in GOAL_KINDS}
        if any(key not in specs for key in target_markets):
            raise ContextContractError("outcome projection received a foreign goal market")
        return {key: int(market_outcome(specs[key], result["goals_home"], result["goals_away"])) for key in target_markets}
    home_win = int(result["winner_id"] == event["home_id"])
    targets = {"winner_a": home_win, "winner_b": 1-home_win}
    if base["family"] == "tennis:serve":
        scores = result["set_scores"]
        sets = [sum(score["home"] > score["away"] for score in scores), sum(score["away"] > score["home"] for score in scores)]
        games = [sum(score[side] for score in scores) for side in ("home", "away")]
        breaker = int(any(sorted(score.values()) == [6, 7] for score in scores))
        targets.update(tiebreak_yes=breaker, tiebreak_no=1-breaker)
        for key in target_markets:
            if key in targets:
                continue
            if match := re.fullmatch(r"exact_([2-5])_sets", key):
                answer = len(scores) == int(match[1])
            elif match := re.fullmatch(r"(over|under)_([2-4])_5_sets", key):
                answer = len(scores) > int(match[2])+.5 if match[1] == "over" else len(scores) < int(match[2])+.5
            elif match := re.fullmatch(r"correct_score_([0-3])_([0-3])", key):
                answer = sets == [int(match[1]), int(match[2])]
            elif match := re.fullmatch(r"set_handicap_([ab])_minus_1_5", key):
                side = int(match[1] == "b")
                answer = sets[side] - sets[1-side] > 1.5
            elif match := re.fullmatch(r"(over|under)_([0-9]+)\.5_games", key):
                answer = sum(games) > int(match[2])+.5 if match[1] == "over" else sum(games) < int(match[2])+.5
            elif match := re.fullmatch(r"game_handicap_([ab])_(minus|plus)_([0-6])_5", key):
                side = int(match[1] == "b")
                line = (int(match[3])+.5) * (-1 if match[2] == "minus" else 1)
                answer = games[side]-games[1-side]+line > 0
            else:
                raise ContextContractError("unsupported tennis final-outcome market")
            targets[key] = int(answer)
    if any(key not in targets for key in target_markets):
        raise ContextContractError("winner-only outcome cannot certify serve markets")
    return {key: targets[key] for key in target_markets}


def _tuning_brier(cases, artifact, config):
    from math import fsum, isfinite
    from context_models.football_effect import apply_football_effect
    from context_models.tennis_effect import apply_tennis_effect
    apply = apply_football_effect if config["sport"] == "football" else apply_tennis_effect
    event_losses = []
    for case in cases:
        payload = case["case"]["payload"]
        comparison = apply(payload["base"], payload["features"], artifact, event=payload["event"])
        targets = case_market_targets(case, config["target_markets"])
        event_losses.append(fsum((comparison["markets"][key]-target)**2 for key, target in targets.items()) / len(targets))
    score = fsum(event_losses) / len(event_losses)
    if not isfinite(score):
        raise ContextContractError("nonfinite complete-cohort tuning loss")
    return score


def _fit_cohort(rows, cases, config, *, exclusions):
    """Internal numeric seam AFTER public causal resolution; not a data API.

    Synthetic B7 law tests exercise this seam without pretending that a real
    native tennis-to-name resolver or a measured service feed already exists.
    """
    from copy import deepcopy
    from context_models.contracts import validate_effect_artifact
    from context_models.training_contracts import validate_family_config
    config = validate_family_config(config)
    by_event = {}
    for row in rows:
        by_event.setdefault(row["event_key"], []).append(row)
    train_cases, tune_cases, exclusions = [], [], list(deepcopy(exclusions))
    for case in sorted(cases, key=lambda c: (c["case"]["payload"]["base"]["cutoff"], c["case"]["payload"]["event"]["event_key"])):
        payload = case["case"]["payload"]
        key, decision = payload["event"]["event_key"], payload["base"]["cutoff"]
        sample = by_event.get(key, [])
        if {row["head"] for row in sample} != set(config["head_links"]) or len(sample) != len(config["head_links"]):
            raise ContextContractError("resolved event must supply exactly the declared training heads")
        phase = "train" if decision < config["train_end"] else "tune"
        boundary = config["train_end"] if phase == "train" else config["tune_end"]
        if decision >= config["tune_end"]:
            raise ContextContractError("final cases cannot enter train/tune fitting")
        if max(row["result_observed_at"] for row in sample) > boundary:
            exclusions.append({"event_key": key, "case_hash": case["case"]["digest"],
                               "status": "excluded", "reason": "late_result_for_" + phase})
        else:
            (train_cases if phase == "train" else tune_cases).append(case)
    train_keys = {c["case"]["payload"]["event"]["event_key"] for c in train_cases}
    tune_keys = {c["case"]["payload"]["event"]["event_key"] for c in tune_cases}
    training_rows = tuple(row for row in rows if row["event_key"] in train_keys)
    tuning_rows = tuple(row for row in rows if row["event_key"] in tune_keys)
    config_hash = digest(config)
    train_refs = {"schema": 1, "family_config_hash": config_hash,
                  "case_hashes": sorted(c["case"]["digest"] for c in train_cases), "rows_hash": digest(training_rows)}
    report = {"schema": 1, "status": "insufficient_data", "reason": "requires_two_train_events_and_one_tune_event",
        "family_config_hash": config_hash, "event_identity_hash": cases[0]["case"]["payload"]["event_identity_hash"] if cases else None,
        "artifact": None, "effect_hash": None, "selected_alpha": None, "alpha_scores": [], "candidate_artifacts": {},
        "case_hashes": sorted(c["case"]["digest"] for c in cases), "rows_hash": digest(rows),
        "training_case_hashes": train_refs["case_hashes"], "tuning_case_hashes": sorted(c["case"]["digest"] for c in tune_cases),
        "training_rows_hash": digest(training_rows), "tuning_rows_hash": digest(tuning_rows),
        "training_events": len(train_cases), "tuning_events": len(tune_cases), "exclusions": exclusions}
    if len(train_cases) < 2 or not tune_cases:
        if not cases and exclusions:
            report.update(status="unsupported", reason="no_supported_causal_cases")
        return report
    for alpha in config["alpha_grid"]:
        try:
            heads = _fit_heads(training_rows, config, alpha)
            artifact = validate_effect_artifact({"schema": 1, "sport": config["sport"], "family": config["family"],
                "feature_version": config["feature_version"], "feature_names": config["feature_names"], "heads": heads,
                "preprocessing_artifacts": config["preprocessing_artifacts"], "joint_calibration": config["joint_calibration"],
                "training_end": config["train_end"], "training_refs_hash": digest(train_refs),
                "population": config["population"], "coverage": config["coverage"], "model_variant": config["model_variant"]})
            effect_hash = digest({"kind": "context-effect-v1", "payload": artifact})
            score = _tuning_brier(tune_cases, artifact, config)
        except (ContextContractError, ArithmeticError) as exc:
            report["alpha_scores"].append({"alpha": alpha, "status": "fit_failed", "mean_brier": None,
                                           "effect_hash": None, "reason": str(exc)})
            continue
        report["candidate_artifacts"][effect_hash] = artifact
        report["alpha_scores"].append({"alpha": alpha, "status": "scored", "mean_brier": score,
                                       "effect_hash": effect_hash, "reason": None})
    scored = [score for score in report["alpha_scores"] if score["status"] == "scored"]
    if not scored:
        report.update(status="fit_failed", reason="no_complete_successful_train_tune_candidate")
        return report
    selected = min(scored, key=lambda score: (score["mean_brier"], -score["alpha"]))
    report.update(status="fitted", reason=None, selected_alpha=selected["alpha"], effect_hash=selected["effect_hash"],
                  artifact=deepcopy(report["candidate_artifacts"][selected["effect_hash"]]))
    return report


def fit_family(rows: tuple[dict, ...], config: dict, *, cases: tuple[dict, ...]) -> dict:
    """Fit train-only coefficients; select on tune, never inspect final cases."""
    from context_models.contracts import ContextIntegrityError
    from context_models.training_cases import assemble_training_cases, case_header
    from context_models.training_contracts import validate_family_config, validate_fit_result
    config = validate_family_config(config)
    if type(rows) is not tuple or type(cases) is not tuple:
        raise ContextContractError("fit rows and cases must be immutable inventories")
    # ALL cutoffs checked before assembly, source resolution or row.target.
    for case in cases:
        header = case_header(case, config=config)
        if header["base"]["cutoff"] >= config["tune_end"]:
            raise ContextContractError("final-test cases cannot enter training or tuning")
    assembly = assemble_training_cases(cases, config)
    supplied = tuple(sorted((validate_training_row(row) for row in rows), key=lambda row: (row["decision_at"], row["event_key"], row["head"])))
    reconstructed = tuple(sorted(assembly["rows"], key=lambda row: (row["decision_at"], row["event_key"], row["head"])))
    if supplied != reconstructed:
        raise ContextIntegrityError("training rows differ from their reconstructed original cases")
    report = _fit_cohort(reconstructed, assembly["cases"], config, exclusions=assembly["excluded"])
    report["case_hashes"] = sorted(case["case"]["digest"] for case in cases)
    if cases:
        report["event_identity_hash"] = cases[0]["case"]["payload"]["event_identity_hash"]
    return validate_fit_result(report, config=config)


def train_family(rows: tuple[dict, ...], config: dict, *, cases: tuple[dict, ...]) -> dict:
    """Artifact-only projection; incomplete data is never a fabricated fit."""
    from copy import deepcopy
    report = fit_family(rows, config, cases=cases)
    if report["status"] != "fitted":
        raise TrainingUnavailable(report)
    return deepcopy(report["artifact"])
