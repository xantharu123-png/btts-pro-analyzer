from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

import app
import alternative_markets_tab_extended as market_tab
from betting_math import BETTING_POLICY_VERSION
from advanced_analyzer import calculate_evidence_score
from alternative_markets import PreMatchAlternativeAnalyzer
from alternative_markets_tab_extended import _api_football_items, _market_scope_signature
from api_football import APIFootball
from config_loader import AppConfig
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from red_card_bot import RED_CARD_MONITORED_LEAGUE_IDS, RedCardBotEnhanced


class _ProgressStub:
    def progress(self, _value, **_kwargs):
        return None

    def empty(self):
        return None

    def caption(self, _value):
        return None


def test_red_card_monitor_uses_the_full_canonical_league_scope():
    assert len(RED_CARD_MONITORED_LEAGUE_IDS) == 51
    assert set(RED_CARD_MONITORED_LEAGUE_IDS) == set(ALTERNATIVE_MARKET_LEAGUES)


def test_app_formats_new_league_codes_from_existing_catalog_symbols():
    assert app._league_label_for_code("NOR1") == "Norway: Eliteserien"
    assert app._league_label_for_code("unknown") == "UNKNOWN"


def test_market_worker_forwards_detailed_progress(monkeypatch):
    updates = []
    provider = object()
    monkeypatch.setattr(
        market_tab,
        "ChallengeDataProvider",
        lambda *_args: provider,
    )

    def fake_scan(
        received_provider,
        league_ids,
        search_date,
        max_fixtures,
        *,
        progress_cb=None,
    ):
        assert received_provider is provider
        assert league_ids == [78, 39]
        assert max_fixtures == 400
        progress_cb(0.25, "Liga 1/2")
        progress_cb(1.0, "Fertig")
        return {"search_date": search_date.isoformat()}

    monkeypatch.setattr(market_tab, "scan_daily_challenge", fake_scan)
    result = market_tab._run_market_scan_worker(
        "api-key",
        None,
        [78, 39],
        datetime.now().date(),
        400,
        {"league_ids": [39, 78]},
        progress_cb=lambda fraction, text: updates.append((fraction, text)),
    )

    assert updates == [(0.25, "Liga 1/2"), (1.0, "Fertig")]
    assert result["scope"] == {"league_ids": [39, 78]}


def test_multi_sport_worker_reports_real_phases(monkeypatch):
    monkeypatch.setattr(
        app,
        "_fetch_multi_sport_snapshot",
        lambda _sport, _detail: {"items": [{}, {}]},
    )
    updates = []

    result = app._run_multi_sport_worker(
        "Basketball",
        "NBA",
        progress_cb=lambda fraction, text: updates.append((fraction, text)),
    )

    assert [fraction for fraction, _text in updates] == [
        0.05,
        0.25,
        0.90,
        1.0,
    ]
    assert result["snapshot"]["items"] == [{}, {}]


def test_live_recommendation_snapshot_age_requires_timezone_and_freshness():
    now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)

    assert app._snapshot_age_seconds(now.isoformat(), now=now) == 0
    assert app._snapshot_age_seconds(
        (now - timedelta(seconds=181)).isoformat(),
        now=now,
    ) == 181
    assert app._snapshot_age_seconds("2026-07-20T10:00:00", now=now) is None


def test_persisted_football_signal_keeps_point_probability_and_haircut_separate(
    monkeypatch,
):
    monkeypatch.setattr(
        app,
        "prematch_btts_candidate",
        lambda *_args, **_kwargs: SimpleNamespace(
            model_ready=True,
            model_probability=64.0,
            probability_haircut=12.0,
            evidence_stage="SHADOW",
            selection="Ja",
        ),
    )
    frame = pd.DataFrame(
        [
            {
                "Home": "A",
                "Away": "B",
                "League": "BL1",
                "Date": "2026-08-03",
                "_analysis": {"details": {"ml_active": True}},
            }
        ]
    )

    signal = app._persist_prematch(frame)["signals"][0]

    assert signal["p"] == pytest.approx(0.64)
    assert signal["haircut"] == pytest.approx(0.12)
    assert signal["evidence_stage"] == "SHADOW"
    assert signal["policy_version"] == BETTING_POLICY_VERSION


