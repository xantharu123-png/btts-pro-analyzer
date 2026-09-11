"""Small owner-equivalence tests for the ignored B0 sizing instrument."""
from datetime import datetime, timedelta, timezone
from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('task14_size', ROOT / '.pytest_tmp/probe_task14_growth_size.py')
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
OWNERS = PROBE.bind_owners(ROOT)
from context_runtime_tennis import _cold_replay_history
from runtime_paths import RuntimeArtifactTrustError


class SizeEquivalence(unittest.TestCase):
    def setUp(self):
        self.clock = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.cutoff = self.clock + timedelta(hours=1)
        self.rows = [PROBE.generated_physical(index + 1, self.clock + timedelta(seconds=index), OWNERS)[2]
                     for index in range(4)]
        self.rows += [PROBE.generated_physical(8, self.clock, OWNERS, tour='WTA')[2],
                      PROBE.generated_physical(9, self.clock + timedelta(days=1), OWNERS)[2]]

    def test_accumulator_is_exact_cold_budget_for_each_tour(self):
        for tour in ('ATP', 'WTA'):
            with self.subTest(tour=tour):
                counter = PROBE.ByteCounter()
                for row in self.rows:
                    for selected in PROBE.selected_single(row, self.cutoff, OWNERS[2]):
                        if selected['payload']['tour'] == tour:
                            counter.add(selected, OWNERS[0].canonical_bytes)
                inventory = {row['digest']: row for row in reversed(self.rows)}
                cold = _cold_replay_history(inventory, cutoff=self.cutoff, tour=tour, max_bytes=counter.bytes)
                self.assertEqual(len(cold), counter.rows)
                self.assertEqual(sum(len(OWNERS[0].canonical_bytes(row)) for row in cold), counter.bytes)
                with self.assertRaisesRegex(RuntimeArtifactTrustError, 'canonical input budget'):
                    _cold_replay_history(inventory, cutoff=self.cutoff, tour=tour, max_bytes=counter.bytes - 1)

    def test_empty_history_fits_zero_and_no_container_bytes_are_charged(self):
        result = _cold_replay_history({}, cutoff=self.cutoff, tour='ATP', max_bytes=0)
        self.assertEqual(result, ())
        self.assertEqual(PROBE.ByteCounter().bytes, 0)

    def test_generated_physical_bytes_equal_real_append_read_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix='task14-owner-', dir=ROOT / '.pytest_tmp') as temporary:
            path = Path(temporary) / 'context.db'
            for tour in ('ATP', 'WTA'):
                for index in (1, 70_000, 70_001, 490_000):
                    content, physical, decoded = PROBE.generated_physical(index, self.clock, OWNERS, tour=tour)
                    receipt = OWNERS[1].append_observation(path, content, observed_at=self.clock)
                    self.assertEqual(receipt, physical[0])
                    self.assertEqual(OWNERS[1].append_observation(path, content, observed_at=self.clock), receipt)
                    with closing(sqlite3.connect(path)) as connection:
                        actual = connection.execute(OWNERS[1]._SELECT + ' WHERE r.digest=?', (receipt,)).fetchone()
                    self.assertEqual(actual, physical)
                    self.assertEqual(OWNERS[1]._decode_receipt(actual), decoded)
                    self.assertEqual(len(PROBE.selected_single(decoded, self.cutoff, OWNERS[2])), 1)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT count(*) FROM context_observations').fetchone()[0], 8)

    def test_new_event_identity_is_unique_and_fixed_width(self):
        ids = [PROBE.generated_physical(index, self.clock, OWNERS)[2]['event_key']
               for index in (1, 69_999, 70_000, 70_001, 490_000)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(set(map(len, ids))), 1)
        self.assertTrue(all(key.startswith('espn:tennis:ATP:match:97014') for key in ids))

    def test_physical_owner_rejects_changed_outer_field(self):
        _, physical, _ = PROBE.generated_physical(1, self.clock, OWNERS)
        damaged = list(physical)
        damaged[2] += '1'
        with self.assertRaises(ValueError):
            OWNERS[1]._decode_receipt(tuple(damaged))

    def test_unknown_d2_kind_aborts_before_any_body_decoder(self):
        with closing(sqlite3.connect(':memory:')) as connection:
            connection.execute('CREATE TABLE artifacts(digest TEXT,kind TEXT,created_at TEXT)')
            for name in ('context_contents', 'context_observations', 'context_snapshots'):
                connection.execute('CREATE TABLE ' + name + '(unused TEXT)')
            connection.execute('INSERT INTO artifacts VALUES (?,?,?)',
                               ('0' * 64, 'context-experiment-v1', self.clock.isoformat()))
            with patch.object(OWNERS[0], '_load_artifact', side_effect=AssertionError('body opened')) as artifact_decoder:
                with patch.object(OWNERS[1], '_decode_receipt', side_effect=AssertionError('body opened')) as receipt_decoder:
                    with self.assertRaises(PROBE.DiagnosticStop):
                        PROBE.preflight(connection, OWNERS)
                    artifact_decoder.assert_not_called()
                    receipt_decoder.assert_not_called()

    def test_generated_stop_is_first_exact_overflow_and_no_full_day_claim(self):
        output = []
        result = PROBE.generated(None, OWNERS, {'start': self.clock, 'receipt_count': 1},
            ['1', '1', str(PROBE.HISTORY_CAP - 1), '0', '0', '0' * 64], output.append)
        self.assertTrue(result['storage_stop'])
        self.assertFalse(result['day_completed'])
        self.assertEqual(result['new_receipts']['rows'], 1)
        self.assertEqual(result['snapshots_generated'], 0)
        self.assertFalse(result['complete_verification_claimed'])
        self.assertGreater(result['combined_selected_canonical_bytes'], PROBE.HISTORY_CAP)

    def test_missing_prior_chunk_cannot_start_later_day(self):
        with self.assertRaises(PROBE.DiagnosticStop):
            PROBE.generated(None, OWNERS, {'start': self.clock, 'receipt_count': 1},
                ['2', '1', '100', '0', '0', '0' * 64], lambda value: None)


if __name__ == '__main__':
    unittest.main(verbosity=2)
