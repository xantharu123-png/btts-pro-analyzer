from dataclasses import replace
from datetime import datetime, timedelta, timezone

import market_consensus
from market_consensus import (
    MIN_REFERENCE_BOOKMAKERS,
    MarketConsensus,
    ODDS_API_REFERENCE_SOURCE,
    REFERENCE_SOURCE,
    exact_market_target,
    parse_h2h_event_consensus,
    parse_fixture_consensus,
    quote_matches_candidate,
    reference_price_status,
)


UTC = timezone.utc


def _candidate(market_key: str = "BTTS_YES") -> dict:
    return {
        "candidate_id": f"1493030:{market_key}",
        "fixture_id": 1493030,
        "market_key": market_key,
    }


def _payload(now: datetime, *, values=None) -> dict:
    values = values or {
        "Bet365": "1.88",
        "Pinnacle": "1.91",
        "Unibet": "1.86",
        "Betano": "1.84",
    }
    return {
        "errors": [],
        "response": [
            {
                "fixture": {"id": 1493030},
                "update": now.isoformat(),
                "bookmakers": [
                    {
                        "name": bookmaker,
                        "bets": [
                            {
                                "name": "Both Teams Score",
                                "values": [
                                    {"value": "Yes", "odd": odds},
                                    {"value": "No", "odd": "1.90"},
                                ],
                            }
                        ],
                    }
                    for bookmaker, odds in values.items()
                ],
            }
        ],
    }


def test_exact_market_mapping_covers_direct_lines_but_not_synthetic_ranges():
    assert exact_market_target("RESULT_HOME") == ("Match Winner", "Home")
    assert exact_market_target("TOTAL_OVER_2_5") == (
        "Goals Over/Under",
        "Over 2.5",
    )
    assert exact_market_target("HOME_CORNERS_UNDER_4_5") == (
        "Home Corners Over/Under",
        "Under 4.5",
    )
    assert exact_market_target("AWAY_YELLOW_OVER_1_5") == (
        "Away Team Yellow Cards",
        "Over 1.5",
    )
    assert exact_market_target("HOME_RANGE_1_3") is None
    assert exact_market_target("RESULT_TOTAL_1X_UNDER_3_5") is None
    assert exact_market_target("MIXED_BTTS_OR_OVER_2_5") is None


def test_consensus_uses_lower_quartile_not_best_quote():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    quotes = parse_fixture_consensus(
        _payload(now),
        [_candidate()],
        fetched_at=now,
    )

    quote = quotes[_candidate()["candidate_id"]]
    assert quote.bookmaker_count == 4
    assert quote.lowest_odds == 1.84
    assert quote.conservative_odds == 1.855
    assert quote.consensus_odds == 1.87
    assert quote.best_odds == 1.91
    assert MarketConsensus.from_dict(quote.to_dict()) == quote


def test_consensus_deduplicates_bookmaker_casing_conservatively():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    quote = parse_fixture_consensus(
        _payload(
            now,
            values={
                "Bet365": "1.92",
                " bet365 ": "1.84",
                "Pinnacle": "1.91",
                "Unibet": "1.86",
            },
        ),
        [_candidate()],
        fetched_at=now,
    )[_candidate()["candidate_id"]]

    assert quote.bookmaker_count == 3
    assert len({point.bookmaker.casefold() for point in quote.points}) == 3
    bet365 = next(
        point for point in quote.points if point.bookmaker.casefold() == "bet365"
    )
    assert bet365.odds == 1.84
    assert MarketConsensus.from_dict(quote.to_dict()) == quote


def test_price_status_requires_fresh_multi_book_consensus_and_minimum_buffer():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    quote = next(
        iter(
            parse_fixture_consensus(
                _payload(now),
                [_candidate()],
                fetched_at=now,
            ).values()
        )
    )

    assert reference_price_status(quote, 1.85, now=now).code == "PLAYABLE"
    assert reference_price_status(quote, 1.87, now=now).code == "BORDERLINE"
    assert reference_price_status(quote, 1.95, now=now).code == "TOO_LOW"
    assert reference_price_status(
        quote,
        1.85,
        now=now + timedelta(hours=2),
    ).code == "STALE"

    source_old_but_recently_fetched = next(
        iter(
            parse_fixture_consensus(
                _payload(now - timedelta(hours=10)),
                [_candidate()],
                fetched_at=now,
            ).values()
        )
    )
    assert reference_price_status(
        source_old_but_recently_fetched,
        1.85,
        now=now,
    ).code == "PLAYABLE"

    source_too_old = parse_fixture_consensus(
        _payload(now - timedelta(hours=25)),
        [_candidate()],
        fetched_at=now,
    )
    assert source_too_old == {}

    thin_payload = _payload(
        now,
        values={f"Book {index}": "1.90" for index in range(MIN_REFERENCE_BOOKMAKERS - 1)},
    )
    thin = next(
        iter(
            parse_fixture_consensus(
                thin_payload,
                [_candidate()],
                fetched_at=now,
            ).values()
        )
    )
    assert reference_price_status(thin, 1.80, now=now).code == "THIN"


def test_price_status_never_publishes_an_extreme_short_price() -> None:
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    short = next(
        iter(
            parse_fixture_consensus(
                _payload(
                    now,
                    values={
                        "Book A": "1.05",
                        "Book B": "1.06",
                        "Book C": "1.07",
                        "Book D": "1.08",
                    },
                ),
                [_candidate()],
                fetched_at=now,
            ).values()
        )
    )

    assert reference_price_status(short, 1.05, now=now).code == "TOO_LOW"


