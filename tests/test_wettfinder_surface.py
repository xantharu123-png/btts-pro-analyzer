from __future__ import annotations

from dataclasses import replace
import math
from datetime import datetime, timedelta, timezone

import pytest
import wettfinder_surface as surface
from ev_signal_sources import ModelSignal
from market_consensus import (
    MarketConsensus,
    QuotePoint,
    REFERENCE_SOURCE,
    WETTFINDER_FETCH_MAX_AGE,
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
    assert card.price_label == "Quote passend"
    assert card.price_tone == "warning"


def test_public_quote_binding_adapter_preserves_loader_identity():
    legacy = _signal(
        context_summary="Kontext: Kontext: H2H geprüft · Aufstellungen offen"
    )
    legacy_card = _card(legacy)
    legacy_markup = surface.render_top_card_html(legacy_card)
    assert legacy_card.context_label == "H2H geprüft · Aufstellungen offen"
    assert "Kontext: Kontext:" not in legacy_markup
    for raw in (None, "Kontext ausstehend", "Kontext: ausstehend"):
        fallback_card = _card(_signal(context_summary=raw))
        fallback_markup = surface.render_top_card_html(fallback_card)
        assert fallback_card.context_label == "ausstehend"
        assert "Kontext: Kontext" not in fallback_markup

    signal = replace(
        _signal("binding"),
        candidate_id="provider-candidate",
        fixture_id=321,
        home_team="Alpha",
        away_team="Beta",
        quote_provider_event_id="event-77",
        competitor_a="Alpha",
        competitor_b="Beta",
        selected_competitor="Alpha",
    )

    assert surface.wettfinder_quote_binding_candidate(signal) == {
        "candidate_id": "provider-candidate",
        "market_key": signal.market_key,
        "sport": signal.sport,
        "source": signal.source,
        "fixture_id": 321,
        "scheduled_start": signal.scheduled_start,
        "selection": signal.selection,
        "home_team": "Alpha",
        "away_team": "Beta",
        "quote_provider_event_id": "event-77",
        "competitor_a": "Alpha",
        "competitor_b": "Beta",
        "selected_competitor": "Alpha",
    }


def test_card_uses_precomputed_price_snapshot_at_age_boundary(monkeypatch):
    from app import _automated_signal_candidate
    from bet_finder_ui import evaluate_reference_price

    signal = _signal()
    quote = _quote(signal)
    candidate = _automated_signal_candidate(signal)
    boundary_now = NOW + WETTFINDER_FETCH_MAX_AGE
    evaluation = evaluate_reference_price(
        candidate,
        quote,
        bankroll=100.0,
        reference_binding_candidate=surface.wettfinder_quote_binding_candidate(
            signal
        ),
        now=boundary_now,
    )
    assert evaluation.status.code == "PLAYABLE"
    assert evaluation.quote is not None
    monkeypatch.setattr(
        surface,
        "wettfinder_reference_price_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("price status was recomputed")
        ),
    )
    monkeypatch.setattr(
        surface,
        "wettfinder_consensus",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("effective quote was recomputed")
        ),
    )

    card = surface.build_wettfinder_card(
        signal,
        quote,
        now=boundary_now,
        price_evaluation=evaluation,
    )

    assert card.price_code == evaluation.status.code
    assert card.observed_odds == evaluation.status.usable_odds
    assert card.reference_quote is evaluation.quote


def test_precomputed_price_rejects_same_key_with_different_candidate_content():
    from app import _automated_signal_candidate
    from bet_finder_ui import evaluate_reference_price

    signal = _signal(
        stage="RELEASED",
        statistical_release_passed=True,
    )
    quote = _quote(signal)
    candidate = _automated_signal_candidate(signal)
    evaluation = evaluate_reference_price(
        candidate,
        quote,
        bankroll=100.0,
        reference_binding_candidate=surface.wettfinder_quote_binding_candidate(
            signal
        ),
        now=NOW,
    )
    overlay = _overlay(signal, quote)
    assert evaluation.decision is not None
    assert evaluation.decision.status == "BET"

    for altered in (
        replace(signal, market="Manipulierter Markt"),
        replace(signal, selection="Manipulierte Auswahl"),
        replace(signal, probability=0.72),
        replace(signal, minimum_odds=1.90),
    ):
        with pytest.raises(ValueError, match="candidate"):
            surface.build_wettfinder_card(
                altered,
                quote,
                now=NOW,
                release_overlay=overlay,
                price_evaluation=evaluation,
            )


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
        "PLAYABLE": (_quote(signal), "Quote passend", 1.80),
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
    research = _card(_signal(context_complete=True, stage="RESEARCH"))
    pending = _card(_signal(context_complete=None, stage="RELEASED"))

    assert released.evidence_label == "Freigegeben"
    assert fully_checked.evidence_label == "Evidenzprüfung"
    assert partial.evidence_label == "Evidenzprüfung"
    assert research.evidence_label == "Forschungsmodell"
    assert pending.evidence_label == "Freigabe ausstehend"