def test_multi_sport_fetches_only_the_selected_basketball_scope(monkeypatch):
    from scanners import basketball_scanner

    calls = []

    class FakeBasketballScanner:
        def __init__(self):
            self.errors = {}

        def scan_live_games(self, league):
            calls.append(("basketball", league))
            return [
                {
                    "home_team": "Home",
                    "away_team": "Away",
                    "league": league,
                    "period": 2,
                    "home_score": 42,
                    "away_score": 40,
                }
            ]

        def calculate_scoring_projection(self, _game):
            raise AssertionError("Legacy projection must not run")

        def get_live_nhl_games(self):
            raise AssertionError("NHL must not be fetched for Basketball")

    monkeypatch.setattr(
        basketball_scanner,
        "BasketballScanner",
        FakeBasketballScanner,
    )

    snapshot = app._fetch_multi_sport_snapshot("Basketball", "NBA")

    assert calls == [("basketball", "NBA")]
    assert snapshot["sport"] == "Basketball"
    assert snapshot["detail_filter"] == "NBA"
    assert len(snapshot["items"]) == 1
    assert "nhl" not in snapshot
    assert app._multi_sport_event_label("Basketball", snapshot["items"][0]) == (
        "Home vs Away | Q2 | 42:40"
    )


def test_multi_sport_eishockey_does_not_run_basketball_scan(monkeypatch):
    from scanners import basketball_scanner

    calls = []

    class FakeBasketballScanner:
        def __init__(self):
            self.errors = {}

        def scan_live_games(self, _league):
            raise AssertionError("Basketball must not be fetched for Eishockey")

        def get_live_nhl_games(self):
            calls.append("nhl")
            return [
                {
                    "home_team": "ZSC",
                    "away_team": "SCB",
                    "period": 1,
                    "home_score": 1,
                    "away_score": 0,
                    "game_clock": "12:34",
                }
            ]

    monkeypatch.setattr(
        basketball_scanner,
        "BasketballScanner",
        FakeBasketballScanner,
    )

    snapshot = app._fetch_multi_sport_snapshot("Eishockey")

    assert calls == ["nhl"]
    assert snapshot["sport"] == "Eishockey"
    assert app._multi_sport_event_label("Eishockey", snapshot["items"][0]) == (
        "SCB @ ZSC | P1 | 0:1"
    )


def test_multi_sport_esports_filter_is_scoped_to_pandascore(monkeypatch):
    from scanners import esports_scanner

    calls = []

    class FakeEsportsScanner:
        def __init__(self):
            self.api_key = "configured"
            self.errors = {}

        def get_matches(self, game):
            calls.append(game)
            return [
                {
                    "team1": "Alpha",
                    "team2": "Beta",
                    "game": "VALORANT",
                    "team1_score": 1,
                    "team2_score": 0,
                }
            ]

        def analyze_match(self, _match):
            raise AssertionError("Legacy exploratory estimate must not run")

    monkeypatch.setattr(esports_scanner, "EsportsScanner", FakeEsportsScanner)

    snapshot = app._fetch_multi_sport_snapshot("E-Sport", "Valorant")

    assert calls == ["valorant"]
    assert snapshot["sport"] == "E-Sport"
    assert snapshot["credentials_available"] is True
    assert app._multi_sport_event_label("E-Sport", snapshot["items"][0]) == (
        "Alpha vs Beta | 1:0"
    )


def test_multi_sport_rejects_filters_from_another_sport():
    with pytest.raises(ValueError):
        app._fetch_multi_sport_snapshot("Tennis", "CS2")
    with pytest.raises(ValueError):
        app._fetch_multi_sport_snapshot("E-Sport", "NBA")


def test_multi_sport_release_is_fail_closed_during_shadow_ramp_up():
    blocker = app._multi_sport_release_blockers(
        "E-Sport",
        {"status": "upcoming"},
        esports_release={"ready": False, "settled": 5, "required": 300},
    )
    assert blocker
    assert "5/300" in blocker[0]


def test_esport_calibration_alone_never_unlocks_real_money():
    blocker = app._multi_sport_release_blockers(
        "E-Sport",
        {"status": "upcoming"},
        esports_release={
            "ready": False,
            "calibration_ready": True,
            "price_evidence_ready": False,
            "settled": 300,
            "required": 300,
        },
    )

    assert blocker
    assert "CLV" in blocker[0]


def test_multi_sport_live_esport_is_separate_from_prematch_release():
    blocker = app._multi_sport_release_blockers(
        "E-Sport",
        {"status": "live"},
        esports_release={"ready": True, "settled": 100, "required": 100},
    )
    assert blocker
    assert "Live-Wetten" in blocker[0]


