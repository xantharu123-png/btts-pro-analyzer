"""Disk headroom guard of the runtime volume (Audit 25.10.2026 D6, Massnahme 9)."""
import json
from collections import namedtuple
from datetime import datetime, timedelta, timezone

import pytest

import runtime_disk_guard as guard

Usage = namedtuple("Usage", "total used free")
GIB = 1024 ** 3
NOW = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)


def _usage(free_gib, total_gib=38):
    return lambda _path: Usage(total_gib * GIB, (total_gib - free_gib) * GIB, free_gib * GIB)


def _databases(tmp_path, **sizes):
    for name, size in sizes.items():
        (tmp_path / f"{name}.db").write_bytes(b"\0" * size)


def test_healthy_volume_is_ok_and_names_the_largest_databases(tmp_path):
    _databases(tmp_path, context_models=3000, forecast_evidence=200, daily3=10)
    record = guard.check_runtime_disk(tmp_path, now=NOW, usage=_usage(20))

    assert record["status"] == "ok" and guard.disk_problem(record) is None
    assert record["database_bytes"] == 3210
    assert list(record["largest_databases"]) == ["context_models.db", "forecast_evidence.db", "daily3.db"]
    assert json.loads((tmp_path / guard.STATUS_FILE).read_text(encoding="utf-8")) == record


@pytest.mark.parametrize("free_gib,total_gib", [(4, 38), (30, 400)])
def test_low_headroom_by_bytes_or_ratio_reports_one_alert_line(tmp_path, free_gib, total_gib):
    record = guard.check_runtime_disk(tmp_path, now=NOW, usage=_usage(free_gib, total_gib))

    assert record["status"] == "low"
    line = guard.disk_problem(record)
    assert line.startswith(f"Speicherplatz knapp: {free_gib:.1f} GB frei") and "Nichts wird gelöscht" in line


def test_one_sample_per_day_and_growth_estimate(tmp_path):
    _databases(tmp_path, context_models=1000)
    guard.check_runtime_disk(tmp_path, now=NOW - timedelta(days=4), usage=_usage(20))
    (tmp_path / "context_models.db").write_bytes(b"\0" * 1400)
    guard.check_runtime_disk(tmp_path, now=NOW - timedelta(hours=1), usage=_usage(20))
    record = guard.check_runtime_disk(tmp_path, now=NOW, usage=_usage(20))

    assert [sample["day"] for sample in record["daily_samples"]] == ["2026-10-24", "2026-10-28"]
    assert record["database_growth_bytes_per_day"] == 100
    assert record["days_until_min_free"] == (20 * GIB - guard.MIN_FREE_BYTES) // 100


def test_samples_are_bounded_and_a_damaged_status_file_starts_over(tmp_path):
    (tmp_path / guard.STATUS_FILE).write_text("{broken", encoding="utf-8")
    record = guard.check_runtime_disk(tmp_path, now=NOW, usage=_usage(20))
    assert len(record["daily_samples"]) == 1

    for day in range(guard.MAX_DAILY_SAMPLES + 5):
        record = guard.check_runtime_disk(tmp_path, now=NOW + timedelta(days=day + 1), usage=_usage(20))
    assert len(record["daily_samples"]) == guard.MAX_DAILY_SAMPLES


def test_scheduled_guard_never_fails_the_job_on_a_measurement_error(tmp_path, capsys):
    def broken(_path):
        raise OSError("no statvfs")

    assert guard.guard_runtime_disk(directory=tmp_path, now=NOW, usage=broken) is None
    assert json.loads(capsys.readouterr().out) == {"disk_guard": "unavailable", "error_type": "OSError"}
    assert guard.guard_runtime_disk(directory=tmp_path, now=NOW, usage=_usage(3)).startswith("Speicherplatz knapp")


@pytest.mark.parametrize("problem,operational,expected", [
    (None, [], 0), ("Speicherplatz knapp: 3.0 GB frei (8 %)", [], 1), (None, ["Fussball: HTTP 500"], 1),
])
def test_quotes_run_fails_only_on_low_headroom_or_operational_errors(monkeypatch, capsys, problem, operational, expected):
    import wettfinder_automation as automation

    monkeypatch.setattr(automation, "refresh_prices_only", lambda **_kwargs: {
        "errors": operational, "operational_errors": operational})
    monkeypatch.setattr(guard, "guard_runtime_disk", lambda: problem)

    assert automation.main(["--quotes-only", "--quote-sport", "all"]) == expected
    assert (problem in capsys.readouterr().out) if problem else True
