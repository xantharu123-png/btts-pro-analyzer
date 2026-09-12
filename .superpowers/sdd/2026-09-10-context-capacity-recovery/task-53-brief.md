# Task 53 — preserve old large-row admission through History and Tennis

Follow-on correction within approved C3/C4/C6, before unfinished Task51.
Base product: a52b4b7ed46bb6e8c67d0b90c516163a7c2566fe.
Read this brief first, then the concrete Task52 audit and the owning code.
Task52 is a confirmed defect, not an invitation to re-audit without fixing it.

## Ownership

Modify only `context_storage_v2/history.py`, `context_storage_v2/tennis.py`,
their focused tests (including a new large-row regression module if useful),
and this directory's `task-53-report.md`. Existing adjacent assertions may be
updated only when this actual format/admission contract changes them.
Do not edit old source/model/feature/original owners or Task51's WIP. No Git,
server, dependency, other-agent, cleanup or production operations. Root owns
integration/index/commit and independently reviews this task.

## Binding constraints

Approved C: `docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md`,
SHA256 08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba.
Its historical unapproved heading is superseded by the user and ledger.

- All old source, physical, opaque-final, ordering, cutoff, conflict and math
  semantics remain unchanged. Small old paths remain independent byte oracles.
- Active full inputs <=4GiB; full canonical selected history <=1GiB/tour;
  new reference/processing blocks <=16MiB encoded; total new workspace/QA and
  retries <=8GiB; free reserve >=4GiB. Limits can tighten, never silently widen.
- Existing worker CPU300s/AS2GiB/RSS<1GiB/output1MiB and global preparation
  CPU1800s/elapsed3600s remain mandatory later native/global gates.
- Neither 16MiB processing blocks nor the old 64MiB whole legacy image is an
  old per-value admission cap. No new SQLITE_LIMIT_LENGTH for old objects.
- C4: "Eine einzelne große Altstruktur muss unter ihrem bisherigen Lesevertrag
  bleiben oder erhält einen eigens geprüften Adapter". Do not change the frozen
  spec to make a test pass. One old object may still be allocated by the actual
  old reader; blockwise hashing does not retrospectively bound that allocation.

## Confirmed RED and engineering ruling

`task-52-history-value-audit.md` and retained
`.pytest_tmp/task52-history-value-probe.py` show an actual native scheduled
status name of 16777217 bytes. The genuine source normalizer, append,
VerifiedReceiptMapping.validate_all and old cold replay all accept it; selected
canonical row is 16778570 bytes, entire legacy DB 16838656 bytes. New History
rejects only because the row exceeds the unchanged default processing block.
Tennis has the same next rejection at its complete pre-projection validation.
The audit's 1 passed means the probe ran and recorded rejection, not GREEN.

Ruling: use an explicit source-backed large-row mode on the already held real
Source/History lifetime. Keep small inline canonical rows. Do not introduce an
independent chunk store, callback loader, large decoded cache or new admission
restriction merely to solve this coupling. This preserves C4's actual old
reader exception; native allocation/performance remains an explicit later gate.

## Required implementation

1. Complete physical traversal/selection/seen/opaque-final rules stay intact.
   Only an actually source-validated selected row may enter the large mode.
   Record explicit mode, receipt/content identities, ordering/event fields,
   actual full selected canonical size and SHA rather than duplicating its
   oversized canonical payload. Small inline mode must be unambiguous. Preserve
   old admissible large index values too; do not turn locator metadata into a
   new hidden value cap or claim SQL logical key allocation is a bounded block.
2. Resolve a large row by its exact receipt key on the same held Source using
   base SQL, actual VerifiedReceiptMapping._decode_row and actual source
   selection. Check complete reconstructed canonical identity/length and all
   indexed metadata, tour and cutoff. No just-hash proof, mutable dict reuse,
   source reopen, caller proof flag or swallowing a source validation exception.
3. All History iteration, as_of, event/latest and build-end verification use
   the same resolver. Check source/view lifetimes before and after resolution
   and yield resumption; source/parent close or generation drift poisons reads.
   No full tuple/event-group/seen set materialization. Preserve total order.