def test_basketball_and_nhl_require_independent_release_evidence():
    assert app._multi_sport_release_blockers("Basketball", {})
    assert app._multi_sport_release_blockers("Eishockey", {})


def test_multi_sport_tennis_event_label_uses_verified_set_score():
    label = app._multi_sport_event_label("Tennis", {
        "player1": "Player A",
        "player2": "Player B",
        "player1_score": 1,
        "player2_score": 0,
    })

    assert label == "Player A vs Player B | 1:0"


def test_multi_sport_cricket_event_label_uses_current_innings_fields():
    label = app._multi_sport_event_label("Cricket", {
        "team1": "Alpha",
        "team2": "Beta",
        "current_runs": 191,
        "current_wickets": 4,
        "current_over": 40.2,
    })

    assert label == "Alpha vs Beta | 191/4 nach 40.2 Over"


def test_football_data_org_key_is_never_used_as_api_football_key(monkeypatch):
    monkeypatch.setattr(
        app,
        "load_app_config",
        lambda _st: AppConfig(api_key="football-data-only"),
    )
    app.get_analyzer.clear()
    try:
        assert app.get_analyzer() is None
    finally:
        app.get_analyzer.clear()


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
    with pytest.raises(ValueError):
        calculate_evidence_score(12.5, 12, 5, 5, [60.0, 61.0])


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


def test_live_market_filter_uses_selected_remaining_goal_probability():
    analyses = [
        {
            "id": "high-btts",
            "home_team": "A",
            "away_team": "B",
            "btts_prob": 90.0,
            "btts_confidence": "MEDIUM",
            "live_data_quality": "MEDIUM",
            "remaining_goals": {
                "over_0_5_probability": 40.0,
                "home_scores_probability": 35.0,
                "away_scores_probability": 20.0,
            },
        },
        {
            "id": "high-rest",
            "home_team": "C",
            "away_team": "D",
            "btts_prob": 45.0,
            "btts_confidence": "MEDIUM",
            "live_data_quality": "MEDIUM",
            "remaining_goals": {
                "over_0_5_probability": 75.0,
                "home_scores_probability": 30.0,
                "away_scores_probability": 65.0,
            },
        },
    ]

    another_goal = app._filter_live_opportunities(
        analyses,
        60,
        "Streng: Live-xG + Prematch (empfohlen)",
        "Noch ein Tor",
    )
    team_goal = app._filter_live_opportunities(
        analyses,
        60,
        "Streng: Live-xG + Prematch (empfohlen)",
        "Team trifft noch",
    )

    assert [item["id"] for item in another_goal] == ["high-rest"]
    assert [item["id"] for item in team_goal] == ["high-rest"]
    probability, selection = app._live_market_signal(analyses[1], "Team trifft noch")
    assert probability == pytest.approx(65.0)
    assert selection == "D trifft noch"


def test_strict_live_data_basis_is_the_ui_default():
    assert app.LIVE_DATA_BASIS_OPTIONS[0] == "Streng: Live-xG + Prematch (empfohlen)"


def test_equal_team_goal_probabilities_do_not_create_a_team_selection():
    probability, selection = app._live_market_signal(
        {
            "home_team": "A",
            "away_team": "B",
            "remaining_goals": {
                "home_scores_probability": 45.0,
                "away_scores_probability": 45.0,
            },
        },
        "Team trifft noch",
    )

    assert probability is None
    assert selection == "Kein klarer Teamvorteil"


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

    updates = []
    app._scan_prematch(
        analyzer,
        ["BL1"],
        7,
        progress_cb=lambda fraction, text: updates.append((fraction, text)),
    )
    fractions = [fraction for fraction, _text in updates]
    assert fractions == sorted(fractions)
    assert fractions[0] == 0.01
    assert fractions[-1] == 1.0
    assert any("Liga 1/1" in text for _fraction, text in updates)


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


def test_alternative_market_provider_records_http_200_account_error():
    analyzer = PreMatchAlternativeAnalyzer("api")
    response = Mock(
        status_code=200,
        json=Mock(return_value={"errors": {"access": "account suspended"}, "response": []}),
    )

    assert analyzer._response_data(response, "team stats", list) is None
    assert "suspended" in analyzer.errors["team stats"]


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
            "fixture": {"id": 10, "status": {"elapsed": 70}},
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
    assert bot.predictor.predict.call_args.kwargs["minute"] == 70
    assert bot.predictor.format_prediction.call_args.kwargs["red_card_minute"] == 55


