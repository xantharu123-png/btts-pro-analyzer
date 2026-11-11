"""Owner 11.11.2026 ("Ja, Eishockey zulassen"): the ice-hockey research model may enter Doublebet.

Basketball stays out, and every other surface keeps the research gate.
"""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

import team_sport_prices as prices
from daily3_selection import DOUBLEBET_RESEARCH_SPORTS, daily3_choices
from forecast_analysis import forecast_highlight_reason
from test_sports_prematch import NOW
from test_team_sport_forecasts import _snapshot

# The fixture game starts at NOW+6h (20:00 Zurich); the nightly model is 4 h old by then.
EVENING = NOW + timedelta(hours=4)


def _research_signal(sport, side=0, *, odds=('1.90', '1.95')):
    from ev_signal_sources import ModelSignal
    from team_sport_forecasts import team_sport_forecast_rows
    row = team_sport_forecast_rows(SimpleNamespace(snapshots=(_snapshot(sport),)), now=NOW,
                                   target_date=NOW.date())[side]
    game = dict(id=81, date=row['scheduled_start'], league={'name': row['competition']}, status={'short': 'NS'},
                teams={'home': {'name': row['competitor_a']}, 'away': {'name': row['competitor_b']}})
    entries = [{'game': game, 'bookmakers': [
        {'id': index, 'name': f'Book {index}', 'bets': [{'id': 2, 'name': 'Home/Away', 'values': [
            {'value': 'Home', 'odd': odds[0]}, {'value': 'Away', 'odd': odds[1]}]}]} for index in (1, 2, 3)]}]
    quote = prices.parse_game_quotes(entries, [row], game, fetched_at=NOW + timedelta(hours=1))[row['candidate_id']]
    signal = ModelSignal(**{k: v for k, v in row.items() if k in ModelSignal.__dataclass_fields__},
                         event_label=row['event'])
    return replace(signal, reference_quote=quote.to_dict())


def test_ice_hockey_research_pick_in_the_band_enters_doublebet():
    signal = _research_signal('ice_hockey')
    choices = daily3_choices([signal], now=EVENING)
    assert [c.signal.key for c in choices] == [signal.key]
    assert choices[0].sport == 'hockey' and choices[0].offer_median_odds == pytest.approx(1.90)
    assert 'Basis:' in choices[0].basis


def test_both_sides_of_one_game_never_become_two_bets():
    pool = [_research_signal('ice_hockey', side) for side in (0, 1)]
    choices = daily3_choices(pool, now=EVENING)
    assert len(choices) == 1
    assert choices[0].signal.probability == max(s.probability for s in pool)


def test_basketball_research_model_stays_out_of_doublebet():
    assert 'basketball' not in DOUBLEBET_RESEARCH_SPORTS
    assert daily3_choices([_research_signal('basketball')], now=EVENING) == ()


def test_ice_hockey_outside_the_band_stays_out():
    assert daily3_choices([_research_signal('ice_hockey', odds=('1.50', '2.60'))], now=EVENING) == ()


def test_other_surfaces_keep_the_research_gate():
    for sport in ('ice_hockey', 'basketball'):
        signal = _research_signal(sport)
        assert forecast_highlight_reason(signal, now=EVENING) == 'Modell noch nicht unabhängig bestätigt'
        assert forecast_highlight_reason(signal, now=EVENING, check_context=False) == 'Modell noch nicht unabhängig bestätigt'


def test_admitted_research_row_keeps_only_the_daily_lifetime_of_its_match_day():
    signal = _research_signal('ice_hockey')
    admitted = dict(check_context=False, admit_research_sports=DOUBLEBET_RESEARCH_SPORTS)
    assert forecast_highlight_reason(signal, now=EVENING, **admitted) == ''
    # A model clock from the future or a match on another day gets no daily lifetime.
    assert forecast_highlight_reason(signal, now=NOW - timedelta(minutes=1), **admitted) == 'Modellstand nicht aktuell belegt'
    assert forecast_highlight_reason(signal, now=EVENING, match_day=(NOW + timedelta(days=1)).date(),
                                     **admitted) == 'Modellstand nicht aktuell belegt'
