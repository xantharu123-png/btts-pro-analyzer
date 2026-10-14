# Task 21 scoped stream harness: module verification remains RED

Canonical checkout: `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`.
Controller-supplied base: `242093f`. Scope: owning test module and this report only.
Production sources, tests outside this module, index, Git, VPS/API and backups
were not changed. Controller owns the 17-source hash freeze and full-suite work.

## Test-only change and precise contract

The existing test ID remains
`tests/test_context_storage_ref_chunks.py::test_full_stream_uses_bounded_python_buffers_separately_from_timing`.
One fixed separate 19-reference private database/descriptor is completely streamed
in one-byte chunks and discarded before constructing the new measured 12k input.
This transparently calibrates interpreter initialization for incremental Python
streaming allocations; it does NOT claim a cold-total-peak reduction or native RSS
fix. No 12k target pre-read, cached/memo answer, GC, trace reset/filter/clearing,
threshold increase, skip, retry-until-green, or production change was introduced.
The real stream still performs complete admission/validation/emission/terminal
checks; the measured limits remain block4096/chunk1024/peak524288 bytes. Digest,
byte count, chunk size/count and multiblock checks remain.

An additive negative control allocates and retains an actual owned 1048576-byte
buffer only AFTER tracing starts, throughout the same real 12k iterator. Its
`pytest.raises(AssertionError, match="incremental_stream_python_peak_exceeded")`
matches only the actual final memory gate, not unrelated chunk/digest/integrity
failures. The returned getter value is real; no memory getter/limit is stubbed.
Successful and failed peak/control metadata is recorded only after measurement
through `record_property` and persisted in JUnit.

## RED provenance and earlier diagnostic evidence

Original untouched standalone RED: 645510 bytes (controller evidence at
`C:/Projekt/BetBoy/output/context-completion-20261014/qa-final/stream-memory-repro.log`
and associated XML). Independent original-value-preserving snapshots reproduced
641969 and 641984 bytes. Dominant terminal allocation sites were repeated cursor,
stat, generation/dataclass tuple and schema work. Post-measurement full GC reduced
current traced bytes from 621690 to 14827, but this was diagnostic ONLY and never a
passing gate or native-memory proof. A separate pre-start GC experiment still
FAILED at 677492 bytes. All those failure artifacts remain under
`C:/Projekt/BetBoy/output/context-completion-20261014/stream-memory-diagnosis`.

One separate fixed 19-reference warmup experiment passed the unchanged original
test before implementation. Its exact peak was not retained by default successful
capture; the log/XML proves only peak below 524288, not an exact number. That
single experiment did not establish module/full-suite robustness.

## Single owning-module verification: RED

The authorized verification was run exactly once, offline, using
`.codex_test_venv/Scripts/python.exe -B` and the existing
`C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py` launcher, selecting
only `tests/test_context_storage_ref_chunks.py`, with JUnit xunit1/logging=all.
External network connections remained blocked by that existing launcher.

Result: exit 1, **71 passed / 1 failed**, 72 total, 6.57s pytest time.

- Original existing ID: FAIL, real peak **993124 bytes**, zero retained control
  bytes, measured 12000 references, block 4096, chunk 1024, limit 524288.
- Additive negative control: PASS, real peak **1080581 bytes**, actual retained
  buffer 1048576 bytes. It completed real iterator/digest/byte checks and then
  caught the expected unchanged memory assertion.

Evidence:

- `C:/Projekt/BetBoy/output/context-completion-20261014/stream-memory-diagnosis/harness-module.log`
- `C:/Projekt/BetBoy/output/context-completion-20261014/stream-memory-diagnosis/harness-module.xml`

No whole suite was run by this implementer. Controller reports A stopped and its
failure log preserved, while B continues without importing this test module.
The skill's usual full-suite verification recommendation was explicitly bounded
by the controller's one-owning-module/no-full-QA instruction.

## Frozen review handoff, not completion

Owning test SHA256 after the single verification:
`9AF838EA40BFDC7531E15B80C49B3F0310818D6FB104F72D3C6DC8F97A8626DF`.
Source is frozen for independent review. No further attempts or adjustments made.
The fixed 19-reference warmup is **insufficient in this owning-module ordering**: a passing
standalone warmup diagnostic is not a module PASS. This test-only proposal is not
verified complete and must not be reported as a cold-peak/RSS production fix or
used to restart A as an accepted green gate. Next decision belongs to controller
and independent reviewer; the real peak failure remains open.
