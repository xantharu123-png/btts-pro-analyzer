"""Display-only football facts must not invent form or favourable opposition."""
from copy import deepcopy
from datetime import datetime, timezone
from importlib import import_module

import pytest

from test_forecast_analysis import _basis, _row, _signal
from forecast_analysis import project_football_analysis

NOW = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)


def api():
    return import_module('football_customer_facts')


def signal(key='RESULT_AWAY'):
    row = _row(key)
    row['analysis_evidence'] = project_football_analysis(row, model_basis=_basis(row))
    return _signal(row)


def test_selected_weaker_side_has_concrete_counterargument_not_favourable_strength():
    result = api().football_customer_analysis(signal(), now=NOW)
    assert 'Außenseiter' in result.summary
    assert 'Beta' in result.summary and '1,13' in result.summary
    assert 'Alpha' in result.counterargument and '1,53' in result.counterargument
    assert '53,6 %' in result.counterargument


def test_form_sample_is_not_a_last_five_record_or_opponent_quality_claim():
    result = api().football_customer_analysis(signal('RESULT_HOME'), now=NOW)
    text = ' '.join((result.summary, result.counterargument, *result.details))
    assert ('Formbasis', '6 / 6 erfasste Spiele') in result.facts
    assert 'Sieg-/Remis-/Niederlagenbilanz nicht hinterlegt' in text
    assert all(word not in text for word in ('bessere Form', 'stärkere Gegner', 'Letzte 5', 'Letzte 10'))


def test_misbound_model_rates_are_not_displayed():
    s = signal()
    s.analysis_evidence['identity']['away_id'] = 999
    assert api().football_customer_analysis(s, now=NOW) is None


def test_double_chance_has_concrete_opposing_rate_without_claiming_away_advantage():
    result = api().football_customer_analysis(signal('DC_X2'), now=NOW)
    assert 'Heimsieg' in result.counterargument
    assert 'Alpha' in result.counterargument and 'höhere Torprognose' in result.counterargument
    assert '1,53' in result.counterargument


@pytest.mark.parametrize('key,counter', [('BTTS_YES', 'mindestens ein Team ohne Tor'),
                                       ('RESULT_DRAW', 'Heim- oder Auswärtssieg')])
def test_counterargument_remains_exact_for_the_selected_market(key, counter):
    result = api().football_customer_analysis(signal(key), now=NOW)
    assert counter in result.counterargument
    assert '53,6 %' in result.counterargument


def test_display_analysis_does_not_mutate_signal_or_evidence():
    s = signal()
    before = deepcopy(vars(s))
    api().football_customer_analysis(s, now=NOW)
    assert vars(s) == before


def test_future_model_does_not_display_bound_rates():
    assert api().football_customer_analysis(signal(), now=datetime(2029, 1, 1, tzinfo=timezone.utc)) is None
