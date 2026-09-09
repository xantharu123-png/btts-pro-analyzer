"""Pure D1 event split mechanics, not a fitted model or source-proof resolver.

Dataset assembly MUST first resolve the canonical B Event and receipt evidence.
This function cannot infer provider aliases or authenticate an evidence label.
It neither writes datasets nor opens final labels, and grants no activation.
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
