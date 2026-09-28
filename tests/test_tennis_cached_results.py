import csv
import os
from copy import deepcopy
from datetime import timedelta

from test_daily3_selection import NOW, tennis


def cache(tmp_path):
    def write(name, rows):
        path = tmp_path / name
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        os.utime(path, (NOW.timestamp()-60, NOW.timestamp()-60))
        return path
    tournaments = [dict(id=str(i), surface='Clay', start_dtm=(NOW-timedelta(days=i*12)).strftime('%Y%m%d')) for i in range(1, 13)]
    write('atp_tournaments.csv', tournaments)
    rows = [dict(id=str(i), tournament_id=str(i), stadie_id='R32', match_ret='',
                 winner_name='Spieler A' if i % 3 else 'Gegner G',
                 loser_name='Gegner G' if i % 3 else 'Spieler A',
                 winner_sets_won='2', loser_sets_won='0') for i in range(1, 13)]
    write('atp_matches_2029.csv', rows)
    return rows, write


def test_cache_projects_real_five_ten_windows_without_fetch_or_model_mutation(tmp_path, monkeypatch):
    from tennis.cached_results import cached_match_statistics
    from tennis.customer_facts import customer_record_facts, customer_record_details
    import requests
    cache(tmp_path)
    monkeypatch.setattr(requests, 'get', lambda *a, **k: (_ for _ in ()).throw(AssertionError('no fetch')))
    context = deepcopy(tennis().context_evidence)
    context['match_statistics'] = cached_match_statistics('Spieler A', 'Spieler B',
        surface='Clay', tour='ATP', as_of=NOW, cache_dir=tmp_path)
    facts = customer_record_facts(context, 'Spieler A', 'Spieler B', modeled_at=NOW)
    assert facts[0][1] == '4/5 · 7/10 Siege'
    details = customer_record_details(context, 'Spieler A', 'Spieler B', modeled_at=NOW)
    assert len(details['Spieler A']) == 10
    assert 'Gegner G' in details['Spieler A'][0] and 'Turnierdatum' in details['Spieler A'][0]
    assert 'Rang' not in ' '.join(details['Spieler A'])


def test_cache_modified_after_forecast_cannot_rewrite_old_form(tmp_path):
    from tennis.cached_results import cached_match_statistics
    cache(tmp_path)
    path = tmp_path/'atp_matches_2029.csv'
    os.utime(path, (NOW.timestamp()+1, NOW.timestamp()+1))
    assert cached_match_statistics('Spieler A', 'Spieler B', surface='Clay',
        tour='ATP', as_of=NOW, cache_dir=tmp_path) is None


def test_same_tournament_rounds_are_ordered_by_actual_stage_not_input_order(tmp_path):
    from tennis.cached_results import cached_match_statistics
    rows, write = cache(tmp_path)
    rows = [dict(rows[0], id='r1', stadie_id='R32'),
            dict(rows[0], id='r2', stadie_id='QF', winner_name='Gegner G', loser_name='Spieler A')]
    write('atp_matches_2029.csv', rows)
    stats = cached_match_statistics('Spieler A', 'Spieler B', surface='Clay',
        tour='ATP', as_of=NOW, cache_dir=tmp_path)
    assert [item['won'] for item in stats['players']['a']['surface_results']] == [False, True]


def test_conflicting_duplicate_and_retirement_cannot_count_as_wins(tmp_path):
    from tennis.cached_results import cached_match_statistics
    rows, write = cache(tmp_path)
    write('atp_matches_2029.csv', [rows[0], dict(rows[0], winner_name='Gegner G', loser_name='Spieler A'),
        dict(rows[1], match_ret='RET'), dict(rows[2], stadie_id='unknown')])
    assert cached_match_statistics('Spieler A', 'Spieler B', surface='Clay',
        tour='ATP', as_of=NOW, cache_dir=tmp_path) is None


def test_event_copied_between_season_files_is_counted_once(tmp_path):
    from tennis.cached_results import cached_match_statistics
    rows, write = cache(tmp_path)
    write('atp_matches_2030.csv', rows[:1])
    stats = cached_match_statistics('Spieler A', 'Spieler B', surface='Clay',
        tour='ATP', as_of=NOW, cache_dir=tmp_path)
    dates = [row['date'] for row in stats['players']['a']['surface_results']]
    assert len(dates) == len(set(dates)) == 10


def test_disputed_tournament_identity_does_not_pick_last_metadata_row(tmp_path):
    from tennis.cached_results import cached_match_statistics
    rows, write = cache(tmp_path)
    write('atp_tournaments.csv', [dict(id='1', surface='Clay', start_dtm='20291220'),
                                  dict(id='1', surface='Clay', start_dtm='20291219')])
    write('atp_matches_2029.csv', rows[:1])
    assert cached_match_statistics('Spieler A', 'Spieler B', surface='Clay',
        tour='ATP', as_of=NOW, cache_dir=tmp_path) is None


def test_malformed_optional_statistics_do_not_break_details():
    from tennis.customer_facts import customer_record_details
    for malformed in ('broken', None, [], {'players': 'broken'}):
        context = deepcopy(tennis().context_evidence)
        context['match_statistics'] = malformed
        assert customer_record_details(context, 'Spieler A', 'Spieler B', modeled_at=NOW) == {}
