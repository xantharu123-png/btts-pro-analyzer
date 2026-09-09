# Independent review: persisted context consumer reader

2026-09-09. Reviewer `/root/worker_failures_20260909`.

**Disposition: REQUEST CHANGES. Two P2 findings are reproducible on the frozen source.**

## Frozen target and scope

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-reader-review-20260909`.

Commit: `97cb672bea8d2e5ca2705f05e41a25eb9cab070b`, tracked tree clean before and after review.

Read completely: all three commit files, the approved context-model specification, Task18 brief/controller rulings, current pure public copy, the relevant complete B3 decoder/read path, established `dataset._reader` and runtime trust primitives. Actual imports/callsites were searched: outside its tests, the new reader is not called by a live consumer yet. Root's stated previous test outcomes are not counted as independent evidence.

| Frozen source/evidence | Raw SHA256 |
| --- | --- |
| `context_consumers.py` | `56f97df9cf133698d40b878a52be2ba27c01a69e010fc0c87e415eb38224af2b` |
| `tests/test_context_consumers.py` | `20dc712161b317d448f4c6ceefaa8c984a1cdd54e5324e913d1e2a743a553e6d` |
| `docs/audits/2026-09-09-d3-consumer-reader.md` | `b6bae944b22d2840931d5d8a8e17d67af3191fc7270f87e57e1fa45b47f594af` |
| `context_models/dataset.py` | `3b87304d86684bb0cae8e72b9cae6fe7f3fc5610e770b84b3a0568bb2b3e59e7` |
| `context_transport.py` | `d55e8ad4f81fc8a3958f48fe5e0a072e1640de8e6e5b9f694de794fafd3c9713` |
| `context_copy.py` | `f69678e5888aeddc21177d5660ca6bf9e220413a2653a3b2445efee4bab88683` |
| `context_snapshots.py` | `de9d8146917f568e1567cd8a92b92b64af1b33157f2afadf3c91c27a153de1da` |
| `runtime_paths.py` | `710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c` |

## F1 [P2] Claimed closed physical schema ignores generated columns

Location: `context_consumers.py:54`, the `PRAGMA table_info` equality check.

Reproduction: create a real valid B3 snapshot using the owning writer, then execute:

```sql
ALTER TABLE context_snapshots
ADD COLUMN unexpected TEXT GENERATED ALWAYS AS ('not-contract') VIRTUAL;
```

`table_info(context_snapshots)` still reports three columns; `table_xinfo(context_snapshots)` reports four. The reader accepts the altered table and returns its probability instead of rejecting the changed closed schema. The original payload and digest remain untouched, isolating the physical schema boundary. This is not claimed to have changed the selected probability; it defeats the explicit closed storage-schema contract.

Immutable RED: `test_reader_boundary_findings.py::test_closed_b3_table_rejects_generated_extra_column`.

Smallest correction agreed with Root: use the complete `table_xinfo` descriptor and exact expected columns with `hidden=0`; no permissive second schema or migration.

## F2 [P2] Read-only connection can overwrite an unrelated hardlinked SHM file

Locations: `context_consumers.py:48` uses `context_models/dataset.py:40-53`. The shared reader checks main-file/ancestor trust and main inode before/after connect, but not the physical `-wal`, `-shm`, or `-journal` companions. Nor does it reject a multiply linked main/companion file.

Actual NTFS reproduction, without symbolic-link privileges:

1. Produce a real valid B3 database, enable WAL and close it cleanly.
2. Create a separate non-database sentinel file with 88,064 bytes.
3. Create `models.db-shm` as a hardlink to that sentinel. Verify equal inode and `st_nlink == 2`.
4. Call the unchanged `load_context_market` with the valid reference/Event/cutoff.

The read returns the correct probability **and replaces the separate sentinel's bytes with 32,768 bytes of SQLite shared memory**. The input database and forecast need not be corrupt for the unrelated write to occur. All paths were isolated test files; no existing user or production file was touched.

Immutable RED: `test_reader_sidecar_qualification.py::test_read_does_not_overwrite_other_file_through_preexisting_shm_hardlink`.

A separate real symbolic-link counterpart is preserved, but skipped because this Windows host cannot create that symlink (WinError 1314). The real hardlink result does not depend on that skip or a mocked filesystem.

Root's bounded repair ruling: reuse the runtime trust primitives, validate the main file and every existing `-wal`, `-shm`, `-journal` as trusted regular, non-symlink, singly linked files with acceptable owner/permissions before SQLite opens and after opening. Keep the exact main/previous-companion identity checks. An already invalid companion must never be opened by SQLite. Apply the narrow shared context-reader guard, not a global SQLite change. A same-trusted-user replacement between checks remains a documented race limit, not an absolute race-proof claim. Normal live-WAL behavior must remain supported.

## WAL qualification: normal metadata is not a third finding

The first boundary file also contains an intentionally preserved initially overbroad assertion that reading a clean WAL database must not create any sidecars. It fails: a live SQLite read creates `-wal` and `-shm` synchronization files even with `mode=ro/query_only`. Root clarified that the live reader forbids data/schema/model publication, not ordinary trusted SQLite synchronization metadata. This failed assertion is therefore **not** a production finding and must not be made green by discarding live WAL data.

Do not replace this live reader with `immutable=1`, a raw-main-file copy, or the separately owned sealed D4 reader. A newly committed uncheckpointed snapshot must remain visible. Two independent passing tests prove that boundary:

- `test_new_committed_wal_row_is_visible_without_discarding_old_frozen_reference`: a real keeper read transaction retains the original snapshot while the owning writer commits a distinct `.71` prediction to WAL. The main-file bytes remain unchanged, the WAL has committed bytes, and the live reader sees the new reference while the old reference still returns its old value.
- `test_live_commit_between_schema_and_payload_queries_cannot_mix_revisions`: a writer commits corrupt bytes after the consumer has begun its schema snapshot but before its row query. The in-flight read consistently returns the old valid snapshot; a new read rejects the committed corruption. This uses real SQLite WAL transactions, not a mocked result row.

The first attempted positive live-WAL setup kept only an idle connection. On this Windows VFS that did not retain the WAL file after the second writer closed. Its assertion failed before calling the reader and is a **harness setup failure**, not another source finding. That entire first controls file remains unchanged; the qualified separate file pins an actual read transaction. The earlier controls file also contains a passing interleaving hook tied to `table_info`; after the planned `table_xinfo` correction, use the qualified file's query-bound interleaving control to avoid testing the old implementation's PRAGMA spelling.

## Other independent controls

36 passing cases in the first controls file establish:

- Current source path; malformed closed references rejected before database opening.
- Exact canonical persisted decision strings, not equivalent offset spelling, Python datetime, implicit current time or another cutoff.
- Whole expected competition, format, surface, indoor setting and native event key, in addition to Root's orientation/schedule tests.
- Real corrupt BLOB/SQLite-value types, duplicate JSON keys, nonfinite/truncated/invalid/noncanonical JSON and fresh rehashed wrong stored Event remain integrity errors, never requests to calculate a replacement.
- Repeated selected-market reads preserve main database bytes in normal DELETE mode, retain exact probability/parameters, have detached admin/public outputs, issue no INSERT/UPDATE/DELETE/CREATE/DROP/ALTER/REPLACE/ATTACH statements, and close every connection.
- A real main-file replacement between the precheck and open is detected even when replacement bytes are identical; the opened connection is closed on rejection.
- Explicit relative Unicode/space/percent/hash filenames are safely encoded as a read-only SQLite URI.
- Missing-row errors do not leak open connections.

Root's 375 reader/transport/copy/B3 tests were independently rerun on the frozen worktree, all passed. They include all five currently supported owning-family synthetic persisted cases, exact public summary, baseline/experimental/synthetic-applied roles, no source/model/writer invocation, and existing transport invariants. This is not a full-repository execution.

## Immutable probe and run ledger

All new files are under `.pytest_tmp/consumer-reader-independent-20260909/`. No existing tests, source, assertions, reports or Git state were changed. Every probe file remains exactly as first run, including the two disclosed non-source failures.

| Probe file | Raw SHA256 |
| --- | --- |
| `test_reader_boundary_findings.py` | `c22cee5ef34125d46a29fa0b90aa843ed4b2041d2b9e2f7fe67aa5577ac1e83b` |
| `test_reader_sidecar_qualification.py` | `5781925e83cac7bfa75161bb3c0f613093747e177022ed3a7800b05d107cdd41` |
| `test_reader_independent_controls.py` | `98d5ff690da56ed87ccc2481d32a08141b22e1470554c6efc40473a0d9398479` |
| `test_reader_wal_live_controls.py` | `7aa3e3a317c1e15bbfcba047f171c3c152a12577ad147cc8319efcd1523c13e5` |

Python: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`; each run uses a fresh `.pytest_tmp/consumer-reader-independent-<run>-01` basetemp and JUnit output in the frozen worktree.