@pytest.mark.parametrize("stage", ("SHADOW", "RESEARCH"))
def test_unreleased_evidence_with_playable_price_never_looks_released(stage):
    signal = _signal(stage=stage, context_complete=True)

    card = _card(signal, _quote(signal))
    markup = surface.render_top_card_html(card)

    assert card.confirmed_tip is False
    assert card.price_code == "PLAYABLE"
    assert card.price_label == "Quote passend"
    assert card.price_tone == "warning"
    assert card.evidence_label != "Vollständig geprüft"
    assert "Bestätigter Tipp" not in markup
    assert ">Spielbar</span>" not in markup
    assert "noch kein freigegebener Tipp" in markup


def test_confirmed_tip_requires_all_four_release_and_price_conditions():
    signal = _signal(stage="RELEASED", statistical_release_passed=True)
    quote = _quote(signal)

    assert _card(signal, quote).confirmed_tip is False
    confirmed = surface.build_wettfinder_card(
        signal, quote, now=NOW, release_overlay=_overlay(signal, quote)
    )
    assert confirmed.confirmed_tip is True
    assert confirmed.evidence_label == "Bestätigter Tipp"
    assert confirmed.price_label == "Spielbar"
    assert confirmed.price_tone == "positive"
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


def test_html_card_and_row_escape_all_visible_provider_text_and_hide_detail():
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
        assert "Detail &lt;script&gt;" not in markup
        assert "<button" not in markup
    assert "Kontext:</span> &lt;img src=x onerror=alert(1)&gt;" in top
    assert "Kontext &lt;img src=x onerror=alert(1)&gt;" not in row
    assert "Book &lt;2&gt;" in bookmaker_markup


def test_top_card_markup_exposes_the_decision_hierarchy_in_reading_order():
    signal = _signal(
        event="Rosenborg – Viking",
        context_summary="Kontext teilweise · Aufstellungen offen",
    )
    card = _card(signal, _quote(signal))

    markup = surface.render_top_card_html(card)

    expected_fragments = (
        'class="wf-badge wf-badge-top" aria-label="Top-Auswahl">TOP</span>',
        'class="wf-badge wf-badge-evidence wf-evidence-warning"',
        'class="wf-badge wf-badge-price wf-price-warning"',
        'class="wf-meta"',
        'class="wf-event"',
        'class="wf-market"',
        'class="wf-selection"',
        'class="wf-primary-probability"',
        'class="wf-metric-grid"',
        'data-price-code="PLAYABLE"',
        'class="wf-context"',
    )
    positions = [markup.index(fragment) for fragment in expected_fragments]
    assert positions == sorted(positions)
    assert '<article class="wf-top-card"' in markup
    assert "Vorsichtige Trefferchance" in markup
    assert "Modellwert" in markup
    assert "Value ab" in markup
    assert "Aktuell" in markup
    assert "noch kein freigegebener Tipp" in markup
    assert "Modell mit Form- und Kaderdaten" not in markup


@pytest.mark.parametrize(
    ("odds", "price_code", "expected_note"),
    (
        (
            (1.40, 1.45, 1.50),
            "TOO_LOW",
            "Aktuelle Quote unter Value. Die Prognose bleibt unverändert.",
        ),
        (
            None,
            "UNAVAILABLE",
            "Keine exakt passende Quote. Die Prognose bleibt unverändert.",
        ),
    ),
)
def test_price_note_is_short_and_keeps_forecast_separate_from_price(
    odds,
    price_code,
    expected_note,
):
    signal = _signal()
    quote = None if odds is None else _quote(signal, odds)
    card = _card(signal, quote)

    markup = surface.render_top_card_html(card)

    assert f'data-price-code="{price_code}"' in markup
    assert expected_note in markup
    assert "Mindestquote" not in markup


def test_compact_row_is_semantic_flat_and_keeps_the_same_decision_fields():
    signal = _signal(
        key="additional-row",
        event="Stabaek – Ranheim",
        market="Doppelte Chance",
        selection="1X",
    )
    card = _card(signal, _quote(signal))

    markup = surface.render_compact_row_html(card)

    assert '<article class="wf-row"' in markup
    assert 'class="wf-badge wf-badge-top"' not in markup
    assert 'class="wf-badge wf-badge-evidence' in markup
    assert 'class="wf-badge wf-badge-price' in markup
    assert 'class="wf-row-event"' in markup
    assert 'class="wf-row-pick"' in markup
    assert markup.count('class="wf-row-value"') == 4
    assert '>Modell</span>' in markup
    assert '>Vorsichtig</span>' in markup
    assert '>Value ab</span>' in markup
    assert '>Aktuell</span>' in markup
    assert 'class="wf-primary-probability"' not in markup
    assert 'class="wf-metric-grid"' not in markup
    assert 'class="wf-price-note' not in markup
    assert 'class="wf-context"' not in markup
    assert "Modell mit Form- und Kaderdaten" not in markup


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
