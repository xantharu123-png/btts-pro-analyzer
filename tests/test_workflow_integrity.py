from unittest.mock import Mock

import pandas as pd
import pytest

import btts_pro_app as app
from advanced_analyzer import calculate_evidence_score
from alternative_markets_tab_extended import _api_football_items, _market_scope_signature
from api_football import APIFootball
from red_card_bot import RedCardBotEnhanced


class _ProgressStub:
    def progress(self, _value):
        return None

    def empty(self):
        return None

    def caption(self, _value):
        return None


def test_evidence_score_full_coverage_and_agreement_is_100():
    result = calculate_evidence_score(12, 12, 5, 5, [64.0, 64.0, 64.0])

    assert result["score"] == pytest.approx(100.0)
    assert result["agreement_score"] == pytest.approx(100.0)
    assert sum(result["contributions"].values()) == pytest.approx(100.0)


def test_evidence_score_without_form_is_capped_at_80():
    result = calculate_evidence_score(12, 12, 0, 0, [60.0, 60.0, 60.0])

    assert result["score"] == pytest.approx(80.0)
    assert result["contributions"]["home_form"] == 0.0
    assert result["contributions"]["away_form"] == 0.0


def test_evidence_score_penalizes_active_model_disagreement():
    aligned = calculate_evidence_score(12, 12, 5, 5, [60.0, 60.0, 60.0])
    divergent = calculate_evidence_score(12, 12, 5, 5, [60.0, 60.0, 60.0, 100.0])

    assert divergent["score"] < aligned["score"]
    assert divergent["agreement_score"] < aligned["agreement_score"]


def test_evidence_score_rejects_ambiguous_inputs():
    with pytest.raises(ValueError):
        calculate_evidence_score(True, 12, 5, 5, [60.0, 60.0])
    with pytest.raises(ValueError):
        calculate_evidence_score(12, 12, 5, 5, [60.0])
    with pytest.raises(ValueError):
        calculate_evidence_score(12, 12, 5, 5, [60.0, 101.0])


def test_live_quality_filter_has_two_distinct_levels():
    analyses = [
        {"id": "low", "btts_prob": 65.0, "btts_confidence": "LOW"},
        {"id": "medium", "btts_prob": 70.0, "btts_confidence": "MEDIUM"},
        {"id": "insufficient", "btts_prob": None, "btts_confidence": "INSUFFICIENT"},
        {"id": "complete", "btts_prob": 100.0, "btts_confidence": "COMPLETE"},
    ]

    calculable = app._filter_live_opportunities(analyses, 60, "Berechenbar")
    complete_basis = app._filter_live_opportunities(
        analyses, 60, "Live-xG + Prematch"
    )

    assert [item["id"] for item in calculable] == ["medium", "low"]
    assert [item["id"] for item in complete_basis] == ["medium"]


def test_prematch_scan_collects_before_probability_filter(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "BTTS %": "42.0%",
                "Data Quality": "70.0%",
                "Home": "A",
                "Away": "B",
            }
        ]
    )
    analyzer = Mock()
    analyzer.analyze_upcoming_matches.return_value = frame
    monkeypatch.setattr(app.st, "progress", lambda _value: _ProgressStub())
    monkeypatch.setattr(app.st, "empty", _ProgressStub)

    result = app._scan_prematch(analyzer, ["BL1"], 7)

    analyzer.analyze_upcoming_matches.assert_called_once_with(
        "BL1", days_ahead=7, min_probability=0
    )
    assert result.iloc[0]["BTTS_num"] == pytest.approx(42.0)


def test_scope_signatures_are_order_independent():
    assert app._scope_signature(["PL", "BL1"], 7) == app._scope_signature(
        ["BL1", "PL"], 7
    )
    assert _market_scope_signature([78, 39], pd.Timestamp("2026-07-11").date()) == {
        "league_ids": [39, 78],
        "date": "2026-07-11",
    }


def test_api_football_http_200_provider_error_is_not_treated_as_empty_success():
    response = Mock(
        status_code=200,
        json=Mock(return_value={"errors": {"access": "account suspended"}, "response": []}),
    )
    response.raise_for_status = Mock()

    with pytest.raises(ValueError, match="account suspended"):
        _api_football_items(response, "fixtures")


def test_red_card_bot_respects_explicit_credentials_outside_streamlit():
    bot = RedCardBotEnhanced(
        api_key="explicit-api",
        telegram_token="explicit-token",
        telegram_chat_id="explicit-chat",
        streamlit_mode=False,
    )

    assert bot.api_key == "explicit-api"
    assert bot.telegram_token == "explicit-token"
    assert bot.telegram_chat_id == "explicit-chat"


def test_telegram_reuses_preloaded_live_stats(monkeypatch):
    bot = RedCardBotEnhanced(
        api_key="api",
        telegram_token="token",
        telegram_chat_id="chat",
        streamlit_mode=False,
    )
    bot.get_live_stats = Mock()
    prediction = object()
    bot.predictor = Mock()
    bot.predictor.predict.return_value = prediction
    bot.predictor.format_prediction.return_value = "model output"
    response = Mock(status_code=200)
    monkeypatch.setattr("red_card_bot.requests.post", Mock(return_value=response))
    card = {
        "player": "Player",
        "team": "Home",
        "team_id": 1,
        "minute": 55,
        "match": {
            "fixture": {"id": 10},
            "teams": {
                "home": {"id": 1, "name": "Home"},
                "away": {"id": 2, "name": "Away"},
            },
            "goals": {"home": 1, "away": 0},
            "league": {"name": "League", "country": "Country"},
        },
    }

    sent = bot.send_telegram_alert_with_stats(
        card,
        live_stats=None,
        fetch_live_stats=False,
    )

    assert sent is True
    bot.get_live_stats.assert_not_called()
    assert bot.predictor.predict.call_args.kwargs["live_stats"] is None


def test_red_card_provider_records_http_errors(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    monkeypatch.setattr(
        "red_card_bot.requests.get",
        Mock(return_value=Mock(status_code=503)),
    )

    assert bot.get_live_matches() == []
    assert bot.errors == [{"operation": "live_matches", "message": "HTTP 503"}]


def test_red_card_empty_league_scope_does_not_expand_to_worldwide(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    response = Mock(
        status_code=200,
        json=Mock(
            return_value={
                "response": [
                    {"league": {"id": 78}, "fixture": {"id": 1}},
                ]
            }
        ),
    )
    monkeypatch.setattr("red_card_bot.requests.get", Mock(return_value=response))

    assert bot.get_live_matches([]) == []


def test_live_provider_exposes_http_failure(monkeypatch):
    client = APIFootball("api")
    monkeypatch.setattr(client, "_rate_limit", Mock())
    monkeypatch.setattr(
        "api_football.requests.get",
        Mock(return_value=Mock(status_code=429)),
    )

    assert client.get_live_matches() == []
    assert client.last_error == "HTTP 429"


def test_live_provider_exposes_http_200_account_error(monkeypatch):
    client = APIFootball("api")
    monkeypatch.setattr(client, "_rate_limit", Mock())
    monkeypatch.setattr(
        "api_football.requests.get",
        Mock(
            return_value=Mock(
                status_code=200,
                json=Mock(
                    return_value={
                        "errors": {"access": "Your account is suspended"},
                        "response": [],
                    }
                ),
            )
        ),
    )

    assert client.get_live_matches() == []
    assert "suspended" in client.last_error
