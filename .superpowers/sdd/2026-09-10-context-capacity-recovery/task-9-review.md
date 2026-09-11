# Task9 independent combined SPEC + CODE QUALITY review

Date: 2026-09-11. Scope: Task9 only; not the final whole-branch or release review.

BASE: `d138ac5b14e94ac37a6b089bf3efbda3a7dc0c92`.
HEAD: `1c65adae1e9de85a6d457cf452f21c4d9cbb589e`.
Package: `review-d138ac5..1c65ada.diff`, 84508 bytes, independently verified
SHA256 `be0bace35d8fbfe712a2a74a6768f4c234c8e492fc1faa7bf63757218c80d5f5`.

Read the complete immutable change package, Task9 brief, design analysis and
implementation report, and current progress.md Task9 scope rulings. Inspected
real physical/source validators, cache/projection owners, original/snapshot
callers and targeted tests. The disappeared superpowers package was not used
or represented as executed; this is the dispatched manual immutable-package
review. Author assertions were checked against code and independent executions.

## Findings

- Critical: none.
- Important: none.
- Minor: none actionable in the reviewed Task9 delta.

There is no defect/reproduction location to report. Scoped SPEC compliance and
CODE QUALITY are APPROVED, subject to the distinct acceptance gates below.

## Contract and implementation assessment

- `context_runtime_inventory.py`: ordinary and coordinated paths share the
  complete content/receipt/orphan implementation. The new unfiltered ordered
  LEFT JOIN retains physical decoding of all ordinary receipts, and opaque
  protected final bodies remain unopened. The unchanged real `_decode_receipt`
  precedes the complete shared source tail in one non-yielding owning frame;
  decoded rows are not exposed to an intermediate consumer.
- `context_sources/tennis_status.py`: only the source tail was factored. The
  public cold prefix still performs closed B1/generic/hash/evidence checks.
  Status payload/reception and canonical expected-envelope checks remain;
  workload kind/format and its unchanged full validator remain. Replacing the
  already canonically equal normalized payload/event values with row values
  does not substitute Python equality or relax signed-zero/type distinctions.
- Exact artifact/receipt mapping classes, identical connection/generation and
  persisted creation timestamps own planning. All originals are visited,
  including unreferenced/excess-query publications. Both tour maxima govern
  source eligibility before own-tour retention; optional queries do not prune
  source evidence. Dict/subclass/foreign/already-validated paths confer no new
  completion authority.
- Planning/source domain deferral is narrow. Physical decode is outside the
  source catch. Deferred source failure ends its exception frame, clears all
  optional tours, finishes physical validation and hands back to real ordinary
  cold planning/selection. SQLite/lifetime/resource/interrupt failures propagate.
  Final physical corruption or orphan evidence cannot be hidden by an earlier
  source or planning error.
- The one-time preproof transition is in the completed physical/source owner,
  after the final inventory stamp. Each retained encoding then undergoes an
  independent fresh JSON decode and full cold selected validation. Row seals
  alone do not grant aggregate completeness: that owner binds exact entry
  serials and actual artifact mapping afterward. No global proof check was
  weakened, and direct/subset stores cannot acquire that authority.
- There is one retained-plus-pending byte pool. Two tour bases, bounded query
  and planning metadata, and serialized owned markers stay charged. The new
  query-binding helper defers uncharge until dropped-key/draft/iterator locals
  die. Pending encodings transfer references rather than duplicate encoded
  content; source row and encoded work locals are explicitly released before
  optional cancellation. Reentrant storage cancels preparation; recursive
  physical verification fails closed. Final/empty and serial checks remain.
- Runtime still verifies each actual original/native/state/predictor and sends
  full fresh histories through snapshot feature/transport replay. Whole-prefix
  admission remains before native absence/ambiguity. No model/math/CODE_PATHS,
  source data, schemas, snapshot/report contract, deploy helper or resource cap
  change appears in the exact seven-file diff.

## Independent verification

Quality executable for pytest:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Flags: `-B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning`.

1. `--basetemp=.pytest_tmp/task9-independent-01`
   `tests/test_context_runtime_coordinated_tennis.py`
   `tests/test_tennis_check_equivalence.py`
   `tests/test_context_runtime_receipt_witness.py`
   `tests/test_context_runtime_original_projection.py`:
   **365 passed, 0 skipped, 114.87s**.
   Includes delegating physical/generic/full-seal/predictor counts, real full
   snapshot tuples, source/cold rejection, unequal maxima, actual lifetime
   probes, pressure/marker fit, all 37 persisted original publications,
   direct-store poisoning, public aliases and transaction/schema boundaries.
2. `--basetemp=.pytest_tmp/task9-independent-02`
   `tests/test_context_runtime_capacity.py`
   `-k 'complete or physical or validated_cutoff or permanently or unordered or orphan'`:
   **32 passed, 111 deselected, 0 skipped, 8.35s**.
   Checks the shared generic inventory's complete/cutoff/physical boundaries.
3. A reviewer-authored transient Python harness, without product/test edits,
   constructed **12 additional actual persisted workload cases** using real
   `_stored`, normalized source records and `append_observation`. For ATP and
   opposite-tour WTA, valid rows produced byte-identical retained versus full
   cold ATP history; sets, future end-time, revision, kind and format defects
   each completed the physical pass, returned no cache and were then rejected
   by actual `verify_live_originals` cold preparation. All 12 passed. Fixture
   evidence remains in `.pytest_tmp/task9-independent-source-sbmdih31`.
4. `git diff --check BASE HEAD` passed. Explicit working-tree comparison to
   reviewed HEAD showed no changes in the five product modules or new test
   module before/after verification. Only this review file is reviewer-authored;
   controller documentation WIP is untouched. No index mutation, commit, push,
   full repository suite, SSH/VPS action or subagent was performed.

These independent executions do not relabel the author's 1109-pass focused
run, later 75-case run, separate one-case generic strengthening, or development
oracle counts as reviewer reruns. The author's 71/178 immutable-oracle outcomes
remain explicitly author-reported additional evidence.

## Acceptance boundary

APPROVED is only this Task9 correctness/maintainability review. Native exact
current-input measurement comes first; fresh G1-G3 plus retained historical
largest, actual SQL sort/resource behavior, native skipped controls, whole
repository suite, final whole-branch review, fresh full backup/actual restore/
HMAC and separate release/deployment gates remain controller work. No native
speedup, 300-second pass, empirical/model approval or production readiness is
inferred. Prior actual-current failure remains release-HOLD until replaced by
fresh exact-source acceptance evidence.

Final status: **APPROVED**.