def test_red_card_app_prediction_uses_current_snapshot_minute():
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    bot.get_live_stats = Mock(return_value={"xg_home": 0.9, "xg_away": 0.4})
    card = {
        "player": "Player",
        "team": "Home",
        "team_id": 1,
        "minute": 55,
        "match": {
            "fixture": {"id": 10, "status": {"elapsed": 70}},
            "teams": {
                "home": {"id": 1, "name": "Home"},
                "away": {"id": 2, "name": "Away"},
            },
            "goals": {"home": 1, "away": 0},
            "league": {"name": "League", "country": "Country"},
        },
    }

    entry = app._red_card_entry(bot, card)

    assert entry["prediction_minute"] == 70
    assert entry["prediction"]["minute"] == 70
    assert entry["card"]["minute"] == 55


def test_red_card_provider_records_http_errors(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    monkeypatch.setattr(
        "red_card_bot.requests.get",
        Mock(return_value=Mock(status_code=503)),
    )

    assert bot.get_live_matches() == []
    assert bot.errors == [{"operation": "live_matches", "message": "HTTP 503"}]


def test_red_card_provider_records_http_200_account_errors(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    response = Mock(
        status_code=200,
        json=Mock(return_value={"errors": {"access": "account suspended"}, "response": []}),
    )
    monkeypatch.setattr("red_card_bot.requests.get", Mock(return_value=response))

    assert bot.get_live_stats(1, 10, 20) is None
    assert bot.errors == [{
        "operation": "live_stats",
        "message": "{'access': 'account suspended'}",
    }]


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


def test_red_card_event_rejects_boolean_extra_time(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    match = {
        "fixture": {"id": 1, "status": {"elapsed": 50}},
        "league": {"id": 39},
        "teams": {"home": {"id": 10}, "away": {"id": 20}},
        "goals": {"home": 1, "away": 0},
    }
    response = Mock(
        status_code=200,
        json=Mock(return_value={
            "response": [{
                "type": "Card",
                "detail": "Red Card",
                "player": {"id": 7, "name": "Player"},
                "team": {"id": 10, "name": "Home"},
                "time": {"elapsed": 50, "extra": False},
            }],
        }),
    )
    monkeypatch.setattr("red_card_bot.requests.get", Mock(return_value=response))

    assert bot.check_match_for_red_cards(match) == []


def test_red_card_finder_can_recheck_a_seen_live_event(monkeypatch):
    bot = RedCardBotEnhanced(api_key="api", streamlit_mode=False)
    match = {
        "fixture": {"id": 1, "status": {"elapsed": 50}},
        "league": {"id": 39},
        "teams": {"home": {"id": 10}, "away": {"id": 20}},
        "goals": {"home": 1, "away": 0},
    }
    response = Mock(
        status_code=200,
        json=Mock(return_value={
            "response": [{
                "type": "Card",
                "detail": "Red Card",
                "player": {"id": 7, "name": "Player"},
                "team": {"id": 10, "name": "Home"},
                "time": {"elapsed": 50, "extra": 0},
            }],
        }),
    )
    monkeypatch.setattr("red_card_bot.requests.get", Mock(return_value=response))
    bot.alerted_cards = {"1_10_7_50_0": 1.0}

    assert bot.check_match_for_red_cards(match) == []
    assert len(bot.check_match_for_red_cards(match, include_seen=True)) == 1


def test_h2h_provider_rejects_wrong_fixture_membership(monkeypatch):
    client = APIFootball("api")
    monkeypatch.setattr(client, "_rate_limit", Mock())
    response = Mock(
        status_code=200,
        json=Mock(return_value={
            "response": [{
                "teams": {"home": {"id": 10}, "away": {"id": 30}},
                "goals": {"home": 1, "away": 1},
            }],
        }),
    )
    monkeypatch.setattr("api_football.requests.get", Mock(return_value=response))

    assert client.get_h2h(10, 20) == []
    assert client.last_error == "head-to-head: invalid fixture data"


def test_live_provider_exposes_http_failure(monkeypatch):
    client = APIFootball("api")
    monkeypatch.setattr(client, "_rate_limit", Mock())
    monkeypatch.setattr(
        "api_football.requests.get",
        Mock(return_value=Mock(status_code=429)),
    )

    assert client.get_live_matches() == []
    assert client.last_error == "live fixtures: HTTP 429"


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
