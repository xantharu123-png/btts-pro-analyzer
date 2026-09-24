"""Real Streamlit render checks for quote-free 15K model selections."""

from streamlit.testing.v1 import AppTest


def _render_model_candidates() -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from challenge_15k import _render_model_challenge
    from test_challenge_15k import stress_safe_ticket_candidates

    candidates = stress_safe_ticket_candidates()
    _render_model_challenge(
        {
            "search_date": datetime.now(timezone.utc).date().isoformat(),
            "challenge_model_candidates": candidates,
            "reference_quotes": {
                candidates[0].candidate_id: {"best_odds": 1.05},
            },
        },
        SimpleNamespace(pending_tickets=lambda: []),
        {"current_balance": 100.0, "stake_fraction": 0.05},
    )


def test_15k_model_cards_render_without_quote_or_nested_expander():
    app = AppTest.from_function(_render_model_candidates).run(timeout=30)
    assert not app.exception
    assert [heading.value for heading in app.subheader] == ["15K-Modellauswahl"]
    assert len(app.multiselect) == 1
    assert len(app.get("popover")) >= 1
    visible = " ".join(item.value for item in app.markdown)
    captions = " ".join(item.value for item in app.caption)
    assert "Beide Teams treffen" in visible
    assert "Quote 1.05" not in visible + captions
    assert "Preisfreigabe" not in visible + captions


def test_15k_asks_for_actual_odds_only_after_user_selects_models():
    app = AppTest.from_function(_render_model_candidates).run(timeout=30)
    assert not app.exception
    assert not app.number_input
    app.multiselect[0].set_value(["1:BTTS", "2:BTTS"]).run(timeout=30)
    assert not app.exception
    assert len(app.number_input) == 2
    assert any(item.value == "Tatsächliche Wette erfassen" for item in app.subheader)
    app.number_input[0].set_value(1.50).run(timeout=30)
    app.number_input[1].set_value(1.50).run(timeout=30)
    assert not app.exception
    assert any(item.label == "Tatsächliche Gesamtquote" for item in app.metric)
