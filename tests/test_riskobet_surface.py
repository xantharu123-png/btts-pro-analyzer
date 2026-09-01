from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from riskobet_domain import ContextState, EvidenceStage, RiskCandidate
import riskobet_surface as surface


START = datetime(2030, 1, 1, 15, 0, tzinfo=timezone.utc)
SNAPSHOT_ID = "snapshot_" + ("a" * 64)


def _candidate(
    key: str = "football-win",
    *,
    event_key: str = "event-alpha",
    sport: str = "football",
    competition: str = "Europa League",
    event_label: str = "Alpha vs Beta",
    market_key: str = "underdog_win",
    market_label: str = "Außenseitersieg",
    selection_key: str | None = None,
    selection_label: str = "Sieg Alpha",
    model_probability: float | None = 0.34,
    cautious_probability: float | None = 0.28,
    stage: EvidenceStage = EvidenceStage.SHADOW,
    context_state: ContextState = ContextState.FRESH,
    pros: tuple[str, ...] = ("Alpha ist auf diesem Belag formstark.",),
    cons: tuple[str, ...] = ("Beta besitzt die höhere Langzeitstärke.",),
    missing_core_data: tuple[str, ...] = (),
) -> RiskCandidate:
    return RiskCandidate(
        snapshot_id=SNAPSHOT_ID,
        event_key=event_key,
        sport=sport,
        competition=competition,
        event_label=event_label,
        starts_at=START,
        market_key=market_key,
        market_label=market_label,
        selection_key=selection_key or key,
        selection_label=selection_label,
        model_probability=model_probability,
        cautious_probability=cautious_probability,
        stage=stage,
        context_state=context_state,
        policy_version="risk-v1",
        pros=pros,
        cons=cons,
        missing_core_data=missing_core_data,
        settlement_contract=(
            None if stage is EvidenceStage.RESEARCH else "match-winner-v1"
        ),
    )


def _card(candidate: RiskCandidate, **price) -> surface.RiskBetCard:
    overlay = (
        surface.RiskBetPriceOverlay(
            candidate_id=candidate.candidate_id,
            **price,
        )
        if price
        else None
    )
    return surface.build_riskobet_card(candidate, overlay)


def test_sport_filters_are_exactly_all_plus_the_six_product_sports():
    assert surface.SPORT_FILTERS == (
        "Alle",
        "Fußball",
        "Tennis",
        "Basketball",
        "Eishockey",
        "Cricket",
        "E-Sport",
    )


def test_card_maps_domain_candidate_and_exact_price_overlay():
    candidate = _candidate()
    card = _card(
        candidate,
        status="AVAILABLE",
        observed_odds=3.45,
        bookmaker="Book One",
        observed_at="2030-01-01T13:00:00+00:00",
    )

    assert card.candidate_id == candidate.candidate_id
    assert card.event_key == "event-alpha"
    assert card.sport_key == "football"
    assert card.sport == "Fußball"
    assert card.scheduled_start_label == "01.01. 16:00"
    assert card.model_probability == 0.34
    assert card.cautious_probability == 0.28
    assert card.evidence_label == "Im Test · noch nicht historisch bestätigt"
    assert card.context_label == "Kontext frisch"
    assert card.pros == candidate.pros
    assert card.cons == candidate.cons
    assert card.price_code == "AVAILABLE"
    assert card.price_label == "Quote beobachtet"
    assert card.observed_odds == 3.45
    assert card.bookmaker == "Book One"


def test_missing_research_probability_is_honestly_open_in_both_surfaces():
    candidate = _candidate(
        "cricket-open",
        sport="cricket",
        market_key="underdog_match_win",
        selection_label="Sieg Außenseiter",
        model_probability=None,
        cautious_probability=None,
        stage=EvidenceStage.RESEARCH,
        context_state=ContextState.OPEN,
        missing_core_data=("Belastbare Pitch-Historie", "Toss"),
    )
    card = _card(candidate)

    full = surface.render_riskobet_card_html(card)
    compact = surface.render_riskobet_compact_row_html(card)

    assert surface.format_riskobet_probability(None) == "offen"
    for markup in (full, compact):
        assert "offen" in markup
        assert "Frühe Analyse · noch nicht historisch geprüft" in markup
        assert "Kontext offen" in markup
        assert "Belastbare Pitch-Historie" in markup
        assert "Quote fehlt" in markup
        assert ">–</strong>" in markup


