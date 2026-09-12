"""One small, real local corpus timing; not native/global capacity acceptance."""
import time

START_WALL, START_CPU = time.perf_counter(), time.process_time()
import hashlib
import json
from pathlib import Path
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


def main():
    count = 1000
    owned = ROOT / ".pytest_tmp" / "corpus-cost-diagnostic-20260912-bt-01"
    owned.mkdir()  # Never reuse, overwrite or remove a previous attempt.
    source = owned / "source.sqlite"
    with sqlite3.connect(source) as connection:
        for sql in _SCHEMA.values():
            connection.execute(sql)
    connection.close()
    before = file_sha(source)
    work = owned / "work"
    work.mkdir()
    corpus = work / "corpus"
    corpus.mkdir()
    main_cap, ledger_cap = 16 * 1024**2, 1024**2
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

    connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True,
        factory=TrackedConnection, isolation_level=None)
    try:
        _configure_copy_reader(connection, page_size=4096, page_count=source.stat().st_size // 4096)
        connection.execute("BEGIN").close()
        started_wall, started_cpu = time.perf_counter(), time.process_time()
        result = build_receipt_corpus(connection, records(), expected_source_sha256=before,
            workspace=work, owned_directory=corpus, main_cap_bytes=main_cap,
            ledger_cap_bytes=ledger_cap)
        corpus_seconds = {"wall": time.perf_counter() - started_wall,
                          "cpu": time.process_time() - started_cpu}
        if result.new_receipts != count or result.new_contents != count:
            raise RuntimeError("complete actual addition counts differ")
        connection.commit()
    finally:
        connection.close()
    observation = budget.check_quiescent()
    reader = sqlite3.connect(result.path.as_uri() + "?mode=ro", uri=True,
        factory=TrackedConnection, isolation_level=None)
    try:
        _configure_copy_reader(reader, page_size=result.page_size,
            page_count=result.path.stat().st_size // result.page_size)
        reader.execute("BEGIN").close()
        if inventory_raw(reader) != result.inventory:
            raise RuntimeError("fresh full raw inventory differs")
        # No model/original or D2 objects exist in this intentionally empty
        # transport baseline. This is not source authority for a C consumer.
        receipts = VerifiedReceiptMapping(reader)
        if receipts.validate_all() != count or len(receipts) != count:
            raise RuntimeError("fresh actual physical validation differs")
        reader.commit()
    finally:
        reader.close()
    if file_sha(source) != before:
        raise RuntimeError("original source bytes changed")
    print(json.dumps({"format": "local-corpus-cost-diagnostic-v1", "count": count,
        "source_sha256": before, "output_sha256": result.output_sha256,
        "corpus_seconds": corpus_seconds,
        "whole_seconds": {"wall": time.perf_counter() - START_WALL, "cpu": time.process_time() - START_CPU},
        "source_bytes": source.stat().st_size, "output_bytes": result.path.stat().st_size,
        "ledger_bytes": result.ledger_path.stat().st_size,
        "workspace_bytes": observation.workspace_bytes,
        "workspace_ceiling_bytes": observation.workspace_ceiling_bytes,
        "active_input_ceiling_bytes": observation.active_input_ceiling_bytes,
        "free_bytes": observation.free_bytes, "native_capacity_claim": False,
        "growth_or_consumer_or_B_claim": False}, sort_keys=True))


if __name__ == "__main__":
    main()
