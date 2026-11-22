"""Offline provider-boundary and numerical parity tests for grouped football data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from scanners.ultra_live_scanner_v3 import UltraLiveScanner


def native():
    def stats(team, xg, red):
        return {"team": {"id": team, "name": str(team)}, "statistics": [
            {"type": "expected_goals", "value": xg}, {"type": "Red Cards", "value": red},
            {"type": "Total Shots", "value": 5}]}
    start = datetime.now(timezone.utc) - timedelta(minutes=60)
    from season_utils import current_season_start_year_for_id
    return {"fixture": {"id": 81, "date": start.isoformat(), "status": {"short": "2H", "elapsed": 60}},
            "league": {"id": 39, "season": current_season_start_year_for_id(39), "name": "Liga"},
            "teams": {"home": {"id": 1, "name": "1"}, "away": {"id": 2, "name": "2"}},
            "goals": {"home": 1, "away": 0}, "score": {"halftime": {"home": 1, "away": 0}},
            "statistics": [stats(2, "0.40", 1), stats(1, "1.60", None)],
            "events": [{"time": {"elapsed": 31}, "team": {"id": 1}, "type": "Goal", "detail": "Normal Goal"},
                       {"time": {"elapsed": 52}, "team": {"id": 2, "name": "2"}, "player": {"id": 9, "name": "Gast"},
                        "type": "Card", "detail": "Red Card"}]}


def source():
    import live_football_source
    return live_football_source


def response(rows, params, **update):
    payload = {"get": "fixtures", "parameters": params, "results": len(rows), "errors": [],
               "paging": {"current": 1, "total": 1}, "response": rows}
    payload.update(update)
    return SimpleNamespace(status_code=200, json=lambda: payload)


def test_customers_share_one_governed_group_request_without_redirect_or_fallback(monkeypatch):
    import api_budget
    row = native()
    other = deepcopy(row)
    other["league"]["id"] = 1000000
    other["fixture"]["id"] = 82
    calls = []
    def get(url, **kw):
        calls.append((url, kw))
        return response([row, other] if "live" in kw["params"] else [row], kw["params"])
    monkeypatch.setattr(api_budget, "api_football_get", get)
    live = source().LiveFootballSource("offline", ready=lambda: True)
    assert live.discover() == [row]
    assert live.details([81, 83]) == [row]
    assert [k["label"] for _, k in calls] == ["live-ticker:discover", "live-ticker:details"]
    assert calls[-1][1]["params"] == {"ids": "81-83"}
    assert all(url.endswith("/fixtures") and k["priority"] == api_budget.APIBudgetPriority.BACKGROUND
               and k["allow_redirects"] is False and 0 < k["timeout"] <= 15 for url, k in calls)


@pytest.mark.parametrize("update", [{"errors": {"token": "private"}}, {"results": True},
    {"parameters": {"ids": "82"}}, {"paging": {"current": 1, "total": 2}}, {"get": "odds"},
    {"response": "private"}, {"response": [dict(native(), fixture={"id": 82})]}])
def test_unproved_group_is_error_not_successful_empty(monkeypatch, update):
    import api_budget
    calls = []
    def get(*args, **kw):
        calls.append(kw)
        return response([native()], kw["params"], **update)
    monkeypatch.setattr(api_budget, "api_football_get", get)
    with pytest.raises(source().LiveSourceError) as exc:
        source().LiveFootballSource("offline", ready=lambda: True).details([81])
    assert "private" not in str(exc.value) and len(calls) == 1


def test_local_job_gate_runs_immediately_before_each_call_and_invalid_ids_never_fetch(monkeypatch):
    import api_budget
    calls = []
    def get(*args, **kw):
        calls.append(kw)
        return response([], kw["params"])
    monkeypatch.setattr(api_budget, "api_football_get", get)
    states = iter([True, False])
    live = source().LiveFootballSource("offline", ready=lambda: next(states))
    assert live.discover() == []
    with pytest.raises(source().LiveSourceError):
        live.details([81])
    for bad in ([], [True], [0], [1, 1], list(range(1, 22))):
        with pytest.raises(ValueError):
            live.details(bad)
    assert len(calls) == 1


def test_native_group_uses_existing_ordinary_and_red_models_without_http(monkeypatch):
    import requests
    from dataclasses import asdict
    from red_card_impact_predictor import RED_CARD_MODEL_VERSION, RedCardImpactPredictor
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("unexpected network"))
    row = native()
    ordinary, red = source().analyze_detail(row)
    legacy = UltraLiveScanner(None, SimpleNamespace(
        get_match_statistics=lambda *args: {"xg_home": 1.6, "xg_away": 0.4, "red_cards_home": 0, "red_cards_away": 1},
        get_fixture_events=lambda _: row["events"])).analyze_live_match_ultra(row)
    for key in ("remaining_goals", "over_under", "next_goal", "breakdown", "btts_prob", "model_version"):
        assert ordinary[key] == legacy[key]
    assert ordinary["live_data_quality"] == "LOW" and ordinary["scheduled_start"] == row["fixture"]["date"]
    assert red["card"]["card_id"] == "81_2_9_52_0" and red["red_side"] == "away"
    assert red["model_version"] == RED_CARD_MODEL_VERSION and red["prediction"] == asdict(
        RedCardImpactPredictor().predict(60, 1, 0, "away", {"xg_home": 1.6, "xg_away": 0.4}, red_card_minute=52))


@pytest.mark.parametrize("change", [
    lambda r: r.pop("statistics"), lambda r: r.pop("events"),
    lambda r: r["goals"].update(home=0), lambda r: r["score"]["halftime"].update(home=0),
    lambda r: r["statistics"][0]["team"].update(id=1), lambda r: r["statistics"][0]["team"].update(id=3),
    lambda r: r["statistics"][0]["statistics"].pop(1), lambda r: r["statistics"][0]["statistics"].pop(0),
    lambda r: r["statistics"][0]["statistics"][0].update(value="1.5%"),
    lambda r: r["statistics"][0]["statistics"].append({"type": "Red Cards", "value": 0}),
    lambda r: r["events"][0].update(type="Var", detail="Goal under review"),
    lambda r: r["events"].append(dict(r["events"][0], type="Var", detail="Card upgrade")),
    lambda r: r["events"][1]["time"].update(elapsed=61), lambda r: r["events"][1]["team"].update(id=1),
    lambda r: r["events"][1].update(detail="Red Card", comments="card cancelled"),
    lambda r: r["fixture"]["status"].update(elapsed=90, extra=2), lambda r: r["fixture"]["status"].update(short="FT"),
])
def test_uncorroborated_details_do_not_publish_either_model(change):
    row = native()
    change(row)
    assert source().analyze_detail(row) == (None, None)


def warm(row, monkeypatch, broken=None):
    """Run the real native team decoder, cache, old Analyzer and old LiveScanner."""
    import advanced_analyzer as advanced
    import api_football
    analyzer = advanced.AdvancedBTTSAnalyzer.__new__(advanced.AdvancedBTTSAnalyzer)
    analyzer.engine = SimpleNamespace(LEAGUES_CONFIG={"PL": 39}, get_recent_form=lambda *a, **k: {})
    analyzer.weights = {"statistical": .6, "poisson": .4}
    analyzer.api_football_key = None
    analyzer.bivariate_poisson = advanced.BivariatePoissonModel()
    analyzer.dixon_coles = advanced.DixonColesModel()
    analyzer.model_trained = False
    season = row["league"]["season"]
    start = datetime.fromisoformat(row["fixture"]["date"]).timestamp()
    api = api_football.APIFootball("offline")
    monkeypatch.setattr(api_football.time, "time", lambda: start - 100 if broken != "live" else start + 1)
    def get(url, *, params, **kw):
        team = params["team"]
        if url.endswith("/teams/statistics"):
            result = {"team": {"id": team if broken != "team" else 7, "name": str(team)},
                      "league": {"id": 39, "season": season}, "clean_sheet": {"home": 0, "away": 0},
                      "failed_to_score": {"home": 0, "away": 0}, "fixtures": {"played": {"home": 5, "away": 5}},
                      "goals": {"for": {"average": {"home": "2.1", "away": "1.24"}},
                                "against": {"average": {"home": "1.34", "away": "0.8"}}}}
        else:
            result = [{"fixture": {"id": 21+i, "status": {"short": "FT"}}, "league": {"id": 39, "season": season},
                       "teams": {"home": {"id": team if i % 2 else 8}, "away": {"id": 8 if i % 2 else team}},
                       "goals": {"home": 1, "away": 1}} for i in range(6)]
            if broken == "history":
                result[0]["league"]["id"] = 78
        return SimpleNamespace(status_code=200, json=lambda: {"response": result})
    api._rate_limit = lambda: None
    api._get = get
    for team in (1, 2):
        stats = api.get_team_statistics(team, 39, season)
        if stats is not None:
            analyzer._store_stats_cache("_team_stats_cache", f"season_{team}_39_{season}", stats)
    return analyzer


def test_verified_warm_venue_priors_match_the_existing_live_solver(monkeypatch):
    row = native()
    analyzer = warm(row, monkeypatch)
    legacy_stats = {"xg_home": 1.6, "xg_away": .4, "red_cards_home": 0, "red_cards_away": 1}
    scanner = UltraLiveScanner(analyzer, SimpleNamespace(get_match_statistics=lambda *a: legacy_stats,
                                                         get_fixture_events=lambda _: row["events"]))
    expected = scanner.analyze_live_match_ultra(row)
    assert expected["live_data_quality"] == "MEDIUM"
    actual, _ = source().analyze_detail(row, analyzer)
    assert actual["live_data_quality"] == "MEDIUM"
    assert actual["breakdown"] == expected["breakdown"]
    assert actual["breakdown"]["prematch_home_goal_prior"] == 1.45
    assert actual["breakdown"]["prematch_away_goal_prior"] == 1.29
    assert actual["remaining_goals"] == expected["remaining_goals"]


@pytest.mark.parametrize("bad", ["team", "history", "live", "expired", "season", "naive", "other_team"])
def test_cache_hit_needs_proved_team_venue_season_and_pre_kickoff_data(monkeypatch, bad):
    row = native()
    analyzer = warm(row, monkeypatch, bad)
    if bad == "expired":
        analyzer._stats_cache_observed = {}
    if bad == "season":
        row["league"]["season"] -= 1
    if bad == "naive":
        row["fixture"]["date"] = "2026-11-22T11:00:00"
    if bad == "other_team":
        row["statistics"][1]["team"]["id"] = row["teams"]["home"]["id"] = row["events"][0]["team"]["id"] = 18
    actual, _ = source().analyze_detail(row, analyzer)
    assert actual["live_data_quality"] == "LOW"
    assert actual["xg_data"]["home_prior"] is actual["xg_data"]["away_prior"] is None


def test_empty_zero_page_ok_only_if_success_and_no_rows(monkeypatch):
    import api_budget
    rows = []
    def get(*a, **kw):
        return response(rows, kw["params"], paging={"current": 1, "total": 0})
    monkeypatch.setattr(api_budget, "api_football_get", get)
    live = source().LiveFootballSource("offline", ready=lambda: True)
    assert live.discover() == []
    rows.append(native())
    with pytest.raises(source().LiveSourceError):
        live.discover()


def test_duplicate_or_unidentified_discovery_must_not_delete_last_stand(monkeypatch):
    import api_budget
    row = native()
    rows = [row, row]
    monkeypatch.setattr(api_budget, "api_football_get", lambda *a, **kw: response(rows, kw["params"]))
    live = source().LiveFootballSource("offline", ready=lambda: True)
    with pytest.raises(source().LiveSourceError):
        live.discover()
    rows[:] = [dict(row, league={})]
    with pytest.raises(source().LiveSourceError):
        live.discover()


@pytest.mark.parametrize("stray", [99, None, True])
def test_partial_bound_details_keep_requested_end_not_foreign_missing_or_duplicate_ids(monkeypatch, stray):
    import api_budget
    row = native()
    row["fixture"]["status"]["short"] = "FT"
    duplicate = dict(row, fixture={"id": 82})
    rows = [dict(row, fixture={"id": stray}), duplicate, row, duplicate]
    monkeypatch.setattr(api_budget, "api_football_get", lambda *a, **kw: response(rows, kw["params"]))
    assert source().LiveFootballSource("offline", ready=lambda: True).details([81, 82, 83]) == [row]


def test_completed_var_confirmation_on_a_corroborated_goal_is_not_permanent_block():
    row = native()
    confirmation = {"type": "Var", "detail": "Goal confirmed", "time": {"elapsed": 32}, "team": {"id": 1}}
    row["events"].append(confirmation)
    assert source().analyze_detail(row)[1] is not None
    confirmation["team"]["id"] = 2
    assert source().analyze_detail(row) == (None, None)


@pytest.mark.parametrize("index", ["statistics", "events"])
def test_native_child_identifiers_cannot_point_to_another_fixture(index):
    row = native()
    row[index][0]["fixture"] = {"id": 92}
    assert source().analyze_detail(row) == (None, None)


def test_foreign_league_or_swapped_named_team_statistics_cannot_get_misattributed():
    row = native()
    row["statistics"][0]["team"]["name"] = row["teams"]["home"]["name"]
    assert source().analyze_detail(row) == (None, None)


def test_second_yellow_native_dismissal_keeps_existing_card_attribution():
    row = native()
    row["events"][1]["detail"] = "Second Yellow card"
    actual, red = source().analyze_detail(row)
    assert actual["red_cards"]["away_count"] == 1
    assert red["prediction_minute"] == 60 and red["card"]["minute"] == 52
    row["events"][1]["time"] = {"elapsed": 45, "extra": 31}
    assert source().analyze_detail(row) == (None, None)


@pytest.mark.parametrize("card_minute", [52, 32])
def test_second_yellow_and_straight_red_share_the_observed_duration_and_goal_probabilities(card_minute):
    row = native()
    card = row["events"][1]
    card["time"]["elapsed"] = card_minute
    row["events"].insert(0, dict(card, time={"elapsed": 12}, detail="Yellow Card"))
    straight_red, _ = source().analyze_detail(row)

    card["detail"] = "Second Yellow card"
    second_yellow, _ = source().analyze_detail(row)
    assert second_yellow["red_cards"]["context"]["minutes_since_card"] == 60 - card_minute
    assert second_yellow["remaining_goals"] == straight_red["remaining_goals"]
    # The standalone scanner reads the native event itself, without the
    # grouped adapter's already-corroborated minute.
    scanner = UltraLiveScanner(None, SimpleNamespace(
        get_match_statistics=lambda *args: second_yellow["stats"], get_fixture_events=lambda _: row["events"]))
    standalone = scanner.analyze_live_match_ultra(row, prematch_priors=(None, None))
    assert standalone["red_cards"]["context"]["minutes_since_card"] == 60 - card_minute
    assert standalone["remaining_goals"] == straight_red["remaining_goals"]


@pytest.mark.parametrize("detail", ["Red Card", "Second Yellow card"])
def test_grouped_first_half_added_time_uses_one_model_clock_but_preserves_native_receipt(detail):
    from red_card_impact_predictor import RED_CARD_MODEL_VERSION
    row = native()
    row["fixture"]["status"]["elapsed"] = 57
    row["events"][1]["detail"] = detail

    def at(timing):
        original = deepcopy(timing)
        row["events"][1]["time"] = timing
        ordinary, red = source().analyze_detail(row)
        assert row["events"][1]["time"] == original
        return ordinary, red

    split, split_red = at({"elapsed": 45, "extra": 3})
    packed, packed_red = at({"elapsed": 48, "period": "1H"})
    regular, regular_red = at({"elapsed": 48})  # no period evidence for first-half added time
    assert packed["remaining_goals"] == split["remaining_goals"]
    assert packed_red["prediction"] == split_red["prediction"]
    assert packed["red_cards"]["context"]["minutes_since_card"] == 12
    assert regular["red_cards"]["context"]["minutes_since_card"] == 9
    assert regular_red["prediction"]["context_effects"]["minutes_since_card"] == 9
    assert regular["remaining_goals"] != packed["remaining_goals"]
    assert regular_red["model_version"] == RED_CARD_MODEL_VERSION
    assert packed_red["model_version"] == split_red["model_version"] != RED_CARD_MODEL_VERSION
    assert (split_red["card"]["card_id"], packed_red["card"]["card_id"]) == ("81_2_9_45_3", "81_2_9_48_0")
    assert (split_red["card"]["minute"], split_red["card"]["extra_minute"]) == (45, 3)
    assert (packed_red["card"]["minute"], packed_red["card"]["extra_minute"]) == (48, 0)


def test_duplicate_goal_row_cannot_validate_an_inflated_score():
    row = native()
    row["goals"]["home"] = row["score"]["halftime"]["home"] = 2
    row["events"].append(deepcopy(row["events"][0]))
    assert source().analyze_detail(row) == (None, None)


@pytest.mark.parametrize("status", [302, 429, "timeout"])
def test_http_error_stays_a_single_failed_attempt_without_echoing_secrets(monkeypatch, status):
    import api_budget
    calls = []
    def get(*args, **kw):
        calls.append(kw)
        if status == "timeout":
            raise TimeoutError("secret from failed network")
        return SimpleNamespace(status_code=status)
    monkeypatch.setattr(api_budget, "api_football_get", get)
    with pytest.raises(source().LiveSourceError) as exc:
        source().LiveFootballSource("secret", ready=lambda: True).discover()
    assert len(calls) == 1 and "secret" not in str(exc.value)