def test_exact_one_probability_never_looks_like_a_guaranteed_100_percent():
    assert surface.format_riskobet_probability(1.0) == "> 99,5 %"
    assert surface.format_riskobet_probability(0.9995) == "> 99,5 %"
    assert surface.format_riskobet_probability(0.9994) == "99.9 %"


def test_full_and_genuinely_compact_markup_keep_every_decision_field_visible():
    candidate = _candidate(
        pros=("Pro eins", "Pro zwei"),
        cons=("Contra eins", "Contra zwei"),
    )
    card = _card(candidate, status="TOO_LOW", observed_odds=2.10)

    full = surface.render_riskobet_card_html(card)
    compact = surface.render_riskobet_compact_row_html(card)

    for markup in (full, compact):
        for visible in (
            "Fußball",
            "01.01. 16:00",
            "Im Test · noch nicht historisch bestätigt",
            "Kontext frisch",
            "Außenseitersieg",
            "Sieg Alpha",
            "34.0 %",
            "28.0 %",
            "Pro eins",
            "Contra eins",
            "Quote niedrig",
            "2.10",
        ):
            assert visible in markup
        assert "<details" not in markup
        assert "<button" not in markup

    assert '<article class="rb-card rb-card-featured"' in full
    assert '<article class="rb-row"' in compact
    assert "Pro zwei" in full
    assert "Contra zwei" in full
    assert "Pro zwei" not in compact
    assert "Contra zwei" not in compact
    assert "<ul>" not in compact
    assert len(compact) < len(full)


def test_internal_context_statuses_are_translated_without_promoting_evidence():
    candidate = _candidate(
        pros=("Wetter: passed", "Direktduelle: neutral"),
        cons=("Aufstellungen: required_missing", "Ausfälle: unavailable"),
        missing_core_data=("Toss: open",),
    )

    card = _card(candidate)
    markup = surface.render_riskobet_card_html(card)

    assert card.evidence_code == "SHADOW"
    assert card.evidence_label == "Im Test · noch nicht historisch bestätigt"
    assert card.pros == (
        "Wetter: geprüft",
        "Direktduelle: ohne klaren Einfluss",
    )
    assert card.cons == (
        "Aufstellungen: noch nicht bestätigt",
        "Ausfälle: nicht verfügbar",
    )
    assert card.missing_core_data == ("Toss: noch offen",)
    for internal in (
        "Shadow",
        ": passed",
        ": neutral",
        ": required_missing",
        ": unavailable",
    ):
        assert internal not in markup


def test_public_detail_maps_known_model_terms_and_fails_safe_for_debug_copy():
    assert surface.format_riskobet_public_detail(
        "RESEARCH: Lineups sind noch nicht kausal validiert."
    ) == (
        "Frühe Analyse · noch nicht historisch geprüft: "
        "Lineups sind noch nicht kausal validiert."
    )
    assert "Beta(2,2)" not in surface.format_riskobet_public_detail(
        "Team: 4/9 Siege; Beta(2,2)-Glättung."
    )
    assert "Log5" not in surface.format_riskobet_public_detail(
        "Das geglättete Log5-Modell ergibt 31,0 %."
    )
    assert "Subgraph-Elo" not in surface.format_riskobet_public_detail(
        "Subgraph-Elo 1510/1580, Best-of-3."
    )
    assert "i.i.d." not in surface.format_riskobet_public_detail(
        "Die i.i.d.-Mapannahme bildet den Veto-Effekt nicht vollständig ab."
    )
    assert "eingefrorenen Modellzustand" not in surface.format_riskobet_public_detail(
        "Fitness ist enthalten, soweit sie im eingefrorenen Modellzustand vorlag."
    )
    for raw in (
        "Walk-forward gate passed",
        "API-Football provider failed (403)",
        "injury_provider_id=99123 failed",
        "factor_key=weather passed",
    ):
        public = surface.format_riskobet_public_detail(raw)
        assert public == (
            "Technischer Prüfstatus ist noch nicht nutzerverständlich "
            "aufbereitet."
        )