def test_parser_rejects_wrong_fixture_and_provider_errors():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    wrong = _candidate()
    wrong["fixture_id"] = 99
    assert parse_fixture_consensus(_payload(now), [wrong], fetched_at=now) == {}
    assert parse_fixture_consensus(
        {"errors": {"plan": "blocked"}, "response": []},
        [_candidate()],
        fetched_at=now,
    ) == {}


def test_parser_never_mixes_prices_between_fixtures():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    first = _payload(now)["response"][0]
    second = {
        **first,
        "fixture": {"id": 1493031},
        "bookmakers": [
            {
                **bookmaker,
                "bets": [
                    {
                        "name": "Both Teams Score",
                        "values": [{"value": "Yes", "odd": "3.00"}],
                    }
                ],
            }
            for bookmaker in first["bookmakers"]
        ],
    }
    other_candidate = {
        "candidate_id": "1493031:BTTS_YES",
        "fixture_id": 1493031,
        "market_key": "BTTS_YES",
    }

    quotes = parse_fixture_consensus(
        {"errors": [], "response": [first, second]},
        [_candidate(), other_candidate],
        fetched_at=now,
    )

    assert quotes[_candidate()["candidate_id"]].best_odds == 1.91
    assert quotes[other_candidate["candidate_id"]].lowest_odds == 3.0


def test_quote_identity_binds_market_fixture_and_provider_source():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    candidate = _candidate()
    quote = parse_fixture_consensus(
        _payload(now),
        [candidate],
        fetched_at=now,
    )[candidate["candidate_id"]]

    assert quote_matches_candidate(quote, candidate) is True
    assert quote_matches_candidate(
        replace(quote, market_key="BTTS_NO"),
        candidate,
    ) is False
    assert quote_matches_candidate(
        replace(quote, value_name="No"),
        candidate,
    ) is False
    assert quote_matches_candidate(
        replace(quote, fixture_id=1493031),
        candidate,
    ) is False
    assert quote_matches_candidate(
        replace(
            quote,
            source=ODDS_API_REFERENCE_SOURCE,
            provider_event_id="provider-event-wrong-source",
        ),
        candidate,
    ) is False

    tennis_candidate = {
        "candidate_id": "tennis-1-A",
        "market_key": "H2H",
        "sport": "Tennis",
        "source": "tennis_shadow",
        "competitor_a": "Anna Lena",
        "competitor_b": "Bea",
        "selected_competitor": "Anna Lena",
    }
    tennis_quote = replace(
        quote,
        fixture_id=None,
        candidate_id=tennis_candidate["candidate_id"],
        market_key="H2H",
        value_name="Anna-Lena",
        source=ODDS_API_REFERENCE_SOURCE,
        provider_event_id="provider-event-1",
    )
    assert quote_matches_candidate(tennis_quote, tennis_candidate) is True
    assert quote_matches_candidate(
        replace(tennis_quote, source=REFERENCE_SOURCE),
        tennis_candidate,
    ) is False
    assert quote_matches_candidate(
        replace(tennis_quote, provider_event_id=None),
        tennis_candidate,
    ) is False
    assert quote_matches_candidate(
        replace(tennis_quote, value_name="Bea"),
        tennis_candidate,
    ) is False


def test_tennis_identity_punctuation_is_a_word_separator():
    assert market_consensus._identity_name("Winston-Salem") == (
        market_consensus._identity_name("Winston Salem")
    )
    assert market_consensus._identity_name("Anna-Lena") == (
        market_consensus._identity_name("Anna Lena")
    )


def test_football_consensus_excludes_individually_stale_bookmaker_points():
    now = datetime(2030, 1, 3, 10, 0, tzinfo=UTC)
    entries = [
        _payload(now, values={"Fresh Book": "1.90"})["response"][0],
        _payload(
            now - timedelta(days=2),
            values={"Stale Book 1": "2.00"},
        )["response"][0],
        _payload(
            now - timedelta(days=3),
            values={"Stale Book 2": "2.10"},
        )["response"][0],
    ]

    quote = parse_fixture_consensus(
        {"errors": [], "response": entries},
        [_candidate()],
        fetched_at=now,
    )[_candidate()["candidate_id"]]

    assert quote.bookmaker_count == 1
    assert [point.bookmaker for point in quote.points] == ["Fresh Book"]
    assert reference_price_status(quote, 1.80, now=now).code == "THIN"


def test_tennis_consensus_excludes_individually_stale_bookmaker_points():
    now = datetime(2030, 1, 3, 10, 0, tzinfo=UTC)
    candidate = {
        "candidate_id": "tennis-1-A",
        "market_key": "H2H",
        "sport": "Tennis",
        "competitor_a": "Anna Lena",
        "competitor_b": "Bea",
        "selected_competitor": "Anna Lena",
        "scheduled_start": "2030-01-03T16:00:00+00:00",
    }
    updates = (now, now - timedelta(days=2), now - timedelta(days=3))
    payload = {
        "id": "provider-event-1",
        "home_team": "Bea",
        "away_team": "Anna-Lena",
        "commence_time": "2030-01-03T16:00:00Z",
        "bookmakers": [
            {
                "key": f"book-{index}",
                "title": f"Book {index}",
                "last_update": updated.isoformat(),
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Anna-Lena", "price": 1.90 + index / 10},
                            {"name": "Bea", "price": 1.80},
                        ],
                    }
                ],
            }
            for index, updated in enumerate(updates)
        ],
    }

    quote = parse_h2h_event_consensus(
        payload,
        [candidate],
        fetched_at=now,
    )[candidate["candidate_id"]]

    assert quote.bookmaker_count == 1
    assert [point.bookmaker for point in quote.points] == ["Book 0"]
    assert reference_price_status(quote, 1.80, now=now).code == "THIN"
