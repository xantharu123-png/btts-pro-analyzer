# Task14 B0: bounded canonical-history sizing instrument

Date: 2026-09-12. Author scope: only this report and the two explicitly named
ignored diagnostic/test files. No production changes, SSH, Git/index action,
database migration, full D4 run, or deployment by this author.

## Fixed artifacts, ready for independent review

- `.pytest_tmp/probe_task14_growth_size.py`, SHA256
  `9b4d3a0f8501dda9d0ab0bb3714bcf4f59d5487d2ccdc5f23cefda56f07327f4`.
- `.pytest_tmp/test_task14_growth_size.py`, SHA256
  `eac0ef49826fdda95efe66414e414cd0022bae79c1dc8cd3f3e1cc1a963aa197`.
- Source: exact product revision `72421d3bdbec4ab15a3d2953cb153e867e7e340a`,
  `/var/lib/betboy-capacity-code-5es6n672/source`.
- Fresh sealed input: `/var/lib/betboy-live-backup-ssfvf5xs/context-current.db`,
  270,233,600 bytes, SHA256
  `73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa`.
  Root supplied these fresh backup facts; this author did not access the VPS.

Reviewed instructions: the complete approved Stage-B specification, its
conditional implementation plan, and Task13 growth-sizing report. Current
approval permits B0 and the new proof lifecycle, not raising the existing
256-MiB history / 1-GiB database / 64-MiB cache / 2-GiB AS limits.

## What this measures, precisely

The unchanged `context_runtime_tennis._cold_replay_history` selects each decoded
row with the unchanged `select_tennis_observations` owner, then charges exactly
`len(canonical_bytes(selected_row))` before appending. The history admission
counter does not charge an enclosing JSON tuple's brackets or commas.

The helper uses these same physical/source/canonical owners on one row at a
time and sums those exact byte lengths. It never retains a full generated
history, constructs a new model, supplies a synthetic validation flag, or
changes any existing row. For a deterministic given receipt set, the byte sum
is independent of iteration order; its additional length-framed stream digest
binds the diagnostic order without pretending to be a production proof.

### Baseline mode

1. UID997, exact root-owned unwriteable source/input paths, no symlinks or
   database companions, complete input SHA, source pins, and identities checked
   before source imports. Native execution must be `python -I -B` with the
   environment and process supervision specified by root.
2. Read-only immutable SQLite connection only to that sealed copy; fixed
   row/payload/output bounds and quick_check. All artifact headers are inspected
   before any body decode. The complete artifact set must contain exclusively
   `tennis-tour-state` and `tennis-live-winner-original-v1`; full artifact
   envelopes are then decoded through `_load_artifact`, and original headers
   through `validate_original_publication`.
3. This narrow fixture has no D2/approval artifact capable of declaring unopened
   protected finals. It matches the frozen `verify_d2_artifacts` early branch.
   **Unrelated `match_outcome` receipts are retained, physically decoded, and
   counted**. A new D2/approval/unknown artifact aborts before receipt body decode;
   this is not a generic safe decoder for arbitrary D2 datasets.
4. Every stored receipt is physically decoded before source/tour pruning. Both
   tour histories are selected using their unchanged owning API. Baseline
   canonical row/byte counts, min/max row bytes and framed digests are exact.
   The future cutoff is after every current receipt/original/creation clock;
   all existing causal rows remain included in the later size probe.
5. Existing snapshots are decoded by `_decode_snapshot`; actual raw payload
   bytes and full canonical observation-reference array bytes/counts are
   recorded by cutoff. Prefix byte/count measurements describe the current
   source selection. A reference-count match is explicitly not full feature,
   transport or original replay equivalence.
6. Actual content/artifact/snapshot payload totals, page size/count/freelist and
   dbstat table/index aggregates (if SQLite provides dbstat) are emitted.
   Source/input/ancestor seals and exact identities are freshly rechecked at
   the end. Python version, SQLite version and interpreter realpath/hash are
   runtime metadata only, not a completed Stage-B transitive runtime closure.

