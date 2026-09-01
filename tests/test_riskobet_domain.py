from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone

import pytest

from riskobet_domain import (
    ContextState,
    EvidenceStage,
    EventModelSnapshot,
    FactorEvidence,
    FactorRole,
    RiskCandidate,
    RiskRunSnapshot,
    RunStatus,
    ValidationEvidenceArtifact,
    canonical_input_hash,
    stable_event_key,
)


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)


def _factor() -> FactorEvidence:
    return FactorEvidence(
        factor_key="recent_form",
        summary="Außenseiter blieb in vier Spielen konkurrenzfähig.",
        source="results-provider",
        observed_at=NOW - timedelta(hours=2),
        imported_at=NOW - timedelta(hours=1),
        fresh_until=NOW + timedelta(hours=5),
        coverage=0.8,
        sample_size=20,
        role=FactorRole.MODEL,
    )


def _snapshot(*, input_payload=None, event_label="Alpha vs Beta"):
    event_key = stable_event_key("football", "provider", "fixture-17")
    return EventModelSnapshot(
        event_key=event_key,
        sport="football",
        competition="Testliga",
        event_label=event_label,
        starts_at=NOW + timedelta(hours=8),
        modeled_at=NOW,
        input_cutoff_at=NOW - timedelta(minutes=1),
        model_version="football-risk-v1",
        input_hash=canonical_input_hash(
            input_payload if input_payload is not None else {"fixture": 17, "form": [1, 0]}
        ),
        factors=(_factor(),),
    )


def _candidate(
    snapshot: EventModelSnapshot,
    *,
    stage=EvidenceStage.RESEARCH,
    probability=0.31,
    cautious_probability=None,
    missing_core_data=(),
    settlement_contract=None,
):
    return RiskCandidate(
        snapshot_id=snapshot.snapshot_id,
        event_key=snapshot.event_key,
        sport=snapshot.sport,
        competition=snapshot.competition,
        event_label=snapshot.event_label,
        starts_at=snapshot.starts_at,
        market_key="underdog_win",
        market_label="Außenseitersieg",
        selection_key="away",
        selection_label="Beta gewinnt",
        model_probability=probability,
        cautious_probability=cautious_probability,
        stage=stage,
        context_state=ContextState.PARTIAL,
        policy_version="risk-policy-v1",
        pros=("Gute aktuelle Form",),
        cons=("Schwächere Langzeitbasis",),
        missing_core_data=missing_core_data,
        settlement_contract=settlement_contract,
    )


def test_contracts_are_frozen_and_nested_sequences_are_tuples():
    snapshot = _snapshot()
    candidate = _candidate(snapshot)
    run = RiskRunSnapshot(
        started_at=NOW,
        completed_at=NOW + timedelta(minutes=2),
        status=RunStatus.COMPLETE,
        snapshots=[snapshot],
        candidates=[candidate],
    )

    assert isinstance(snapshot.factors, tuple)
    assert isinstance(candidate.pros, tuple)
    assert isinstance(run.candidates, tuple)
    with pytest.raises(FrozenInstanceError):
        candidate.market_key = "draw"


def test_input_hash_and_snapshot_identity_are_canonical_and_revision_bound():
    assert canonical_input_hash({"b": 2, "a": 1}) == canonical_input_hash(
        {"a": 1, "b": 2}
    )
    first = _snapshot(input_payload={"revision": 1})
    same = _snapshot(input_payload={"revision": 1})
    changed = _snapshot(input_payload={"revision": 2})

    assert first.snapshot_id == same.snapshot_id
    assert changed.snapshot_id != first.snapshot_id


def test_candidate_identity_is_stable_across_input_revisions():
    first = _candidate(_snapshot(input_payload={"revision": 1}))
    changed = _candidate(_snapshot(input_payload={"revision": 2}))

    assert first.snapshot_id != changed.snapshot_id
    assert first.candidate_id == changed.candidate_id


def test_only_research_may_omit_model_probability_and_names_missing_data():
    snapshot = _snapshot()
    research = _candidate(
        snapshot,
        probability=None,
        cautious_probability=None,
        missing_core_data=("historical upset baseline",),
    )
    assert research.model_probability is None

    with pytest.raises(ValueError, match="only RESEARCH"):
        _candidate(
            snapshot,
            stage=EvidenceStage.SHADOW,
            probability=None,
            missing_core_data=("baseline",),
            settlement_contract="match_winner_v1",
        )
    with pytest.raises(ValueError, match="missing_core_data"):
        _candidate(snapshot, probability=None)


def test_cautious_probability_may_be_absent_but_never_invented_or_higher():
    snapshot = _snapshot()
    candidate = _candidate(snapshot, probability=0.34, cautious_probability=None)
    assert candidate.cautious_probability is None

    with pytest.raises(ValueError, match="must not exceed"):
        _candidate(snapshot, probability=0.34, cautious_probability=0.35)


def test_shadow_and_validated_require_deterministic_settlement_contract():
    snapshot = _snapshot()
    with pytest.raises(ValueError, match="settlement_contract"):
        _candidate(snapshot, stage=EvidenceStage.SHADOW)

    shadow = _candidate(
        snapshot,
        stage=EvidenceStage.SHADOW,
        settlement_contract="football_match_winner_90m_v1",
    )
    assert shadow.stage is EvidenceStage.SHADOW


