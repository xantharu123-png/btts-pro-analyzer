"""One retained 100-addition cProfile diagnosis; no product patch or capacity pass."""
import time

START_WALL, START_CPU = time.perf_counter(), time.process_time()
import cProfile
import hashlib
import json
from pathlib import Path
import platform
import pstats
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from context_runtime import _SCHEMA
from context_runtime_transaction import TrackedConnection
from context_sources.tennis_status import normalize_tennis_status
from context_storage_v2.copying import _configure_copy_reader
from context_storage_v2.receipt_corpus import build_receipt_corpus
from context_storage_v2.workspace_budget import WorkspaceBudget, FileSlot, ExternalInput
from context_storage_v2.inventory import inventory_raw
from context_runtime_inventory import VerifiedReceiptMapping


def file_sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while part := stream.read(1024**2):
            value.update(part)
    return value.hexdigest()


def code_pins():
    files = {Path(__file__).resolve()}
    for module in tuple(sys.modules.values()):
        location = getattr(module, "__file__", None)
        if location:
            path = Path(location).resolve()
            if path.is_relative_to(ROOT) and path.suffix == ".py" and ".pytest_tmp" not in path.parts:
                files.add(path)
    return {str(path.relative_to(ROOT)): file_sha(path) for path in sorted(files)}


