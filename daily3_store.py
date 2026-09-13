"""Separate Daily3 bookkeeping for manually confirmed real bookmaker bets.

Whole-cent arithmetic, one SQLite write transaction per command, idempotent
requests and an authenticated event history. This does not place bets or verify
what a bookmaker actually paid. Restoring an entire old DB together with its
head is not detectable without an external checkpoint.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

from daily3_math import (Daily3Bet, Daily3Error, balance, cents, decimal_odds,
                         has_unfinished_bets, reserve_allowed)
from daily3_identity import events_overlap, validate_guard

_ID = re.compile(r'[a-f0-9]{32}\Z', re.ASCII)
_ZERO = '0'*64
_TZ = ZoneInfo('Europe/Zurich')
_DOMAIN = b'betboy-daily3-v1\0'


class Daily3IntegrityError(Daily3Error):
    pass


def _require(condition, message):
    if not condition:
        raise Daily3Error(message)


def _text(value, maximum=500):
    _require(type(value) is str and bool(value.strip()) and len(value) <= maximum
             and not any(ord(char) < 32 for char in value), 'Eine gültige Bezeichnung oder Belegangabe fehlt.')
    return value


def _identity(value):
    _require(type(value) is str and _ID.fullmatch(value) is not None, 'Die dauerhafte Zuordnung fehlt.')
    return value


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _timestamp(value):
    _require(isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None,
             'Die Serverzeit ist nicht eindeutig.')
    return value.astimezone(timezone.utc)


def _day(value):
    _require(type(value) is str and date.fromisoformat(value).isoformat() == value, 'Das Tagesdatum ist ungültig.')
    return value


def _rows(day):
    return [Daily3Bet(b['event_id'], b['stake_cents'], b['status'], b['returned_cents'], b['under_review'])
            for b in day['bets'].values()]


def day_balance(day):
    return balance(_rows(day), closed=day['closed'])


def _snapshot(value, *, external=False):
    fields = {'event_id', 'event_guard', 'sport', 'event_label', 'market_key', 'market', 'selection',
              'scheduled_start', 'signal_key', 'model_probability', 'modeled_at',
              'model_version', 'analysis_basis', 'analysis_caution', 'policy_version'}
    _require(type(value) is dict and set(value) == fields, 'Der unveränderliche Auswahlstand fehlt.')
    unmodeled = external and value.get('model_probability') is None
    optional = {'modeled_at', 'model_version'} if unmodeled else set()
    for name in fields-{'model_probability', 'event_guard'}-optional:
        _text(value[name], 1500 if name.startswith('analysis_') else 1024)
    _require(value['sport'] in ('football', 'tennis', 'basketball', 'hockey', 'esports'), 'Diese Sportart gehört nicht zu Daily3.')
    _require(not value['event_id'].startswith('unresolved:'), 'Das Spiel ist nicht eindeutig zugeordnet.')
    validate_guard(value['event_guard'], value['event_id'])
    probability = value['model_probability']
    _require(unmodeled or type(probability) in (int, float) and 0 < probability < 1, 'Die Modellwahrscheinlichkeit ist ungültig.')
    if unmodeled:
        _require(value['modeled_at'] is None and value['model_version'] is None
                 and value['policy_version'] == 'external-bookmaker-record-v1', 'Eine externe Wette darf keinen erfundenen Modellstand enthalten.')
    for name in ('scheduled_start',) if unmodeled else ('scheduled_start', 'modeled_at'):
        _timestamp(datetime.fromisoformat(value[name]))
    return deepcopy(value)


def _apply(days, payload):
    _require(type(payload) is dict and set(payload) == {'version', 'kind', 'at', 'day', 'args'}
             and type(payload['version']) is int and payload['version'] == 1, 'Der Buchungsvertrag ist ungültig.')
    at = _timestamp(datetime.fromisoformat(payload['at']))
    current_date = at.astimezone(_TZ).date().isoformat()
    day_id, kind, args = _day(payload['day']), payload['kind'], payload['args']
    _require(type(args) is dict, 'Die Buchung ist ungültig.')
    shapes = {'start': set(), 'close': set(),
              'reserve': {'bet_id', 'snapshot', 'stake_cents', 'odds'},
              'external': {'bet_id', 'snapshot', 'stake_cents', 'odds', 'reference', 'reason'},
              'place': {'bet_id', 'revision', 'reference'},
              'cancel': {'bet_id', 'revision', 'not_placed'},
              'settle': {'bet_id', 'revision', 'returned_cents', 'reference'},
              'review': {'bet_id', 'revision', 'reason'},
              'correct': {'bet_id', 'revision', 'returned_cents', 'reference', 'reason'}}
    _require(kind in shapes and set(args) == shapes[kind], 'Die Buchungsfelder sind ungültig.')
    if kind == 'start':
        _require(day_id == current_date and day_id not in days, 'Dieser Tag wurde bereits begonnen oder ist nicht heute.')
        _require(not days or day_id > max(days), 'Ein vergangener Tag kann nicht neu gestartet werden.')
        _require(not any(has_unfinished_bets(_rows(d)) for d in days.values()),
                 'Bitte zuerst die offenen Wetten, Vormerkungen oder Abrechnungen des Vortags klären.')
        days[day_id] = dict(date=day_id, started_at=payload['at'], closed=False, bets={})
        return
    _require(day_id in days, 'Bitte das Tagesbudget zuerst bestätigen.')
    day = days[day_id]
    if kind == 'close':
        _require(not day['closed'], 'Dieser Tag wurde bereits beendet.')
        day['closed'] = True
        return
    if kind in ('reserve', 'external'):
        bet_id = _identity(args['bet_id'])
        _require(bet_id not in day['bets'], 'Diese Wette wurde bereits erfasst.')
        snap = _snapshot(args['snapshot'], external=kind == 'external')
        stake = cents(args['stake_cents'], positive=True)
        odds = decimal_odds(args['odds'])
        _require(odds == args['odds'], 'Die gespeicherte Quote ist nicht kanonisch.')
        if kind == 'reserve':
            _require(day_id == current_date, 'Neue Einsätze gehören zum heutigen Tag.')
            _require(not any(has_unfinished_bets(_rows(d)) for other, d in days.items() if other != day_id),
                     'Bitte zuerst die offenen Wetten oder Vormerkungen des Vortags klären.')
            _require(not any(b['under_review'] for d in days.values() for b in d['bets'].values()),
                     'Bitte zuerst die offene Abrechnung klären.')
            _require(not any(b['status'] != 'cancelled' and events_overlap(snap['event_guard'], b['snapshot']['event_guard'])
                             for b in day['bets'].values()),
                     'Für dieses Spiel oder eine nicht eindeutig getrennte Spielzuordnung ist bereits eine Wette erfasst.')
            start = _timestamp(datetime.fromisoformat(snap['scheduled_start']))
            _require(start > at and start.astimezone(_TZ).date().isoformat() == day_id,
                     'Neue Vormerkungen sind nur vor Spielbeginn und für heute möglich.')
            reserve_allowed(_rows(day), event_id=snap['event_id'], stake_cents=stake, closed=day['closed'])
        else:
            # Records an already existing outside-limit liability, never grants
            # permission or creates a balancing credit to disguise that breach.
            _text(args['reference']); _text(args['reason'])
        day['bets'][bet_id] = dict(id=bet_id, event_id=snap['event_id'], snapshot=snap,
            stake_cents=stake, odds=odds, status='reserved' if kind == 'reserve' else 'open',
            returned_cents=None, under_review=False, revision=1, created_at=payload['at'],
            placed_at=None if kind == 'reserve' else payload['at'],
            reference=args.get('reference'), external_deviation=kind == 'external',
            last_reason=args.get('reason'), settled_at=None)
        day_balance(day)
        return
    bet_id = _identity(args['bet_id'])
    _require(bet_id in day['bets'], 'Diese Wette gehört nicht zu diesem Tageslauf.')
    bet = day['bets'][bet_id]
    _require(type(args['revision']) is int and args['revision'] == bet['revision'],
             'Diese Ansicht ist veraltet. Bitte neu laden und den aktuellen Stand prüfen.')
    if kind == 'place':
        _require(bet['status'] == 'reserved', 'Nur eine offene Vormerkung kann als platziert bestätigt werden.')
        _text(args['reference'])
        bet.update(status='open', placed_at=payload['at'], reference=args['reference'])
    elif kind == 'cancel':
        _require(bet['status'] == 'reserved' and args['not_placed'] is True,
                 'Nur ausdrücklich nicht platzierte Vormerkungen können freigegeben werden.')
        bet['status'] = 'cancelled'
    elif kind == 'review':
        _require(bet['status'] in ('open', 'settled') and not bet['under_review'], 'Diese Abrechnung kann nicht erneut geöffnet werden.')
        bet.update(under_review=True, last_reason=_text(args['reason']))
    elif kind in ('settle', 'correct'):
        expected = 'open' if kind == 'settle' else 'settled'
        _require(bet['status'] == expected, 'Der aktuelle Wettstatus erlaubt diese Abrechnung nicht.')
        cents(args['returned_cents']); _text(args['reference'])
        if kind == 'correct':
            bet['last_reason'] = _text(args['reason'])
        bet.update(status='settled', returned_cents=args['returned_cents'], under_review=False,
                   reference=args['reference'], settled_at=payload['at'])
    bet['revision'] += 1
    day_balance(day)


class Daily3Store:
    def __init__(self, path, *, key=None, clock=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _require(not self.path.is_symlink(), 'Der Speicherpfad ist ungültig.')
        if key is None:
            # Reuse the existing ledger key/configuration. No new production
            # service, secret, or migration of any Challenge data is introduced.
            from challenge_store import _load_ledger_hmac_key, DEFAULT_CHALLENGE_DB
            key, _ = _load_ledger_hmac_key(DEFAULT_CHALLENGE_DB.parent/'challenge_sessions'/'shared-ledger.db')
        _require(type(key) is bytes and len(key) == 32, 'Der vorhandene Integritätsschlüssel ist nicht verfügbar.')
        self.key = key
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        with self._connection() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS daily3_events (
                    scope TEXT NOT NULL, sequence INTEGER NOT NULL, action_id TEXT NOT NULL,
                    payload TEXT NOT NULL, previous_mac TEXT NOT NULL, mac TEXT NOT NULL,
                    PRIMARY KEY(scope, sequence), UNIQUE(scope, action_id)
                ) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS daily3_heads (
                    scope TEXT PRIMARY KEY NOT NULL, sequence INTEGER NOT NULL,
                    tail TEXT NOT NULL, mac TEXT NOT NULL
                ) WITHOUT ROWID;
            ''')

    @contextmanager
    def _connection(self):
        con = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        try:
            con.execute('PRAGMA synchronous=FULL')
            con.execute('PRAGMA busy_timeout=15000')
            con.row_factory = sqlite3.Row
            yield con
        finally:
            con.close()

    def _mac(self, kind, values):
        return hmac.new(self.key, _DOMAIN+kind.encode('ascii')+b'\0'+_canonical(values).encode('ascii'), hashlib.sha256).hexdigest()

    def _read(self, con, scope):
        _identity(scope)
        head = con.execute('SELECT * FROM daily3_heads WHERE scope=?', (scope,)).fetchone()
        rows = con.execute('SELECT * FROM daily3_events WHERE scope=? ORDER BY sequence', (scope,)).fetchall()
        days, actions, previous, previous_at = {}, {}, _ZERO, None
        try:
            _require((head is None) == (not rows), 'Kopf und Historie passen nicht zusammen.')
            if head is not None:
                _require(type(head['sequence']) is int and head['sequence'] == len(rows)
                         and type(head['mac']) is str
                         and hmac.compare_digest(head['mac'], self._mac('head', [scope, len(rows), head['tail']])),
                         'Der aktuelle Kontoprüfstand ist ungültig.')
            for index, row in enumerate(rows, 1):
                _require(type(row['sequence']) is int and row['sequence'] == index and row['previous_mac'] == previous,
                         'Die Buchungshistorie ist unvollständig.')
                action_id = _identity(row['action_id'])
                _require(type(row['payload']) is str and len(row['payload']) <= 16384, 'Die gespeicherte Buchung ist ungültig.')
                payload = json.loads(row['payload'])
                _require(_canonical(payload) == row['payload'], 'Die gespeicherte Buchung wurde verändert.')
                expected = self._mac('event', [scope, index, action_id, row['payload'], previous])
                _require(type(row['mac']) is str and hmac.compare_digest(row['mac'], expected), 'Die Buchung wurde verändert.')
                at = _timestamp(datetime.fromisoformat(payload['at']))
                _require(previous_at is None or at >= previous_at, 'Die Buchungsreihenfolge wurde verändert.')
                _apply(days, payload)
                actions[action_id] = payload
                previous, previous_at = row['mac'], at
            _require(head is None or head['tail'] == previous, 'Das Ende der Buchungshistorie fehlt.')
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise Daily3IntegrityError('Die Tagesaufzeichnungen konnten nicht verlässlich geprüft werden. Keine neue Budgetfreigabe.') from exc
        return days, actions, previous, previous_at

    def history(self, scope):
        with self._connection() as con:
            con.execute('BEGIN')
            return deepcopy(self._read(con, scope)[0])

    def command(self, scope, *, action_id, kind, day, **args):
        _identity(scope); _identity(action_id)
        # No client clock, session balance, quote calculation, or model output
        # can credit this ledger. Caller supplies the actual recorded facts.
        now = _timestamp(self.clock())
        payload = dict(version=1, kind=kind, at=now.isoformat(), day=day, args=deepcopy(args))
        with self._connection() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                days, actions, previous, previous_at = self._read(con, scope)
                existing = actions.get(action_id)
                if existing is not None:
                    _require(all(existing[k] == payload[k] for k in ('version', 'kind', 'day', 'args')),
                             'Diese Bestätigung wurde bereits mit anderen Angaben verarbeitet.')
                    con.execute('COMMIT')
                    return deepcopy(days)
                _require(previous_at is None or now >= previous_at, 'Die Serverzeit liegt vor der letzten Buchung.')
                _apply(days, payload)
                raw = _canonical(payload)
                _require(len(raw) <= 16384, 'Die Buchung ist zu groß.')
                sequence = len(actions)+1
                mac = self._mac('event', [scope, sequence, action_id, raw, previous])
                con.execute('INSERT INTO daily3_events VALUES (?,?,?,?,?,?)', (scope, sequence, action_id, raw, previous, mac))
                con.execute('INSERT INTO daily3_heads VALUES (?,?,?,?) ON CONFLICT(scope) DO UPDATE SET sequence=excluded.sequence, tail=excluded.tail, mac=excluded.mac',
                            (scope, sequence, mac, self._mac('head', [scope, sequence, mac])))
                con.execute('COMMIT')
                return deepcopy(days)
            except BaseException:
                if con.in_transaction:
                    con.execute('ROLLBACK')
                raise

    def backup(self, destination):
        """SQLite-consistent backup. The existing HMAC key is backed up separately."""
        destination = Path(destination)
        _require(not destination.exists(), 'Die Sicherungsdatei existiert bereits.')
        with self._connection() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
