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


def test_double_chance_accepts_provider_tokens_without_losing_exact_side():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    candidates = [{**_candidate(key), 'selection': selection}
                  for key, selection in (('DC_1X', '1X'), ('DC_X2', 'X2'), ('DC_12', '12'))]
    for values in (
        [('1X', '1.25'), ('X2', '1.55'), ('12', '1.30')],
        [('Home/Draw', '1.25'), ('Draw/Away', '1.55'), ('Home/Away', '1.30')],
    ):
        payload = _payload(now, provider_ids=True)
        for bookmaker in payload['response'][0]['bookmakers']:
            bookmaker['bets'] = [{'name': 'Double Chance', 'values': [
                {'value': value, 'odd': odds} for value, odds in values]}]
        quotes = parse_fixture_consensus(payload, candidates, fetched_at=now)
        assert set(quotes) == {'1493030:DC_1X', '1493030:DC_X2', '1493030:DC_12'}
        for candidate, expected in zip(candidates, (1.25, 1.55, 1.30)):
            quote = quotes[candidate['candidate_id']]
            assert quote.best_odds == expected
            assert quote_matches_candidate(quote, candidate)
            assert not quote_matches_candidate(quote, {**candidate, 'market_key': 'RESULT_HOME'})
            assert not quote_matches_candidate(quote, {**candidate, 'scheduled_start': '2030-01-01T17:00:00+00:00'})


def test_double_chance_aliases_do_not_inflate_books_or_match_other_periods():
    now = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    payload = _payload(now, provider_ids=True)
    payload['response'][0]['bookmakers'][0]['bets'] = [
        {'name': 'Double Chance', 'values': [
            {'value': '1X', 'odd': '1.40'}, {'value': 'Home/Draw', 'odd': '1.25'}]},
        {'name': 'Double Chance - First Half', 'values': [{'value': '1X', 'odd': '9.00'}]},
    ]
    candidate = _candidate('DC_1X')
    quote = parse_fixture_consensus(payload, [candidate], fetched_at=now)[candidate['candidate_id']]
    assert quote.bookmaker_count == 1
    assert quote.best_odds == 1.25


def test_football_batch_uses_each_response_clock(monkeypatch):
    from types import SimpleNamespace
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    later = start + timedelta(minutes=2)
    clocks = iter((start, start, later))
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(clocks)
    monkeypatch.setattr(market_consensus, 'datetime', Clock)
    candidates = [_candidate(), {**_candidate(), 'candidate_id': '1493031:BTTS_YES', 'fixture_id': 1493031}]
    def get(_url, **kwargs):
        fixture = kwargs['params']['fixture']
        payload = _payload(start if fixture == 1493030 else later, provider_ids=True)
        payload['response'][0]['fixture']['id'] = fixture
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
    monkeypatch.setattr(market_consensus, 'api_football_get', get)
    quotes, errors = market_consensus.fetch_football_consensus('test', candidates)
    assert errors == []
    assert set(quotes) == {'1493030:BTTS_YES', '1493031:BTTS_YES'}
    assert quotes['1493030:BTTS_YES'].fetched_at == start.isoformat()
    assert quotes['1493031:BTTS_YES'].fetched_at == later.isoformat()
    assert quotes['1493031:BTTS_YES'].quoted_at == later.isoformat()


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


def _gea_zhang_quote_fixture(now, *, selected="Arthur Gea"):
    candidate = {
        "candidate_id": "tennis-gea-zhang-A" if selected == "Arthur Gea" else "tennis-gea-zhang-B",
        "market_key": "H2H", "sport": "Tennis", "source": "tennis_shadow",
        "competitor_a": "Arthur Gea", "competitor_b": "Zhang Zhizhen",
        "selected_competitor": selected, "competition": "ATP China Open",
        "scheduled_start": "2030-09-30T09:00:00+00:00",
    }
    event = {
        "id": "gea-zhang-provider-event", "home_team": "Zhizhen Zhang",
        "away_team": "Arthur Gea", "commence_time": candidate["scheduled_start"],
        "bookmakers": [{
            "key": "pinnacle", "title": "Pinnacle", "last_update": now.isoformat(),
            "markets": [{"key": "h2h", "outcomes": [
                {"name": "Zhizhen Zhang", "price": 2.70},
                {"name": "Arthur Gea", "price": 1.52},
            ]}],
        }],
    }
    return candidate, event


def test_tennis_full_name_order_matches_provider_event_and_selected_side():
    now = datetime(2030, 9, 30, 8, tzinfo=UTC)
    for selected, expected in (("Arthur Gea", 1.52), ("Zhang Zhizhen", 2.70)):
        candidate, event = _gea_zhang_quote_fixture(now, selected=selected)
        assert market_consensus._h2h_event_matches(event, candidate)
        quotes = parse_h2h_event_consensus(event, [candidate], fetched_at=now)
        quote = quotes[candidate["candidate_id"]]
        assert quote.best_odds == expected
        assert quote.value_name == selected
        assert quote.event_home == "Zhizhen Zhang"
        assert quote_matches_candidate(quote, candidate)
        provider_selected = "Zhizhen Zhang" if selected == "Zhang Zhizhen" else "Gea Arthur"
        assert quote_matches_candidate(replace(quote, value_name=provider_selected), candidate)
        assert not quote_matches_candidate(replace(quote, value_name="Other Player"), candidate)


