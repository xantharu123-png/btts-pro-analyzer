from __future__ import annotations

from datetime import datetime, timedelta, timezone

from streamlit.testing.v1 import AppTest

from market_consensus import MarketConsensus, QuotePoint, REFERENCE_SOURCE
from multi_sport_recommendations import EVIDENCE_RELEASED, RecommendationCandidate


NOW = datetime.now(timezone.utc).isoformat()


def _candidate(*, release_pending: bool = False) -> RecommendationCandidate:
    return RecommendationCandidate(
        event_key="compact-price-action", sport="Fußball", event_label="Alpha vs Beta",
        market="Beide treffen", selection="Ja", line=None,
        model_probability=65.0, risk_adjusted_probability=60.0,
        probability_haircut=5.0, fair_odds=1.538, minimum_odds=1.80,
        model_name="Testmodell", expected_total=3.0, evidence=("interne Prüfung",),
        evidence_stage=EVIDENCE_RELEASED, release_pending=release_pending,
    )


def _quote() -> MarketConsensus:
    return MarketConsensus(
        fixture_id=1, candidate_id="compact-price-action", market_key="BTTS_YES",
        bet_name="Both Teams Score", value_name="Yes", consensus_odds=2.00,
        conservative_odds=2.00, lowest_odds=1.95, best_odds=2.10,
        bookmaker_count=3, quoted_at=NOW, fetched_at=NOW, source=REFERENCE_SOURCE,
        points=(
            QuotePoint("A", 1.95, "api-football:1", NOW),
            QuotePoint("B", 2.00, "api-football:2", NOW),
            QuotePoint("C", 2.10, "api-football:3", NOW),
        ),
        scheduled_start="2030-01-01T16:00:00+00:00",
    )


def _render_full() -> None:
    from datetime import datetime, timezone
    from bet_finder_ui import render_price_decision
    from market_consensus import MarketConsensus, QuotePoint, REFERENCE_SOURCE
    from multi_sport_recommendations import EVIDENCE_RELEASED, RecommendationCandidate

    now = datetime.now(timezone.utc).isoformat()
    candidate = RecommendationCandidate(
        event_key="full-contract", sport="Fußball", event_label="Alpha vs Beta",
        market="Beide treffen", selection="Ja", line=None, model_probability=65.0,
        risk_adjusted_probability=60.0, probability_haircut=5.0, fair_odds=1.538,
        minimum_odds=1.80, model_name="Testmodell", expected_total=3.0,
        evidence=("interne Prüfung",), evidence_stage=EVIDENCE_RELEASED,
    )
    quote = MarketConsensus(
        fixture_id=1, candidate_id="full-contract", market_key="BTTS_YES",
        bet_name="Both Teams Score", value_name="Yes", consensus_odds=2.00,
        conservative_odds=2.00, lowest_odds=1.95, best_odds=2.10, bookmaker_count=3,
        quoted_at=now, fetched_at=now, source=REFERENCE_SOURCE,
        points=(
            QuotePoint("A", 1.95, "api-football:1", now),
            QuotePoint("B", 2.00, "api-football:2", now),
            QuotePoint("C", 2.10, "api-football:3", now),
        ), scheduled_start="2030-01-01T16:00:00+00:00",
    )
    render_price_decision(candidate, key="full-contract", reference_quote=quote, allow_manual_check=True)