def test_every_external_text_is_escaped_in_full_and_compact_markup():
    candidate = _candidate(
        competition='<Liga & "Pokal">',
        event_label="<Alpha & Beta>",
        market_label="Markt <script>alert(1)</script>",
        selection_label='Auswahl "x" <img src=x>',
        pros=("Pro <svg onload=alert(1)>",),
        cons=("Contra </section><script>x</script>",),
        missing_core_data=("Quelle <iframe>",),
    )
    card = _card(
        candidate,
        status="AVAILABLE",
        observed_odds=2.25,
        bookmaker="Book <b> & Co",
    )

    for markup in (
        surface.render_riskobet_card_html(card),
        surface.render_riskobet_compact_row_html(card),
    ):
        assert "<script>" not in markup
        assert "<img" not in markup
        assert "<svg" not in markup
        assert "<iframe" not in markup
        assert "&lt;Alpha &amp; Beta&gt;" in markup
        assert "Auswahl &quot;x&quot; &lt;img src=x&gt;" in markup
        assert "Pro &lt;svg onload=alert(1)&gt;" in markup
        assert "Book &lt;b&gt; &amp; Co" in markup


def test_price_overlay_is_strictly_bound_to_candidate_identity():
    candidate = _candidate()
    wrong = surface.RiskBetPriceOverlay(
        candidate_id="candidate_wrong",
        status="AVAILABLE",
        observed_odds=3.0,
    )

    with pytest.raises(ValueError, match="candidate mismatch"):
        surface.build_riskobet_card(candidate, wrong)


def test_price_changes_neither_visibility_nor_order():
    candidates = [
        _candidate(
            "football-one",
            event_key="football-one",
            selection_key="football-one",
        ),
        _candidate(
            "tennis-one",
            event_key="tennis-one",
            sport="tennis",
            selection_key="tennis-one",
        ),
        _candidate(
            "basketball-one",
            event_key="basketball-one",
            sport="basketball",
            selection_key="basketball-one",
        ),
        _candidate(
            "football-two",
            event_key="football-two",
            selection_key="football-two",
        ),
    ]
    cards = [_card(candidate) for candidate in candidates]
    repriced = [
        replace(
            card,
            price_code="PLAYABLE" if index % 2 else "TOO_LOW",
            price_label="Beliebiger neuer Preisstatus",
            observed_odds=9.99 - index,
            bookmaker="Anderer Anbieter",
        )
        for index, card in enumerate(cards)
    ]

    catalog = surface.compose_riskobet_catalog(cards)
    repriced_catalog = surface.compose_riskobet_catalog(repriced)

    assert [card.candidate_id for card in catalog.cards] == [
        card.candidate_id for card in repriced_catalog.cards
    ]
    assert len(catalog.cards) == len(cards)


def test_all_filter_round_robins_sports_in_fixed_product_order():
    cards = [
        _card(
            _candidate(
                "football-one",
                event_key="football-one",
                selection_key="football-one",
            )
        ),
        _card(
            _candidate(
                "football-two",
                event_key="football-two",
                selection_key="football-two",
            )
        ),
        _card(
            _candidate(
                "tennis-one",
                event_key="tennis-one",
                sport="tennis",
                selection_key="tennis-one",
            )
        ),
        _card(
            _candidate(
                "tennis-two",
                event_key="tennis-two",
                sport="tennis",
                selection_key="tennis-two",
            )
        ),
        _card(
            _candidate(
                "basketball-one",
                event_key="basketball-one",
                sport="basketball",
                selection_key="basketball-one",
            )
        ),
    ]

    catalog = surface.compose_riskobet_catalog(cards)

    assert [card.sport_key for card in catalog.cards] == [
        "football",
        "tennis",
        "basketball",
        "football",
        "tennis",
    ]


def test_research_candidates_follow_shadow_and_validated_candidates():
    research = _card(
        _candidate(
            "football-research",
            event_key="football-research",
            stage=EvidenceStage.RESEARCH,
            selection_key="football-research",
        )
    )
    shadow = _card(
        _candidate(
            "tennis-shadow",
            event_key="tennis-shadow",
            sport="tennis",
            selection_key="tennis-shadow",
        )
    )
    validated = _card(
        _candidate(
            "basketball-validated",
            event_key="basketball-validated",
            sport="basketball",
            stage=EvidenceStage.VALIDATED,
            selection_key="basketball-validated",
        )
    )

    catalog = surface.compose_riskobet_catalog(
        [research, shadow, validated]
    )

    assert [card.evidence_code for card in catalog.cards] == [
        "SHADOW",
        "VALIDATED",
        "RESEARCH",
    ]


