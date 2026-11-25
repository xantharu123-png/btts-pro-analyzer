"""Handball availability must come from the same current, bound source."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from handball_pilot import run_europe
from scanners.api_handball import HANDBALL_LEAGUES, HandballGame, HandballMarket, HandballSourceError


NOW = datetime(2026, 11, 25, 7, tzinfo=timezone.utc)
LEAGUE_IDS = {'ES': 103, 'DE': 39, 'DK': 23, 'FR': 34, 'HU': 49}


class Feed:
    def __init__(self):
        self.price = (1.20, 7.0, 2.0)
        self.price_time = NOW - timedelta(minutes=10)
        self.fail_odds = False
        self.show_odds = True
        self.reschedule = False
        self.kickoff = NOW + timedelta(hours=31)

    def league_games(self, profile, season):
        league_id = LEAGUE_IDS[profile.code]
        game = HandballGame(100, league_id, season, self.kickoff, 1, 2,
                            f'Home {profile.code}', f'Away {profile.code}', 'NS', None, None)
        if self.reschedule:
            game = replace(game, starts_at=self.kickoff + timedelta(hours=1))
        history = [
            replace(game, game_id=i+1, starts_at=NOW-timedelta(days=81-i),
                    home_id=1+(i%2), away_id=2-(i%2), status='FT', home_score=33, away_score=23)
            for i in range(64)
        ]
        return history + [game]

    def league_prices(self, profile, season, *, now):
        if self.fail_odds:
            raise HandballSourceError('api_http_error')
        if not self.show_odds:
            return {}
        return {100: HandballMarket(self.price_time, {'Book': self.price})}


def test_current_handball_1x2_receipt_publishes_all_five_in_one_existing_pass(tmp_path, monkeypatch):
    monkeypatch.setenv('BETBOY_HANDBALL_PILOT', '1')
    run_europe(Feed(), directory=tmp_path, clock=lambda: NOW)
    data = json.loads((tmp_path/'handball_pilot_2026.json').read_text(encoding='utf-8'))
    assert data['version'] == 3, 'Private v2 observations are not a public receipt'
    from handball_publication import read_handball_selections

    picks = read_handball_selections(now=NOW, directory=tmp_path)
    assert len(picks) == 5
    assert len({pick.event_id for pick in picks}) == 5
    assert {pick.league for pick in picks} == {profile.name for profile in HANDBALL_LEAGUES}
    assert {pick.home for pick in picks} == {'Home '+code for code in LEAGUE_IDS}
    assert all(pick.side == 'home' and .7 < pick.probability < 1 for pick in picks)
    assert picks[0].expires_at == NOW + timedelta(hours=31)


@pytest.mark.parametrize('case', ['price_missing', 'old', 'too_low', 'wrong_game'])
def test_no_display_without_new_exact_current_eligible_market(tmp_path, monkeypatch, case):
    monkeypatch.setenv('BETBOY_HANDBALL_PILOT', '1')
    from handball_publication import read_handball_selections

    feed = Feed()
    run_europe(feed, directory=tmp_path, clock=lambda: NOW)
    assert len(read_handball_selections(now=NOW, directory=tmp_path)) == 5
    nxt = NOW + timedelta(days=1)
    feed.price_time = nxt - timedelta(minutes=10)
    if case == 'price_missing':
        feed.show_odds = False
    if case == 'old':
        feed.price_time = nxt - timedelta(hours=37)
    if case == 'too_low':
        feed.price = (1.19, 2.7, 2.1)  # no replacement with the next-best side
    if case == 'wrong_game':
        feed.reschedule = True     # the frozen estimate is tied to the original start
    run_europe(feed, directory=tmp_path, clock=lambda: nxt)
    assert read_handball_selections(now=nxt, directory=tmp_path) == ()
    data = json.loads((tmp_path/'handball_pilot_2026.json').read_text(encoding='utf-8'))
    assert data['forecasts']['100']['odds'] == {'Book': [1.20, 7.0, 2.0]}


def test_handball_reader_fail_closed_per_file_and_at_kickoff(tmp_path, monkeypatch):
    from handball_publication import read_handball_selections

    assert read_handball_selections(now=NOW, directory=tmp_path/'does-not-exist') == ()
    assert not (tmp_path/'does-not-exist').exists()
    monkeypatch.setenv('BETBOY_HANDBALL_PILOT', '1')
    feed = Feed()
    run_europe(feed, directory=tmp_path, clock=lambda: NOW)
    germany = tmp_path/'handball_pilot_2026.json'
    older = json.loads(germany.read_text(encoding='utf-8'))
    older.update(version=2)
    germany.write_text(json.dumps(older), encoding='utf-8')
    (tmp_path/'handball_pilot_dk_2026.json').write_text('{truncated', encoding='utf-8')
    picks = read_handball_selections(now=NOW, directory=tmp_path)
    assert {pick.home for pick in picks} == {'Home ES', 'Home FR', 'Home HU'}
    assert read_handball_selections(now=feed.kickoff, directory=tmp_path) == ()
    monkeypatch.delenv('BETBOY_HANDBALL_PILOT')
    assert read_handball_selections(now=NOW, directory=tmp_path) == ()


def test_broken_price_or_noncanonical_key_cannot_crash_or_duplicate_games(tmp_path, monkeypatch):
    monkeypatch.setenv('BETBOY_HANDBALL_PILOT', '1')
    from handball_publication import read_handball_selections

    run_europe(Feed(), directory=tmp_path, clock=lambda: NOW)
    germany = tmp_path/'handball_pilot_2026.json'
    data = json.loads(germany.read_text(encoding='utf-8'))
    rows = data['publication']['rows']
    rows['0100'] = {**rows['100']}
    data['forecasts']['0100'] = {**data['forecasts']['100']}
    germany.write_text(json.dumps(data), encoding='utf-8')
    assert sum(pick.home == 'Home DE' for pick in read_handball_selections(now=NOW, directory=tmp_path)) == 1
    rows['100']['median'] = 10**400
    germany.write_text(json.dumps(data), encoding='utf-8')
    picks = read_handball_selections(now=NOW, directory=tmp_path)
    assert {pick.home for pick in picks} == {'Home ES', 'Home DK', 'Home FR', 'Home HU'}
