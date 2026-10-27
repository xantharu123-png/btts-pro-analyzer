"""Exit code of the tennis daily scan (owner 28.10.2026, Gesamtaudit D3/D5).

``betboy-tennis.service`` carries ``OnFailure=betboy-alert@%n.service``. A night
that excludes one oversized case with a diagnosis and stores the rest is a
success; operational errors still exit 1.
"""
from contextlib import contextmanager

import pytest

from scripts import tennis_daily as daily

EXCLUDED = {"tour": "WTA", "event_key": "espn:tennis:WTA:match:185676", "reason": "live_case_raw_admission_exceeded",
            "rows": 31499, "bytes": 33626244, "max_chunk_bytes": 1205, "missing_payloads": 0}


def _workers(monkeypatch, errors, *, run_code=0, issues=()):
    import context_sources.tennis_capture as capture
    import tennis.live_context as live
    result = {"stored": 56, "errors": list(errors)}

    class Batch:
        pending = [{"result": result}]
        path = "unused-context.db"

        def attach_capture(self, capture):
            pass

        def finish(self):
            pass

    class Capture:
        pending = []

        def report(self):
            return {"status": "complete", "issues": list(issues)}

    @contextmanager
    def live_worker(**kwargs):
        yield Batch()

    @contextmanager
    def capture_worker(**kwargs):
        yield Capture()

    monkeypatch.setattr(live, "live_worker", live_worker)
    monkeypatch.setattr(capture, "capture_tennis_worker", capture_worker)
    monkeypatch.setattr(daily.shadow, "summary", lambda: {})
    monkeypatch.setattr(daily, "_run_daily", lambda args: run_code)
    monkeypatch.setattr(daily.sys, "argv", ["tennis_daily.py", "2026-10-28"])


def test_a_diagnosed_case_exclusion_alone_is_a_successful_night(monkeypatch, capsys):
    _workers(monkeypatch, [EXCLUDED])
    assert daily.main() == 0
    output = capsys.readouterr().out
    assert "Nach Datenempfang gespeichert: 56 neue Predictions" in output
    assert "Prognose-Abschluss mit Teildaten" in output and "live_case_raw_admission_exceeded" in output
    assert "nur diagnostizierte Fallausschlüsse" in output


@pytest.mark.parametrize("other", [
    {"tour": "ATP", "provider_event_id": "1", "reason": "fixture_identity_conflict", "error_type": "FixtureIdentityConflict"},
    {"tour": "ATP", "provider_event_id": "2", "reason": "prediction_scan_failed", "error_type": "ValueError"},
    "an unstructured error",
])
def test_any_other_final_error_still_fails_the_night(monkeypatch, capsys, other):
    _workers(monkeypatch, [EXCLUDED, other])
    assert daily.main() == 1
    assert "nur diagnostizierte Fallausschlüsse" not in capsys.readouterr().out


def test_scan_errors_and_unreported_capture_issues_still_fail(monkeypatch, capsys):
    _workers(monkeypatch, [EXCLUDED], run_code=1)
    assert daily.main() == 1
    _workers(monkeypatch, [EXCLUDED], issues=("espn-schema-drift",))
    assert daily.main() == 1
    _workers(monkeypatch, [])
    assert daily.main() == 0
    capsys.readouterr()


def test_classification_is_exact():
    assert daily.operational_final_errors([EXCLUDED]) == []
    assert daily.operational_final_errors([dict(EXCLUDED, reason="live_case_raw_admission")]) != []
    assert daily.DIAGNOSED_EXCLUSION_REASONS == frozenset({"live_case_raw_admission_exceeded"})
