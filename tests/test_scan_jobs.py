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

    def test_session_scopes_are_stable_and_isolated(self):
        first = {}
        second = {}
        first_scope = scan_jobs.session_scope(first)
        self.assertEqual(scan_jobs.session_scope(first), first_scope)
        self.assertNotEqual(scan_jobs.session_scope(second), first_scope)

    def test_scoped_persistence_does_not_mix_sessions(self):
        scan_jobs._persist("live", {"value": 1}, scope="session-a")
        scan_jobs._persist("live", {"value": 2}, scope="session-b")
        self.assertEqual(
            scan_jobs.load_persisted(
                "live",
                jobs_dir=self.tmp,
                scope="session-a",
            )["value"],
            1,
        )
        self.assertEqual(
            scan_jobs.load_persisted(
                "live",
                jobs_dir=self.tmp,
                scope="session-b",
            )["value"],
            2,
        )

    def test_timed_out_generation_cannot_overwrite_restart(self):
        def slow(progress_cb=None):
            time.sleep(0.2)
            return "old"

        self.assertTrue(
            scan_jobs.start_job("test", slow, timeout_seconds=0.03)
        )
        time.sleep(0.05)
        self.assertEqual(scan_jobs.get_job("test")["state"], "error")
        self.assertTrue(
            scan_jobs.start_job(
                "test",
                lambda progress_cb=None: "new",
                timeout_seconds=1,
            )
        )
        current = _wait_for_state("test", {"done"})
        self.assertEqual(current["result"], "new")
        time.sleep(0.2)
        self.assertEqual(scan_jobs.get_job("test")["result"], "new")


class RunningPagesTests(unittest.TestCase):
    """Seiten-Rädchen: running_pages bildet laufende Jobs auf Seiten ab."""

    MAPPING = {
        "Spiele": ("prematch",),
        "Live": ("live", "red_cards"),
        "15K Challenge": ("challenge_15k",),
    }

    def tearDown(self):
        for key in ("prematch", "live", "red_cards", "challenge_15k"):
            scan_jobs.clear_job(key)

    def test_idle_means_no_running_pages(self):
        self.tearDown()
        self.assertEqual(scan_jobs.running_pages(self.MAPPING), set())

    def test_running_job_marks_exactly_its_page(self):
        gate = []

        def slow(progress_cb=None):
            gate.append(True)
            time.sleep(0.5)
            return 1

        scan_jobs.start_job("red_cards", slow)
        try:
            self.assertEqual(scan_jobs.running_pages(self.MAPPING), {"Live"})
        finally:
            _wait_for_state("red_cards", {"done"})
        self.assertEqual(gate, [True])
        self.assertEqual(scan_jobs.running_pages(self.MAPPING), set())

    def test_second_job_key_of_same_page(self):
        scan_jobs.start_job("challenge_15k", lambda progress_cb=None: 1)
        _wait_for_state("challenge_15k", {"done"})
        scan_jobs.clear_job("challenge_15k")
        scan_jobs.start_job("live", lambda progress_cb=None: time.sleep(0.4) or 1)
        try:
            self.assertEqual(scan_jobs.running_pages(self.MAPPING), {"Live"})
        finally:
            _wait_for_state("live", {"done"})

    def test_running_pages_can_be_session_scoped(self):
        scope = "abc"
        key = scan_jobs.scoped_key("prematch", scope)
        scan_jobs.start_job(
            key,
            lambda progress_cb=None: time.sleep(0.2) or 1,
        )
        try:
            self.assertEqual(
                scan_jobs.running_pages(self.MAPPING, scope=scope),
                {"Spiele"},
            )
            self.assertEqual(scan_jobs.running_pages(self.MAPPING), set())
        finally:
            _wait_for_state(key, {"done"})
            scan_jobs.clear_job(key)


if __name__ == "__main__":
    unittest.main()
