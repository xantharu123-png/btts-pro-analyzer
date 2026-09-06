"""Transparent, quote-free evidence ordering, not a betting-value estimate."""
from __future__ import annotations

from math import sqrt
from riskobet_domain import ContextState, EvidenceStage, FactorRole


def evidence_order(candidate, snapshot=None) -> tuple:
    """Prefer evidenced, complete and precise scenarios before start time.

    This is a lexicographic data-quality order, not an optimized return score.
    Sample sizes are not added across correlated factors. The uncertainty gap
    is scaled by Bernoulli dispersion so simply raising p cannot earn priority.
    No quote, implied market probability or price-status field is inspected.
    """
    stage = {EvidenceStage.VALIDATED: 0, EvidenceStage.SHADOW: 1, EvidenceStage.RESEARCH: 2}
    context = {ContextState.FRESH: 0, ContextState.PARTIAL: 1, ContextState.OPEN: 2, ContextState.STALE: 3}
    probability = candidate.model_probability
    cautious = candidate.cautious_probability
    uncertainty = (
        max(0.0, probability - cautious) / sqrt(max(probability * (1 - probability), 1e-12))
        if probability is not None and cautious is not None else float("inf")
    )
    sample = max((
        factor.sample_size or 0 for factor in getattr(snapshot, "factors", ())
        if factor.role == FactorRole.MODEL
    ), default=0)
    return (
        stage[candidate.stage],
        len(candidate.missing_core_data),
        context[candidate.context_state],
        uncertainty,
        -sample,
        candidate.starts_at,
        candidate.sport,
        candidate.event_key,
        candidate.candidate_id,
    )
