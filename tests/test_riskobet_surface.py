from __future__ import annotations

from copy import deepcopy
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
        assert "Frühe Analyse · noch nicht historisch geprüft" not in markup
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
            "Kontext frisch",
            "Außenseitersieg",
            "Sieg Alpha",
            "34.0 %",
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


def test_model_probability_is_visible_without_internal_safety_or_method_notes():
    card = _card(_candidate())
    full = surface.render_riskobet_card_html(card)
    compact = surface.render_riskobet_compact_row_html(card)
    assert "Modellwahrscheinlichkeit" in full
    assert "Modell" in compact
    for markup in (full, compact):
        assert "Vorsichtige Trefferchance" not in markup
        assert "34.0 %" in markup
        assert "28.0 %" not in markup
        assert "Sicherheitswert" not in markup
        assert "Heuristischer Abschlag" not in markup
        assert "statistisch bestätigte Mindestchance" not in markup
    assert card.cautious_probability == 0.28


@pytest.mark.parametrize('renderer', [
    surface.render_riskobet_card_html, surface.render_riskobet_compact_row_html,
])
def test_legacy_simulation_and_recovery_copy_is_not_a_customer_match_reason(renderer):
    simulation = 'Die Serve-Simulation weist 64.2% für drei Sätze aus.'
    recovery = ('Arthur Gea: jüngstes beobachtetes Ergebnis seit 10.0 Stunden bestätigt; '
                'unvollständige Historie belegt keine tatsächliche Erholungsdauer.')
    candidate = _candidate(sport='tennis', pros=(simulation, 'Arthur gewann 3 der letzten 5 Spiele.'),
        cons=(recovery, 'Zhang gewann beide Direktduelle.'))
    card = _card(candidate, status='AVAILABLE', observed_odds=2.25)
    before = deepcopy(candidate), deepcopy(card)
    markup = renderer(card)
    assert simulation not in markup and recovery not in markup
    assert 'Serve-Simulation' not in markup and 'Erholungsdauer' not in markup
    assert 'Arthur gewann 3 der letzten 5 Spiele.' in markup
    assert 'Zhang gewann beide Direktduelle.' in markup
    assert '34.0 %' in markup and '2.25' in markup
    assert (candidate, card) == before
    assert card.pros[0] == simulation and card.cons[0] == recovery


@pytest.mark.parametrize('renderer', [
    surface.render_riskobet_card_html, surface.render_riskobet_compact_row_html,
])
def test_method_only_reason_blocks_disappear_without_inventing_a_sporting_argument(renderer):
    card = _card(_candidate(sport='tennis',
        pros=('Die Serve-Simulation weist 64.2% für drei Sätze aus.',),
        cons=('Das Modell setzt ein regulär beendetes Best-of-3-Match voraus.',)))
    markup = renderer(card)
    assert 'Serve-Simulation' not in markup and 'Best-of-3-Match' not in markup
    assert 'rb-reason-pro' not in markup and 'rb-reason-contra' not in markup
    assert 'rb-row-pro"' not in markup and 'rb-row-contra"' not in markup
    assert 'müde' not in markup and 'fit' not in markup
    assert '34.0 %' in markup


@pytest.mark.parametrize('renderer', [
    surface.render_riskobet_card_html, surface.render_riskobet_compact_row_html,
])
def test_equal_market_and_selection_labels_are_rendered_once_without_changing_the_card(renderer):
    card = _card(_candidate(sport='tennis', market_key='over_2_5_sets',
        market_label='Über 2,5 Sätze', selection_label='Über 2,5 Sätze'))
    before = deepcopy(card)
    markup = renderer(card)
    assert markup.count('Über 2,5 Sätze') == 1
    assert '34.0 %' in markup
    assert card == before and card.market == card.selection == 'Über 2,5 Sätze'
    different = replace(card, market='Über 2,5 Sätze · Match', selection='Über 2,5 Sätze')
    different_markup = renderer(different)
    assert 'Über 2,5 Sätze · Match' in different_markup
    assert different_markup.count('Über 2,5 Sätze') == 2


@pytest.mark.parametrize('renderer', [
    surface.render_riskobet_card_html, surface.render_riskobet_compact_row_html,
])
def test_technical_fallback_never_becomes_a_reason_or_missing_sport_fact(renderer):
    candidate = _candidate(pros=('API-Football provider failed (403)', 'Alpha gewann 4/5 Spiele.'),
        cons=('Walk-forward gate passed', 'Beta gewann beide Direktduelle.'),
        missing_core_data=('factor_key=weather passed', 'Startaufstellung'))
    card = _card(candidate)
    before = deepcopy(candidate), deepcopy(card)
    markup = renderer(card)
    assert 'Technischer Prüfstatus' not in markup
    assert 'Alpha gewann 4/5 Spiele.' in markup
    assert 'Beta gewann beide Direktduelle.' in markup
    assert 'Startaufstellung' in markup
    assert (candidate, card) == before


