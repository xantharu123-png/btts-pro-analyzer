"""Daily3 real-stake arithmetic in whole CHF cents, independent of odds/models.

This is accounting, not a recommendation to bet the available amount. Only an
actually confirmed return can fund a subsequent stake. It never estimates a
return from a model probability, a target profit, or a newly observed quote.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

DAILY_BUDGET_CENTS = 5000
MAX_BETS = 3
MAX_CENTS = 2**63-1
_MONEY = re.compile(r'(?:0|[1-9][0-9]{0,16})(?:[.,][0-9]{1,2})?\Z', re.ASCII)
_ODDS = re.compile(r'(?:0|[1-9][0-9]{0,16})(?:[.,][0-9]{1,12})?\Z', re.ASCII)


class Daily3Error(ValueError):
    """User-readable invalid accounting action; no new money is released."""


def cents(value: object, *, positive: bool = False) -> int:
    if type(value) is not int or not (1 if positive else 0) <= value <= MAX_CENTS:
        raise Daily3Error('Der Betrag muss in ganzen Rappen angegeben werden.')
    return value


def parse_chf(value: str, *, positive: bool = False) -> int:
    if not isinstance(value, str) or _MONEY.fullmatch(value.strip()) is None:
        raise Daily3Error('Bitte einen CHF-Betrag mit höchstens zwei Nachkommastellen eingeben.')
    amount = Decimal(value.strip().replace(',', '.'))*100
    return cents(int(amount), positive=positive)


def decimal_odds(value: str) -> str:
    if not isinstance(value, str) or _ODDS.fullmatch(value.strip()) is None:
        raise Daily3Error('Bitte die tatsächlich angenommene Dezimalquote eingeben.')
    try:
        number = Decimal(value.strip().replace(',', '.'))
    except InvalidOperation as exc:
        raise Daily3Error('Die Quote ist ungültig.') from exc
    if not number.is_finite() or number <= 1:
        raise Daily3Error('Die Dezimalquote muss größer als 1 sein.')
    return format(number, 'f').rstrip('0').rstrip('.') if '.' in format(number, 'f') else format(number, 'f')


def format_chf(value: int) -> str:
    if type(value) is not int or not -MAX_CENTS <= value <= MAX_CENTS:
        raise Daily3Error('Der gespeicherte Betrag ist ungültig.')
    sign = '−' if value < 0 else ''
    whole, remainder = divmod(abs(value), 100)
    return f'{sign}CHF {whole:,}.{remainder:02d}'.replace(',', '’')


@dataclass(frozen=True)
class Daily3Bet:
    event_id: str
    stake_cents: int
    status: str
    returned_cents: int | None = None
    under_review: bool = False

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id or len(self.event_id) > 1024:
            raise Daily3Error('Das Spiel ist nicht eindeutig zugeordnet.')
        cents(self.stake_cents, positive=True)
        if self.status not in ('reserved', 'open', 'settled', 'cancelled') or type(self.under_review) is not bool:
            raise Daily3Error('Der gespeicherte Wettstatus ist ungültig.')
        if self.status == 'settled':
            cents(self.returned_cents)
        elif self.returned_cents is not None:
            raise Daily3Error('Eine offene Wette hat noch keine bestätigte Rückzahlung.')


@dataclass(frozen=True)
class Daily3Balance:
    realised_cents: int
    open_cents: int
    reserved_cents: int
    available_cents: int
    worst_net_cents: int
    used_slots: int
    placed_count: int
    under_review: bool
    closed: bool


def balance(bets, *, closed: bool = False) -> Daily3Balance:
    if type(closed) is not bool:
        raise Daily3Error('Der Tagesstatus ist ungültig.')
    rows = tuple(bets)
    if any(type(row) is not Daily3Bet for row in rows):
        raise Daily3Error('Die gespeicherten Wetten sind ungültig.')
    realised = sum(row.returned_cents-row.stake_cents for row in rows if row.status == 'settled')
    opened = sum(row.stake_cents for row in rows if row.status == 'open')
    reserved = sum(row.stake_cents for row in rows if row.status == 'reserved')
    available = DAILY_BUDGET_CENTS+realised-opened-reserved
    worst = realised-opened-reserved
    if any(not -MAX_CENTS <= number <= MAX_CENTS for number in (realised, opened, reserved, available, worst)):
        raise Daily3Error('Die Tagesrechnung überschreitet den unterstützten Zahlenbereich.')
    placed = sum(row.status in ('open', 'settled') for row in rows)
    return Daily3Balance(realised, opened, reserved, available, worst,
                         placed+sum(row.status == 'reserved' for row in rows), placed,
                         any(row.under_review for row in rows), closed)


def reserve_allowed(bets, *, event_id: str, stake_cents: int, closed: bool = False) -> Daily3Balance:
    cents(stake_cents, positive=True)
    rows = tuple(bets)
    state = balance(rows, closed=closed)
    if state.closed:
        raise Daily3Error('Dieser Tag wurde bereits beendet.')
    if state.under_review:
        raise Daily3Error('Bitte zuerst die offene Abrechnung klären.')
    if state.used_slots >= MAX_BETS:
        raise Daily3Error('Die drei Wettslots für diesen Tag sind bereits belegt.')
    if any(row.event_id == event_id and row.status != 'cancelled' for row in rows):
        raise Daily3Error('Für dieses Spiel ist bereits eine Wette vorgemerkt oder erfasst.')
    if stake_cents > state.available_cents or state.worst_net_cents-stake_cents < -DAILY_BUDGET_CENTS:
        raise Daily3Error('Dieser Einsatz überschreitet das verfügbare Tagesbudget.')
    return balance((*rows, Daily3Bet(event_id, stake_cents, 'reserved')), closed=closed)


def has_unfinished_bets(bets) -> bool:
    rows = tuple(bets)
    balance(rows)  # Validate before using the overnight decision.
    return any(row.status in ('reserved', 'open') or row.under_review for row in rows)