### One-day generated mode

The probe adds at most 70,000 wholly new scheduled ATP status receipts for one
specified day, with deterministic unique fixed-width native event IDs and
future actual receipt clocks. The chosen native namespace is confirmed absent
from the baseline. No source request is performed and these events are never
described as real matches or upstream provider facts.

Each new competition traverses `normalize_tennis_status`; the closed content
and receipt envelope are canonicalized through the real owners and physically
decoded by `_decode_receipt`, then consumed by the actual ATP selector. The
stream maintains exact generated row/content/selected-byte counts and digest.

The arguments carry the preceding **externally verified measurements**:
baseline ATP row/byte counts, prior completed generated row/byte counts, and
the SHA of the preceding diagnostic evidence. These are neither an HMAC proof
nor automatically self-authenticating numbers. Root must compare each argument
with the exact completed baseline/previous output, preserve evidence hashes,
and sum all native CPU/wall costs. Missing prior row counts cannot start a
later day; a previous partial day cannot be skipped.

At the first actual selected row that makes the combined canonical byte sum
exceed 268,435,456, generation stops immediately. It records a partial day and
zero generated snapshots/database files. For the declared ATP-heavy scenario,
that is a **necessary-condition StorageSTOP**: unchanged full-history admission
would reject that exact receipt set regardless of a future proof cache.

This is not a measurement of a physically grown database and not a completed
199-snapshot/7-day fixture. It proves no SQLite file-size upper/lower bound,
model/feature validity, or supported production range. If no necessary-size
failure occurs, proper owner-produced snapshots, actual database/index size,
mixed-tour/burst controls and full B0 acceptance still remain necessary.

## Execution/resource contract

Native modes are `baseline` or
`generated DAY BASE_ROWS BASE_BYTES PRIOR_ROWS PRIOR_BYTES EVIDENCE_SHA`.
The script is sent on stdin; there are no native writes. Main enforces AS2GiB,
CPU300 hard, diagnostic CPU280/wall285 interruptions and RSS<1GiB. Root adds
controlled external timeout/process-group cleanup and whole-invocation resource
measurement. Output is at most 520 metadata records / 1MiB; arbitrary persisted
values and exception text are never printed. A timeout, owner failure, missing
summary, post-seal mismatch or excess RSS cannot count as completed measurement.

Baseline and generated chunks are separate **diagnostic** processes, never
relabelled as a single passing old D4 run. Root owns the explicit cumulative
1800-CPU/3600-wall B0 budget, including already spent backup/preparation work.
Stop after a demonstrated necessary-condition failure; do not keep creating
unused history for an attractive completion count.

## Local checks and review changes

Final command, active recovery worktree as cwd:

`C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B .pytest_tmp/test_task14_growth_size.py`

**8 tests passed in 0.139s**, final helper SHA above. Includes per-tour cold
exact-cap success/cap-minus-one rejection; empty history at zero; eight real
append/read roundtrips including day-boundary IDs and idempotence; unique
fixed-width native IDs; physical outer-field tamper rejection; D2 guard before
body decoder; first exact overflow with no full-day claim; and rejected missing
prior chunk. ATP/WTA/future receipts are present in the equivalence fixture.

The first launch against the inherited `.venv` could not start its missing
Python312 host executable. No environment was changed. A first bundled-runtime
test exposed the diagnostic test's own unclosed read connection during Windows
temporary cleanup; explicit `closing` fixed that test-only issue. The final
roundtrip and all eight checks pass. The one abandoned isolated temporary test
directory was left untouched; it contains synthetic QA data only.

Independent reviewer requested two additional source pins
(`context_models/tennis_live.py`, `context_runtime_semantics.py`), runtime identity
metadata and full post-run source/input/ancestor revalidation. These narrow
corrections are included in the final helper; post-check failures emit only the
fixed exception class and an incomplete summary. Independent final review and
actual native execution/results remain root-owned and pending at report writing.