4. Full selected digest remains the exact sequence of
   uint64_be(len(canonical_row)) || canonical_row, not a hash of row hashes.
   Count full canonical row bytes toward the tour limit even with small
   locators. Process hash updates in bounded chunks while honestly retaining
   old per-object decoding/canonicalization. The existing tour/input limits
   bound that old object in this mode, not a new arbitrary per-row constant.
5. Remove the duplicate Tennis processing-block admission rejection without
   removing its complete cold source validation before participant projection.
   Chosen large workloads must not become oversized new canonical BLOBs at
   tennis_chosen. Prefer storing bound History receipt references for chosen
   rows (all chosen rows may use that single representation) and resolving via
   the owning view while preserving sequence, side and association exactly.
   A large scheduled-status test alone does not exercise this workload seam.
6. Version the changed private History format (v3) and Tennis staging format
   if changed (v3). Do not change semantic feature/source/selection versions,
   historical code hashes, old public artifacts or live consumers.
7. Existing fixed writer reservations/profiles, source policy, end checks,
   unpublished-failure retention and exact dependency identities stay intact.
   No partial return after limit/transaction/close/canonical mismatch failures.

## TDD and scoped verification

Start with a genuine default-block large-status regression that fails on the
confirmed old new-builder rejection. Compare full bytes to the unchanged old
source/replay and old Tennis features; preserve source SHA and transaction.
Cover repeat/prefix/event/latest reads and a genuinely usable selected workload
larger than a tightened processing block, also compared to old feature output.
Small oracle fixtures can materialize; new product loops cannot use that excuse.
Exercise mixed inline/reference rows, ordering/ties, complete byte/count/digest
budgets, changed source/view lifetime between yields and invalid locator or
resolved-row identity. Verify source SQL value limit remains unchanged.
Adjudicated old test: the `block` case in
`test_hard_budgets_do_not_return_a_partial_history` must not retain its incorrect
per-row-cap assertion; replace it with real bounded-format behavior. Tour/input/
workspace/free failures must remain tested. Do not manufacture invalid input
or alter source validators to force a desired outcome.

Use `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`, external pytest plugins
disabled, -B and no cacheprovider, fresh unused retained basetemp/XML per run.
Run focused new tests during edits; one relevant History/Tennis/profile/source
adapter regression at the final freeze. Do not run the whole product suite.
Record exact RED/GREEN commands, true results, changed file hashes and remaining
native/allocation boundaries in task-53-report.md. Return only concise status,
test summary, report path and any concrete unresolved concern.

Task53 is not Task51, the complete small producer chain, a measured growth or
global budget pass, B, empirical injuries/fatigue approval, restore or rollout.

## Pre-review correction ruling after freeze07

Actual freeze07:422 passed/1 failed,475.32s, two warnings. The 65536-byte
real-FULL assertion now fits with the changed representation; retain true
4096/32768 FULL failures and explicitly verify the actual 65536 outcome for
the final chosen format. Correct _union_refs generator teardown before closing
its writer (focused RED first). Use -o junit_family=xunit1 for existing
record_property tests; do not alter that source-adapter test to suppress noise.

The all-reference chosen-row format was optional, not a required new contract.
Actual unchanged paired test is6.439s versus retained old1.406/1.470s; the
78-match/156-receipt floating-sum test is70.005s versus16.861/18.388s. Historical
walltimes alone are not a controlled causal/native benchmark, but the repeated
owning lookup is a concrete new work path. Ruling: keep bounded small chosen
rows inline and use explicit owning History references only when their actual
canonical value exceeds the processing block. Preserve source/view checks,
exact metadata/association and all full cold validations; do not remove those
to gain time. Record a focused before/after measurement using the existing
paired and summation tests and the exact-byte large-workload regression before
the final combined rerun. No strict flaky walltime assertion and no native-fit
claim. If the named change does not account for the cost, report that evidence
rather than stack speculative optimizations. Cost if wrong: scoped format/test
rework, not changed math, source admission, caps or hidden data pruning.
