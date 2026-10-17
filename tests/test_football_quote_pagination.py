"""Offline regression coverage for complete, bounded native football odds pages."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

import market_consensus as mc
from api_budget import APIBudgetExceeded, APIBudgetPriority
from quote_publication import publication_quote


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
START = "2030-01-01T16:00:00+00:00"


def candidate(key="TOTAL_RANGE_1_4"):
    return dict(candidate_id=f"42:{key}", fixture_id=42, market_key=key,
                source="football_challenge", sport="Fussball", scheduled_start=START,
                selection="Yes" if key == "BTTS_YES" else "1-4 Tore")


def entry(*, book=1, name=None, odd="1.25", market="range", updated=NOW,
          fixture=42, start=START):
    bet_id, bet_name, value = {
        "range": (186, "Total Goals Number By Ranges", "1-4"),
        "alias": (223, "Number of Goals In Match (Range)", "1-4"),
        "btts": (8, "Both Teams Score", "Yes"),
        "half": (186, "Total Goals Number By Ranges - First Half", "1-4"),
        "home": (40, "Home Team Exact Goals Number", "1-4"),
    }[market]
    return dict(fixture=dict(id=fixture, date=start), update=updated.isoformat(),
                bookmakers=[dict(id=book, name=name or f"Book {book}",
                    bets=[dict(id=bet_id, name=bet_name,
                               values=[dict(value=value, odd=odd)])])])


def page(number, total, *entries):
    return dict(get="odds", parameters=dict(fixture="42", page=str(number)),
                errors=[], results=len(entries), paging=dict(current=number, total=total),
                response=list(entries))


def serve(monkeypatch, responses):
    """Replace only the paid transport, keeping fetching and parsing real."""
    calls = []

    def get(url, **kwargs):
        assert url == "https://v3.football.api-sports.io/odds"
        assert kwargs["priority"] == APIBudgetPriority.RECOMMENDATION
        params = dict(kwargs["params"])
        calls.append(params)
        result = responses[params.get("page", 1)]
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: deepcopy(result))

    monkeypatch.setattr(mc, "api_football_get", get)
    return calls


def test_second_page_range_is_an_exact_native_offer_in_the_shared_market_pool(monkeypatch):
    ranged, btts = candidate(), candidate("BTTS_YES")
    calls = serve(monkeypatch, {1: page(1, 2, entry(market="btts")),
                               2: page(2, 2, entry(market="alias"))})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [ranged, btts], now=NOW,
                                                diagnostics=diagnostics)

    assert errors == []
    assert set(quotes) == {"42:TOTAL_RANGE_1_4", "42:BTTS_YES"}
    quote = quotes[ranged["candidate_id"]]
    assert quote.best_odds == 1.25
    assert quote.value_name == "1-4"
    assert quote.quoted_at == NOW.isoformat()
    assert quote.fetched_at == NOW.isoformat()
    assert mc.quote_matches_candidate(quote, ranged)
    assert publication_quote(quote, candidate=ranged, now=NOW) is not None
    assert diagnostics[ranged["candidate_id"]]["reason_code"] == "OBSERVED"
    assert calls == [{"fixture": 42}, {"fixture": 42, "page": 2}]


def test_pages_merge_before_stable_bookmaker_deduplication_newest_and_lower_tie(monkeypatch):
    older, newer = NOW - timedelta(minutes=5), NOW - timedelta(minutes=1)
    serve(monkeypatch, {
        1: page(1, 3, entry(book=7, odd="1.70", updated=older)),
        2: page(2, 3, entry(book=7, name="Renamed Book", odd="1.40", updated=newer),
                entry(book=8, odd="1.50")),
        3: page(3, 3, entry(book=7, name="Renamed Again", odd="1.30", updated=newer),
                entry(book=9, odd="1.60")),
    })

    quotes, errors = mc.fetch_football_consensus("offline", [candidate()], now=NOW)

    assert errors == []
    quote = quotes["42:TOTAL_RANGE_1_4"]
    assert quote.bookmaker_count == 3
    assert quote.lowest_odds == 1.30
    assert quote.consensus_odds == 1.50
    assert [(p.bookmaker_id, p.odds) for p in quote.points] == [
        ("api-football:7", 1.30), ("api-football:8", 1.50), ("api-football:9", 1.60)]


def test_later_native_offer_above_publication_floor_is_not_lost(monkeypatch):
    row = candidate()
    serve(monkeypatch, {1: page(1, 2, entry(odd="1.19")),
                        2: page(2, 2, entry(book=2, odd="1.25"))})

    quotes, _ = mc.fetch_football_consensus("offline", [row], now=NOW)

    assert not mc.quote_below_publication_floor(quotes[row["candidate_id"]], candidate=row, now=NOW)
    assert publication_quote(quotes[row["candidate_id"]], candidate=row, now=NOW) is not None


@pytest.mark.parametrize("failure,error_type", [
    (requests.Timeout("secret timeout"), "TIMEOUT"),
    (APIBudgetExceeded("secret quota"), "BUDGET_EXHAUSTED"),
    (ValueError("secret JSON"), "INVALID_RESPONSE"),
])
def test_failed_later_page_retains_real_quotes_but_never_asserts_absence(monkeypatch, failure, error_type):
    rows = [candidate(), candidate("BTTS_YES")]
    calls = serve(monkeypatch, {1: page(1, 2, entry(market="btts")), 2: failure})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", rows, now=NOW, diagnostics=diagnostics)

    assert set(quotes) == {"42:BTTS_YES"}
    missing = diagnostics["42:TOTAL_RANGE_1_4"]
    assert missing["reason_code"] == "REQUEST_FAILED"
    assert missing["error_type"] == error_type
    assert missing["pagination_complete"] is False
    assert missing["pagination_pages_received"] == 1
    assert missing["pagination_total_pages"] == 2
    assert diagnostics["42:BTTS_YES"]["reason_code"] == "OBSERVED"
    assert diagnostics["42:BTTS_YES"]["pagination_complete"] is False
    assert len(errors) == 1
    assert "secret" not in str(errors) + str(diagnostics)
    assert len(calls) == 2


def test_provider_error_on_later_page_does_not_discard_previous_page(monkeypatch):
    bad = page(2, 2)
    bad["errors"] = {"secret": "provider secret"}
    serve(monkeypatch, {1: page(1, 2, entry()), 2: bad})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                now=NOW, diagnostics=diagnostics)

    assert quotes["42:TOTAL_RANGE_1_4"].best_odds == 1.25
    assert diagnostics["42:BTTS_YES"]["reason_code"] == "REQUEST_FAILED"
    assert diagnostics["42:BTTS_YES"]["error_type"] == "PROVIDER_ERROR"
    assert diagnostics["42:BTTS_YES"]["pagination_complete"] is False
    assert len(errors) == 1
    assert "secret" not in str(errors) + str(diagnostics)


def test_provider_error_without_response_body_retains_its_actual_failure_class(monkeypatch):
    serve(monkeypatch, {1: {"errors": {"secret": "provider secret"}}})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate()], now=NOW,
                                                diagnostics=diagnostics)

    assert quotes == {}
    assert diagnostics["42:TOTAL_RANGE_1_4"]["error_type"] == "PROVIDER_ERROR"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["pagination_complete"] is False
    assert len(errors) == 1
    assert "secret" not in str(errors) + str(diagnostics)


@pytest.mark.parametrize("invalid", [None, "invalid"])
def test_invalid_response_entries_cannot_prove_fixture_absence(monkeypatch, invalid):
    serve(monkeypatch, {1: page(1, 1, invalid)})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate()], now=NOW,
                                                diagnostics=diagnostics)

    assert quotes == {}
    receipt = diagnostics["42:TOTAL_RANGE_1_4"]
    assert receipt["reason_code"] == "REQUEST_FAILED"
    assert receipt["error_type"] == "INVALID_RESPONSE"
    assert receipt["pagination_complete"] is False
    assert receipt["pagination_failure"] == "INVALID_RESPONSE"
    assert len(errors) == 1


def test_mixed_invalid_response_keeps_received_offer_without_claiming_other_absence(monkeypatch):
    serve(monkeypatch, {1: page(1, 1, entry(market="btts"), None)})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                now=NOW, diagnostics=diagnostics)

    assert set(quotes) == {"42:BTTS_YES"}
    assert diagnostics["42:BTTS_YES"]["reason_code"] == "OBSERVED"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["reason_code"] == "REQUEST_FAILED"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["error_type"] == "INVALID_RESPONSE"
    assert len(errors) == 1


def test_partial_failure_keeps_the_received_rejected_selection_provider_clock(monkeypatch):
    serve(monkeypatch, {1: page(1, 2, entry(odd="0")),
                        2: requests.Timeout("not a new provider observation")})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate()], now=NOW,
                                                diagnostics=diagnostics)

    assert quotes == {}
    receipt = diagnostics["42:TOTAL_RANGE_1_4"]
    assert receipt["reason_code"] == "REQUEST_FAILED"
    assert receipt["error_type"] == "TIMEOUT"
    assert receipt["provider_updated_at"] == NOW.isoformat()
    assert receipt["pagination_complete"] is False
    assert len(errors) == 1


def test_deadline_between_pages_defers_missing_targets_without_claiming_absence(monkeypatch):
    calls = serve(monkeypatch, {1: page(1, 2, entry(market="btts"))})
    clocks = iter((0.0, 2.0))
    monkeypatch.setattr(mc, "monotonic", lambda: next(clocks))
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                now=NOW, deadline=1.0, diagnostics=diagnostics)

    assert errors == []
    assert set(quotes) == {"42:BTTS_YES"}
    missing = diagnostics["42:TOTAL_RANGE_1_4"]
    assert missing["reason_code"] == "DEFERRED"
    assert missing["pagination_complete"] is False
    assert missing["pagination_failure"] == "DEADLINE"
    assert calls == [{"fixture": 42}]


@pytest.mark.parametrize("paging", [None, {}, {"current": True, "total": 1},
    {"current": 1, "total": "2"}, {"current": 2, "total": 2},
    {"current": 1, "total": 0}])
def test_malformed_first_page_metadata_is_bounded_and_cannot_prove_absence(monkeypatch, paging):
    data = page(1, 1, entry(market="btts"))
    if paging is None:
        data.pop("paging")
    else:
        data["paging"] = paging
    calls = serve(monkeypatch, {1: data})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                now=NOW, diagnostics=diagnostics)

    assert set(quotes) == {"42:BTTS_YES"}
    missing = diagnostics["42:TOTAL_RANGE_1_4"]
    assert missing["reason_code"] == "REQUEST_FAILED"
    assert missing["error_type"] == "INCOMPLETE_PAGINATION"
    assert missing["pagination_complete"] is False
    assert len(errors) == 1
    assert calls == [{"fixture": 42}]


@pytest.mark.parametrize("second_paging", [None, {"current": 1, "total": 2},
                                           {"current": 2, "total": 3}])
def test_missing_repeated_or_changed_later_page_metadata_stops_without_false_absence(monkeypatch, second_paging):
    second = page(2, 2, entry(market="btts", book=2))
    if second_paging is None:
        second.pop("paging")
    else:
        second["paging"] = second_paging
    calls = serve(monkeypatch, {1: page(1, 2, entry(market="btts")), 2: second})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                now=NOW, diagnostics=diagnostics)

    assert "42:BTTS_YES" in quotes
    assert diagnostics["42:TOTAL_RANGE_1_4"]["reason_code"] == "REQUEST_FAILED"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["pagination_complete"] is False
    assert len(errors) == 1
    assert len(calls) == 2


def test_excessive_total_has_a_finite_request_cap_and_no_definitive_absence(monkeypatch):
    calls = []

    def get(_url, **kwargs):
        number = kwargs["params"].get("page", 1)
        calls.append(number)
        assert len(calls) <= 20, "untrusted paging must not exhaust the daily quota"
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: page(number, 10**9,
            entry(market="btts", book=number)))

    monkeypatch.setattr(mc, "api_football_get", get)
    diagnostics = {}

    _, errors = mc.fetch_football_consensus("offline", [candidate()], now=NOW, diagnostics=diagnostics)

    assert 1 <= len(calls) <= 20
    assert diagnostics["42:TOTAL_RANGE_1_4"]["reason_code"] == "REQUEST_FAILED"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["pagination_failure"] == "PAGE_LIMIT"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["pagination_complete"] is False
    assert len(errors) == 1


def test_repeated_response_body_is_incomplete_even_when_page_counter_advances(monkeypatch):
    repeated = entry(market="btts")
    calls = serve(monkeypatch, {1: page(1, 2, repeated), 2: page(2, 2, repeated)})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                now=NOW, diagnostics=diagnostics)

    assert quotes["42:BTTS_YES"].bookmaker_count == 1
    assert diagnostics["42:TOTAL_RANGE_1_4"]["reason_code"] == "REQUEST_FAILED"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["pagination_failure"] == "REPEATED_PAGE"
    assert len(errors) == 1
    assert len(calls) == 2


def test_complete_pages_preserve_exact_fixture_period_team_and_start_boundaries(monkeypatch):
    calls = serve(monkeypatch, {1: page(1, 2, entry(market="btts")),
        2: page(2, 2, entry(fixture=43), entry(market="half"), entry(market="home"))})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate()], now=NOW, diagnostics=diagnostics)

    assert quotes == {}
    assert errors == []
    assert diagnostics["42:TOTAL_RANGE_1_4"]["reason_code"] == "MARKET_ABSENT"
    assert len(calls) == 2


def test_later_conflicting_fixture_start_cannot_bind_the_merged_range(monkeypatch):
    serve(monkeypatch, {1: page(1, 2, entry(market="btts")),
                        2: page(2, 2, entry(start="2030-01-01T18:00:00+00:00"))})

    quotes, _ = mc.fetch_football_consensus("offline", [candidate()], now=NOW)

    assert not mc.quote_matches_candidate(quotes["42:TOTAL_RANGE_1_4"], candidate())


def test_merged_retrieval_clock_uses_completion_not_batch_start(monkeypatch):
    later = NOW + timedelta(minutes=2)
    clocks = iter((NOW, NOW, later))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(clocks)

    monkeypatch.setattr(mc, "datetime", Clock)
    serve(monkeypatch, {1: page(1, 2, entry(market="btts")),
                        2: page(2, 2, entry(updated=later))})

    quotes, errors = mc.fetch_football_consensus("offline", [candidate()])

    assert errors == []
    quote = quotes["42:TOTAL_RANGE_1_4"]
    assert quote.quoted_at == later.isoformat()
    assert quote.fetched_at == later.isoformat()


def receipt_clocks(monkeypatch, *values):
    clocks = iter(values)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(clocks)

    monkeypatch.setattr(mc, "datetime", Clock)


def test_slow_later_page_cannot_validate_a_previously_future_dated_offer(monkeypatch):
    future, later = NOW + timedelta(minutes=2), NOW + timedelta(minutes=3)
    receipt_clocks(monkeypatch, NOW, NOW, later)
    serve(monkeypatch, {1: page(1, 2, entry(updated=future)),
                        2: page(2, 2, entry(market="btts", updated=later))})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                diagnostics=diagnostics)

    assert errors == []
    assert set(quotes) == {"42:BTTS_YES"}
    rejected = diagnostics["42:TOTAL_RANGE_1_4"]
    assert rejected["reason_code"] == "BAD_CLOCK"
    assert rejected["provider_updated_at"] == future.isoformat()
    assert rejected["fetched_at"] == NOW.isoformat()


def test_unrelated_later_page_does_not_renew_an_earlier_quote_receipt(monkeypatch):
    later = NOW + timedelta(minutes=2)
    receipt_clocks(monkeypatch, NOW, NOW, later)
    serve(monkeypatch, {1: page(1, 2, entry()),
                        2: page(2, 2, entry(market="btts", updated=later))})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                diagnostics=diagnostics)

    assert errors == []
    assert quotes["42:TOTAL_RANGE_1_4"].fetched_at == NOW.isoformat()
    assert quotes["42:BTTS_YES"].fetched_at == later.isoformat()
    assert diagnostics["42:TOTAL_RANGE_1_4"]["fetched_at"] == NOW.isoformat()
    assert diagnostics["42:BTTS_YES"]["fetched_at"] == later.isoformat()


@pytest.mark.parametrize("later_odd,later_update,want_odd,want_receipt", [
    ("1.70", NOW - timedelta(minutes=1), 1.25, NOW),
    ("1.70", NOW, 1.25, NOW),
    ("1.20", NOW, 1.20, NOW + timedelta(minutes=2)),
    ("1.30", NOW + timedelta(minutes=1), 1.30, NOW + timedelta(minutes=2)),
])
def test_deduplicated_quote_receipt_belongs_to_the_chosen_offer(
        monkeypatch, later_odd, later_update, want_odd, want_receipt):
    second, third = NOW + timedelta(minutes=2), NOW + timedelta(minutes=4)
    receipt_clocks(monkeypatch, NOW, NOW, second, third)
    serve(monkeypatch, {1: page(1, 3, entry(book=7)),
                        2: page(2, 3, entry(book=7, odd=later_odd, updated=later_update)),
                        3: page(3, 3, entry(market="btts", updated=third))})

    quotes, errors = mc.fetch_football_consensus("offline", [candidate()])

    assert errors == []
    quote = quotes["42:TOTAL_RANGE_1_4"]
    assert quote.bookmaker_count == 1
    assert quote.best_odds == want_odd
    assert quote.fetched_at == want_receipt.isoformat()


@pytest.mark.parametrize("broken_field", ["fixture", "fixture_id", "bookmakers", "book",
                                         "bets", "bet", "values", "value"])
def test_malformed_nested_page_shape_cannot_prove_a_missing_market(monkeypatch, broken_field):
    broken = entry(market="btts")
    if broken_field == "fixture":
        broken.pop("fixture")
    elif broken_field == "fixture_id":
        broken["fixture"]["id"] = True
    elif broken_field == "bookmakers":
        broken["bookmakers"] = None
    elif broken_field == "book":
        broken["bookmakers"] = [None]
    elif broken_field == "bets":
        broken["bookmakers"][0]["bets"] = None
    elif broken_field == "bet":
        broken["bookmakers"][0]["bets"] = [None]
    elif broken_field == "values":
        broken["bookmakers"][0]["bets"][0]["values"] = None
    else:
        broken["bookmakers"][0]["bets"][0]["values"] = [None]
    serve(monkeypatch, {1: page(1, 1, broken)})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate()], now=NOW,
                                                diagnostics=diagnostics)

    assert quotes == {}
    assert diagnostics["42:TOTAL_RANGE_1_4"]["reason_code"] == "REQUEST_FAILED"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["error_type"] == "INVALID_RESPONSE"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["pagination_complete"] is False
    assert len(errors) == 1


def test_mixed_valid_and_broken_nested_books_keep_the_actual_received_offer(monkeypatch):
    mixed = entry(market="btts")
    mixed["bookmakers"].append(dict(id=2, name="Broken", bets=None))
    serve(monkeypatch, {1: page(1, 1, mixed)})
    diagnostics = {}

    quotes, errors = mc.fetch_football_consensus("offline", [candidate(), candidate("BTTS_YES")],
                                                now=NOW, diagnostics=diagnostics)

    assert quotes["42:BTTS_YES"].best_odds == 1.25
    assert diagnostics["42:BTTS_YES"]["reason_code"] == "OBSERVED"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["reason_code"] == "REQUEST_FAILED"
    assert diagnostics["42:TOTAL_RANGE_1_4"]["pagination_complete"] is False
    assert len(errors) == 1
