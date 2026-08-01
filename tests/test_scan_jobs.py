"""Hintergrund-Scan-Jobs: Thread-Lebenszyklus, Persistenz, Fehlerpfad."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import scan_jobs


def _wait_for_state(key: str, states: set[str], timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = scan_jobs.get_job(key)
        if job["state"] in states:
            return job
        time.sleep(0.02)
    raise AssertionError(f"Job {key} blieb in Zustand {scan_jobs.get_job(key)}")


class ScanJobTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._jobs_dir_patch = patch.object(scan_jobs, "JOBS_DIR", self.tmp)
        self._jobs_dir_patch.start()

    def tearDown(self):
        self._jobs_dir_patch.stop()
        scan_jobs.clear_job("test")
        self._tmp.cleanup()

    def test_done_result_and_persistence(self):
        def work(progress_cb=None):
            progress_cb(0.5, "halb")
            return {"value": 42}

        started = scan_jobs.start_job(
            "test",
            work,
            persist_name="testjob",
            persist_fn=lambda result: {"signals": [result["value"]]},
        )
        self.assertTrue(started)
        job = _wait_for_state("test", {"done"})
        self.assertEqual(job["result"], {"value": 42})

        # _persist läuft im Worker NACH dem done-Status: auf die Datei warten,
        # bevor der JOBS_DIR-Patch im tearDown endet.
        target = self.tmp / "testjob.json"
        deadline = time.time() + 2.0
        while not target.exists() and time.time() < deadline:
            time.sleep(0.02)
        document = scan_jobs.load_persisted("testjob", jobs_dir=self.tmp)
        self.assertIsNotNone(document)
        self.assertEqual(document["signals"], [42])
        self.assertIn("finished_at", document)

    def test_second_start_while_running_is_rejected(self):
        gate = []

        def slow(progress_cb=None):
            gate.append(True)
            time.sleep(0.3)
            return 1

        self.assertTrue(scan_jobs.start_job("test", slow))
        self.assertFalse(scan_jobs.start_job("test", slow))
        _wait_for_state("test", {"done"})
        self.assertEqual(gate, [True])  # nur ein Thread lief

    def test_error_path_captures_exception(self):
        def broken(progress_cb=None):
            raise RuntimeError("kaputt")

        scan_jobs.start_job("test", broken)
        job = _wait_for_state("test", {"error"})

        self.assertIn("RuntimeError", job["error"])
        self.assertIn("kaputt", job["error"])
        self.assertIn("traceback", job)

    def test_progress_updates_are_visible(self):
        seen = []

        def work(progress_cb=None):
            progress_cb(0.25, "Schritt 1")
            seen.append(scan_jobs.get_job("test")["progress"])
            progress_cb(1.0, "fertig")
            return "ok"

        scan_jobs.start_job("test", work)
        _wait_for_state("test", {"done"})

        self.assertEqual(seen, [0.25])
        self.assertEqual(scan_jobs.get_job("test").get("progress"), 1.0)

    def test_clear_and_idle(self):
        self.assertEqual(scan_jobs.get_job("test"), {"state": "idle"})
        scan_jobs.start_job("test", lambda progress_cb=None: 1)
        _wait_for_state("test", {"done"})
        scan_jobs.clear_job("test")
        self.assertEqual(scan_jobs.get_job("test"), {"state": "idle"})

    def test_load_persisted_missing_or_broken(self):
        self.assertIsNone(scan_jobs.load_persisted("fehlt", jobs_dir=self.tmp))
        (self.tmp / "kaputt.json").write_text("{kein json", encoding="utf-8")
        self.assertIsNone(scan_jobs.load_persisted("kaputt", jobs_dir=self.tmp))


if __name__ == "__main__":
    unittest.main()
