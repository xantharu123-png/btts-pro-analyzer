"""Actual P3 captures and persisted synthetic B1 replies, never live-feed proof."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
import importlib
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from context_observations import append_observation
from context_sources import team_sports_status as status
from model_artifacts import canonical_bytes
from tests.test_team_sports_live_original import NOW, build, capture, raw_inputs

PROVIDERS = ("ESPN", "EuroLeague", "NHL")


def api():
    return importlib.import_module("context_sources.team_sports_binding")


def source_inputs(provider):
    sport = "ice_hockey" if provider == "NHL" else "basketball"
    target, history = raw_inputs(sport)
    if provider == "EuroLeague":
        for i, raw in enumerate([target, *history]):
            raw.update(provider="EuroLeague", competition="EuroLeague", season="E2025",
                provider_event_id=f"uuid-{i}",
                context_rules=dict(regulation_minutes=40, regulation_periods=4, overtime_period_minutes=5))
            for side in ("home", "away"):
                raw[side + "_team_id"] = "Club" + raw[side + "_team_id"]
    return sport, target, history


def source_reply(provider, raw, *, target=False):
    start = raw.get("starts_at") or raw.get("start_time")
    lifecycle = raw.get("status")
    if provider == "ESPN":
        native_status = {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False} if target else {
            "state": "post", "name": "STATUS_FINAL", "completed": True}
        if lifecycle == "started":
            native_status = {"state": "in", "name": "STATUS_IN_PROGRESS", "completed": False}
        if lifecycle == "cancelled":
            native_status = {"state": "post", "name": "STATUS_CANCELED", "completed": False}
        game = dict(id=raw["provider_event_id"], date=start, status={"type": native_status},
                    competitors=[dict(homeAway=side, team=dict(id=raw[side + "_team_id"], abbreviation=side),
                        **({"score": str(raw[side + "_score"])} if side + "_score" in raw else {}))
                        for side in ("home", "away")])
        if "neutral_site" in raw:
            game["neutralSite"] = raw["neutral_site"]
        return {"season": {"year": 2026}, "events": [{"id": raw["provider_event_id"], "date": start,
                "competitions": [game]}]}
    if provider == "EuroLeague":
        game = dict(id=raw["provider_event_id"], identifier="E2025_" + raw["provider_event_id"],
            seasonCode="E2025", played=not target and lifecycle == "completed", utcDate=start,
            local=dict(club=dict(code=raw["home_team_id"])), road=dict(club=dict(code=raw["away_team_id"])))
        for side, native_side in (("home", "local"), ("away", "road")):
            if side + "_score" in raw:
                game[native_side]["score"] = raw[side + "_score"]
        if lifecycle == "cancelled":
            game["cancelled"] = True
        if "neutral_site" in raw:
            game["isNeutralVenue"] = raw["neutral_site"]
        return {"data": [game]}
    game = dict(id=int(raw["provider_event_id"]), season=int(raw["season"]), gameType=raw["game_type"],
        startTimeUTC=start, gameState="FUT" if target else {"started": "LIVE", "cancelled": "CANC"}.get(lifecycle, "OFF"),
        gameScheduleState="OK", homeTeam=dict(id=int(raw["home_team_id"]), abbrev="HOME"),
        awayTeam=dict(id=int(raw["away_team_id"]), abbrev="AWAY"))
    for side in ("home", "away"):
        if side + "_score" in raw:
            game[side + "Team"]["score"] = raw[side + "_score"]
    if "last_period_type" in raw:
        game["gameOutcome"] = {"lastPeriodType": raw["last_period_type"]}
    if "neutral_site" in raw:
        game["neutralSite"] = raw["neutral_site"]
    return {"gameWeek": [{"games": [game]}]}


def native_game(provider, body):
    return body["events"][0]["competitions"][0] if provider == "ESPN" else body["data"][0] if provider == "EuroLeague" else body["gameWeek"][0]["games"][0]


def record(path, provider, body, *, observed=NOW-timedelta(seconds=1), target=False, season="E2025"):
    if provider == "ESPN":
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        query = {"dates": "20260905" if target else "20260501-20260905", "limit": 100 if target else 1000}
        request_key = None if target else "nba:2026-05-01"
    elif provider == "EuroLeague":
        url = f"https://api-live.euroleague.net/v2/competitions/E/seasons/{season}/games"
        query, request_key = {"limit": 500}, None if target else season
    else:
        url, query, request_key = "https://api-web.nhle.com/v1/schedule/2026-09-05", {}, None if target else "2026-09-05"
    request = status.response_request(provider, url, query, phase="schedule" if target else "history",
        window=(date(2026, 9, 5), date(2026, 9, 5)) if target else None, request_key=request_key,
        response=SimpleNamespace(status_code=200, history=[], url=url + ("?" + urlencode(query) if query else "")))
    normalized, _ = status.normalize_team_sport_response(request, body, observed_at=observed)
    assert normalized
    return [append_observation(path, item, observed_at=observed) for item in normalized]


def pool(path, *, cutoff=NOW+timedelta(days=1)):
    return status.team_sport_observations_as_of(path, cutoff=cutoff)


def original(provider, *, target=None, history=None):
    sport, default_target, default_history = source_inputs(provider)
    return capture(sport, target=default_target if target is None else target,
                   rows=default_history if history is None else history)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_actual_source_rows_bind_by_raw_index_without_repeating_any_model_work(tmp_path, monkeypatch, provider):
    import sports_prematch
    sport, target, history = source_inputs(provider)
    current, prediction = original(provider)
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, target, target=True), target=True)
    record(path, provider, source_reply(provider, history[7]))
    rows = pool(path)
    def forbidden(*args, **kwargs): pytest.fail("binding repeated model work or IO")
    for name in ("predict_prematch", "_fit", "_predict", "_normalise_history", "_identity"):
        monkeypatch.setattr(sports_prematch, name, forbidden)
    frozen = canonical_bytes(prediction.to_dict())
    value = api().resolve_team_sport_original(current, rows)
    assert len(value.input_bindings) == 1 + len(history)
    assert value.input_bindings[0]["match_state"] == "matched"
    assert value.input_bindings[8]["match_state"] == "matched"
    assert value.input_bindings[7]["match_state"] == "missing"
    assert value.receipt_binding["history_receipts"] == [dict(input_index=7,
        receipt=value.input_bindings[8]["matching_receipt_refs"][0])]
    assert value.receipt_binding["artifact_refs"] == []
    assert canonical_bytes(prediction.to_dict()) == frozen
    if provider == "EuroLeague":
        assert value.event is None
        assert "native-scheduled-status-unconfirmed" in value.input_bindings[0]["reasons"]
    else:
        assert value.event["scheduled_start"] == canonical_timestamp(NOW+timedelta(hours=6))
        assert value.event["status"] == "scheduled"
        assert value.event["event_key"].endswith(target["provider_event_id"])


@pytest.mark.parametrize("provider", PROVIDERS)
def test_empty_warm_history_receipts_do_not_certify_or_erase_original(provider):
    current, prediction = original(provider)
    frozen = canonical_bytes(prediction.to_dict())
    value = api().resolve_team_sport_original(current, ())
    assert value.event is None and value.receipt_binding["event_receipt"] is None
    assert value.receipt_binding["history_receipts"] == []
    assert all(item["match_state"] == "missing" for item in value.input_bindings)
    assert canonical_bytes(prediction.to_dict()) == frozen


@pytest.mark.parametrize("provider", PROVIDERS)
def test_future_receipt_never_becomes_an_earlier_cache_observation(tmp_path, provider):
    _, target, history = source_inputs(provider)
    current, _ = original(provider)
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, target, target=True), target=True, observed=NOW+timedelta(microseconds=1))
    record(path, provider, source_reply(provider, history[0]), observed=NOW+timedelta(microseconds=1))
    value = api().resolve_team_sport_original(current, pool(path))
    assert value.event is None and value.receipt_binding["history_receipts"] == []
    assert value.receipt_binding["event_receipt"] is None
    assert all(not item["matching_receipt_refs"] for item in value.input_bindings)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_identical_later_recheck_binds_today_not_the_old_cache_timestamp(tmp_path, provider):
    _, _, history = source_inputs(provider)
    current, _ = original(provider)
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, history[0]), observed=NOW)
    rows = pool(path)
    value = api().resolve_team_sport_original(current, rows)
    assert value.input_bindings[1]["match_state"] == "matched"
    assert value.receipt_binding["history_receipts"] == [dict(input_index=0, receipt=rows[0]["digest"])]
    assert rows[0]["observed_at"] == canonical_timestamp(NOW)
    assert current.raw_history[0]["result_observed_at"] == history[0]["result_observed_at"]
    assert datetime.fromisoformat(history[0]["result_observed_at"]) < NOW


def test_outer_only_espn_withdrawal_reaches_old_competition_before_exact_key_filter(tmp_path):
    _, target, _ = source_inputs("ESPN")
    current, _ = original("ESPN")
    path = tmp_path / "context.db"
    initial = source_reply("ESPN", target, target=True)
    initial["events"][0]["id"] = "123"
    record(path, "ESPN", initial, target=True)
    valid = api().resolve_team_sport_original(current, pool(path))
    assert valid.event is not None
    correction = deepcopy(initial)
    correction["events"][0].pop("competitions")
    record(path, "ESPN", correction, target=True, observed=NOW)
    all_rows = pool(path)
    actual = api().resolve_team_sport_original(current, all_rows)
    assert actual.event is None
    assert actual.input_bindings[0]["current_state"] == "unknown"
    assert actual.input_bindings[0]["native_event_key"] == "espn:basketball:" + target["provider_event_id"]
    assert set(actual.input_bindings[0]["lineage_refs"]) == {row["digest"] for row in all_rows}
    assert asdict(actual) == asdict(api().resolve_team_sport_original(current, tuple(reversed(all_rows))))


def test_same_euroleague_alias_under_two_uuids_never_selects_a_default(tmp_path):
    _, target, _ = source_inputs("EuroLeague")
    path = tmp_path / "context.db"
    first = source_reply("EuroLeague", target, target=True)
    alias = first["data"][0]["identifier"]
    target["provider_event_id"] = alias
    current, _ = original("EuroLeague", target=target)
    record(path, "EuroLeague", first, target=True)
    second = deepcopy(first)
    second["data"][0]["id"] = "another-uuid"
    record(path, "EuroLeague", second, target=True, observed=NOW)
    value = api().resolve_team_sport_original(current, pool(path))
    assert value.event is None and value.receipt_binding["event_receipt"] is None
    assert value.input_bindings[0]["current_state"] == "conflicting"
    assert "native-alias-ambiguous" in value.input_bindings[0]["reasons"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_equal_receipt_time_differing_full_event_is_conflicting_before_matching_fields(tmp_path, provider):
    _, target, _ = source_inputs(provider)
    current, _ = original(provider)
    path = tmp_path / "context.db"
    first = source_reply(provider, target, target=True)
    record(path, provider, first, target=True)
    changed = deepcopy(first)
    game = native_game(provider, changed)
    time_field = {"ESPN": "date", "EuroLeague": "utcDate", "NHL": "startTimeUTC"}[provider]
    game[time_field] = canonical_timestamp(NOW+timedelta(hours=7))
    record(path, provider, changed, target=True)
    result = api().resolve_team_sport_original(current, pool(path))
    assert result.event is None
    assert result.input_bindings[0]["current_state"] == "conflicting"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_all_claimed_records_validate_even_when_unrelated_and_future(tmp_path, provider):
    _, target, _ = source_inputs(provider)
    current, _ = original("ESPN")
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, target, target=True), target=True, observed=NOW+timedelta(seconds=1))
    rows = list(pool(path))
    rows[0] = deepcopy(rows[0])
    rows[0]["payload"]["projection"]["status"] = "corrupted"
    with pytest.raises(ContextContractError):
        api().resolve_team_sport_original(current, rows)


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("score", [0, None])
def test_final_score_alias_never_falls_through_zero_or_explicit_null(tmp_path, provider, score):
    _, target, history = source_inputs(provider)
    raw = history[7]
    raw.update(home_score_final=score, home_score=99, away_score=1, winner_side="away")
    if provider == "NHL": raw["last_period_type"] = "REG"
    current, _ = original(provider, target=target, history=history)
    source = deepcopy(raw)
    source["home_score"] = 0
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, source))
    result = api().resolve_team_sport_original(current, pool(path)).input_bindings[8]
    assert result["match_state"] == ("matched" if score == 0 else "unknown")
    if score is None:
        assert "native-score-unavailable" in result["reasons"]
        assert result["matching_receipt_refs"] == []


@pytest.mark.parametrize("provider", PROVIDERS)
def test_historical_start_priority_is_actual_start_time_not_secondary_starts_at(tmp_path, provider):
    _, target, history = source_inputs(provider)
    source = deepcopy(history[7])
    history[7]["starts_at"] = canonical_timestamp(NOW-timedelta(days=4))
    current, _ = original(provider, target=target, history=history)
    assert any(match.event_id == history[7]["provider_event_id"].lower() for match in current.matches)
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, source))
    result = api().resolve_team_sport_original(current, pool(path))
    assert result.input_bindings[8]["match_state"] == "matched"


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("correction", ["started", "cancelled", "bad-participant", "rescheduled"])
def test_historical_documentary_match_never_revives_newer_native_revision(tmp_path, provider, correction):
    _, _, history = source_inputs(provider)
    current, _ = original(provider)
    path = tmp_path / "context.db"
    raw = deepcopy(history[7])
    first = source_reply(provider, raw)
    record(path, provider, first, observed=NOW-timedelta(seconds=2))
    if correction in ("started", "cancelled"):
        raw["status"] = correction
        second = source_reply(provider, raw)
    else:
        second = deepcopy(first)
        game = native_game(provider, second)
        if correction == "rescheduled":
            game[{"ESPN": "date", "EuroLeague": "utcDate", "NHL": "startTimeUTC"}[provider]] = canonical_timestamp(NOW-timedelta(days=1))
        elif provider == "ESPN":
            game["competitors"][0]["team"]["id"] = None
        elif provider == "EuroLeague":
            game["local"]["club"]["code"] = None
        else:
            game["homeTeam"]["id"] = None
    record(path, provider, second, observed=NOW-timedelta(seconds=1))
    rows = pool(path)
    result = api().resolve_team_sport_original(current, rows).input_bindings[8]
    assert result["match_state"] == "matched"  # actual OLD raw fact is retained
    assert len(result["matching_receipt_refs"]) == 1
    assert len(result["lineage_refs"]) == 2
    assert result["current_received_at"] == canonical_timestamp(NOW-timedelta(seconds=1))
    assert result["current_state"] == ("unknown" if correction == "bad-participant" else "available")
    assert any(reason in result["reasons"] for reason in ("native-current-unknown", "native-original-revision-superseded"))
    record(path, provider, first, observed=NOW)
    restored = api().resolve_team_sport_original(current, pool(path)).input_bindings[8]
    assert restored["current_state"] == "available"
    assert "native-original-revision-superseded" not in restored["reasons"]
    assert len(restored["matching_receipt_refs"]) == 2
    assert len(restored["lineage_refs"]) == 3
    # A historical cutoff remains frozen even when later source facts are supplied.
    historical = replace(current, as_of=NOW-timedelta(seconds=2))
    then = api().resolve_team_sport_original(historical, pool(path)).input_bindings[8]
    assert len(then["lineage_refs"]) == len(then["matching_receipt_refs"]) == 1


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_raw_history_position_survives_ignored_and_corrected_rows(tmp_path, provider):
    _, target, history = source_inputs(provider)
    old_raw = deepcopy(history[7])
    revised = deepcopy(old_raw)
    revised["home_team_id"] = "Club33" if provider == "EuroLeague" else "33"
    revised["result_observed_at"] = canonical_timestamp(NOW-timedelta(seconds=4))
    future = deepcopy(old_raw)
    future["result_observed_at"] = canonical_timestamp(NOW+timedelta(days=1))
    unusual = [None, "not-an-object", old_raw, revised, future, *history]
    current, prediction = original(provider, target=target, history=unusual)
    frozen = canonical_bytes(prediction.to_dict())
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, old_raw), observed=NOW-timedelta(seconds=2))
    record(path, provider, source_reply(provider, revised), observed=NOW-timedelta(seconds=1))
    result = api().resolve_team_sport_original(current, pool(path))
    assert len(result.input_bindings) == len(unusual)+1
    assert [row["input_index"] for row in result.input_bindings] == [None, *range(len(unusual))]
    assert result.input_bindings[1]["match_state"] == result.input_bindings[2]["match_state"] == "not_applicable"
    assert [row["input_index"] for row in result.receipt_binding["history_receipts"]] == [2, 3, 4, 12]
    assert all(len(result.input_bindings[i+1]["lineage_refs"]) == 2 for i in (2, 3, 4, 12))
    assert canonical_bytes(prediction.to_dict()) == frozen


def test_unique_espn_outer_alias_preserves_actual_selected_raw_id(tmp_path, monkeypatch):
    import sports_prematch
    _, target, history = source_inputs("ESPN")
    first = source_reply("ESPN", target, target=True)
    first["events"][0]["id"] = "12345"
    target["provider_event_id"] = "12345"
    current, prediction = original("ESPN", target=target, history=history)
    path = tmp_path / "context.db"
    record(path, "ESPN", first, target=True)
    binding = api().resolve_team_sport_original(current, pool(path))
    assert binding.event["event_key"] == "espn:basketball:12345"
    assert binding.input_bindings[0]["native_event_key"] == "espn:basketball:401999999"
    for name in ("_fit", "_predict", "predict_prematch"):
        monkeypatch.setattr(sports_prematch, name, lambda *a, **k: pytest.fail("a second target execution"))
    captured = build("basketball", current, event=binding.event, receipt_binding=binding.receipt_binding)
    assert captured.base["markets"]["home_win"].hex() == prediction.p_home.hex()
    assert captured.original["inputs"]["event"]["provider_event_id"] == "12345"
    assert captured.original["source_resolution"] == "unresolved"  # no invented P4b worker/approval


@pytest.mark.parametrize("timing", [-1, 0])
def test_espn_shared_outer_alias_does_not_choose_between_competitions(tmp_path, timing):
    _, target, _ = source_inputs("ESPN")
    body = source_reply("ESPN", target, target=True)
    body["events"][0]["id"] = "12345"
    path = tmp_path / "context.db"
    record(path, "ESPN", body, target=True)
    second = deepcopy(body)
    second["events"][0]["competitions"][0]["id"] = "67890"
    record(path, "ESPN", second, target=True, observed=NOW+timedelta(seconds=timing))
    current, _ = original("ESPN")
    result = api().resolve_team_sport_original(current, pool(path))
    assert result.event is None
    assert result.input_bindings[0]["current_state"] == "conflicting"
    assert "native-alias-ambiguous" in result.input_bindings[0]["reasons"]


@pytest.mark.parametrize("raw_id", ["E2025_uuid-0", "uuid-0", "UUID-0", "ｕuid-0", " uuid-0 "])
def test_euroleague_native_alias_is_exact_not_normalized(tmp_path, raw_id):
    _, target, history = source_inputs("EuroLeague")
    body = source_reply("EuroLeague", target, target=True)
    target["provider_event_id"] = raw_id
    current, prediction = original("EuroLeague", target=target, history=history)
    path = tmp_path / "context.db"
    record(path, "EuroLeague", body, target=True)
    binding = api().resolve_team_sport_original(current, pool(path))
    assert binding.event is None  # played=false is NOT scheduled
    assert binding.input_bindings[0]["match_state"] == ("matched" if raw_id in ("E2025_uuid-0", "uuid-0") else "missing" if raw_id == "UUID-0" else "unknown")
    if binding.input_bindings[0]["match_state"] == "matched":
        assert binding.input_bindings[0]["native_event_key"] == "euroleague:basketball:uuid-0"
        assert "native-scheduled-status-unconfirmed" in binding.input_bindings[0]["reasons"]
    captured = build("basketball", current, event=binding.event, receipt_binding=binding.receipt_binding)
    assert captured.base is None
    assert captured.original["outputs"]["p_home"].hex() == prediction.p_home.hex()


@pytest.mark.parametrize("raw_season", ["E2025", "E2024", None])
def test_euroleague_gamecode_only_stays_explicitly_composite(tmp_path, raw_season):
    _, target, history = source_inputs("EuroLeague")
    body = source_reply("EuroLeague", target, target=True)
    game = native_game("EuroLeague", body)
    game.pop("id")
    game.pop("identifier")
    game["gameCode"] = 406
    target.update(provider_event_id="406", season=raw_season)
    current, _ = original("EuroLeague", target=target, history=history)
    path = tmp_path / "context.db"
    record(path, "EuroLeague", body, target=True)
    result = api().resolve_team_sport_original(current, pool(path))
    assert result.event is None and result.input_bindings[0]["native_event_key"] is None
    assert result.receipt_binding["event_receipt"] is None
    assert "native-season-composite-unresolved" in result.input_bindings[0]["reasons"]
    assert len(result.input_bindings[0]["lineage_refs"]) == int(raw_season == "E2025")


def test_euroleague_same_gamecode_in_two_seasons_does_not_join_uuids(tmp_path):
    _, target, _ = source_inputs("EuroLeague")
    body = source_reply("EuroLeague", target, target=True)
    body["data"][0]["gameCode"] = 406
    target["provider_event_id"] = "406"
    current, _ = original("EuroLeague", target=target)
    path = tmp_path / "context.db"
    record(path, "EuroLeague", body, target=True)
    other = deepcopy(body)
    other["data"][0].update(id="old-uuid", identifier="E2024_old-uuid", seasonCode="E2024")
    record(path, "EuroLeague", other, target=True, season="E2024")
    value = api().resolve_team_sport_original(current, pool(path))
    assert value.input_bindings[0]["match_state"] == "matched"
    assert value.input_bindings[0]["native_event_key"] == "euroleague:basketball:uuid-0"
    assert len(value.input_bindings[0]["lineage_refs"]) == 1


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("claim", ["home", "away", "start", "neutral", "season", "provider", "competition", "sport"])
def test_known_conflicting_raw_claims_never_become_current_event(tmp_path, provider, claim):
    _, target, history = source_inputs(provider)
    body = source_reply(provider, target, target=True)
    if claim in ("home", "away"):
        target[claim + "_team_id"] = "Club33" if provider == "EuroLeague" else "33"
    elif claim == "start": target["starts_at"] = canonical_timestamp(NOW+timedelta(hours=7))
    elif claim == "neutral": target["neutral_site"] = True
    elif claim == "season": target["season"] = "E2024" if provider == "EuroLeague" else 20262027
    elif claim == "provider": target["source"] = "NHL" if provider != "NHL" else "ESPN"
    elif claim == "competition": target["league"] = "NHL" if provider != "NHL" else "NBA"
    else: target["sport"] = "ice_hockey" if provider != "NHL" else "basketball"
    current, _ = original(provider, target=target, history=history)
    path = tmp_path / "context.db"
    record(path, provider, body, target=True)
    result = api().resolve_team_sport_original(current, pool(path))
    assert result.event is None
    assert result.input_bindings[0]["match_state"] == "conflicting"
    assert result.receipt_binding["event_receipt"] is None
    assert any(reason.endswith("conflict") for reason in result.input_bindings[0]["reasons"])


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("side", ["home", "away"])
def test_unknown_team_does_not_hide_known_opponent_conflict(tmp_path, provider, side):
    _, target, history = source_inputs(provider)
    body = source_reply(provider, target, target=True)
    target.pop(side + "_team_id")
    other = "away" if side == "home" else "home"
    target[other + "_team_id"] = "Club33" if provider == "EuroLeague" else "33"
    current, _ = original(provider, target=target, history=history)
    path = tmp_path / "context.db"
    record(path, provider, body, target=True)
    value = api().resolve_team_sport_original(current, pool(path))
    assert value.event is None
    assert value.input_bindings[0]["match_state"] == "conflicting"
    assert "native-participants-conflict" in value.input_bindings[0]["reasons"]
    assert "native-participants-unavailable" in value.input_bindings[0]["reasons"]


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("field", ["neutral", "season", "rule"])
def test_missing_native_scope_is_explicit_not_inherited_from_original_defaults(tmp_path, provider, field):
    _, target, history = source_inputs(provider)
    body = source_reply(provider, target, target=True)
    game = native_game(provider, body)
    if field == "neutral": game.pop("isNeutralVenue" if provider == "EuroLeague" else "neutralSite")
    elif field == "season":
        if provider == "ESPN": body.pop("season")
        elif provider == "EuroLeague": game.pop("seasonCode")
        else: game.pop("season")
    # No owning status schema carries regulation/player-exposure rules, even
    # though the actual synthetic Original's raw input has a context_rules tag.
    current, prediction = original(provider, target=target, history=history)
    path = tmp_path / "context.db"
    record(path, provider, body, target=True)
    value = api().resolve_team_sport_original(current, pool(path))
    detail = value.input_bindings[0]
    assert detail["match_state"] == "matched"
    assert "native-rules-unavailable" in detail["reasons"]
    if field == "neutral": assert "native-neutral-unavailable" in detail["reasons"]
    if field == "season" and provider != "EuroLeague": assert "native-season-unavailable" in detail["reasons"]
    if provider == "EuroLeague" or provider == "NHL" and field == "season": assert value.event is None
    captured = build(current.sport, current, event=value.event, receipt_binding=value.receipt_binding)
    assert captured.original["outputs"]["p_home"].hex() == prediction.p_home.hex()
    assert captured.original["source_resolution"] == "unresolved"


@pytest.mark.parametrize("season,game_type,expected", [
    (20252026, 2, "nhl_reg60_regular_ot_so"), (20252026, 3, "nhl_reg60_playoff_ot"),
    (20252026, 1, None), (20262027, 2, None), (None, 2, None),
    (20252026, None, None), (20252026, True, None), (20252026, 2.0, None),
])
def test_hockey_routes_only_existing_actual_native_scope(tmp_path, season, game_type, expected):
    _, target, history = source_inputs("NHL")
    body = source_reply("NHL", target, target=True)
    game = native_game("NHL", body)
    game.update(season=season, gameType=game_type)
    target.update(season=season, game_type=game_type)
    current, prediction = original("NHL", target=target, history=history)
    path = tmp_path / "context.db"
    record(path, "NHL", body, target=True)
    result = api().resolve_team_sport_original(current, pool(path))
    assert (result.event["format"] if result.event else None) == expected
    if expected is None: assert "native-format-unreviewed" in result.input_bindings[0]["reasons"]
    assert result.input_bindings[0]["matching_receipt_refs"]  # retained partial evidence
    # Only routing is at issue. No missing prediction becomes a guessed 50%.
    if prediction.p_home is None: assert current.probability is None


@pytest.mark.parametrize("provider", PROVIDERS)
def test_binding_and_original_builder_do_not_turn_absent_model_into_a_prediction(tmp_path, provider):
    _, target, _ = source_inputs(provider)
    current, prediction = original(provider, history=[])
    assert prediction.p_home is None
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, target, target=True), target=True)
    value = api().resolve_team_sport_original(current, pool(path))
    captured = build(current.sport, current, event=value.event, receipt_binding=value.receipt_binding)
    assert captured.base is None
    assert captured.original["outputs"]["p_home"] is None


@pytest.mark.parametrize("provider", PROVIDERS)
def test_duplicate_receipts_and_request_paths_do_not_count_as_conflicting_events(tmp_path, provider):
    _, _, history = source_inputs(provider)
    current, _ = original(provider)
    path = tmp_path / "context.db"
    body = source_reply(provider, history[7])
    record(path, provider, body)
    record(path, provider, body, target=True)
    rows = pool(path)
    assert len(rows) == 2
    value = api().resolve_team_sport_original(current, rows)
    detail = value.input_bindings[8]
    assert detail["current_state"] == "available"
    assert detail["match_state"] == "matched"
    assert len(detail["matching_receipt_refs"]) == len(detail["lineage_refs"]) == 2
    repeated = api().resolve_team_sport_original(current, [*reversed(rows), *rows, rows[0]])
    assert asdict(repeated) == asdict(value)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_binding_is_detached_price_independent_and_no_io(tmp_path, monkeypatch, provider):
    import builtins
    import sqlite3
    import sports_prematch
    import requests
    _, target, _ = source_inputs(provider)
    current, _ = original(provider)
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, target, target=True), target=True)
    rows = pool(path)
    resolver = api().resolve_team_sport_original
    baseline = resolver(current, rows)
    changed = deepcopy(current.raw_event)
    changed.update(odds_home=999, odds_away=None, price_status="missing", bookmaker="changed", tab="Risk")
    priced = replace(current, raw_event=changed)
    def forbidden(*args, **kwargs): pytest.fail("pure binding invoked IO/model work")
    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(sqlite3, "connect", forbidden)
        guard.setattr(requests, "get", forbidden)
        for name in ("_fit", "_predict", "_normalise_history", "_identity", "predict_prematch"):
            guard.setattr(sports_prematch, name, forbidden)
        result = resolver(priced, rows)
    assert asdict(result) == asdict(baseline)
    before = canonical_bytes(asdict(result))
    rows[0]["payload"]["native"].clear()
    priced.raw_event["provider_event_id"] = "changed"
    assert canonical_bytes(asdict(result)) == before
    result.input_bindings[0]["reasons"].append("detached mutation")
    assert "detached mutation" not in baseline.input_bindings[0]["reasons"]


@pytest.mark.parametrize("mutation", ["digest", "content_digest", "extra", "effective_at", "source", "event_key", "published_at"])
def test_claimed_receipt_integrity_checked_before_unrelated_and_future_filtering(tmp_path, mutation):
    _, target, _ = source_inputs("NHL")
    current, _ = original("ESPN")
    path = tmp_path / "context.db"
    record(path, "NHL", source_reply("NHL", target, target=True), target=True, observed=NOW+timedelta(seconds=1))
    rows = deepcopy(pool(path))
    if mutation in ("digest", "content_digest"): rows[0][mutation] = "a" * 64
    elif mutation == "extra": rows[0]["verified"] = True
    elif mutation in ("effective_at", "published_at"): rows[0][mutation] = canonical_timestamp(NOW-timedelta(days=1))
    else: rows[0][mutation] += "-changed"
    with pytest.raises(ContextContractError):
        api().resolve_team_sport_original(current, rows)


@pytest.mark.parametrize("mutation", ["sport", "as_of", "naive", "history", "raw", "not-original"])
def test_malformed_original_interface_has_typed_failure(mutation):
    current, _ = original("ESPN")
    if mutation == "sport": current = replace(current, sport="cricket")
    elif mutation == "as_of": current = replace(current, as_of="2026-09-05T12:00:00Z")
    elif mutation == "naive": current = replace(current, as_of=NOW.replace(tzinfo=None))
    elif mutation == "history": current = replace(current, raw_history=list(current.raw_history))
    elif mutation == "raw": current = replace(current, raw_event=None)
    else: current = {"original": current}
    with pytest.raises(ContextContractError):
        api().resolve_team_sport_original(current, ())


@pytest.mark.parametrize("provider", ["ESPN", "NHL"])
def test_revision_binds_all_causal_current_receipts_without_rewriting_old_cutoff(tmp_path, provider):
    _, target, _ = source_inputs(provider)
    current, _ = original(provider)
    path = tmp_path / "context.db"
    body = source_reply(provider, target, target=True)
    record(path, provider, body, target=True, observed=NOW-timedelta(microseconds=1))
    earlier = api().resolve_team_sport_original(current, pool(path))
    record(path, provider, body, target=True, observed=NOW)
    rows = pool(path)
    after = api().resolve_team_sport_original(current, rows)
    assert after.event["schedule_revision"] != earlier.event["schedule_revision"]
    assert len(after.input_bindings[0]["matching_receipt_refs"]) == 2
    assert after.event["home_id"] == earlier.event["home_id"]
    old = replace(current, as_of=NOW-timedelta(microseconds=1))
    assert asdict(api().resolve_team_sport_original(old, rows)) == asdict(earlier)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_equivalent_utc_clocks_match_without_retiming_original_or_receipts(tmp_path, provider):
    _, target, history = source_inputs(provider)
    target["starts_at"] = (NOW+timedelta(hours=6)).astimezone(timezone(timedelta(hours=2))).isoformat()
    current, _ = original(provider, target=target, history=history)
    current = replace(current, as_of=NOW.astimezone(timezone(timedelta(hours=-4))))
    path = tmp_path / "context.db"
    source_target = deepcopy(target)
    source_target["starts_at"] = canonical_timestamp(NOW+timedelta(hours=6))
    record(path, provider, source_reply(provider, source_target, target=True), target=True, observed=NOW)
    rows = pool(path)
    value = api().resolve_team_sport_original(current, rows)
    assert value.input_bindings[0]["match_state"] == "matched"
    assert value.input_bindings[0]["current_received_at"] == canonical_timestamp(NOW)
    assert current.raw_event["starts_at"].endswith("+02:00")
    assert current.as_of.utcoffset() == timedelta(hours=-4)


@pytest.mark.parametrize("provider", ["ESPN", "NHL"])
@pytest.mark.parametrize("wrong", ["name", "wrong-id", "time-only"])
def test_same_names_scores_or_times_never_substitute_for_native_identity(tmp_path, provider, wrong):
    _, target, history = source_inputs(provider)
    body = source_reply(provider, target, target=True)
    if wrong == "name": target.pop("provider_event_id")
    elif wrong == "wrong-id": target["provider_event_id"] = "123456789"
    else:
        target["provider_event_id"] = "123456789"
        target.pop("home_team_id")
        target.pop("away_team_id")
    current, _ = original(provider, target=target, history=history)
    path = tmp_path / "context.db"
    record(path, provider, body, target=True)
    value = api().resolve_team_sport_original(current, pool(path))
    assert value.event is None and value.receipt_binding["event_receipt"] is None
    assert not value.input_bindings[0]["lineage_refs"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_closed_binding_shapes_carry_no_verified_or_coverage_flags(tmp_path, provider):
    _, target, history = source_inputs(provider)
    current, _ = original(provider)
    path = tmp_path / "context.db"
    record(path, provider, source_reply(provider, target, target=True), target=True)
    record(path, provider, source_reply(provider, history[7]))
    value = api().resolve_team_sport_original(current, pool(path))
    assert set(asdict(value)) == {"event", "receipt_binding", "input_bindings"}
    assert set(value.receipt_binding) == {"schema", "kind", "event_receipt", "history_receipts", "artifact_refs"}
    assert value.receipt_binding["schema"] == 1
    assert value.receipt_binding["kind"] == "team-sports-live-receipt-refs-v1"
    expected = {"input_index", "native_event_key", "match_state", "current_state", "current_received_at",
                "reasons", "matching_receipt_refs", "lineage_refs"}
    assert all(set(row) == expected for row in value.input_bindings)
    assert all(set(row) == {"input_index", "receipt"} for row in value.receipt_binding["history_receipts"])
    assert "native-rules-unavailable" in value.input_bindings[0]["reasons"]
