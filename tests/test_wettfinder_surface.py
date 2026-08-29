from __future__ import annotations

from dataclasses import replace
import math
from datetime import datetime, timedelta, timezone

import wettfinder_surface as surface
from ev_signal_sources import ModelSignal
from market_consensus import (
    MarketConsensus,
    QuotePoint,
    REFERENCE_SOURCE,
    wettfinder_consensus,
)


NOW = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)


def _signal(
    key: str = "football-main",
    *,
    sport: str = "Fussball",
    event: str = "Alpha vs Beta",
    market: str = "Doppelte Chance",
    selection: str = "1X",
    market_key: str = "DC_1X",
    stage: str = "SHADOW",
    context_complete: bool | None = True,
    statistical_release_passed: bool | None = False,
    detail: str = "Modell mit Form- und Kaderdaten",
    context_summary: str | None = "Kader geprüft",
) -> ModelSignal:
    return ModelSignal(
        key=key,
        label=f"{event} · {selection}",
        probability=0.68,
        probability_haircut=0.08,
        evidence_stage=stage,
        policy_version="surface-test",
        detail=detail,
        scheduled_start="2030-01-01T15:00:00+00:00",
        minimum_odds=1.70,
        source="football_challenge" if sport == "Fussball" else "tennis_shadow",
        sport=sport,
        event_label=event,
        market=market,
        selection=selection,
        market_key=market_key,
        candidate_id=f"candidate:{key}",
        fixture_id=123 if sport == "Fussball" else None,
        home_team="Alpha" if sport == "Fussball" else None,
        away_team="Beta" if sport == "Fussball" else None,
        context_summary=context_summary if context_complete is not None else None,
        context_complete=context_complete,
        statistical_release_passed=statistical_release_passed,
    )