def _render_compact() -> None:
    from datetime import datetime, timezone
    from bet_finder_ui import render_price_decision
    from market_consensus import MarketConsensus, QuotePoint, REFERENCE_SOURCE
    from multi_sport_recommendations import EVIDENCE_RELEASED, RecommendationCandidate

    now = datetime.now(timezone.utc).isoformat()
    candidate = RecommendationCandidate(
        event_key="compact-contract", sport="Fußball", event_label="Alpha vs Beta",
        market="Beide treffen", selection="Ja", line=None, model_probability=65.0,
        risk_adjusted_probability=60.0, probability_haircut=5.0, fair_odds=1.538,
        minimum_odds=1.80, model_name="Testmodell", expected_total=3.0,
        evidence=("interne Prüfung",), evidence_stage=EVIDENCE_RELEASED,
    )
    quote = MarketConsensus(
        fixture_id=1, candidate_id="compact-contract", market_key="BTTS_YES",
        bet_name="Both Teams Score", value_name="Yes", consensus_odds=2.00,
        conservative_odds=2.00, lowest_odds=1.95, best_odds=2.10, bookmaker_count=3,
        quoted_at=now, fetched_at=now, source=REFERENCE_SOURCE,
        points=(
            QuotePoint("A", 1.95, "api-football:1", now),
            QuotePoint("B", 2.00, "api-football:2", now),
            QuotePoint("C", 2.10, "api-football:3", now),
        ), scheduled_start="2030-01-01T16:00:00+00:00",
    )
    render_price_decision(
        candidate, key="compact-contract", reference_quote=quote,
        save_source="Automatischer Wettfinder", allow_manual_check=True,
        presentation="compact", manual_surface="popover",
    )


def test_default_full_presentation_keeps_reference_details_and_manual_expander():
    app = AppTest.from_function(_render_full)
    app.run(timeout=30)

    assert not app.exception
    assert any("Beide treffen: Ja" == item.value for item in app.subheader)
    assert {item.label for item in app.metric} >= {
        "Modellwahrscheinlichkeit", "Vorsichtige Prognose", "Value-Grenze",
    }
    assert any("SPIELBARER TIPP" in item.value for item in app.success)
    assert len(app.expander) == 1


def test_compact_presentation_evaluates_same_automatic_bet_without_duplicate_content():
    from bet_finder_ui import evaluate_reference_price

    expected = evaluate_reference_price(_candidate(), _quote(), bankroll=100.0)
    app = AppTest.from_function(_render_compact)
    app.run(timeout=30)

    assert not app.exception
    assert expected.decision is not None
    assert expected.decision.status == "BET"
    assert not app.subheader
    assert not app.metric
    assert not app.success
    assert not app.info
    assert any(item.label == "Tipp merken" for item in app.button)


def test_compact_and_full_return_the_same_reference_decision_as_the_helper(monkeypatch):
    import bet_finder_ui as ui

    class _Streamlit:
        session_state = {}

        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: self

        def columns(self, _count):
            return (self, self, self)

        def button(self, *_args, **_kwargs):
            return False

        def metric(self, *_args, **_kwargs):
            return None

    fake_streamlit = _Streamlit()
    monkeypatch.setattr(ui, "st", fake_streamlit)
    expected = ui.evaluate_reference_price(_candidate(), _quote(), bankroll=100.0)

    full = ui.render_price_decision(
        _candidate(), key="full-decision", reference_quote=_quote(),
    )
    compact = ui.render_price_decision(
        _candidate(), key="compact-decision", reference_quote=_quote(),
        presentation="compact",
    )

    assert full == expected.decision
    assert compact == expected.decision


def test_compact_and_full_automatic_bets_render_stake_once():
    compact = AppTest.from_function(_render_compact)
    compact.run(timeout=30)
    full = AppTest.from_function(_render_full)
    full.run(timeout=30)

    compact_stakes = [
        item.value for item in compact.caption if "Einsatzvorschlag:" in item.value
    ]
    full_stakes = [
        item.value for item in full.caption if "Einsatzvorschlag:" in item.value
    ]
    assert len(compact_stakes) == 1
    assert full_stakes == compact_stakes


