"""Daily3 day planning is a policy, never proof of a bookmaker credit time."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import uuid

import pytest

from daily3_math import Daily3Error
from daily3_schedule import fits_daily3_window, pending_ready_at, planning_allowance
from daily3_selection import daily3_choices
from daily3_store import Daily3Store, day_balance
import daily3_store as store_module
from test_daily3_selection import football


ZURICH = ZoneInfo('Europe/Zurich')
PLAN_NOW = datetime(2030, 1, 1, 8, tzinfo=timezone.utc)
SCOPE = 'a' * 32
DAY = '2030-01-01'


@pytest.mark.parametrize('sport,hours', [
    ('football', 3), ('basketball', 3), ('hockey', 3),
    ('tennis', 4), ('esports', 4),
])
def test_planning_allowances_are_explicit_policy_not_bookmaker_finality(sport, hours):
    assert planning_allowance(sport) == timedelta(hours=hours)


@pytest.mark.parametrize('sport,slots,hour', [
    ('football', 0, 15), ('football', 1, 18), ('football', 2, 21),
    ('tennis', 0, 14), ('tennis', 1, 17), ('tennis', 2, 20),
])
def test_each_leg_reserves_day_capacity_for_remaining_slots(sport, slots, hour):
    boundary = datetime(2026, 10, 3, hour, tzinfo=ZURICH)
    assert fits_daily3_window(boundary, sport, slots)
    assert not fits_daily3_window(boundary + timedelta(seconds=1), sport, slots)


def test_football_at_twenty_one_can_only_be_the_third_leg():
    start = datetime(2026, 10, 3, 21, tzinfo=ZURICH)
    assert not fits_daily3_window(start, 'football', 0)
    assert not fits_daily3_window(start, 'football', 1)
    assert fits_daily3_window(start, 'football', 2)


@pytest.mark.parametrize('day', [(2026, 3, 29), (2026, 10, 25), (2026, 10, 3)])
def test_day_deadline_is_zurich_midnight_including_dst_and_utc_input(day):
    boundary = datetime(*day, 15, tzinfo=ZURICH)
    as_utc = boundary.astimezone(timezone.utc)
    assert fits_daily3_window(boundary, 'football', 0)
    assert fits_daily3_window(as_utc, 'football', 0)
    assert not fits_daily3_window(as_utc + timedelta(seconds=1), 'football', 0)


@pytest.mark.parametrize('slots', [-1, 3, True, 1.5])
def test_invalid_or_full_slot_counts_do_not_create_daytime_capacity(slots):
    assert not fits_daily3_window(PLAN_NOW + timedelta(hours=5), 'football', slots)


def test_naive_kickoff_is_not_silently_interpreted_as_local_time():
    assert not fits_daily3_window(datetime(2030, 1, 1, 14), 'football', 0)


def test_selector_builds_ordered_nonoverlapping_legs_not_three_parallel_games():
    first = football(101, probability=.75, now=PLAN_NOW, start_hours=5)
    second = football(102, probability=.77, now=PLAN_NOW, start_hours=8)
    third = football(103, probability=.90, now=PLAN_NOW, start_hours=11)
    pool = (third, second, first)
    choices = daily3_choices(pool, now=PLAN_NOW)
    assert [choice.signal.key for choice in choices] == [first.key, second.key, third.key]
    assert all(right.start >= left.start + planning_allowance(left.sport)
               for left, right in zip(choices, choices[1:]))
    assert pool == (third, second, first)


def test_same_start_is_not_presented_as_a_reinvestment_sequence():
    pool = [football(index, probability=.75, now=PLAN_NOW, start_hours=5)
            for index in (111, 112, 113)]
    assert len(daily3_choices(pool, now=PLAN_NOW)) == 1


def test_high_probability_late_single_is_not_a_daily3_first_leg():
    late = football(121, probability=.95, now=PLAN_NOW, start_hours=12)
    assert datetime.fromisoformat(late.scheduled_start).astimezone(ZURICH).hour == 21
    assert daily3_choices([late], now=PLAN_NOW) == ()


def test_time_window_does_not_relax_quality_or_force_three_cards():
    unsupported = football(122, probability=.69, now=PLAN_NOW, start_hours=3)
    late = football(123, probability=.95, now=PLAN_NOW, start_hours=12)
    assert daily3_choices([unsupported, late], now=PLAN_NOW) == ()
    early = football(124, probability=.75, now=PLAN_NOW, start_hours=5)
    assert [choice.signal.key for choice in daily3_choices([early], now=PLAN_NOW)] == [early.key]


def test_pending_planning_boundary_excludes_already_missed_next_match():
    early = football(131, probability=.90, now=PLAN_NOW, start_hours=5)
    late = football(132, probability=.75, now=PLAN_NOW, start_hours=12)
    choices = daily3_choices([early, late], now=PLAN_NOW, used_slots=2,
                             not_before=PLAN_NOW + timedelta(hours=10))
    assert [choice.signal.key for choice in choices] == [late.key]
    assert daily3_choices([late], now=PLAN_NOW, used_slots=2,
                          not_before=PLAN_NOW + timedelta(days=1)) == ()


def test_naive_not_before_is_rejected_instead_of_changing_the_timeline():
    with pytest.raises(ValueError):
        daily3_choices([], now=PLAN_NOW, not_before=datetime(2030, 1, 1, 14))


def _ident():
    return uuid.uuid4().hex


def _command(store, kind, *, action_id=None, **args):
    return store.command(SCOPE, action_id=action_id or _ident(), kind=kind, day=DAY, **args)


def _snapshot(event, start_hour=5):
    return dict(
        event_id=event, event_guard={'identity': event, 'aliases': []}, sport='football',
        event_label='Home vs Away', market_key='RESULT_HOME', market='Endergebnis',
        selection='Heimsieg', scheduled_start=(PLAN_NOW + timedelta(hours=start_hour)).isoformat(),
        signal_key=event + ':home', model_probability=.75, modeled_at=PLAN_NOW.isoformat(),
        model_version='sequence-test-v1', analysis_basis='Datenbasierte Testauswahl.',
        analysis_caution='', policy_version='daily3-sequence-test-v1',
    )


def test_pending_projection_uses_latest_existing_liability_not_a_fake_credit():
    bets = [
        dict(status='reserved', snapshot=_snapshot('football:fixture:141', 5)),
        dict(status='open', snapshot=_snapshot('football:fixture:142', 8)),
        dict(status='settled', snapshot=_snapshot('football:fixture:143', 11)),
        dict(status='cancelled', snapshot=_snapshot('football:fixture:144', 12)),
    ]
    assert pending_ready_at(bets, now=PLAN_NOW) == PLAN_NOW + timedelta(hours=11)
    # Once the planning allowance has elapsed, the existing liability is still
    # open. This helper advances only a plan; the command guard must still deny
    # an actual next reservation until its manually confirmed settlement.
    later = PLAN_NOW + timedelta(hours=12)
    assert pending_ready_at(bets, now=later) == later


@pytest.fixture
def store(tmp_path):
    return Daily3Store(tmp_path / 'sequence.db', key=b's' * 32, clock=lambda: PLAN_NOW)


def _reserve(store, event='football:fixture:151', *, amount=1000, start_hour=5, action_id=None):
    bet_id = _ident()
    _command(store, 'reserve', action_id=action_id, bet_id=bet_id,
             snapshot=_snapshot(event, start_hour), stake_cents=amount, odds='1.2')
    return bet_id


@pytest.mark.parametrize('place_first', [False, True])
def test_unspent_budget_does_not_allow_parallel_reinvestment_legs(store, place_first):
    _command(store, 'start')
    first = _reserve(store)
    if place_first:
        _command(store, 'place', bet_id=first, revision=1, reference='Buchmacherbeleg')
    before = store.history(SCOPE)
    assert day_balance(before[DAY]).available_cents == 4000
    with pytest.raises(Daily3Error):
        _reserve(store, 'football:fixture:152', start_hour=8)
    assert store.history(SCOPE) == before


def test_two_connections_with_enough_money_still_accept_only_one_current_leg(store):
    _command(store, 'start')
    def attempt(index):
        connection = Daily3Store(store.path, key=b's' * 32, clock=lambda: PLAN_NOW)
        try:
            _reserve(connection, f'football:fixture:{160 + index}')
            return True
        except Daily3Error:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, (1, 2))) == [False, True]
    assert day_balance(store.history(SCOPE)[DAY]).available_cents == 4000


def test_elapsed_planning_buffer_does_not_unlock_an_unsettled_bet(store):
    _command(store, 'start')
    first = _reserve(store)
    _command(store, 'place', bet_id=first, revision=1, reference='Buchmacherbeleg')
    later = Daily3Store(store.path, key=b's' * 32,
                        clock=lambda: PLAN_NOW + timedelta(hours=9))
    before = later.history(SCOPE)
    assert PLAN_NOW + timedelta(hours=9) > pending_ready_at(
        list(before[DAY]['bets'].values()), now=PLAN_NOW)
    with pytest.raises(Daily3Error):
        _reserve(later, 'football:fixture:162', start_hour=12)
    assert later.history(SCOPE) == before


def test_cancelled_reservation_releases_the_current_leg_without_fake_money(store):
    _command(store, 'start')
    first = _reserve(store)
    _command(store, 'cancel', bet_id=first, revision=1, not_placed=True)
    _reserve(store, 'football:fixture:172')
    state = day_balance(store.history(SCOPE)[DAY])
    assert state.used_slots == 1 and state.available_cents == 4000


def test_only_real_confirmed_return_funds_next_leg_without_changing_net_loss_limit(store):
    _command(store, 'start')
    first = _reserve(store, amount=5000)
    _command(store, 'place', bet_id=first, revision=1, reference='Buchmacherbeleg')
    with pytest.raises(Daily3Error):
        _reserve(store, 'football:fixture:182', amount=12000, start_hour=8)
    _command(store, 'settle', bet_id=first, revision=2,
             returned_cents=12000, reference='Tatsächlich gutgeschrieben')
    _reserve(store, 'football:fixture:182', amount=12000, start_hour=8)
    state = day_balance(store.history(SCOPE)[DAY])
    assert state.used_slots == 2 and state.available_cents == 0 and state.worst_net_cents == -5000


def test_late_first_reservation_is_rejected_before_ledger_write(store):
    _command(store, 'start')
    before = store.history(SCOPE)
    with pytest.raises(Daily3Error):
        _reserve(store, start_hour=12)
    assert store.history(SCOPE) == before


def test_existing_reservation_retry_remains_idempotent_after_its_start_time(store):
    _command(store, 'start')
    action_id, bet_id = _ident(), _ident()
    args = dict(bet_id=bet_id, snapshot=_snapshot('football:fixture:191'),
                stake_cents=1000, odds='1.2')
    before = _command(store, 'reserve', action_id=action_id, **args)
    later = Daily3Store(store.path, key=b's' * 32,
                        clock=lambda: PLAN_NOW + timedelta(hours=10))
    assert _command(later, 'reserve', action_id=action_id, **args) == before


def test_authenticated_legacy_parallel_and_late_reservations_remain_readable_and_retryable(store):
    """Construct legitimate old-policy receipts, not new-policy reservations."""
    first, second = _ident(), _ident()
    second_action = _ident()
    second_args = dict(bet_id=second, snapshot=_snapshot('football:fixture:202', 12),
                       stake_cents=1000, odds='1.2')
    commands = [
        (_ident(), 'start', {}),
        (_ident(), 'reserve', dict(bet_id=first,
             snapshot=_snapshot('football:fixture:201'), stake_cents=1000, odds='1.2')),
        (_ident(), 'place', dict(bet_id=first, revision=1, reference='Alter Buchmacherbeleg')),
        (second_action, 'reserve', second_args),
        (_ident(), 'place', dict(bet_id=second, revision=1, reference='Alter zweiter Beleg')),
    ]
    days, previous = {}, '0' * 64
    with store._connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        for sequence, (action, kind, args) in enumerate(commands, 1):
            payload = dict(version=1, kind=kind, at=PLAN_NOW.isoformat(), day=DAY, args=args)
            store_module._apply(days, payload)
            raw = store_module._canonical(payload)
            mac = store._mac('event', [SCOPE, sequence, action, raw, previous])
            connection.execute('INSERT INTO daily3_events VALUES (?,?,?,?,?,?)',
                               (SCOPE, sequence, action, raw, previous, mac))
            previous = mac
        connection.execute('INSERT INTO daily3_heads VALUES (?,?,?,?)',
                           (SCOPE, sequence, previous, store._mac('head', [SCOPE, sequence, previous])))
        connection.commit()
    before = store.history(SCOPE)
    assert before == days
    assert day_balance(before[DAY]).open_cents == 2000
    assert _command(store, 'reserve', action_id=second_action, **second_args) == before
    with pytest.raises(Daily3Error):
        _reserve(store, 'football:fixture:203')
    assert store.history(SCOPE) == before
