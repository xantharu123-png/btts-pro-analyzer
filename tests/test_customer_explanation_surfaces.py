from types import SimpleNamespace

from forecast_analysis import build_forecast_analysis
from forecast_compact import build_compact_analysis


def test_team_adapter_freezes_recent_results_in_existing_display_factors():
    from test_team_sport_forecasts import _snapshot, _signal_and_input, NOW
    from team_sport_forecasts import team_sport_forecast_rows
    from ev_signal_sources import ModelSignal
    snapshot = _snapshot()
    factors = [factor for factor in snapshot.factors if factor.factor_key.startswith('customer_recent_')]
    assert len(factors) == 2
    assert any('/5' in factor.summary and '/10' in factor.summary for factor in factors)
    row = team_sport_forecast_rows(SimpleNamespace(snapshots=(snapshot,)), now=NOW, target_date=NOW.date())[0]
    signal = ModelSignal(**{key: value for key, value in row.items() if key in ModelSignal.__dataclass_fields__}, event_label=row['event'])
    card = build_compact_analysis(signal, build_forecast_analysis(signal, now=NOW), now=NOW)
    assert any(fact.label == 'Letzte Spiele' for fact in card.facts)


def test_football_counterargument_is_reachable_from_the_compact_card():
    from test_football_customer_facts import signal, NOW
    s = signal('DC_X2')
    card = build_compact_analysis(s, build_forecast_analysis(s, now=NOW), now=NOW)
    detail = next(fact for fact in card.facts if fact.label == 'Gegenargument')
    assert 'Alpha' in detail.details[0] and 'höhere Torprognose' in detail.details[0]


def test_esport_customer_reason_does_not_expose_internal_rating_points():
    from test_team_customer_facts import TeamCustomerFactsTests
    from team_customer_facts import team_customer_explanation
    signal = TeamCustomerFactsTests().esports_signal()
    reason = ' '.join(team_customer_explanation(signal)['reasons'])
    assert signal.selected_competitor in reason
    assert 'Elo' not in reason and '100' not in reason


def test_old_riskobet_esport_details_hide_internal_rating_numbers():
    from riskobet_surface import format_riskobet_public_detail
    for text in ('Subgraph-Elo 1600/1500, Best-of-3.',
                 'Spielstärke-Abstand: 100 Elo-Punkte; Best-of-3.'):
        public = format_riskobet_public_detail(text)
        assert 'Best-of-3' in public
        assert 'Elo' not in public and '1600' not in public and '100' not in public
