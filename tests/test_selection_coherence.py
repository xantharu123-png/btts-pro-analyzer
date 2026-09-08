"""Consumer selection sets must be logically possible, not merely pairwise."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from challenge_engine import MARKET_SPECS, market_outcome
from selection_coherence import consumer_event_identity, select_coherent_forecasts


def row(market_key="RESULT_HOME", **changes):
    result = {
        "sport": "Fußball", "fixture_id": 1635654,
        "market_key": market_key, "scheduled_start": "2026-09-08T21:00:00+02:00",
        "home_team": "FC Porto", "away_team": "Manchester City",
        "probability": 0.46361, "observed_odds": None,
    }
    result.update(changes)
    return result


@pytest.mark.parametrize("key", [spec.key for spec in MARKET_SPECS])
def test_all_configured_markets_remain_allowed_as_primary(key):
    candidate = row(key)
    assert select_coherent_forecasts([candidate]) == [candidate]


@pytest.mark.parametrize("first,opposite", [
    ("RESULT_HOME", "RESULT_AWAY"), ("RESULT_HOME", "DC_X2"),
    ("BTTS_YES", "TOTAL_UNDER_1_5"), ("BTTS_NO", "BTTS_YES"),
    ("TOTAL_OVER_2_5", "TOTAL_UNDER_2_5"),
    ("HOME_OVER_1_5", "HOME_UNDER_1_5"),
    ("AWAY_RANGE_2_4", "AWAY_UNDER_1_5"),
    ("CORNERS_OVER_8_5", "CORNERS_UNDER_8_5"),
    ("HOME_CORNERS_OVER_3_5", "HOME_CORNERS_UNDER_3_5"),
    ("YELLOW_OVER_2_5", "YELLOW_UNDER_2_5"),
    ("AWAY_YELLOW_OVER_1_5", "AWAY_YELLOW_UNDER_1_5"),
])
def test_inverse_selections_do_not_coexist(first, opposite):
    candidates = [row(first), row(opposite)]
    assert select_coherent_forecasts(candidates) == candidates[:1]
    assert select_coherent_forecasts(candidates[::-1]) == candidates[1:]


@pytest.mark.parametrize("keys", [
    ("DC_1X", "DC_X2", "DC_12"),
    ("TOTAL_UNDER_2_5", "HOME_OVER_0_5", "AWAY_OVER_1_5"),
    ("CORNERS_UNDER_5_5", "HOME_CORNERS_OVER_2_5", "AWAY_CORNERS_OVER_2_5"),
    ("YELLOW_UNDER_2_5", "HOME_YELLOW_OVER_0_5", "AWAY_YELLOW_OVER_1_5"),
])
def test_jointly_impossible_triples_are_rejected_even_if_every_pair_is_possible(keys):
    candidates = [row(key) for key in keys]
    for a, b in ((0, 1), (1, 2), (0, 2)):
        assert select_coherent_forecasts([candidates[a], candidates[b]]) == [candidates[a], candidates[b]]
    assert select_coherent_forecasts(candidates) == candidates[:2]


def test_goals_corners_and_yellow_cards_are_separate_logical_count_domains():
    candidates = [row(key) for key in (
        "RESULT_HOME", "BTTS_YES", "TOTAL_OVER_2_5", "HOME_RANGE_2_4",
        "CORNERS_UNDER_5_5", "YELLOW_UNDER_1_5",
    )]
    assert select_coherent_forecasts(candidates) == candidates


def test_preferred_anchor_wins_without_reordering_original_rows():
    away, extra, home, other = row("RESULT_AWAY"), row("TOTAL_OVER_2_5"), row(), row(fixture_id=7)
    candidates = [away, extra, home, other]
    result = select_coherent_forecasts(candidates, preferred=[home])
    assert result == [extra, home, other]
    assert result[0] is extra and result[1] is home and result[2] is other


def test_only_first_preferred_anchor_per_event_is_used_and_external_anchor_is_not_inserted():
    home, away, goals = row(), row("RESULT_AWAY"), row("TOTAL_OVER_2_5")
    assert select_coherent_forecasts([home, away, goals], preferred=[home, away]) == [home, goals]
    assert select_coherent_forecasts([away, goals], preferred=[home]) == [goals]


def test_duplicate_market_cards_do_not_repeat_and_full_pool_precedes_pagination():
    home = row()
    candidates = [home] + [row(fixture_id=i) for i in range(1, 23)] + [row("RESULT_AWAY"), deepcopy(home)]
    result = select_coherent_forecasts(candidates)
    assert result == candidates[:23]
    assert len(result[20:40]) == 3


def test_no_probability_price_or_model_mutation_and_no_price_based_preference():
    candidates = [row(), row("RESULT_AWAY"), row("TOTAL_OVER_2_5")]
    snapshot = deepcopy(candidates)
    expected = [item["market_key"] for item in select_coherent_forecasts(candidates)]
    assert candidates == snapshot
    for candidate in candidates:
        candidate["probability"] = object()
        candidate["observed_odds"] = object()
        candidate["evidence_stage"] = "different"
    assert [item["market_key"] for item in select_coherent_forecasts(candidates)] == expected


@pytest.mark.parametrize("opposite", ["FUTURE_MARKET", "H2H", "RESULT_AWAY"])
def test_unknown_semantics_are_allowed_as_sole_primary_not_assumed_compatible(opposite):
    unknown, other = row("UNKNOWN_LINE"), row(opposite)
    assert select_coherent_forecasts([unknown, other]) == [unknown]
    assert select_coherent_forecasts([other, unknown]) == [other]


def test_modelsignal_and_challengecandidate_duck_types_are_supported():
    first = SimpleNamespace(**row())
    second = SimpleNamespace(**row("RESULT_AWAY"))
    assert select_coherent_forecasts([first, second]) == [first]
    # ChallengeCandidate has no sport field and uses kickoff rather than scheduled_start.
    candidate = row()
    del candidate["sport"]
    candidate["kickoff"] = candidate.pop("scheduled_start")
    assert consumer_event_identity(candidate) == consumer_event_identity(first)


def test_identity_separates_sports_native_ids_and_source_namespaces():
    assert consumer_event_identity(row()) != consumer_event_identity(row(fixture_id=17))
    assert consumer_event_identity(row()) != consumer_event_identity(row(sport="Basketball"))
    first = row(fixture_id=None, fixture_source="api-a", provider_event_id="17")
    second = row(fixture_id=None, fixture_source="api-b", provider_event_id="17")
    assert consumer_event_identity(first) != consumer_event_identity(second)
    assert consumer_event_identity(row()) == consumer_event_identity(row(scheduled_start="2026-09-09T19:00:00Z"))


def test_fallback_uses_canonical_full_timestamp_and_exact_competitors():
    base = row(fixture_id=None)
    same = row(fixture_id=None, scheduled_start="2026-09-08T19:00:00Z")
    later = row(fixture_id=None, scheduled_start="2026-09-09T19:00:00Z")
    assert consumer_event_identity(base) == consumer_event_identity(same)
    assert consumer_event_identity(base) != consumer_event_identity(later)
    assert consumer_event_identity(base) != consumer_event_identity(row(fixture_id=None, away_team="Manchester United"))
    assert len(select_coherent_forecasts([base, later])) == 2


def test_display_date_or_event_label_alone_does_not_claim_a_native_identity():
    first = {"sport": "Tennis", "market_key": "H2H", "event_label": "A vs B", "scheduled_start_label": "08.09. 21:00"}
    second = dict(first, selection="other")
    assert consumer_event_identity(first).startswith("unresolved:")
    assert select_coherent_forecasts([first, second]) == [first]


def test_generic_h2h_selected_competitor_must_be_exactly_bound():
    base = row("H2H", sport="Tennis", fixture_id=None, competitor_a="Alice", competitor_b="Bob", home_team=None, away_team=None)
    a = dict(base, selected_competitor="Alice")
    b = dict(base, selected_competitor="Bob")
    invalid = dict(base, selected_competitor="Al")
    assert select_coherent_forecasts([a, b]) == [a]
    assert select_coherent_forecasts([b, a]) == [b]
    assert select_coherent_forecasts([invalid, a]) == [invalid]


def test_reversed_competitor_orientation_does_not_invert_a_market_silently():
    home = row()
    reversed_home = row(home_team="Manchester City", away_team="FC Porto")
    reversed_away = row("RESULT_AWAY", home_team="Manchester City", away_team="FC Porto")
    assert select_coherent_forecasts([home, reversed_home]) == [home]
    # Equivalent reversed-role selections are also not repeated as new cards.
    assert select_coherent_forecasts([home, reversed_away]) == [home]


@pytest.mark.parametrize("changes", [
    {"home_team": None, "away_team": None},
    {"home_team": "Unrelated Club", "away_team": "Manchester City"},
])
def test_missing_or_inconsistent_role_binding_does_not_guess_compatibility(changes):
    # Descending lexical orientation makes a missing role binding particularly
    # dangerous: canonical DC_X2 must not accidentally support a home win.
    first = row(home_team="Z Club", away_team="A Club")
    second = row("DC_X2", home_team="Z Club", away_team="A Club")
    second.update(changes)
    assert select_coherent_forecasts([first, second]) == [first]
    assert select_coherent_forecasts([second, first]) == [second]


def test_preferred_large_pool_preserves_all_original_objects_and_input_order():
    candidates = [row(fixture_id=index + 1) for index in range(5000)]
    assert select_coherent_forecasts(candidates, preferred=reversed(candidates)) == candidates


def test_native_participant_ids_not_mutable_display_names_define_market_orientation():
    first = row("HOME_OVER_1_5", home_team_id=1, away_team_id=2, home_team="Alpha", away_team="Zulu")
    renamed = row("HOME_UNDER_1_5", home_team_id=1, away_team_id=2, home_team="Zulu", away_team="Alpha")
    assert select_coherent_forecasts([first, renamed]) == [first]
    swapped_ids = row("AWAY_OVER_1_5", home_team_id=2, away_team_id=1, home_team="Alpha", away_team="Zulu")
    assert select_coherent_forecasts([first, swapped_ids]) == [first]
    compatible = row("HOME_OVER_2_5", home_team_id=1, away_team_id=2, home_team="Completely New Name", away_team="Other Name")
    assert select_coherent_forecasts([first, compatible]) == [first, compatible]


@pytest.mark.parametrize("ids", [
    {}, {"home_team_id": 3, "away_team_id": 2},
    {"home_team_id": 1, "away_team_id": None},
])
def test_partial_mixed_or_mismatched_native_participant_binding_is_not_an_extra(ids):
    first = row("HOME_OVER_1_5", home_team_id=1, away_team_id=2)
    unbound = row("HOME_OVER_2_5", **ids)
    assert select_coherent_forecasts([first, unbound]) == [first]
    assert select_coherent_forecasts([unbound, first]) == [unbound]


@pytest.mark.parametrize("spec", [s for s in MARKET_SPECS if "_OVER_" in s.key and s.key.replace("_OVER_", "_UNDER_") in {m.key for m in MARKET_SPECS}])
def test_every_configured_over_under_inverse_pair(spec):
    first = row(spec.key)
    second = row(spec.key.replace("_OVER_", "_UNDER_"))
    assert select_coherent_forecasts([first, second]) == [first]
    assert select_coherent_forecasts([second, first]) == [second]


def test_sport_aliases_share_native_football_identity():
    assert consumer_event_identity(row()) == consumer_event_identity(row(sport="football"))
    assert consumer_event_identity(row()) == consumer_event_identity(row(sport="Fussball"))


@pytest.mark.parametrize("weak_first", [False, True])
@pytest.mark.parametrize("prefer_weak", [False, True])
@pytest.mark.parametrize("identity", [{}, {"fixture_source": "event-api", "provider_event_id": "other-id"}])
def test_weaker_exact_event_alias_cannot_bypass_native_conflict_guard(weak_first, prefer_weak, identity):
    native = row()
    weak = row("RESULT_AWAY", fixture_id=None, scheduled_start="2026-09-08T19:00:00Z", **identity)
    candidates = [weak, native] if weak_first else [native, weak]
    preferred = [weak] if prefer_weak else []
    assert select_coherent_forecasts(candidates, preferred=preferred) == [native]


def test_equal_tier_distinct_native_ids_are_never_merged_even_when_names_and_time_match():
    first, second = row(), row("RESULT_AWAY", fixture_id=17)
    assert select_coherent_forecasts([first, second]) == [first, second]
    provider_a = row(fixture_id=None, fixture_source="event-api", provider_event_id="a")
    provider_b = row("RESULT_AWAY", fixture_id=None, fixture_source="event-api", provider_event_id="b")
    assert select_coherent_forecasts([provider_a, provider_b]) == [provider_a, provider_b]


def test_external_native_anchor_also_prevents_weak_alias_reappearing_in_secondary_rows():
    anchor = row()
    weak = row("RESULT_AWAY", fixture_id=None)
    assert select_coherent_forecasts([weak], preferred=[anchor]) == []


def test_participant_id_fallback_survives_label_renaming_and_does_not_reintroduce_weak_alias():
    first = row(fixture_id=None, home_team_id=1, away_team_id=2, home_team="Alpha", away_team="Zulu")
    renamed = dict(first, market_key="RESULT_AWAY", home_team="Renamed Alpha", away_team="Renamed Zulu")
    assert consumer_event_identity(first) == consumer_event_identity(renamed)
    assert select_coherent_forecasts([first, renamed]) == [first]
    weak = row("RESULT_AWAY", fixture_id=None, home_team="Alpha", away_team="Zulu")
    assert select_coherent_forecasts([weak, first], preferred=[weak]) == [first]


def test_participant_id_fallback_remains_provider_namespaced():
    first = row(fixture_id=None, home_team_id=1, away_team_id=2, fixture_source="first-api")
    second = dict(first, fixture_source="second-api")
    assert consumer_event_identity(first) != consumer_event_identity(second)


def test_legacy_full_event_label_with_canonical_timestamp_keeps_distinct_events():
    first = {"sport": "Tennis", "market_key": "H2H", "event_label": "A vs B", "scheduled_start": "2026-09-08T19:00:00Z"}
    second = dict(first, event_label="C vs D")
    assert consumer_event_identity(first) != consumer_event_identity(second)
    assert select_coherent_forecasts([first, second]) == [first, second]


def test_every_selected_domain_has_a_witness_for_many_ordered_market_pools():
    # Independent wide count grid exercises permutations and the high-count tail.
    domains = {
        "goals": [s for s in MARKET_SPECS if s.kind not in {"corner_total", "team_corners", "yellow_total", "team_yellow"}],
        "corners": [s for s in MARKET_SPECS if s.kind in {"corner_total", "team_corners"}],
        "yellow": [s for s in MARKET_SPECS if s.kind in {"yellow_total", "team_yellow"}],
    }
    by_key = {s.key: s for s in MARKET_SPECS}
    for specs in domains.values():
        for offset in range(len(specs)):
            ordered = specs[offset:] + specs[:offset]
            selected = select_coherent_forecasts([row(s.key) for s in ordered])
            assert any(all(market_outcome(by_key[r["market_key"]], h, a) for r in selected) for h in range(26) for a in range(26))
