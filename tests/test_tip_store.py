from datetime import datetime, timezone

from bet_finder_candidates import build_probability_candidate
from multi_sport_recommendations import EVIDENCE_SHADOW, evaluate_candidate_price
from tip_store import TipStore


def _decision(odds: float = 2.0):
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
        evidence_stage=EVIDENCE_SHADOW,
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
        assert "Shadow-Tipps" in str(exc)
    else:
        raise AssertionError("A rejected price must not be persisted")


def test_tip_records_are_isolated_by_session_scope(tmp_path):
    db_path = tmp_path / "tips.db"
    first_user = TipStore(db_path, scope_id="session-a")
    second_user = TipStore(db_path, scope_id="session-b")
    first_user.save_decision(_decision(), source="Prematch")

    assert len(first_user.list_tips()) == 1
    assert second_user.list_tips() == []