def test_research_is_not_promoted_above_established_simple_scenarios():
    established_simple = [
        _card(
            _candidate(
                f"shadow-simple-{index}",
                event_key=f"shadow-simple-{index}",
                market_key="underdog_one_plus_goal",
                selection_key=f"shadow-simple-{index}",
                selection_label="Außenseiter erzielt 1+ Tor",
            )
        )
        for index in range(2)
    ]
    research_useful = _card(
        _candidate(
            "research-win",
            event_key="research-win",
            market_key="underdog_win",
            selection_key="research-win",
            stage=EvidenceStage.RESEARCH,
        )
    )

    catalog = surface.compose_riskobet_catalog(
        [research_useful, *established_simple]
    )

    assert [card.evidence_code for card in catalog.cards] == [
        "SHADOW",
        "SHADOW",
        "RESEARCH",
    ]
    assert research_useful not in catalog.featured


def test_research_fills_free_top_slots_after_all_established_are_featured():
    established = _card(
        _candidate(
            "shadow-win",
            event_key="shadow-win",
            market_key="underdog_win",
            selection_key="shadow-win",
        )
    )
    research = [
        _card(
            _candidate(
                f"research-win-{index}",
                event_key=f"research-win-{index}",
                sport=("basketball", "ice_hockey")[index],
                market_key="underdog_win",
                selection_key=f"research-win-{index}",
                stage=EvidenceStage.RESEARCH,
            )
        )
        for index in range(2)
    ]

    catalog = surface.compose_riskobet_catalog([*research, established])

    assert [card.candidate_id for card in catalog.featured] == [
        established.candidate_id,
        research[0].candidate_id,
        research[1].candidate_id,
    ]
    assert [card.evidence_code for card in catalog.featured] == [
        "SHADOW",
        "RESEARCH",
        "RESEARCH",
    ]


def test_catalog_never_publishes_more_than_two_scenarios_per_event():
    cards = [
        _card(
            _candidate(
                f"scenario-{index}",
                event_key="same-event",
                market_key=f"risk_market_{index}",
                selection_key=f"selection-{index}",
            )
        )
        for index in range(3)
    ]

    catalog = surface.compose_riskobet_catalog(cards)

    assert len(catalog.cards) == 2
    assert [card.market_key for card in catalog.cards] == [
        "risk_market_0",
        "risk_market_1",
    ]


def test_featured_is_capped_at_three_and_simple_markets_cannot_dominate():
    useful = [
        _card(
            _candidate(
                f"useful-{index}",
                event_key=f"useful-{index}",
                sport=("football", "tennis")[index],
                market_key="underdog_win",
                selection_key=f"useful-{index}",
            )
        )
        for index in range(2)
    ]
    simple = [
        _card(
            _candidate(
                f"simple-{index}",
                event_key=f"simple-{index}",
                sport=("football", "tennis", "esports", "ice_hockey")[
                    index
                ],
                market_key=(
                    "underdog_team_over_0_5_90_minutes"
                    if index in (0, 3)
                    else "plus_1_5_sets"
                    if index == 1
                    else "at_least_one_map"
                ),
                selection_key=f"simple-{index}",
                selection_label=(
                    "Außenseiter erzielt 1+ Tor"
                    if index in (0, 3)
                    else "Außenseiter gewinnt 1+ Satz"
                    if index == 1
                    else "Außenseiter gewinnt 1+ Map"
                ),
            )
        )
        for index in range(4)
    ]

    catalog = surface.compose_riskobet_catalog([*simple, *useful])

    assert len(catalog.featured) == 3
    assert sum(card.simple_market for card in catalog.featured) == 1
    assert {card.candidate_id for card in catalog.cards} == {
        card.candidate_id for card in [*simple, *useful]
    }


def test_sport_filter_only_changes_view_and_rejects_non_product_filters():
    football = _card(_candidate())
    tennis = _card(
        _candidate(
            "tennis",
            event_key="tennis",
            sport="tennis",
            selection_key="tennis",
        )
    )

    catalog = surface.compose_riskobet_catalog(
        [football, tennis], sport_filter="Tennis"
    )

    assert [card.sport_key for card in catalog.cards] == ["tennis"]
    with pytest.raises(ValueError, match="SPORT_FILTERS"):
        surface.compose_riskobet_catalog([football, tennis], sport_filter="all")
    with pytest.raises(ValueError, match="one and three"):
        surface.compose_riskobet_catalog([football], max_featured=4)
