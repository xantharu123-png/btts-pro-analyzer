from datetime import datetime, timedelta, timezone
import json

import pytest

from handball_pilot import read_report, run_pilot, scheduled_handball_pilot
from scanners.api_handball import HandballGame, HandballSourceError


NOW = datetime(2026, 11, 25, 3, tzinfo=timezone.utc)


def _game(number, starts, home=1, away=2, scores=None):
    return HandballGame(number, 39, 2026, starts, home, away, f'Team {home}',
                        f'Team {away}', 'FT' if scores else 'NS',
                        *(scores or (None, None)))


class Provider:
    def __init__(self, games):
        self.games = games
        self.game_calls = []
        self.odds_calls = []

    def bundesliga_games(self, season):
        self.game_calls.append(season)
        return list(self.games)

    def prices(self, game, *, now):
        self.odds_calls.append(game.game_id)
        return {'Book': (2., 4., 4.)}


def _history():
    return [_game(i + 1, NOW - timedelta(days=85 - i),
                  1 if i % 2 else 2, 2 if i % 2 else 1, (31 + i % 3, 29))
            for i in range(72)]


def test_pilot_freezes_predictions_caps_prices_and_pairs_only_exact_final(tmp_path):
    path = tmp_path / 'pilot.json'
    starts = NOW + timedelta(hours=8)
    upcoming = [_game(101 + index, starts + timedelta(minutes=index)) for index in range(6)]
    client = Provider(_history() + upcoming[::-1])
    report = run_pilot(client, path=path, clock=lambda: NOW)
    assert report['modelled'] == 6
    assert report['priced'] == 4
    assert report['paired'] == 0
    assert client.odds_calls == [101, 102, 103, 104]
    original = json.loads(path.read_text(encoding='utf-8'))['forecasts']['101']['p']

    run_pilot(client, path=path, clock=lambda: NOW + timedelta(hours=2))
    assert client.game_calls == [2026]
    assert len(client.odds_calls) == 4

    client.games = _history() + [
        _game(101, starts, scores=(30, 30)),
        _game(102, upcoming[1].starts_at + timedelta(minutes=30), scores=(30, 25)),
        _game(103, upcoming[2].starts_at, home=2, away=1, scores=(30, 25)),
        _game(105, upcoming[4].starts_at, scores=(24, 25)),
    ]
    report = run_pilot(client, path=path, clock=lambda: NOW + timedelta(days=1))
    assert (report['settled'], report['paired'], report['changed_fixture']) == (2, 1, 2)
    assert report['market_brier'] == pytest.approx(.875)
    assert report['model_brier'] == pytest.approx(original['home'] ** 2
                                                  + (original['draw'] - 1) ** 2
                                                  + original['away'] ** 2)
    assert read_report(path) == report


def test_no_odds_before_model_and_at_kickoff(tmp_path):
    path = tmp_path / 'pilot.json'
    game = _game(101, NOW + timedelta(minutes=1))
    client = Provider(_history() + [game])
    # This first full market arrives after the fixture has started.
    times = iter([NOW, NOW, NOW, NOW, NOW + timedelta(minutes=2)])
    report = run_pilot(client, path=path, clock=lambda: next(times))
    assert report['modelled'] == 1
    assert report['priced'] == 0

    empty_history = Provider([game])
    report = run_pilot(empty_history, path=tmp_path / 'second.json', clock=lambda: NOW)
    assert report['modelled'] == 0
    assert not empty_history.odds_calls


def test_plan_error_does_not_retry_or_make_an_empty_success(tmp_path):
    class ClosedPlan(Provider):
        def bundesliga_games(self, season):
            self.game_calls.append(season)
            raise HandballSourceError('plan_unavailable')

    provider = ClosedPlan([])
    path = tmp_path / 'pilot.json'
    report = run_pilot(provider, path=path, clock=lambda: NOW)
    assert report['status'] == 'unavailable'
    assert report['diagnostics'] == {'plan_unavailable': 1}
    assert run_pilot(provider, path=path, clock=lambda: NOW) == report
    assert provider.game_calls == [2026]


@pytest.mark.parametrize('flag,forced,canonical', [('0', False, True), ('1', True, True), ('1', False, False)])
def test_scheduled_hook_only_opted_in_canonical_nonforced(flag, forced, canonical, monkeypatch):
    import handball_pilot

    monkeypatch.setenv('BETBOY_HANDBALL_PILOT', flag)
    monkeypatch.setattr(handball_pilot, 'load_handball_api_key', lambda: pytest.fail('disabled hook read config'))
    assert scheduled_handball_pilot(canonical=canonical, forced=forced) is None