def test_tennis_form_projection_copies_each_exact_window_without_scope_protocol():
    raw = ('J. Smith Jr.: 3/5 · 6/10 Siege (Hartplatz · letzte 5 / 10 erfasste Spiele · '
           '22.08.2026–28.09.2026 · K.-o.-Runden einschließlich Qualifikation). '
           'Arthur Gea: 2/5 · 4/10 Siege (Hartplatz · letzte 5 / 10 erfasste Spiele · '
           '22.08.2026–28.09.2026 · K.-o.-Runden einschließlich Qualifikation).')
    surface_label, records = surface.compact_riskobet_tennis_form(raw)
    assert surface_label == 'Hartplatz'
    assert records == (('J. Smith Jr.', '3/5 Siege · 6/10 Siege'),
                       ('Arthur Gea', '2/5 Siege · 4/10 Siege'))
    assert 'K.-o.' not in repr(records) and '2026' not in repr(records)
    assert 'K.-o.-Runden einschließlich Qualifikation' in raw


def test_legacy_all_surface_record_has_a_compact_explicit_scope_and_count():
    raw = ('A: 3/5 Siege · alle Beläge (Alle Beläge · 5 erfasste Spiele · '
           '22.08.2026–28.09.2026).')
    assert surface.compact_riskobet_tennis_form(raw) == (
        'Alle Beläge', (('A', '3/5 Siege'),))


@pytest.mark.parametrize('value', [
    'A: 6/5 Siege (Hartplatz · 5 erfasste Spiele · 22.08.2026–28.09.2026).',
    'A: 3/5 · 4/5 Siege (Hartplatz · 5 erfasste Spiele · 22.08.2026–28.09.2026).',
    'A: Rating 3.5 auf Hartplatz, sechs Siege.',
    'A: 3/5 Siege · alle Beläge (Hartplatz · 5 erfasste Spiele · 22.08.2026–28.09.2026).',
])
def test_tennis_form_projection_never_infers_or_repairs_unknown_win_counts(value):
    assert surface.compact_riskobet_tennis_form(value) == ('', ())


@pytest.mark.parametrize('stage', list(EvidenceStage))
@pytest.mark.parametrize('show_price', [False, True])
@pytest.mark.parametrize('renderer', [
    surface.render_riskobet_card_html,
    surface.render_riskobet_compact_row_html,
])
def test_customer_render_keeps_sport_facts_and_internal_evidence_unchanged(
    stage, show_price, renderer,
):
    candidate = _candidate(
        stage=stage,
        context_state=ContextState.PARTIAL,
        pros=('Alpha gewann 4 der letzten 5 Spiele.',),
        cons=('Beta gewann beide Direktduelle.',),
        missing_core_data=('Startaufstellung',),
    )
    card = _card(
        candidate,
        status='AVAILABLE',
        observed_odds=3.45,
        bookmaker='Book One',
        observed_at='2030-01-01T13:00:00+00:00',
    )
    candidate_before, card_before = deepcopy(candidate), deepcopy(card)

    markup = renderer(card, show_price=show_price)

    for fact in ('Alpha vs Beta', 'Außenseitersieg', 'Sieg Alpha', '34.0 %',
                 'Alpha gewann 4 der letzten 5 Spiele.',
                 'Beta gewann beide Direktduelle.', 'Startaufstellung',
                 'Kontext teilweise offen'):
        assert fact in markup
    for internal in ('rb-badge-evidence', card.evidence_label, 'Sicherheitswert',
                     'heuristischer Abschlag', 'Heuristischer Abschlag',
                     'statistisch bestätigte Mindestchance', '28.0 %'):
        assert internal not in markup
    assert 'Kontext frisch' not in markup
    for price_fact in ('3.45', 'Book One', '01.01. 14:00', 'Quote beobachtet'):
        assert (price_fact in markup) is show_price
    assert candidate == candidate_before
    assert card == card_before
    assert card.evidence_code == stage.value
    assert card.evidence_label
    assert card.cautious_probability == candidate.cautious_probability == 0.28


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
    surface_text = (
        "Hartplatz: A 1.611 Elo (25 Spiele) · B 1.489 Elo (21 Spiele) · "
        "Belag-Elo berücksichtigt"
    )
    assert surface.format_riskobet_public_detail(surface_text) == "Hartplatz: A 25 erfasste Spiele · B 21 erfasste Spiele"
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
            quote_floor_excluded=False,
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