def main():
    count = 100
    owned = ROOT / ".pytest_tmp" / "task55-profile-20260912-bt-01"
    owned.mkdir()  # A previously used name is a failure, never a resume.
    pins = code_pins()
    main_cap, ledger_cap = 16 * 1024**2, 1024**2
    initial_free = shutil.disk_usage(owned).free
    if initial_free < 4 * 1024**3 + 2 * main_cap + ledger_cap + 2 * 1024**2:
        raise RuntimeError("diagnostic free reserve unavailable")
    source = owned / "source.sqlite"
    connection = sqlite3.connect(source)
    try:
        for sql in _SCHEMA.values():
            connection.execute(sql).close()
        connection.commit()
    finally:
        connection.close()
    source_sha = file_sha(source)
    work = owned / "work"
    work.mkdir()
    corpus = work / "corpus"
    corpus.mkdir()
    budget = WorkspaceBudget(work, [
        FileSlot("corpus/legacy-copy.sqlite", main_cap, True),
        FileSlot("corpus/legacy-copy.sqlite-journal", main_cap),
        FileSlot("corpus/receipt-additions.bin", ledger_cap, True),
    ], external_inputs=[ExternalInput(source)])
    at = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)

    def records():
        for number in range(count):
            clock = at + timedelta(seconds=number)
            competition = {"id": str(800000000 + number),
                "date": (at + timedelta(days=2)).isoformat(),
                "competitors": [{"id": "1"}, {"id": "2"}],
                "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}}}
            rows = normalize_tennis_status("ATP", "100", competition,
                grouping_slug="mens-singles", observed_at=clock)
            if len(rows) != 1:
                raise RuntimeError("genuine normalized row count differs")
            yield rows[0], clock

    profile = cProfile.Profile()
    connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True,
        factory=TrackedConnection, isolation_level=None)
    try:
        _configure_copy_reader(connection, page_size=4096, page_count=source.stat().st_size // 4096)
        connection.execute("BEGIN").close()
        started_wall, started_cpu = time.perf_counter(), time.process_time()
        try:
            result = profile.runcall(build_receipt_corpus, connection, records(),
                expected_source_sha256=source_sha, workspace=work, owned_directory=corpus,
                main_cap_bytes=main_cap, ledger_cap_bytes=ledger_cap)
        finally:
            corpus_seconds = {"wall": time.perf_counter() - started_wall,
                              "cpu": time.process_time() - started_cpu}
            profile.dump_stats(str(owned / "corpus.pstats"))
        if result.new_receipts != count or result.new_contents != count:
            raise RuntimeError("complete actual addition counts differ")
        connection.commit()
    finally:
        connection.close()
    validation_wall, validation_cpu = time.perf_counter(), time.process_time()
    observation = budget.check_quiescent()
    reader = sqlite3.connect(result.path.as_uri() + "?mode=ro", uri=True,
        factory=TrackedConnection, isolation_level=None)
    try:
        _configure_copy_reader(reader, page_size=result.page_size,
            page_count=result.path.stat().st_size // result.page_size)
        reader.execute("BEGIN").close()
        if inventory_raw(reader) != result.inventory:
            raise RuntimeError("fresh full raw inventory differs")
        receipts = VerifiedReceiptMapping(reader)
        validated = receipts.validate_all()
        if validated != count or len(receipts) != count:
            raise RuntimeError("fresh actual physical validation differs")
        reader.commit()
    finally:
        reader.close()
    if file_sha(source) != source_sha:
        raise RuntimeError("original source bytes changed")
    if file_sha(result.path) != result.output_sha256 or file_sha(result.ledger_path) != result.ledger_sha256:
        raise RuntimeError("terminal output file hashes differ")
    validation_seconds = {"wall": time.perf_counter() - validation_wall,
                          "cpu": time.process_time() - validation_cpu}
    after_pins = code_pins()
    if any(after_pins.get(path) != sha for path, sha in pins.items()):
        raise RuntimeError("executed code bytes changed during diagnosis")
    with (owned / "profile.txt").open("x", encoding="utf-8") as stream:
        stats = pstats.Stats(profile, stream=stream).sort_stats("cumulative")
        stats.print_stats(65)
        stats.print_callers("source_check|_field_hash|check_profile|_workspace_bytes|_current|fetchmany")
    entries = []
    for key, (primitive, total, own_time, cumulative, callers) in stats.stats.items():
        entries.append({"file": key[0], "line": key[1], "name": key[2],
            "primitive_calls": primitive, "total_calls": total,
            "own_seconds": own_time, "cumulative_seconds": cumulative,
            "callers": [{"file": caller[0], "line": caller[1], "name": caller[2],
                         "counts_and_times": data} for caller, data in callers.items()]})
    with (owned / "stats.json").open("x", encoding="utf-8") as stream:
        json.dump(sorted(entries, key=lambda entry: -entry["cumulative_seconds"]), stream, sort_keys=True)
    artifacts = {str(path.relative_to(owned)): {"bytes": path.stat().st_size, "sha256": file_sha(path)}
                 for path in sorted(owned.rglob("*")) if path.is_file()}
    summary = {"format": "task55-corpus-profile-v1", "count": count, "validated_receipts": validated,
        "source_sha256": source_sha, "output_sha256": result.output_sha256,
        "ledger_sha256": result.ledger_sha256, "corpus_profiled_seconds": corpus_seconds,
        "external_validation_seconds": validation_seconds,
        "whole_through_pre_summary_seconds": {"wall": time.perf_counter() - START_WALL,
                                              "cpu": time.process_time() - START_CPU},
        "workspace_bytes": observation.workspace_bytes,
        "workspace_ceiling_bytes": observation.workspace_ceiling_bytes,
        "active_input_ceiling_bytes": observation.active_input_ceiling_bytes,
        "initial_free_bytes": initial_free, "final_free_bytes": shutil.disk_usage(owned).free,
        "attempt_bytes_before_summary": sum(item["bytes"] for item in artifacts.values()),
        "runtime": {"python": sys.version, "sqlite": sqlite3.sqlite_version, "platform": platform.platform()},
        "code_sha256": pins, "artifacts": artifacts,
        "profile_scope": "complete unmodified build_receipt_corpus, including generator/commit/verify/close",
        "profile_overhead_included": True, "native_capacity_claim": False,
        "growth_or_consumer_or_B_claim": False, "global_quota_or_cpu_claim": False}
    with (owned / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, sort_keys=True, indent=2)
    print(json.dumps({key: summary[key] for key in ("count", "validated_receipts",
        "corpus_profiled_seconds", "external_validation_seconds", "whole_through_pre_summary_seconds",
        "workspace_bytes", "attempt_bytes_before_summary", "native_capacity_claim")}, sort_keys=True))


if __name__ == "__main__":
    main()
