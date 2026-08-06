from datetime import datetime, timedelta, timezone

from market_consensus import (
    MIN_REFERENCE_BOOKMAKERS,
    MarketConsensus,
    exact_market_target,
    parse_fixture_consensus,
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

    source_too_old = next(
        iter(
            parse_fixture_consensus(
                _payload(now - timedelta(hours=25)),
                [_candidate()],
                fetched_at=now,
            ).values()
        )
    )
    assert reference_price_status(source_too_old, 1.85, now=now).code == "STALE"

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