def test_tennis_name_order_equivalence_never_drops_adds_or_fuzzes_tokens():
    now = datetime(2030, 9, 30, 8, tzinfo=UTC)
    candidate, event = _gea_zhang_quote_fixture(now)
    quote = parse_h2h_event_consensus(event, [candidate], fetched_at=now)[candidate["candidate_id"]]
    for wrong_name in ("Zhang", "Zhizhen", "Zhang Z.", "Zhizheng Zhang",
                       "Zhizhen Zhang Jr", "Zhizhen Zhang Zhang", "Arthur Gea Zhang"):
        assert not market_consensus._h2h_event_matches({**event, "home_team": wrong_name}, candidate)
        assert parse_h2h_event_consensus({**event, "home_team": wrong_name}, [candidate], fetched_at=now) == {}
        assert not quote_matches_candidate(replace(quote, event_home=wrong_name), candidate)
    assert market_consensus._identity_name("Zhizhen Zhang") != market_consensus._identity_name("Zhang Zhizhen")
    # Distinct participants cannot collapse to one token identity; repeated
    # tokens also remain part of a name, unlike a plain set comparison.
    assert market_consensus._h2h_candidate_identity({**candidate,
        "competitor_a": "Zhizhen Zhang", "selected_competitor": "Zhizhen Zhang"}) is None
    assert not market_consensus._h2h_event_matches({**event, "away_team": "Zhang Zhizhen"}, candidate)


def test_tennis_name_order_does_not_relax_final_start_or_provider_binding():
    now = datetime(2030, 9, 30, 8, tzinfo=UTC)
    candidate, event = _gea_zhang_quote_fixture(now)
    quote = parse_h2h_event_consensus(event, [candidate], fetched_at=now)[candidate["candidate_id"]]
    start = datetime.fromisoformat(candidate["scheduled_start"])
    assert quote_matches_candidate(replace(quote, scheduled_start=(start+timedelta(minutes=30)).isoformat()), candidate)
    assert not quote_matches_candidate(replace(quote, scheduled_start=(start+timedelta(minutes=31)).isoformat()), candidate)
    bound = {**candidate, "quote_provider_event_id": quote.provider_event_id}
    assert quote_matches_candidate(quote, bound)
    assert not quote_matches_candidate(replace(quote, provider_event_id="another-event"), bound)


def test_tennis_reversed_names_still_reject_ambiguous_provider_events(monkeypatch):
    now = datetime(2030, 9, 30, 8, tzinfo=UTC)
    candidate, event = _gea_zhang_quote_fixture(now)
    calls = []
    def provider(path, _key, **_kwargs):
        calls.append(path)
        if path == "sports/":
            return [{"key": "tennis_atp_china_open", "active": True}], None
        if path.endswith("/events"):
            return [event, {**event, "id": "second-event", "home_team": "Zhang Zhizhen"}], None
        raise AssertionError("Ambiguous identity must not request paid odds")
    monkeypatch.setattr(market_consensus, "_odds_api_json", provider)
    quotes, errors = market_consensus.fetch_tennis_h2h_consensus("test-key", [candidate], now=now)
    assert quotes == {}
    assert len(errors) == 1 and "Ereignis nicht eindeutig" in errors[0]
    assert calls == ["sports/", "sports/tennis_atp_china_open/events"]


def test_tennis_name_order_fetch_discovers_and_parses_one_exact_event(monkeypatch):
    now = datetime(2030, 9, 30, 8, tzinfo=UTC)
    candidate, event = _gea_zhang_quote_fixture(now, selected="Zhang Zhizhen")
    calls = []
    def provider(path, _key, **kwargs):
        calls.append(path)
        if path == "sports/":
            return [{"key": "tennis_atp_china_open", "active": True}], None
        if path.endswith("/events"):
            return [event], None
        assert kwargs["params"]["eventIds"] == event["id"]
        assert kwargs["params"]["markets"] == "h2h"
        return [event], None
    monkeypatch.setattr(market_consensus, "_odds_api_json", provider)
    quotes, errors = market_consensus.fetch_tennis_h2h_consensus("test-key", [candidate], now=now)
    assert errors == []
    quote = quotes[candidate["candidate_id"]]
    assert quote.best_odds == 2.70 and quote_matches_candidate(quote, candidate)
    assert calls == ["sports/", "sports/tennis_atp_china_open/events", "sports/tennis_atp_china_open/odds"]


def test_tennis_name_order_still_rejects_duplicate_odds_event_ids(monkeypatch):
    now = datetime(2030, 9, 30, 8, tzinfo=UTC)
    candidate, event = _gea_zhang_quote_fixture(now)
    def provider(path, _key, **_kwargs):
        if path == "sports/":
            return [{"key": "tennis_atp_china_open", "active": True}], None
        if path.endswith("/events"):
            return [event], None
        return [event, {**event, "home_team": "Zhang Zhizhen"}], None
    monkeypatch.setattr(market_consensus, "_odds_api_json", provider)
    quotes, errors = market_consensus.fetch_tennis_h2h_consensus("test-key", [candidate], now=now)
    assert quotes == {} and errors == []


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
