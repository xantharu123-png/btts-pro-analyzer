# Scoped final QA harness correction, not a production memory repair

Canonical checkout .worktrees/audit-repairs-20261013, base242093f.
Own ONLY tests/test_context_storage_ref_chunks.py and adjacent task report.
Controller owns source freeze, all repository QA, index and publication.
Production/source owners remain frozen. No VPS/API/backup/other agents.

Actual untouched cold test FAIL:645510 bytes; independent641969/641984;
pre-GC alone677492 stillFAIL. Snapshot mainly repeated cursor/stat/schema/
generation tuples, terminal current621690->14827 after fullGC. This is not
proof of lower native RSS and does not erase the original cold peak failure.
One independent fixed19-ref/chunk1 warmup then original12k test PASS; exact
successful peak unavailable because default capture. No repeat-until-green.

Independent final review permits ONLY a transparent steady-state harness:
one completely discarded separate19-reference descriptor/database, chunk1,
before tracing; measured12k descriptor remains new/different. Never pre-read
12k, use cached/memo answers, alter threshold512KiB/block4096/chunk1024,
GC/reset/filter/clear traces during measurement, delete/skip/rename old ID,
or change production to appease test. All complete admission/validation/
emission/terminal digest and byte checks remain unchanged.

Implement the minimal deterministic warmup in the owning existing test,
explicitly documenting this measures incremental streaming allocations after
fixed interpreter initialization, NOT cold total peak/RSS. Existing cold FAIL
evidence stays under output/context-completion-20261014.

TDD: preserve exact actual RED from controller. Add a genuine test-only negative
control: allocate and hold >=1MiB owned buffer while actual tracing is active,
through the real iterator and all its checks, and require this unchanged
512KiB measurement gate to fail. No memory getter/limit stub; fresh descriptors.
Control must not allocate target buffer before tracing or reuse a measured
descriptor. Must discriminate actual expected memory assertion from any
unrelated failure. Baseline ID kept; new control count additive only.

Run only owning module once after minimal change with actual offline launcher,
JUnit/stdout preserving successful measurement metadata using report_properties
or capture configuration, without modifying test measurement. No whole suite.
Read systematic-debugging/TDD skills and full owning code before acting.
Report exact source SHA, all PASS/FAIL provenance and that the new calibrated
contract does not lower previously measured cold peak or assert native memory.
Controller independent review then restarts A only; B has no imports of this
test file and all production sources unchanged throughout both shards.