def test_compact_manual_quote_uses_streamlit_popover_not_legacy_expander(monkeypatch):
    import bet_finder_ui as ui

    calls: list[str] = []

    class _Surface:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(ui.st, "popover", lambda label: calls.append(label) or _Surface())
    monkeypatch.setattr(ui.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "form", lambda *_args, **_kwargs: _Surface())
    monkeypatch.setattr(ui.st, "columns", lambda _count: (_Surface(), _Surface()))
    monkeypatch.setattr(ui.st, "text_input", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(ui.st, "number_input", lambda *_args, **_kwargs: 100.0)
    monkeypatch.setattr(ui.st, "checkbox", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(ui.st, "form_submit_button", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(ui.st, "session_state", {})

    assert ui._render_manual_check(
        _candidate(), key="compact-popover", bankroll_key="bankroll",
        price_source="Dezimalquote", save_source=None, manual_surface="popover",
    ) is None
    assert calls == ["Eigene Quote prüfen"]


def test_reference_evaluation_keeps_exact_executable_offer_provenance():
    from bet_finder_ui import evaluate_reference_price

    evaluation = evaluate_reference_price(_candidate(), _quote(), bankroll=100.0)

    assert evaluation.decision is not None
    assert evaluation.decision.status == "BET"
    assert evaluation.status.bookmaker == "B"
    assert evaluation.status.bookmaker_id == "api-football:2"
    assert evaluation.status.observed_at == NOW
    assert evaluation.quote is not None
    assert evaluation.quote.candidate_id == "compact-price-action"


def test_reference_evaluation_uses_one_injected_clock_and_never_exposes_raw_quote():
    from bet_finder_ui import evaluate_reference_price

    evaluation = evaluate_reference_price(
        _candidate(),
        _quote(),
        bankroll=100.0,
        now=datetime.fromisoformat(NOW) + timedelta(hours=2),
    )

    assert evaluation.status.code == "STALE"
    assert evaluation.decision is None
    assert evaluation.quote is None


def test_compact_automatic_bet_persists_exact_provider_provenance(monkeypatch):
    import bet_finder_ui as ui

    saved: list[tuple[object, str]] = []

    class _Streamlit:
        session_state = {}

        @staticmethod
        def button(*_args, **_kwargs):
            return True

        @staticmethod
        def toast(*_args, **_kwargs):
            return None

        @staticmethod
        def caption(*_args, **_kwargs):
            return None

    monkeypatch.setattr(ui, "st", _Streamlit())
    monkeypatch.setattr(
        ui,
        "_save_tip",
        lambda decision, *, source: saved.append((decision, source)),
    )

    decision = ui.render_price_decision(
        _candidate(), key="compact-save", reference_quote=_quote(),
        save_source="Automatischer Wettfinder", presentation="compact",
    )

    assert decision is not None and decision.status == "BET"
    assert len(saved) == 1
    assert "API-Football" in saved[0][1]
    assert "B [api-football:2]" in saved[0][1]
    assert NOW in saved[0][1]


def test_pending_manual_quote_confirmation_never_persists_a_bet(monkeypatch):
    import bet_finder_ui as ui

    saved: list[object] = []

    class _Surface:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(ui.st, "popover", lambda _label: _Surface())
    monkeypatch.setattr(ui.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "form", lambda *_args, **_kwargs: _Surface())
    monkeypatch.setattr(ui.st, "columns", lambda _count: (_Surface(), _Surface()))
    monkeypatch.setattr(ui.st, "text_input", lambda *_args, **_kwargs: "2.10")
    monkeypatch.setattr(ui.st, "number_input", lambda *_args, **_kwargs: 100.0)
    monkeypatch.setattr(ui.st, "checkbox", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(ui.st, "form_submit_button", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(ui.st, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui.st, "session_state", {})
    monkeypatch.setattr(
        ui,
        "_save_tip",
        lambda decision, *, source: saved.append((decision, source)),
    )

    decision = ui._render_manual_check(
        _candidate(release_pending=True), key="pending-save", bankroll_key="bankroll",
        price_source="Dezimalquote", save_source="Automatischer Wettfinder",
        manual_surface="popover",
    )

    assert decision is not None and decision.status == "SHADOW"
    assert [saved_decision.status for saved_decision, _source in saved] == ["SHADOW"]
