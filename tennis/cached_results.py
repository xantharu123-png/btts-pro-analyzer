"""Read-only customer results from already downloaded training tables.

No loader/download call, no model replay and no database writes. Tournament
dates remain tournament dates, never fabricated exact match timestamps.
"""
import csv
import hashlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from io import BytesIO, StringIO
from pathlib import Path

from .data_loader import DEFAULT_CACHE_DIR, normalize_player_name, resolve_player_name_key
from .workload import _instant

_ROUND = {value: index for index, value in enumerate(
    ('Q1', 'Q2', 'Q3', 'R128', 'R64', 'R32', 'R16', 'QF', 'SF', 'F'))}
_WTA_ROUND = {'1st Round': 'R128', '2nd Round': 'R64', '3rd Round': 'R32',
              '4th Round': 'R16', 'Quarterfinals': 'QF', 'Semifinals': 'SF', 'The Final': 'F'}


def _fingerprint(path):
    stat = path.stat()
    if path.is_symlink() or not path.is_file() or not 0 < stat.st_size <= 40_000_000:
        raise ValueError('unusable statistics file')
    return str(path), stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=2)
def _read_tables(tour, fingerprints):
    tables, digest = {}, hashlib.sha256()
    for fingerprint in fingerprints:
        path = Path(fingerprint[0])
        payload = path.read_bytes()
        if _fingerprint(path) != fingerprint:
            raise ValueError('statistics changed while reading')
        digest.update(path.name.encode()+b'\0'+payload)
        if path.suffix == '.csv':
            tables[path.name] = list(csv.DictReader(StringIO(payload.decode('utf-8-sig'))))
        else:
            import pandas as pd
            try:
                tables[path.name] = pd.read_excel(BytesIO(payload)).fillna('').to_dict('records')
            except Exception as exc:
                raise ValueError('unusable cached result table') from exc
    metadata, disputed = {}, set()
    for row in tables.get('atp_tournaments.csv', []):
        identity = str(row.get('id', ''))
        if identity in metadata and metadata[identity] != row:
            disputed.add(identity)
        metadata[identity] = row
    for identity in disputed:
        metadata.pop(identity, None)
    records, conflicts = {}, set()
    for filename, rows in tables.items():
        if filename == 'atp_tournaments.csv':
            continue
        for row in rows:
            try:
                if tour == 'ATP':
                    tournament = metadata[str(row['tournament_id'])]
                    date = datetime.strptime(str(tournament['start_dtm']), '%Y%m%d').date()
                    surface, stage = tournament['surface'], str(row['stadie_id'])
                    if str(row.get('match_ret', '')).strip() not in ('', '0', '0.0'):
                        continue
                    winner, loser = str(row['winner_name']).strip(), str(row['loser_name']).strip()
                    sets = int(row['winner_sets_won']), int(row['loser_sets_won'])
                    identity = str(row['id'])
                    ranks, date_kind = (None, None), 'tournament_date'
                    competition = str(row['tournament_id'])
                else:
                    date = datetime.fromisoformat(str(row['Date'])).date()
                    surface, stage = row['Surface'], _WTA_ROUND.get(str(row.get('Round')), '')
                    if str(row.get('Comment', '')).casefold() != 'completed':
                        continue
                    winner, loser = str(row['Winner']).strip(), str(row['Loser']).strip()
                    sets = int(row['Wsets']), int(row['Lsets'])
                    competition = str(row.get('Tournament', ''))
                    identity = date, competition, stage, tuple(sorted((winner, loser)))
                    rank = lambda value: int(value) if str(value).replace('.0', '').isdigit() and 1 <= float(value) <= 3000 else None
                    ranks, date_kind = (rank(row.get('WRank')), rank(row.get('LRank'))), 'result_date'
                if stage not in _ROUND or not winner or not loser or winner == loser or sets[0] not in (2, 3) or not 0 <= sets[1] < sets[0]:
                    continue
                record = (date, _ROUND[stage], competition, winner, loser, surface, sets, ranks, date_kind)
                if identity in records and records[identity] != record:
                    conflicts.add(identity)
                records[identity] = record
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
    return tuple(record for identity, record in records.items() if identity not in conflicts), digest.hexdigest()


@lru_cache(maxsize=4)
def _player_results(tour, fingerprints, cutoff_day):
    """Index one immutable cached day once, not once per card or detail field."""
    records, source_hash = _read_tables(tour, fingerprints)
    records = sorted((record for record in records if cutoff_day-timedelta(days=365) <= record[0] < cutoff_day),
                     key=lambda record: record[:3], reverse=True)
    players = {}
    for record in records:
        seen = set()
        for index, name in enumerate(record[3:5]):
            key = normalize_player_name(name)
            if key in seen:
                continue
            seen.add(key)
            players.setdefault(key, []).append((record, index == 0))
    return {key: tuple(rows) for key, rows in players.items()}, source_hash


def cached_match_statistics(player_a, player_b, *, surface, tour, as_of, cache_dir=DEFAULT_CACHE_DIR):
    cutoff = _instant(as_of)
    if cutoff is None or tour not in ('ATP', 'WTA'):
        return None
    root = Path(cache_dir)
    names = (['atp_tournaments.csv'] if tour == 'ATP' else []) + [
        f'atp_matches_{year}.csv' if tour == 'ATP' else f'wta_odds_{year}.xlsx'
        for year in (cutoff.year-1, cutoff.year)]
    try:
        fingerprints = tuple(_fingerprint(root/name) for name in names if (root/name).is_file())
        if not fingerprints or tour == 'ATP' and fingerprints[0][0] != str(root/'atp_tournaments.csv'):
            return None
        if any(stamp/1e9 > cutoff.timestamp() for _, stamp, _ in fingerprints):
            return None
        roster, source_hash = _player_results(tour, fingerprints, cutoff.date())
    except (OSError, ValueError, ImportError):
        return None
    keys = [resolve_player_name_key(name, roster) for name in (player_a, player_b)]
    if not all(keys) or keys[0] == keys[1]:
        return None
    players = {}
    for side, name, key in zip(('a', 'b'), (player_a, player_b), keys):
        results = []
        for (date, _, _, winner, loser, played_surface, sets, ranks, date_kind), won in roster.get(key, ()):
            if played_surface != surface:
                continue
            results.append(dict(date=date.isoformat(), date_kind=date_kind, won=won,
                opponent=loser if won else winner, score=f'{sets[0]}:{sets[1]}' if won else f'{sets[1]}:{sets[0]}',
                opponent_rank=ranks[1 if won else 0]))
            if len(results) == 10:
                break
        entry = {'player': name, 'surface_results': results}
        if results:
            entry['surface'] = dict(matches=len(results), wins=sum(row['won'] for row in results),
                                    **{'from': results[-1]['date'], 'through': results[0]['date']})
        players[side] = entry
    if not any(entry['surface_results'] for entry in players.values()):
        return None
    return dict(schema='tennis-customer-results-v2', observed_at=cutoff.isoformat(), surface=surface,
                tour=tour, source_hash=source_hash, coverage='completed_knockout_rounds', players=players)
