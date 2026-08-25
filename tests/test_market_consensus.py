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
    wettfinder_consensus,
    wettfinder_reference_price_status,
)


UTC = timezone.utc


def _candidate(market_key: str = "BTTS_YES") -> dict:
    return {
        "candidate_id": f"1493030:{market_key}",
        "fixture_id": 1493030,
        "market_key": market_key,
        "sport": "Fussball",
        "source": "football_challenge",
        "scheduled_start": "2030-01-01T16:00:00+00:00",
        "selection": "Ja" if market_key == "BTTS_YES" else "Nein",
    }


def _payload(
    now: datetime,
    *,
    values=None,
    provider_ids: bool = False,
) -> dict:
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
                "fixture": {
                    "id": 1493030,
                    "date": "2030-01-01T16:00:00+00:00",
                },
                "update": now.isoformat(),
                "bookmakers": [
                    {
                        **({"id": index} if provider_ids else {}),
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
                    for index, (bookmaker, odds) in enumerate(
                        values.items(),
                        start=1,
                    )
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
    assert quote.executable_point is not None
    assert quote.executable_point.bookmaker == "Unibet"
    assert quote.executable_point.odds == 1.86
    assert quote.to_dict()["executable_quote"]["odds"] == 1.86
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


def test_consensus_deduplicates_stable_bookmaker_id_and_keeps_newest_offer():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    old = _payload(now - timedelta(minutes=10))["response"][0]
    old["bookmakers"] = [
        {
            "id": 7,
            "name": "Old Brand",
            "bets": [{
                "name": "Both Teams Score",
                "values": [{"value": "Yes", "odd": "2.50"}],
            }],
        }
    ]
    fresh = _payload(now)["response"][0]
    fresh["bookmakers"] = [
        {
            "id": 7,
            "name": "Renamed Brand",
            "bets": [{
                "name": "Both Teams Score",
                "values": [{"value": "Yes", "odd": "1.80"}],
            }],
        },
        {
            "id": 8,
            "name": "Book B",
            "bets": [{
                "name": "Both Teams Score",
                "values": [{"value": "Yes", "odd": "1.90"}],
            }],
        },
        {
            "id": 9,
            "name": "Book C",
            "bets": [{
                "name": "Both Teams Score",
                "values": [{"value": "Yes", "odd": "2.00"}],
            }],
        },
    ]

    quote = parse_fixture_consensus(
        {"errors": [], "response": [old, fresh]},
        [_candidate()],
        fetched_at=now,
    )[_candidate()["candidate_id"]]

    assert quote.bookmaker_count == 3
    renamed = next(
        point for point in quote.points if point.bookmaker_id == "api-football:7"
    )
    assert renamed.bookmaker == "Renamed Brand"
    assert renamed.odds == 1.80
    assert renamed.observed_at == now.isoformat()


def test_legacy_points_load_but_new_payload_persists_concrete_execution_offer():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    quote = parse_fixture_consensus(
        _payload(now),
        [_candidate()],
        fetched_at=now,
    )[_candidate()["candidate_id"]]
    legacy = quote.to_dict()
    legacy.pop("executable_quote")
    for point in legacy["points"]:
        point.pop("bookmaker_id")
        point.pop("observed_at")

    loaded = MarketConsensus.from_dict(legacy)

    assert loaded is not None
    # Legacy aggregate clocks remain readable, but cannot prove that every
    # contributing offer was current and are therefore not actionable.
    assert not loaded.is_fresh(now)
    assert loaded.executable_point is not None
    assert loaded.executable_point.odds == 1.86
    persisted = loaded.to_dict()["executable_quote"]
    assert persisted["bookmaker"] == "Unibet"
    assert persisted["odds"] == 1.86


def test_serialized_execution_offer_cannot_be_replaced_by_synthetic_q25():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    quote = parse_fixture_consensus(
        _payload(now),
        [_candidate()],
        fetched_at=now,
    )[_candidate()["candidate_id"]]
    tampered = quote.to_dict()
    tampered["executable_quote"]["odds"] = quote.conservative_odds

    assert MarketConsensus.from_dict(tampered) is None


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

    playable = reference_price_status(quote, 1.85, now=now)
    assert playable.code == "PLAYABLE"
    # Q25 is only the conservative gate. Ticket math receives the closest
    # actually observed bookmaker offer at/above that gate.
    assert playable.usable_odds == 1.86
    assert playable.usable_odds != quote.conservative_odds
    assert playable.bookmaker == "Unibet"
    assert playable.observed_at == now.isoformat()
    assert reference_price_status(quote, 1.87, now=now).code == "BORDERLINE"
    assert reference_price_status(quote, 1.95, now=now).code == "TOO_LOW"
    assert reference_price_status(
        quote,
        1.85,
        now=now + timedelta(hours=2),
    ).code == "STALE"

    source_recently_fetched_but_oldest_point_near_boundary = next(
        iter(
            parse_fixture_consensus(
                _payload(now - timedelta(minutes=40)),
                [_candidate()],
                fetched_at=now,
            ).values()
        )
    )
    assert reference_price_status(
        source_recently_fetched_but_oldest_point_near_boundary,
        1.85,
        now=now,
    ).code == "PLAYABLE"
    assert reference_price_status(
        source_recently_fetched_but_oldest_point_near_boundary,
        1.85,
        now=now + timedelta(minutes=6),
    ).code == "STALE"

    normal_stale = next(
        iter(
            parse_fixture_consensus(
                _payload(now - timedelta(minutes=40), provider_ids=True),
                [_candidate()],
                fetched_at=now,
            ).values()
        )
    )
    assert reference_price_status(normal_stale, 1.85, now=now).code == "PLAYABLE"
    assert wettfinder_reference_price_status(
        normal_stale,
        1.85,
        candidate=_candidate(),
        now=now + timedelta(minutes=6),
    ).code == "STALE"

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


def test_normal_wettfinder_requires_provider_execution_proof_and_exact_binding():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    candidate = _candidate()
    quote = parse_fixture_consensus(
        _payload(now, provider_ids=True),
        [candidate],
        fetched_at=now,
    )[candidate["candidate_id"]]

    playable = wettfinder_reference_price_status(
        quote,
        1.85,
        candidate=candidate,
        now=now,
    )
    assert playable.code == "PLAYABLE"
    assert playable.usable_odds == 1.86
    assert playable.bookmaker == "Unibet"
    assert playable.bookmaker_id == "api-football:3"
    assert playable.observed_at == now.isoformat()
    assert wettfinder_reference_price_status(
        quote,
        1.85,
        candidate={**candidate, "selection": "Nein"},
        now=now,
    ).code == "UNAVAILABLE"
    assert wettfinder_reference_price_status(
        quote,
        1.85,
        candidate={**candidate, "selection": None},
        now=now,
    ).code == "UNAVAILABLE"


def test_normal_wettfinder_keeps_legacy_quote_readable_but_not_actionable():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    candidate = _candidate()
    modern = parse_fixture_consensus(
        _payload(now, provider_ids=True),
        [candidate],
        fetched_at=now,
    )[candidate["candidate_id"]]
    legacy_payload = modern.to_dict()
    legacy_payload.pop("executable_quote")
    for point in legacy_payload["points"]:
        point.pop("bookmaker_id")
        point.pop("observed_at")
    legacy = MarketConsensus.from_dict(legacy_payload)

    assert legacy is not None
    assert reference_price_status(legacy, 1.85, now=now).code == "STALE"
    assert wettfinder_reference_price_status(
        legacy,
        1.85,
        candidate=candidate,
        now=now,
    ).code == "UNAVAILABLE"
    assert wettfinder_reference_price_status(
        replace(modern, scheduled_start=None),
        1.85,
        candidate=candidate,
        now=now,
    ).code == "UNAVAILABLE"


def test_normal_wettfinder_rejects_name_only_bookmaker_consensus():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    candidate = _candidate()
    name_only = parse_fixture_consensus(
        _payload(now),
        [candidate],
        fetched_at=now,
    )[candidate["candidate_id"]]

    assert reference_price_status(name_only, 1.85, now=now).code == "PLAYABLE"
    assert wettfinder_reference_price_status(
        name_only,
        1.85,
        candidate=candidate,
        now=now,
    ).code == "UNAVAILABLE"


def test_all_echtgeld_freshness_checks_every_contributing_point():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    older = _payload(
        now - timedelta(minutes=40),
        values={"Older A": "1.90", "Older B": "1.92"},
    )["response"][0]
    fresh = _payload(
        now,
        values={"Fresh A": "1.80", "Fresh B": "1.82"},
    )["response"][0]
    quote = parse_fixture_consensus(
        {"errors": [], "response": [older, fresh]},
        [_candidate()],
        fetched_at=now,
    )[_candidate()["candidate_id"]]

    # The aggregate clock is the latest observation, but neither Echtgeld path
    # may use it to conceal an expired contributor.
    assert quote.quoted_at == now.isoformat()
    assert quote.is_fresh(now)
    assert quote.is_wettfinder_fresh(now)
    assert not quote.is_fresh(now + timedelta(minutes=6))
    assert not quote.is_wettfinder_fresh(now + timedelta(minutes=6))


def test_15k_freshness_boundaries_are_35_minute_fetch_and_45_minute_points():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    point_boundary = parse_fixture_consensus(
        _payload(now - timedelta(minutes=45)),
        [_candidate()],
        fetched_at=now,
    )[_candidate()["candidate_id"]]

    assert point_boundary.is_fresh(now)
    assert not point_boundary.is_fresh(now + timedelta(seconds=1))

    fetch_boundary_moment = now - timedelta(minutes=35)
    fetch_boundary = parse_fixture_consensus(
        _payload(fetch_boundary_moment),
        [_candidate()],
        fetched_at=fetch_boundary_moment,
    )[_candidate()["candidate_id"]]

    assert fetch_boundary.is_fresh(now)
    assert not fetch_boundary.is_fresh(now + timedelta(seconds=1))


def test_newest_aggregate_clock_cannot_hide_one_expired_15k_offer():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    quote = parse_fixture_consensus(
        _payload(now),
        [_candidate()],
        fetched_at=now,
    )[_candidate()["candidate_id"]]
    expired = replace(
        quote.points[0],
        observed_at=(now - timedelta(minutes=46)).isoformat(),
    )
    tampered = replace(quote, points=(expired, *quote.points[1:]))

    assert tampered.quoted_at == now.isoformat()
    assert not tampered.is_fresh(now)
    assert reference_price_status(tampered, 1.85, now=now).code == "STALE"


def test_shared_consensus_drops_one_stale_point_but_keeps_three_fresh_books():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    stale = _payload(
        now - timedelta(hours=2),
        values={"Stale Book": "1.05"},
        provider_ids=True,
    )["response"][0]
    stale["bookmakers"][0]["id"] = 99
    fresh = _payload(
        now,
        values={
            "Fresh A": "2.00",
            "Fresh B": "2.10",
            "Fresh C": "2.20",
        },
        provider_ids=True,
    )["response"][0]
    candidate = _candidate()
    quote = parse_fixture_consensus(
        {"errors": [], "response": [stale, fresh]},
        [candidate],
        fetched_at=now,
    )[candidate["candidate_id"]]

    assert quote.bookmaker_count == 3
    assert quote.conservative_odds == 2.05
    effective = wettfinder_consensus(quote, now=now)
    assert effective is not None
    assert effective.bookmaker_count == 3
    assert effective.conservative_odds == 2.05
    status = wettfinder_reference_price_status(
        quote,
        1.95,
        candidate=candidate,
        now=now,
    )
    assert status.code == "PLAYABLE"
    assert status.usable_odds == 2.10
    assert status.bookmaker == "Fresh B"


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
        "fixture": {
            "id": 1493031,
            "date": "2030-01-01T18:00:00+00:00",
        },
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
        "sport": "Fussball",
        "source": "football_challenge",
        "scheduled_start": "2030-01-01T18:00:00+00:00",
        "selection": "Ja",
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
        quote,
        {**candidate, "selection": "Nein"},
    ) is False
    assert quote_matches_candidate(
        quote,
        {
            **candidate,
            "scheduled_start": "2030-01-01T17:00:00+00:00",
        },
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
        "scheduled_start": "2030-01-01T16:00:00+00:00",
        "quote_provider_event_id": "provider-event-1",
    }
    tennis_quote = replace(
        quote,
        fixture_id=None,
        candidate_id=tennis_candidate["candidate_id"],
        market_key="H2H",
        value_name="Anna-Lena",
        source=ODDS_API_REFERENCE_SOURCE,
        provider_event_id="provider-event-1",
        scheduled_start="2030-01-01T16:00:00+00:00",
        event_home="Bea",
        event_away="Anna Lena",
        bet_name="h2h",
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
    assert quote_matches_candidate(
        replace(tennis_quote, provider_event_id="provider-event-2"),
        tennis_candidate,
    ) is False
    assert quote_matches_candidate(
        replace(tennis_quote, bet_name="spreads"),
        tennis_candidate,
    ) is False
    assert quote_matches_candidate(
        replace(tennis_quote, event_home="Other Player"),
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