| JUnit file in `.pytest_tmp/` | Actual result | SHA256 |
| --- | --- | --- |
| `consumer-reader-independent-boundaries-01.xml` | 2 failed, 0.75 s; F1 plus overbroad WAL assertion | `800e3184c2171905c482055d089827cdad31fb06afc2ceaa18649c716c93d998` |
| `consumer-reader-independent-sidecar-01.xml` | 1 failed, 1 skipped, 0.81 s; F2 plus unavailable real symlink | `ae4f3f0a562f089cad81d67de5b26137af93b042b5703759897be4563ace8ae4` |
| `consumer-reader-independent-controls-01.xml` | 36 passed, 1 failed, 1.61 s; one unpinned-WAL setup failure | `133827113a0060045c3376fce72998f497a68b04868a514e12dbfea00d16d7d4` |
| `consumer-reader-independent-wal-controls-01.xml` | 2 passed, 0.71 s | `b7de488ea9a56f77f4e124485c767c93c8d32261133959e207dc812a2aaf53b3` |
| `consumer-reader-independent-focus-01.xml` | 375 passed, 34.97 s | `26b15caba0d3cadf9e74933ac928bb78f1f3443ccbd65075b88595b66d178f7c` |

Literal execution totals: **413 passed, 4 failed, 1 skipped**. Interpretation is deliberately separate: two real findings, one superseded overbroad WAL expectation and one fixture setup failure. No failures are silently counted as successful tests.

For the eventual fix review, keep the original two finding test IDs unchanged, rerun all current owning tests, and use the two qualified WAL controls. The broad old controls can be retained selectively with their explicitly described obsolete setup/hooks excluded; do not rewrite their historical bytes to manufacture an all-green original run.

## Boundaries and handoff

The expected Event/cutoff/reference checks correctly bind an existing worker revision. This reader does not verify actual A1/B1 source truth or real D2 empirical authority. The light reader deliberately does not refit original recipes; it does not publish a new model. Live status invalidation remains a caller responsibility, and old snapshots are not rewritten.

No new provider capability, empirical model effect, complete D3 live consumer/UI integration, D4 release, browser acceptance, production execution or deployment is claimed. Cricket, prices, 15K, tickets and ledger behavior are unchanged by this additive source packet and this review.

Root has accepted the two findings and authorized a later separate bounded fix worktree. **No fix has been implemented during this review.** Root will independently review that future packet. This report, all original probes and all outputs are frozen as evidence against `97cb672`.