def _quote(
    signal: ModelSignal,
    odds: tuple[float, ...] = (1.76, 1.80, 1.84),
    *,
    fetched_at: datetime = NOW,
) -> MarketConsensus:
    return MarketConsensus(
        fixture_id=signal.fixture_id,
        candidate_id=signal.candidate_id or signal.key,
        market_key=signal.market_key or "DC_1X",
        bet_name="Double Chance",
        value_name="Home/Draw",
        consensus_odds=odds[len(odds) // 2],
        conservative_odds=odds[0],
        lowest_odds=odds[0],
        best_odds=odds[-1],
        bookmaker_count=len(odds),
        quoted_at=fetched_at.isoformat(),
        fetched_at=fetched_at.isoformat(),
        source=REFERENCE_SOURCE,
        points=tuple(
            QuotePoint(
                bookmaker=f"Book <{index}>",
                odds=value,
                bookmaker_id=f"api-football:{index}",
                observed_at=fetched_at.isoformat(),
            )
            for index, value in enumerate(odds, 1)
        ),
        scheduled_start=signal.scheduled_start,
        event_home=signal.home_team,
        event_away=signal.away_team,
    )


def _card(signal: ModelSignal, quote: MarketConsensus | None = None):
    return surface.build_wettfinder_card(signal, quote, now=NOW)


def _overlay(
    signal: ModelSignal,
    quote: MarketConsensus,
    *,
    status: str = "BET",
    quoted_odds: float = 1.80,
):
    current = wettfinder_consensus(quote, now=NOW)
    assert current is not None
    executable = current.executable_point
    assert executable is not None
    return surface.WettfinderReleaseOverlay(
        signal_key=signal.key,
        quote_candidate_id=quote.candidate_id,
        quote_market_key=quote.market_key,
        status=status,
        quoted_odds=quoted_odds,
        quote_source=quote.source,
        bookmaker_id=executable.bookmaker_id or "",
        observed_at=executable.observed_at or "",
    )


def test_card_maps_model_and_exact_consensus_without_changing_probabilities():
    signal = _signal()

    card = _card(signal, _quote(signal))

    assert card.event_label == "Alpha vs Beta"
    assert card.sport == "Fussball"
    assert card.scheduled_start_label == "01.01. 16:00"
    assert card.market == "Doppelte Chance"
    assert card.selection == "1X"
    assert card.model_probability == 0.68
    assert math.isclose(card.cautious_probability, 0.60)
    assert card.value_threshold == 1.70
    assert card.observed_odds == 1.80
    assert card.bookmaker == "Book <2>"
    assert card.price_code == "PLAYABLE"
    assert card.price_label == "Spielbar"


def test_price_states_are_concise_and_only_current_prices_are_displayed():
    signal = _signal()
    cases = {
        "TOO_LOW": (_quote(signal, (1.30, 1.40, 1.50)), "Unter Value", 1.50),
        "BORDERLINE": (_quote(signal, (1.50, 1.60, 1.80)), "Quote offen", 1.80),
        "THIN": (_quote(signal, (1.80, 1.82)), "Quote zu dünn", None),
        "STALE": (
            _quote(signal, fetched_at=NOW - timedelta(hours=2)),
            "Veraltet",
            None,
        ),
        "UNAVAILABLE": (None, "Quote fehlt", None),
        "PLAYABLE": (_quote(signal), "Spielbar", 1.80),
    }

    for expected_code, (quote, label, visible_odds) in cases.items():
        card = _card(signal, quote)
        assert card.price_code == expected_code
        assert card.price_label == label
        assert card.observed_odds == visible_odds


def test_too_low_price_uses_only_the_current_consensus_points():
    signal = _signal()
    quote = _quote(signal, (1.40, 1.45, 1.50, 2.00))
    stale_point = replace(
        quote.points[-1],
        observed_at=(NOW - timedelta(hours=2)).isoformat(),
    )
    quote = replace(quote, points=(*quote.points[:-1], stale_point))

    card = _card(signal, quote)

    assert card.price_code == "TOO_LOW"
    assert card.observed_odds == 1.50
    assert card.bookmaker == "Book <3>"


def test_evidence_labels_do_not_invent_confirmation_or_context():
    released = _card(
        _signal(stage="RELEASED", statistical_release_passed=True),
        _quote(_signal(stage="RELEASED", statistical_release_passed=True)),
    )
    fully_checked = _card(_signal(context_complete=True))
    partial = _card(_signal(context_complete=False))
    pending = _card(_signal(context_complete=None, stage="RELEASED"))

    assert released.evidence_label == "Freigegeben"
    assert fully_checked.evidence_label == "Vollständig geprüft"
    assert partial.evidence_label == "Teilprüfung"
    assert pending.evidence_label == "Freigabe ausstehend"


def test_confirmed_tip_requires_all_four_release_and_price_conditions():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    quote = _quote(signal)

    assert _card(signal, quote).confirmed_tip is False
    assert surface.build_wettfinder_card(
        signal, quote, now=NOW, release_overlay=_overlay(signal, quote)
    ).confirmed_tip is True
    assert surface.build_wettfinder_card(
        replace(signal, statistical_release_passed=False),
        quote,
        now=NOW,
        release_overlay=_overlay(signal, quote),
    ).confirmed_tip is False
    assert surface.build_wettfinder_card(
        signal,
        _quote(signal, (1.30, 1.40, 1.50)),
        now=NOW,
        release_overlay=_overlay(signal, quote),
    ).confirmed_tip is False


def test_same_key_and_market_but_wrong_fixture_cannot_become_confirmed_tip():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    quote = replace(_quote(signal), fixture_id=999)

    card = surface.build_wettfinder_card(
        signal,
        quote,
        now=NOW,
        release_overlay=_overlay(signal, quote),
    )

    assert card.price_code == "UNAVAILABLE"
    assert card.observed_odds is None
    assert card.confirmed_tip is False


def test_confirmed_tip_requires_exact_executable_offer_provenance():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    quote = _quote(signal)
    exact = _overlay(signal, quote)

    assert surface.build_wettfinder_card(
        signal, quote, now=NOW, release_overlay=exact
    ).confirmed_tip is True

    for different_same_price_offer in (
        replace(exact, bookmaker_id="api-football:other"),
        replace(exact, observed_at="2030-01-01T12:01:00+00:00"),
        replace(exact, quote_source="other-current-source"),
    ):
        card = surface.build_wettfinder_card(
            signal,
            quote,
            now=NOW,
            release_overlay=different_same_price_offer,
        )
        assert card.price_code == "PLAYABLE"
        assert card.observed_odds == exact.quoted_odds
        assert card.confirmed_tip is False


def test_card_keeps_legacy_direct_constructor_shape():
    card = surface.WettfinderCard(
        "key",
        "Fussball",
        "01.01. 16:00",
        "Alpha vs Beta",
        "Doppelte Chance",
        "1X",
        0.68,
        0.60,
        1.70,
        None,
        None,
        "UNAVAILABLE",
        "Quote fehlt",
        "muted",
        "Teilprüfung",
        "warning",
        "Kontext",
        "Detail",
        False,
        None,
        "key",
    )

    assert card.market_key is None


def test_html_card_and_row_escape_all_provider_and_model_text():
    signal = _signal(
        event="<Alpha & Beta>",
        market='Markt <b>',
        selection='Auswahl "x"',
        detail="Detail <script>",
        context_summary="Kontext <img src=x onerror=alert(1)>",
    )
    card = _card(signal, _quote(signal))

    top = surface.render_top_card_html(card)
    row = surface.render_compact_row_html(card)
    bookmaker_markup = surface.render_top_card_html(
        _card(_signal(), _quote(_signal()))
    )

    for markup in (top, row):
        assert "<script>" not in markup
        assert "&lt;Alpha &amp; Beta&gt;" in markup
        assert "Markt &lt;b&gt;" in markup
        assert "Auswahl &quot;x&quot;" in markup
        assert "Detail &lt;script&gt;" in markup
        assert "Kontext &lt;img src=x onerror=alert(1)&gt;" in markup
        assert "<button" not in markup
    assert "Book &lt;2&gt;" in bookmaker_markup


def test_catalog_round_robins_sports_uses_no_price_order_and_keeps_fixture_rows_adjacent():
    football_broad = _card(
        _signal(
            "football-broad",
            event="Alpha vs Beta",
            market="Team 1 Gesamttore",
            selection="Über 0.5",
            market_key="HOME_OVER_0_5",
        )
    )
    tennis = _card(
        _signal(
            "tennis-h2h",
            sport="Tennis",
            event="Alpha vs Beta",
            market="Match Winner",
            selection="Sieg Alpha",
            market_key="H2H",
        )
    )
    football_useful = _card(
        _signal(
            "football-useful",
            event="Gamma vs Delta",
            market="Resultat & Gesamttore",
            selection="1X und Unter 3,5",
            market_key="RESULT_TOTAL_1X_UNDER_3_5",
        )
    )
    same_fixture_one = _card(
        _signal(
            "same-fixture-one",
            event="Epsilon vs Zeta",
            market="Beide Teams treffen",
            selection="Ja",
            market_key="BTTS_YES",
        )
    )
    unrelated = _card(
        _signal(
            "unrelated",
            event="Eta vs Theta",
            market="Endergebnis",
            selection="Heimsieg",
            market_key="RESULT_HOME",
        )
    )
    same_fixture_two = _card(
        _signal(
            "same-fixture-two",
            event="Epsilon vs Zeta",
            market="Gesamttore",
            selection="Über 2.5",
            market_key="TOTAL_OVER_2_5",
        )
    )
    same_fixture_three = _card(
        _signal(
            "same-fixture-three",
            event="Epsilon vs Zeta",
            market="Team 1 Gesamttore",
            selection="Über 1.5",
            market_key="HOME_OVER_1_5",
        )
    )
    cards = [
        football_broad,
        football_useful,
        same_fixture_one,
        unrelated,
        same_fixture_two,
        same_fixture_three,
        tennis,
    ]

    catalog = surface.compose_wettfinder_catalog(cards, sport_filter="Alle")
    repriced = [replace(card, observed_odds=9.99) for card in cards]
    repriced_catalog = surface.compose_wettfinder_catalog(
        repriced, sport_filter="Alle"
    )

    assert [card.key for card in catalog.featured] == [
        "tennis-h2h",
        "football-useful",
        "same-fixture-one",
    ]
    assert [card.key for card in catalog.featured] == [
        card.key for card in repriced_catalog.featured
    ]
    assert {card.key for card in catalog.featured + catalog.additional} == {
        card.key for card in cards
    }
    assert [card.key for card in catalog.additional] == [
        "football-broad",
        "unrelated",
        "same-fixture-two",
        "same-fixture-three",
    ]
    assert [group.fixture_identity for group in catalog.additional_groups] == [
        "fussball:alpha_vs_beta",
        "fussball:eta_vs_theta",
        "fussball:epsilon_vs_zeta",
    ]
    assert [card.key for card in catalog.additional_groups[2].cards] == [
        "same-fixture-two",
        "same-fixture-three",
    ]


def test_repeated_broad_team_totals_stay_visible_without_monopolizing_featured_cards():
    broad = [
        _card(
            _signal(
                f"broad-{index}",
                event=f"Team {index} vs Gegner {index}",
                market="Team 1 Gesamttore",
                selection="Über 0.5",
                market_key="HOME_OVER_0_5",
            )
        )
        for index in range(1, 4)
    ]
    useful = [
        _card(
            _signal(
                "useful-result",
                event="Omega vs Sigma",
                market="Resultat & Gesamttore",
                selection="1X und Unter 3,5",
                market_key="RESULT_TOTAL_1X_UNDER_3_5",
            )
        ),
        _card(
            _signal(
                "useful-btts",
                event="Iota vs Kappa",
                market="Beide Teams treffen",
                selection="Ja",
                market_key="BTTS_YES",
            )
        ),
    ]

    catalog = surface.compose_wettfinder_catalog([*broad, *useful])

    assert [card.key for card in catalog.featured] == [
        "useful-result",
        "useful-btts",
    ]
    assert {card.key for card in catalog.additional} == {
        "broad-1",
        "broad-2",
        "broad-3",
    }


def test_market_key_drives_basis_treatment_for_corners_and_yellow_markets():
    basic_keys = ("HOME_CORNERS_OVER_2_5", "YELLOW_UNDER_4_5")
    basic = [
        _card(
            _signal(
                key,
                event=f"{key} Event",
                market="Nichtssagender Markttext",
                selection="Nichtssagende Auswahl",
                market_key=key,
            )
        )
        for key in basic_keys
    ]
    useful = _card(
        _signal(
            "useful-btts-market-key",
            event="Useful vs Market",
            market="Beide Teams treffen",
            selection="Ja",
            market_key="BTTS_YES",
        )
    )

    catalog = surface.compose_wettfinder_catalog([*basic, useful])

    assert useful.market_key == "BTTS_YES"
    assert [card.key for card in catalog.featured] == ["useful-btts-market-key"]
    assert {card.key for card in catalog.additional} == set(basic_keys)


def test_same_market_family_can_feature_once_per_sport():
    tennis = _card(
        _signal(
            "tennis-winner",
            sport="Tennis",
            event="Tennis A vs B",
            market="Match Winner",
            selection="Sieg A",
            market_key="H2H",
        )
    )
    esports = _card(
        _signal(
            "esports-winner",
            sport="E-Sport",
            event="E-Sport A vs B",
            market="Match Winner",
            selection="Sieg A",
            market_key="H2H",
        )
    )

    catalog = surface.compose_wettfinder_catalog(
        [tennis, esports], max_featured=2
    )

    assert [card.key for card in catalog.featured] == [
        "tennis-winner",
        "esports-winner",
    ]