def test_candidate_contract_contains_no_price_or_odds_fields():
    field_names = {item.name.casefold() for item in fields(RiskCandidate)}
    forbidden = ("odds", "quote", "price", "bookmaker", "minimum")
    assert not any(token in name for name in field_names for token in forbidden)

    snapshot = _snapshot()
    with pytest.raises(TypeError):
        RiskCandidate(  # type: ignore[call-arg]
            **{
                **{
                    item.name: getattr(_candidate(snapshot), item.name)
                    for item in fields(RiskCandidate)
                    if item.init
                },
                "odds": 4.0,
            }
        )


def test_run_enforces_candidate_snapshot_identity_and_two_per_event():
    snapshot = _snapshot()
    first = _candidate(snapshot)
    second = RiskCandidate(
        **{
            **{
                item.name: getattr(first, item.name)
                for item in fields(RiskCandidate)
                if item.init
            },
            "market_key": "underdog_not_lose",
            "market_label": "Außenseiter verliert nicht",
            "selection_key": "x2",
            "selection_label": "Beta oder Remis",
        }
    )
    third = RiskCandidate(
        **{
            **{
                item.name: getattr(first, item.name)
                for item in fields(RiskCandidate)
                if item.init
            },
            "market_key": "underdog_goal",
            "market_label": "Außenseitertor",
            "selection_key": "away_over_0_5",
            "selection_label": "Beta erzielt ein Tor",
        }
    )

    with pytest.raises(ValueError, match="at most two"):
        RiskRunSnapshot(
            started_at=NOW,
            completed_at=NOW + timedelta(minutes=1),
            status=RunStatus.COMPLETE,
            snapshots=(snapshot,),
            candidates=(first, second, third),
        )


def test_factor_requires_causal_timestamps_and_valid_numeric_metadata():
    with pytest.raises(ValueError, match="imported_at"):
        FactorEvidence(
            factor_key="bad",
            summary="Bad timestamp",
            source="test",
            observed_at=NOW,
            imported_at=NOW - timedelta(seconds=1),
            fresh_until=NOW + timedelta(hours=1),
        )
    with pytest.raises(ValueError, match="coverage"):
        FactorEvidence(
            factor_key="bad",
            summary="Bad coverage",
            source="test",
            observed_at=NOW,
            imported_at=NOW,
            fresh_until=NOW,
            coverage=1.01,
        )


def test_snapshot_rejects_factors_observed_after_cutoff_or_imported_after_model():
    event_key = stable_event_key("football", "provider", "causal-17")

    def snapshot_with(factor):
        return EventModelSnapshot(
            event_key=event_key,
            sport="football",
            competition="Testliga",
            event_label="Alpha vs Beta",
            starts_at=NOW + timedelta(hours=8),
            modeled_at=NOW,
            input_cutoff_at=NOW - timedelta(minutes=1),
            model_version="football-risk-v1",
            input_hash=canonical_input_hash({"causal": factor.factor_key}),
            factors=(factor,),
        )

    with pytest.raises(ValueError, match="observed_at.*input_cutoff"):
        snapshot_with(
            FactorEvidence(
                factor_key="future-observation",
                summary="Too late",
                source="test",
                observed_at=NOW,
                imported_at=NOW,
                fresh_until=NOW + timedelta(hours=1),
            )
        )
    with pytest.raises(ValueError, match="imported_at.*modeled_at"):
        snapshot_with(
            FactorEvidence(
                factor_key="future-import",
                summary="Imported too late",
                source="test",
                observed_at=NOW - timedelta(minutes=2),
                imported_at=NOW + timedelta(seconds=1),
                fresh_until=NOW + timedelta(hours=1),
            )
        )


def test_run_identity_binds_error_content():
    snapshot = _snapshot()
    first = RiskRunSnapshot(
        started_at=NOW,
        completed_at=NOW + timedelta(minutes=1),
        status=RunStatus.PARTIAL,
        snapshots=(snapshot,),
        errors=("football: first",),
    )
    changed = RiskRunSnapshot(
        started_at=NOW,
        completed_at=NOW + timedelta(minutes=1),
        status=RunStatus.PARTIAL,
        snapshots=(snapshot,),
        errors=("football: second",),
    )

    assert first.run_id != changed.run_id


def test_validation_evidence_requires_every_predeclared_gate():
    valid = dict(
        validation_version="validation-v1",
        policy_version="risk-policy-v1",
        model_version="football-risk-v1",
        settlement_contract="riskobet-settlement-v1:football:result_90_minutes:away",
        walk_forward_sample_size=500,
        predeclared_minimum_sample_size=400,
        hac_brier_advantage_lower_bound=0.01,
        bh_fdr_q=0.04,
        tail_calibration_error=0.03,
        maximum_tail_calibration_error=0.05,
        active_drift=False,
        settlement_rate=0.98,
        minimum_settlement_rate=0.95,
        evaluation_blocks=2,
    )
    artifact = ValidationEvidenceArtifact(**valid)
    assert artifact.walk_forward_sample_size == 500

    with pytest.raises(ValueError, match="HAC"):
        ValidationEvidenceArtifact(
            **{**valid, "hac_brier_advantage_lower_bound": 0.0}
        )
    with pytest.raises(ValueError, match="bh_fdr_q"):
        ValidationEvidenceArtifact(**{**valid, "bh_fdr_q": 0.051})
    with pytest.raises(ValueError, match="active drift"):
        ValidationEvidenceArtifact(**{**valid, "active_drift": True})
    with pytest.raises(ValueError, match="at least two blocks"):
        ValidationEvidenceArtifact(**{**valid, "evaluation_blocks": 1})
