"""Historical source reuse keeps clocks, revisions and finite budgets honest."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_models.football_original_storage import StorageBudgetExceeded
from context_observations import append_bounded_observation_batch
from context_sources.football_retention import RetainedFinals, fixture_bundle
from test_context_football_capture import detail, stored
from test_football_context_provider import NOW, payload


def final(fid=1575469):
    raw = detail()
    raw['fixture'].update(id=fid, date='2026-09-01T12:00:00+00:00')
    raw['fixture']['status']['short'] = 'FT'
    raw['goals'] = {'home': 2, 'away': 1}
    # The source example contains a pre-match lineup, not final player stats.
    raw.pop('lineups', None)
    return raw


def save(path, raw, at=NOW):
    additions, base = fixture_bundle(raw, at)
    refs, cost = append_bounded_observation_batch(path, tuple((row, at) for row in additions),
        max_new_payload_bytes=100_000)
    return refs, base, cost


def retained(path, raw, at, received=None):
    return RetainedFinals(path, received or [(raw, canonical_timestamp(at))]).reuse(raw, observed=at)


def test_unchanged_complete_ft_reuses_exact_old_bundle_without_writes(tmp_path):
    path, raw = tmp_path/'sources.db', final()
    refs, base, _ = save(path, raw)
    before = path.read_bytes()
    assert retained(path, raw, NOW+timedelta(days=1)) == (refs, base)
    assert path.read_bytes() == before
    assert {row['observed_at'] for row in stored(path)} == {canonical_timestamp(NOW)}


@pytest.mark.parametrize('change', ['score', 'start', 'team', 'extra'])
def test_any_native_change_requires_new_receipt(tmp_path, change):
    path, raw = tmp_path/'sources.db', final()
    save(path, raw)
    changed = deepcopy(raw)
    if change == 'score':
        changed['goals']['home'] += 1
    elif change == 'start':
        changed['fixture']['date'] = '2026-09-01T13:00:00+00:00'
    elif change == 'team':
        changed['teams']['home']['id'] += 1
    else:
        changed['fixture']['referee'] = 'Revised official'
    assert retained(path, changed, NOW+timedelta(seconds=1)) is None


def test_scheduled_and_future_receipts_are_not_reused(tmp_path):
    path = tmp_path/'sources.db'
    raw = detail()
    save(path, raw)
    assert retained(path, raw, NOW+timedelta(seconds=1)) is None
    other = final(123)
    save(path, other, NOW+timedelta(days=1))
    assert retained(path, other, NOW) is None


def test_latest_revision_and_same_clock_conflicts_cannot_resurrect_old_content(tmp_path):
    path, raw = tmp_path/'sources.db', final()
    old_refs, _, _ = save(path, raw)
    changed = deepcopy(raw)
    changed['goals']['home'] += 1
    save(path, changed, NOW+timedelta(seconds=1))
    assert retained(path, raw, NOW+timedelta(seconds=2)) is None
    # A current response matching one branch cannot arbitrarily pick a tied row.
    save(path, raw, NOW+timedelta(seconds=1))
    assert retained(path, raw, NOW+timedelta(seconds=2)) is None
    assert old_refs


def test_unstored_intermediate_correction_requires_fresh_return_to_a(tmp_path):
    path, raw = tmp_path/'sources.db', final()
    save(path, raw)
    changed = deepcopy(raw)
    changed['goals']['home'] += 1
    at = NOW+timedelta(seconds=2)
    received = [(changed, canonical_timestamp(NOW+timedelta(seconds=1))),
                (raw, canonical_timestamp(at))]
    assert retained(path, raw, at, received) is None


def test_missing_bundle_member_is_not_silently_reconstructed_at_old_clock(tmp_path):
    path, raw = tmp_path/'sources.db', final()
    records, index = fixture_bundle(raw, NOW)
    append_bounded_observation_batch(path, ((records[index], NOW),), max_new_payload_bytes=100_000)
    assert retained(path, raw, NOW+timedelta(seconds=1)) is None


@pytest.mark.parametrize('column', ['kind', 'source', 'payload'])
def test_changed_persisted_identity_propagates_instead_of_becoming_missing(tmp_path, column):
    path, raw = tmp_path/'sources.db', final()
    refs, index, _ = save(path, raw)
    with sqlite3.connect(path) as connection:
        if column == 'payload':
            connection.execute("UPDATE context_contents SET payload=? WHERE content_digest=(SELECT content_digest FROM context_observations WHERE digest=?)", (b'{}', refs[index]))
        else:
            connection.execute(f"UPDATE context_observations SET {column}='changed' WHERE digest=?", (refs[index],))
    with pytest.raises(ContextIntegrityError):
        retained(path, raw, NOW+timedelta(seconds=1))


def capture(path, rows, at, budget):
    from context_sources.football_capture import _Capture
    worker = _Capture(path, baseline_enabled=True)
    for raw in rows:
        worker.record('fixtures', {'team': raw['teams']['home']['id'], 'last': 50,
            'status': 'FT', 'timezone': 'Europe/Zurich'}, payload([raw]), observed_at=at, status=200)
    result = worker.flush_baseline_receipts(tuple(rows), max_new_payload_bytes=budget)
    return worker, result


def test_repeat_scan_can_finish_history_with_the_same_one_bundle_budget(tmp_path):
    path, first, second = tmp_path/'sources.db', final(111), final(222)
    _, _, cost = save(tmp_path/'measure.db', first)
    with pytest.raises(StorageBudgetExceeded):
        capture(path, [first, second], NOW, cost)
    before = stored(path)
    worker, refs = capture(path, [first, second], NOW+timedelta(seconds=1), cost)
    assert all(refs.values())
    assert worker.source_inserted_bytes == cost
    assert len(stored(path)) == 2*len(before)
    assert set(row['digest'] for row in before) <= set(worker.refs)


def test_exhausted_new_row_does_not_prevent_later_free_reuse(tmp_path):
    from context_sources.football_capture import _Capture
    path, old, new = tmp_path/'sources.db', final(111), final(222)
    refs, base, _ = save(path, old)
    worker = _Capture(path, baseline_enabled=True)
    at = NOW+timedelta(seconds=1)
    for raw in (new, old):
        worker.record('fixtures', {'team': raw['teams']['home']['id'], 'last': 50,
            'status': 'FT', 'timezone': 'Europe/Zurich'}, payload([raw]), observed_at=at, status=200)
    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((new, old), max_new_payload_bytes=0)
    assert worker.baseline_refs == {111: {refs[base]}}
    assert worker.source_inserted_bytes == 0
    assert worker.refs == set(refs)


def test_unstored_correction_revokes_older_matching_refs_for_the_same_event(tmp_path):
    from context_sources.football_capture import _Capture
    path, raw = tmp_path/'sources.db', final()
    save(path, raw)
    changed = deepcopy(raw)
    changed['goals']['home'] += 1
    worker = _Capture(path, baseline_enabled=True)
    for offset, body in enumerate((raw, changed, raw), 1):
        worker.record('fixtures', {'team': body['teams']['home']['id'], 'last': 50,
            'status': 'FT', 'timezone': 'Europe/Zurich'}, payload([body]),
            observed_at=NOW+timedelta(seconds=offset), status=200)
    with pytest.raises(StorageBudgetExceeded):
        worker.flush_baseline_receipts((raw,), max_new_payload_bytes=0)
    assert not worker.baseline_refs
    assert worker.refs  # Old bytes remain, but cannot authorize this original.
