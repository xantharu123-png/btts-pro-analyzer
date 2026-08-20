from datetime import datetime, timezone
import sqlite3

from bet_finder_candidates import build_probability_candidate
import pytest

from multi_sport_recommendations import (
    EVIDENCE_RELEASED,
    EVIDENCE_SHADOW,
    evaluate_candidate_price,
)
from tip_store import TipStore


def _decision(odds: float = 2.0, *, evidence_stage: str = EVIDENCE_RELEASED):
    candidate = build_probability_candidate(
        event_key="fixture-17",
        sport="Fußball",
        event_label="Team A vs Team B",
        market="Beide Teams treffen",
        selection="Ja",
        model_probability=60.0,
        probability_haircut=5.0,
        model_name="Testmodell",
        evidence=("Test",),
        evidence_stage=evidence_stage,
    )
    return evaluate_candidate_price(
        candidate,
        odds,
        bankroll=100.0,
        quote_confirmed=True,
    )


def test_price_approved_tip_is_upserted_and_settled(tmp_path):
    store = TipStore(tmp_path / "tips.db")
    first = store.save_decision(
        _decision(2.0),
        source="Fußball Prematch",
        now=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    second = store.save_decision(
        _decision(2.2),
        source="Fußball Prematch",
        now=datetime(2030, 1, 2, tzinfo=timezone.utc),
    )

    assert first.id == second.id
    assert second.quoted_odds == 2.2
    assert len(store.list_tips(active=True)) == 1

    store.settle(
        second.id,
        "WON",
        now=datetime(2030, 1, 3, tzinfo=timezone.utc),
    )
    assert store.list_tips(active=True) == []
    assert store.list_tips(active=False)[0].result == "WON"


def test_failed_fresh_price_can_archive_previous_pick(tmp_path):
    store = TipStore(tmp_path / "tips.db")
    decision = _decision(2.0)
    store.save_decision(decision, source="Live")

    store.archive_candidate(
        sport=decision.candidate.sport,
        event_key=decision.candidate.event_key,
        market=decision.candidate.market,
        selection=decision.candidate.selection,
    )

    assert store.list_tips() == []


def test_rejected_price_is_not_a_saved_tip(tmp_path):
    store = TipStore(tmp_path / "tips.db")
    rejected = _decision(1.2)

    assert not rejected.price_passed
    try:
        store.save_decision(rejected, source="Test")
    except ValueError as exc:
        assert "freigegebene Tipps" in str(exc)
    else:
        raise AssertionError("A rejected price must not be persisted")


def test_tip_records_are_isolated_by_session_scope(tmp_path):
    db_path = tmp_path / "tips.db"
    first_user = TipStore(db_path, scope_id="session-a")
    second_user = TipStore(db_path, scope_id="session-b")
    first_user.save_decision(_decision(), source="Prematch")

    assert len(first_user.list_tips()) == 1
    assert second_user.list_tips() == []


def test_shadow_selection_can_never_enter_the_consumer_tip_ledger(tmp_path):
    store = TipStore(tmp_path / "tips.db")
    shadow = _decision(2.0, evidence_stage=EVIDENCE_SHADOW)

    assert shadow.status == "SHADOW"
    with pytest.raises(ValueError, match="freigegebene Tipps"):
        store.save_decision(shadow, source="Shadow")
    assert store.list_tips() == []


def test_legacy_shadow_rows_are_preserved_but_archived(tmp_path):
    db_path = tmp_path / "tips.db"
    store = TipStore(db_path)
    identity = store._identity("Fußball", "legacy-1", "Sieger", "Heim")
    timestamp = datetime(2030, 1, 1, tzinfo=timezone.utc).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO saved_tips (
                scope_id, identity_key, created_at, updated_at, sport,
                event_key, event_label, market, selection, model_probability,
                risk_adjusted_probability, minimum_odds, quoted_odds,
                decision_status, evidence_stage, stake_amount, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "default", identity, timestamp, timestamp, "Fußball",
                "legacy-1", "Alpha vs Beta", "Sieger", "Heim", 60.0,
                55.0, 1.90, 2.00, "SHADOW", "SHADOW", 0.0, "Legacy",
            ),
        )

    migrated = TipStore(db_path)

    assert migrated.list_tips() == []
    with sqlite3.connect(db_path) as connection:
        archived = connection.execute(
            "SELECT archived FROM saved_tips WHERE identity_key=?",
            (identity,),
        ).fetchone()[0]
    assert archived == 1