def test_pilot_uses_explicit_handball_access_and_cancels_a_slow_worker(monkeypatch):
    import subprocess

    import handball_pilot

    monkeypatch.setenv('BETBOY_HANDBALL_PILOT', '1')
    monkeypatch.setenv('API_FOOTBALL_KEY', 'config-for-another-sport')
    monkeypatch.delenv('API_HANDBALL_KEY', raising=False)
    monkeypatch.setattr(handball_pilot, 'run_pilot', lambda *a, **kw: pytest.fail('main process did a provider call'))
    assert scheduled_handball_pilot(canonical=True, forced=False) == {'status': 'missing_api_key'}

    def slow(argv, **kwargs):
        assert kwargs['timeout'] == 75
        assert 'test-handball-key' not in argv
        raise subprocess.TimeoutExpired(argv, kwargs['timeout'])

    monkeypatch.setenv('API_HANDBALL_KEY', 'test-handball-key')
    monkeypatch.setattr(handball_pilot.subprocess, 'run', slow)
    assert scheduled_handball_pilot(canonical=True, forced=False) == {'status': 'timed_out'}


def test_new_verified_final_replaces_or_retracts_only_the_result(tmp_path):
    from dataclasses import replace

    path = tmp_path / 'pilot.json'
    starts = NOW + timedelta(hours=8)
    client = Provider(_history() + [_game(101, starts)])
    run_pilot(client, path=path, clock=lambda: NOW)
    first = json.loads(path.read_text(encoding='utf-8'))['forecasts']['101']
    client.games[-1] = _game(101, starts, scores=(30, 30))
    assert run_pilot(client, path=path, clock=lambda: NOW + timedelta(days=1))['market_brier'] == .875
    client.games[-1] = _game(101, starts, scores=(31, 30))
    assert run_pilot(client, path=path, clock=lambda: NOW + timedelta(days=2))['market_brier'] == .375
    client.games[-1] = replace(client.games[-1], status='AW')
    assert run_pilot(client, path=path, clock=lambda: NOW + timedelta(days=3))['paired'] == 0
    assert json.loads(path.read_text(encoding='utf-8'))['forecasts']['101'] == first


def test_odds_transport_reads_already_frozen_model(tmp_path):
    path = tmp_path / 'pilot.json'

    class ReadWhileFetching(Provider):
        def prices(self, game, *, now):
            row = json.loads(path.read_text(encoding='utf-8'))['forecasts'][str(game.game_id)]
            assert row['p']['draw'] > 0
            assert 'odds' not in row
            return super().prices(game, now=now)

    report = run_pilot(ReadWhileFetching(_history() + [_game(101, NOW + timedelta(hours=8))]),
                       path=path, clock=lambda: NOW)
    assert report['priced'] == 1


def test_wettfinder_keeps_published_state_and_success_when_opted_in_pilot_has_error(tmp_path, monkeypatch, capsys):
    import handball_pilot
    import wettfinder_automation as automation

    path = tmp_path / 'wettfinder.json'

    def published(**kwargs):
        path.write_text('published', encoding='utf-8')
        return {'generated_at': NOW.isoformat(), 'candidates': [], 'model_candidates': [],
                'bookmaker_data_used': False, 'run_status': 'completed',
                'sources': {'football': {'status': 'completed', 'due_reason': 'scheduled',
                                         'context_status': 'completed', 'discovery_scope': 66}}}

    def failed(**kwargs):
        assert kwargs == {'canonical': True, 'forced': False}
        assert path.read_text(encoding='utf-8') == 'published'
        with automation._quote_publication_lock(path):
            pass  # the ordinary publication lock has been released
        raise OSError('provider-specific message not for output')

    monkeypatch.setenv('BETBOY_HANDBALL_PILOT', '1')
    monkeypatch.setattr(automation, 'STATE_PATH', path)
    monkeypatch.setattr(automation, 'run_wettfinder', published)
    monkeypatch.setattr(handball_pilot, 'scheduled_handball_pilot', failed)
    assert automation.main([]) == 0
    stdout = capsys.readouterr().out
    assert json.loads(stdout)['handball_pilot'] == {'status': 'unavailable', 'error_type': 'OSError'}
    assert 'provider-specific message' not in stdout
