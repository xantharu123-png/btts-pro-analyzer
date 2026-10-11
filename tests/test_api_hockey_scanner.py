"""Offline API-Hockey native contracts. Swiss IDs below are synthetic fixtures,
not guessed account IDs. KHL game8279/league35 are the official docs example.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from api_budget import APIBudgetExceeded
from scanners.api_hockey import (
    APIHockeyScanner, CANDIDATES, LeagueCandidate, PROVIDER, SOURCE_CONTRACT,
    parse_completed_games, parse_upcoming_games, resolve_leagues, supported_competition,
)
from scanners.completed_history import CompletedHistoryStore

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
DAY = NOW.date()


def catalogue(*, identity=8001, name="National League", country="Switzerland", country_id=8000,
              season=2026, start="2026-08-01", end="2027-06-30"):
    return dict(id=identity, name=name, type="League", country=dict(id=country_id, name=country),
                seasons=[dict(season=season, current=True, start=start, end=end)])


def game(*, identity=80010, league=8001, name="National League", country="Switzerland",
         country_id=8000, season=2026, status="FT", start="2026-10-10T17:00:00+00:00"):
    return dict(id=identity, date=start, league=dict(id=league, name=name, type="League", season=season),
                country=dict(id=country_id, name=country),
                teams=dict(home=dict(id=801, name="Synthetic Home"), away=dict(id=802, name="Synthetic Away")),
                status=dict(short=status), scores=dict(home=1, away=3),
                periods=dict(first="0-2", second="0-1", third="1-0", overtime=None, penalties=None))


def scheduled(**kwargs):
    row = game(status="NS", **{"start": "2026-10-11T17:00:00+00:00", **kwargs})
    row["scores"] = dict(home=None, away=None)
    row["periods"] = dict.fromkeys(row["periods"])
    return row


def leagues():
    return resolve_leagues([catalogue()], on=DAY)


def final(row):
    return parse_completed_games([row], leagues(), observed_at=NOW)[0]


class Governor:
    def __init__(self, *, blocked=False):
        self.reservations, self.completions, self.blocked = [], [], blocked

    def reserve(self, **kwargs):
        self.reservations.append(kwargs)
        if self.blocked:
            raise APIBudgetExceeded("offline budget exhausted")
        return len(self.reservations)

    def complete(self, reservation, **kwargs):
        self.completions.append((reservation, kwargs))


class Transport:
    def __init__(self, *, catalog=None, games=None):
        self.catalog, self.games, self.calls = catalog or [catalogue()], games or [], []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        rows = self.catalog if url.endswith("/leagues") else self.games
        if isinstance(rows, Exception):
            raise rows
        return SimpleNamespace(status_code=200, headers={}, json=lambda: dict(errors=[], response=deepcopy(rows), paging=dict(total=1)))


def scanner(tmp_path, *, transport=None, governor=None, clock=None, **kwargs):
    current = clock or (lambda: NOW)
    store = CompletedHistoryStore(tmp_path / "history.db", clock=current)
    return APIHockeyScanner("offline-not-a-secret", governor=governor or Governor(),
                           history_store=store, get=transport or Transport(), clock=current, **kwargs)


def test_actual_catalogue_resolves_swiss_first_without_hardcoded_ids():
    rows = [catalogue(identity=912345), catalogue(identity=812345, name="Swiss League")]
    result = resolve_leagues(list(reversed(rows)), on=DAY)
    assert [(r.name, r.league_id, r.season) for r in result] == [("National League", 912345, 2026), ("Swiss League", 812345, 2026)]
    assert len(CANDIDATES) == 20
    assert CANDIDATES[0] == LeagueCandidate("National League", "Switzerland")
    assert supported_competition("National League")
    assert not supported_competition("national league")
    assert not supported_competition(" National League")
    assert not supported_competition("fictional league")


def test_documented_catalogue_schema_and_khl_completed_example():
    ohl = catalogue(identity=3, name="OHL", country="Canada", country_id=4, season=2019,
                    start="2019-08-29", end="2020-03-11")
    ohl["seasons"][0]["current"] = False
    assert resolve_leagues([ohl], on=date(2020, 2, 1), candidates=(LeagueCandidate("OHL", "Canada"),))[0].league_id == 3
    khl = catalogue(identity=35, name="KHL", country="Russia", country_id=21, season=2020,
                    start="2020-08-01", end="2021-06-30")
    row = game(identity=8279, league=35, name="KHL", country="Russia", country_id=21, season=2020,
               start="2020-10-02T09:00:00+00:00")
    row["teams"] = dict(home=dict(id=367, name="Amur Khabarovsk"), away=dict(id=382, name="SKA St. Petersburg"))
    result = parse_completed_games([row], resolve_leagues([khl], on=date(2020, 10, 2)), observed_at=NOW)[0]
    assert result["provider"] == "API-Hockey"
    assert (result["home_score_regulation"], result["away_score_regulation"]) == (1, 3)
    assert result["winner_side"] == "away"
    assert result["game_id"] == 8279 and result["league_id"] == 35
    assert "game_type" not in result


@pytest.mark.parametrize("field,bad", [("id", True), ("id", "8001"), ("id", 0), ("id", -1)])
def test_invalid_catalogue_native_id_rejected(field, bad):
    row = catalogue()
    row[field] = bad
    with pytest.raises(ValueError):
        resolve_leagues([row], on=DAY)


@pytest.mark.parametrize("field,bad", [("season", "2026"), ("season", True), ("current", 1),
                                      ("start", "2026-8-01"), ("end", "2026-01-01")])
def test_invalid_catalogue_native_season_rejected(field, bad):
    row = catalogue()
    row["seasons"][0][field] = bad
    with pytest.raises(ValueError):
        resolve_leagues([row], on=DAY)


def test_catalogue_does_not_invent_current_season_or_merge_names_countries():
    stale = catalogue(season=2025, start="2025-08-01", end="2026-06-30")
    assert resolve_leagues([stale, catalogue(country="France")], on=DAY) == ()
    cup = catalogue()
    cup["type"] = "Cup"
    assert resolve_leagues([cup], on=DAY) == ()
    with pytest.raises(ValueError, match="ID changed"):
        resolve_leagues([catalogue(), catalogue(identity=9001)], on=DAY)
    conflict = catalogue(name="Swiss League")
    with pytest.raises(ValueError, match="conflicting"):
        resolve_leagues([catalogue(), conflict], on=DAY)
    overlapping = catalogue()
    overlapping["seasons"].append(dict(season=2025, current=False, start="2025-11-01", end="2026-10-31"))
    with pytest.raises(ValueError, match="overlapping"):
        resolve_leagues([overlapping], on=DAY)


def test_upcoming_native_contract_real_clock_and_no_nhl_assumptions():
    row = parse_upcoming_games([scheduled()], leagues(), observed_at=NOW, start=DAY, end=DAY)[0]
    assert row["source_contract"] == SOURCE_CONTRACT
    assert (row["competition_id"], row["league_id"], row["season"]) == ("8001", 8001, 2026)
    assert (row["home_team_id"], row["away_team_id"]) == ("801", "802")
    assert row["source_observed_at"] == NOW.isoformat()
    assert row["neutral_site"] is None and row["phase"] is None
    assert "game_type" not in row and "home_score" not in row
    assert parse_upcoming_games([scheduled(start="2026-10-11T11:00:00+00:00")], leagues(), observed_at=NOW, start=DAY, end=DAY) == []
    assert parse_upcoming_games([scheduled(league=9999)], leagues(), observed_at=NOW, start=DAY, end=DAY) == []


@pytest.mark.parametrize("change", ["country", "league_name", "game_bool", "same_team", "naive_date", "outside_season", "missing_score", "period_score"])
def test_upcoming_malformed_identity_or_scores_fail_closed(change):
    row = scheduled()
    if change == "country": row["country"]["id"] = 9000
    if change == "league_name": row["league"]["name"] = "Swiss League"
    if change == "game_bool": row["id"] = True
    if change == "same_team": row["teams"]["away"]["id"] = row["teams"]["home"]["id"]
    if change == "naive_date": row["date"] = "2026-10-11T17:00:00"
    if change == "outside_season": row["date"] = "2027-07-01T17:00:00+00:00"
    if change == "missing_score": del row["scores"]["away"]
    if change == "period_score": row["periods"]["first"] = "0-0"
    with pytest.raises(ValueError):
        parse_upcoming_games([row], leagues(), observed_at=NOW, start=DAY, end=DAY)


def test_regulation_overtime_and_shootout_are_distinct_native_results():
    regulation = final(game())
    assert regulation["last_period_type"] == "REG"
    assert (regulation["regulation_home_score"], regulation["regulation_away_score"]) == (1, 3)
    row = game(status="AOT")
    row["periods"].update(first="1-0", second="0-1", third="0-0", overtime="0-1")
    row["scores"] = dict(home=1, away=2)
    overtime = final(row)
    assert (overtime["regulation_home_score"], overtime["regulation_away_score"]) == (1, 1)
    assert overtime["home_score_final"] == 1 and overtime["away_score_final"] == 2
    assert overtime["last_period_type"] == "OT" and overtime["winner_side"] == "away"
    row["status"]["short"] = "AP"
    row["periods"].update(overtime="0-0", penalties="1-3")
    shootout = final(row)
    assert shootout["regulation_periods"] == [[1, 0], [0, 1], [0, 0]]
    assert shootout["penalty_score"] == [1, 3]
    assert shootout["last_period_type"] == "SO" and shootout["winner_side"] == "away"
    # Native final winner, not a guessed NHL gameType or invented q=0.5.
    assert "game_type" not in shootout and "overtime_home_probability" not in shootout


@pytest.mark.parametrize("key,bad", [("first", None), ("second", "1:0"), ("third", [1, 0]),
                                   ("overtime", 0), ("penalties", False)])
def test_missing_or_malformed_period_never_substitutes_final_scores(key, bad):
    row = game()
    row["periods"][key] = bad
    with pytest.raises(ValueError): final(row)
    del row["periods"][key]
    with pytest.raises(ValueError): final(row)


@pytest.mark.parametrize("bad", [True, "1", 1.5, float("nan"), float("inf"), -1, None])
def test_final_scores_require_actual_nonnegative_native_integer(bad):
    row = game()
    row["scores"]["home"] = bad
    with pytest.raises(ValueError): final(row)


def test_terminal_phase_contradictions_and_duplicate_revisions_rejected():
    row = game()
    row["scores"]["home"] = 2
    with pytest.raises(ValueError): final(row)
    row = game(status="AOT")
    with pytest.raises(ValueError): final(row)
    row = game(status="AP")
    with pytest.raises(ValueError): final(row)
    assert len(parse_completed_games([game(), game()], leagues(), observed_at=NOW)) == 1
    altered = game()
    altered["teams"]["home"]["id"] += 10
    with pytest.raises(ValueError, match="conflicting"):
        parse_completed_games([game(), altered], leagues(), observed_at=NOW)
    with pytest.raises(ValueError, match="precedes"):
        parse_completed_games([game(start="2026-10-11T17:00:00+00:00")], leagues(), observed_at=NOW)


@pytest.mark.parametrize("status", ["AW", "POST", "CANC", "INTR", "ABD", "NS", "P1", "OT", "PT"])
def test_nonterminal_or_awarded_result_never_becomes_completed(status):
    assert parse_completed_games([game(status=status)], leagues(), observed_at=NOW) == []


def test_constructor_no_network_or_disk_and_default_nhl_not_duplicated(tmp_path):
    def forbidden(*args, **kwargs): raise AssertionError("unexpected I/O")
    adapter = APIHockeyScanner("", get=forbidden)
    assert adapter.history_store is None and adapter.governor is None
    assert not any(c.name == "NHL" for c in adapter.candidates)
    assert any(c.name == "NHL" for c in APIHockeyScanner("", include_nhl=True).candidates)
    with pytest.raises(ValueError, match="unavailable"): adapter._request("games", {})


def test_existing_governor_reserves_before_any_request_and_sanitizes_errors(tmp_path):
    transport, governor = Transport(games=[scheduled()]), Governor(blocked=True)
    adapter = scanner(tmp_path, transport=transport, governor=governor)
    assert adapter.get_upcoming_games(DAY, DAY) == []
    assert transport.calls == []
    assert governor.reservations[0]["provider"] == "api-sports-ice_hockey"
    assert adapter.errors == {"schedule": "APIBudgetExceeded"}


def test_shared_date_and_catalogue_cache_preserves_observation_and_uses_two_calls(tmp_path):
    clock = [NOW]
    transport = Transport(catalog=[catalogue(), catalogue(identity=8002, name="Swiss League")],
                          games=[scheduled(), scheduled(identity=80011, league=8002, name="Swiss League")])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    first = adapter.get_upcoming_games(DAY, DAY)
    assert len(first) == 2 and len(transport.calls) == 2
    assert transport.calls[1][1]["params"] == {"date": "2026-10-11", "timezone": "Europe/Zurich"}
    assert all(c[1]["allow_redirects"] is False and c[1]["timeout"] == 10 for c in transport.calls)
    clock[0] += timedelta(minutes=10)
    another = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    second = another.get_upcoming_games(DAY, DAY)
    assert second == first and len(transport.calls) == 2
    assert second[0]["source_observed_at"] == NOW.isoformat()
    clock[0] += timedelta(hours=5)
    assert another.get_upcoming_games(DAY, DAY) == []  # now kickoff, never resurrect cached pre-match


def test_completed_history_uses_one_season_batch_cache_and_real_asof(tmp_path):
    clock = [NOW]
    transport = Transport(games=[game()])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    start, end = DAY - timedelta(days=30), DAY
    result = adapter.get_completed_games(start, end, as_of=NOW - timedelta(seconds=1))
    assert result == []  # cold history is NOT backdated to past game time
    assert transport.calls[1][1]["params"] == {"league": 8001, "season": 2026}
    result = adapter.get_completed_games(start, end, as_of=NOW)
    assert len(result) == 1 and len(transport.calls) == 2
    assert result[0]["result_observed_at"] == NOW.isoformat()
    assert adapter.history_coverage["status"] == "complete"
    clock[0] += timedelta(minutes=1)
    another = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    assert another.get_completed_games(start, end)[0]["result_observed_at"] == NOW.isoformat()
    assert len(transport.calls) == 2
    with pytest.raises(ValueError):
        adapter.get_completed_games(start, end, as_of=clock[0] + timedelta(seconds=1))
    assert len(transport.calls) == 2


def test_cold_history_request_limit_is_reported_not_fake_twenty_leagues_ready(tmp_path):
    transport = Transport(catalog=[catalogue(), catalogue(identity=8002, name="Swiss League")], games=[])
    adapter = scanner(tmp_path, transport=transport, max_history_requests=1)
    assert adapter.get_completed_games(DAY - timedelta(days=30), DAY) == []
    assert len(transport.calls) == 2  # one catalogue + one season, not per-date per-league
    assert adapter.history_coverage["status"] == "partial"
    assert adapter.history_coverage["requests"] == 1
    assert not adapter.history_coverage["windows_complete"]


def test_native_withdrawal_retains_asof_old_result_but_not_current_result(tmp_path):
    clock = [NOW]
    transport = Transport(games=[game()])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    start = DAY - timedelta(days=30)
    assert len(adapter.get_completed_games(start, DAY)) == 1
    clock[0] += timedelta(days=1)
    transport.games = [game(status="POST")]
    assert adapter.get_completed_games(start, DAY) == []
    assert adapter.history_store.read((PROVIDER,), start, DAY, as_of=NOW)[0]["winner_side"] == "away"
    assert adapter.history_store.read((PROVIDER,), start, DAY) == []


def test_failed_new_native_periods_do_not_return_cached_old_outcome(tmp_path):
    clock = [NOW]
    transport = Transport(games=[game()])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    start = DAY - timedelta(days=30)
    assert len(adapter.get_completed_games(start, DAY)) == 1
    clock[0] += timedelta(days=1)
    invalid = game()
    invalid["periods"]["third"] = None
    transport.games = [invalid]
    assert adapter.get_completed_games(start, DAY) == []
    assert adapter.history_coverage["status"] == "partial"
    assert adapter.get_completed_games(start, DAY) == []  # failed receipt cooldown also blocked
    assert adapter.errors["history"] == "ValueError"
    assert adapter.history_store.read((PROVIDER,), start, DAY) == []
    assert len(adapter.history_store.read((PROVIDER,), start, DAY, as_of=NOW)) == 1


def test_fair_history_budget_eventually_serves_later_leagues(tmp_path):
    clock = [NOW]
    transport = Transport(catalog=[catalogue(), catalogue(identity=8002, name="Swiss League")], games=[])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0], max_history_requests=1)
    start = DAY - timedelta(days=30)
    adapter.get_completed_games(start, DAY)
    assert transport.calls[-1][1]["params"]["league"] == 8001
    clock[0] += timedelta(days=1)
    adapter.get_completed_games(start, DAY)
    assert transport.calls[-1][1]["params"]["league"] == 8002
    assert adapter.history_coverage["resolved_league_seasons"] == 2
    assert adapter.history_coverage["requests"] == 1


def test_opposite_native_terminal_revisions_withdraw_cached_outcome(tmp_path):
    clock = [NOW]
    transport = Transport(games=[game()])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    start = DAY - timedelta(days=30)
    assert len(adapter.get_completed_games(start, DAY)) == 1
    clock[0] += timedelta(days=1)
    opposite = game()
    opposite["scores"] = dict(home=3, away=1)
    opposite["periods"].update(first="2-0", second="1-0", third="0-1")
    transport.games = [game(), opposite]
    assert adapter.get_completed_games(start, DAY) == []
    assert adapter.history_store.read((PROVIDER,), start, DAY) == []
    assert len(adapter.history_store.read((PROVIDER,), start, DAY, as_of=NOW)) == 1


@pytest.mark.parametrize("field", ["participant", "status", "date"])
def test_new_malformed_bound_native_identity_never_resurrects_after_empty_success(tmp_path, field):
    clock = [NOW]
    transport = Transport(games=[game()])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    start = DAY - timedelta(days=30)
    assert len(adapter.get_completed_games(start, DAY)) == 1
    clock[0] += timedelta(days=1)
    malformed = game()
    if field == "participant": malformed["teams"]["away"]["id"] = True
    if field == "status": malformed["status"]["short"] = "unknown"
    if field == "date": malformed["date"] = "not a date"
    transport.games = [malformed]
    assert adapter.get_completed_games(start, DAY) == []
    assert adapter.history_store.read((PROVIDER,), start, DAY) == []
    assert len(adapter.history_store.read((PROVIDER,), start, DAY, as_of=NOW)) == 1
    clock[0] += timedelta(days=1)
    transport.games = []
    assert adapter.get_completed_games(start, DAY) == []
    assert adapter.history_coverage["status"] == "complete"


@pytest.mark.parametrize("field,value", [("id", True), ("id", "80010"), ("id", 99999),
                                        ("country_id", 9999), ("league_id", 9999),
                                        ("season", 2025), ("country_name", "France")])
def test_unknown_or_unbound_native_identity_cannot_withdraw_unrelated_result(tmp_path, field, value):
    clock = [NOW]
    transport = Transport(games=[game()])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    start = DAY - timedelta(days=30)
    assert len(adapter.get_completed_games(start, DAY)) == 1
    clock[0] += timedelta(days=1)
    malformed = game()
    malformed["teams"]["away"]["id"] = True
    if field == "id": malformed["id"] = value
    if field == "country_id": malformed["country"]["id"] = value
    if field == "country_name": malformed["country"]["name"] = value
    if field == "league_id": malformed["league"]["id"] = value
    if field == "season": malformed["league"]["season"] = value
    transport.games = [malformed]
    adapter.get_completed_games(start, DAY)
    assert len(adapter.history_store.read((PROVIDER,), start, DAY)) == 1


def test_cache_refresh_keeps_real_clock_and_result_correction_asof(tmp_path):
    clock = [NOW]
    transport = Transport(games=[game()])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    start = DAY - timedelta(days=30)
    first = adapter.get_completed_games(start, DAY)
    clock[0] += timedelta(days=1)
    corrected = game()
    corrected["scores"] = dict(home=3, away=1)
    corrected["periods"].update(first="2-0", second="1-0", third="0-1")
    transport.games = [corrected]
    current = adapter.get_completed_games(start, DAY)
    assert current[0]["winner_side"] == "home"
    assert current[0]["result_observed_at"] == clock[0].isoformat()
    assert adapter.history_store.read((PROVIDER,), start, DAY, as_of=NOW) == first


def test_native_page_paging_errors_cannot_accept_truncated_results(tmp_path):
    calls = []
    def truncated(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=200, headers={}, json=lambda: dict(errors=[], response=[catalogue()], paging=dict(total=2)))
    adapter = scanner(tmp_path, transport=truncated)
    assert adapter.get_upcoming_games(DAY, DAY) == []
    assert adapter.errors["schedule"] == "ValueError"
    assert len(calls) == 1


def test_successful_date_cache_is_small_and_bounded_not_a_growing_archive(tmp_path):
    from contextlib import closing
    clock = [NOW]
    transport = Transport(games=[])
    adapter = scanner(tmp_path, transport=transport, clock=lambda: clock[0])
    adapter.get_upcoming_games(DAY, DAY + timedelta(days=14))
    with closing(adapter.history_store._connect()) as connection:
        assert connection.execute("SELECT COUNT(*) FROM api_hockey_response_cache").fetchone()[0] <= 16
        assert connection.execute("SELECT SUM(LENGTH(payload)) FROM api_hockey_response_cache").fetchone()[0] < 20_000
    clock[0] += timedelta(days=2)
    adapter.get_upcoming_games(clock[0].date(), clock[0].date())
    with closing(adapter.history_store._connect()) as connection:
        assert connection.execute("SELECT COUNT(*) FROM api_hockey_response_cache").fetchone()[0] == 2


@pytest.mark.parametrize("start,end", [(DAY, DAY - timedelta(days=1)), (NOW, DAY), (DAY, DAY + timedelta(days=15))])
def test_schedule_invalid_window_before_any_io(tmp_path, start, end):
    transport = Transport()
    adapter = scanner(tmp_path, transport=transport)
    with pytest.raises(ValueError): adapter.get_upcoming_games(start, end)
    assert transport.calls == []
