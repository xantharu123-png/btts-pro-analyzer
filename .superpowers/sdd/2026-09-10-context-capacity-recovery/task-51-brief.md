# Task 51 — actual C Tennis consumer bridge

Resume the existing unfinished Task51 after Root explicitly activates it.
This connects the approved storage mode to the genuine existing prediction
owner. It must not change model math, odds, source admission, or the live app.

## Ownership and API

Only new `context_storage_v2/tennis_consumer.py`,
`tests/test_context_storage_tennis_consumer.py`, and this directory's
`task-51-report.md`. Preserve the inherited RED test file. Root alone owns
integration/index/commits/server. No agents, old-module edits, deployments,
source mutation, dependency install or artifact deletion.

```python
prepare_tennis_consumer(history, *, native_competition, tournament_id,
    grouping_slug, observed_at, surface, best_of, indoor, cutoff,
    work_directory, owned_directory, main_cap_bytes)
put_tennis_consumer(connection, prepared, *, created_at)
```

The prepared object has an actual live HistoryView/Source and actual
StreamingTennisFeatures. No public-hash dataclass resurrection or fake history.
Its context manager owns and closes only its feature lifetime; the caller
retains source/history and output transaction ownership.

## Required real dataflow

1. Read the actual active ATP or WTA state from the same held source connection.
   Reuse existing in-connection reads and state parsing, not path loaders that
   open/schema/commit an unrelated legacy writer.
2. Normalize the supplied actual native competition using the old owner. Bind
   to its actual already-stored receipt; no new capture insert or manufactured
   protected-empty/native-reference proof. Missing, stale, mismatched, ambiguous
   or wrong-tour native/state bindings retain old rejection semantics.
3. Call actual predict_match with a once-only same-call original_capture. Bind
   those real inputs and unrounded values, current source state/code/cutoff and
   complete corresponding history. original_base alone is not a prediction.
4. Build actual streaming Tennis features in the fixed owned directory with
   the existing main cap. Reuse pure eligibility/comparison/result-selection
   functions. Preserve unresolved native_state_identity and genuine effect/
   approval outcomes; no fictitious model/source acceptance.
5. The output caller supplies an already active owned transaction. Use a
   savepoint to write the actual Original artifact plus complete reference sets
   and snapshot parts. No own connection, outer commit, schema side effects
   outside that owned output, or partial-success result.
6. Calculate/check the full observation membership, feature-reference subset,
   snapshot key, raw canonical bytes and legacy payload digest with bounded
   iteration. Do not feed a fake list or shortened history into the legacy
   full-list calculate_context_payload contract.
7. All operations recheck actual source/history/feature/transaction lifetimes.
   Collision, source change, released prepared state, wrong generation, SQL
   FULL/TOOBIG or late cleanup failure must not authorize a result.

## Bounds and already adjudicated ambiguity

The 16MiB processing block is NOT an extra per-value SQLite/model/artifact
admission cap. The 64MiB legacy image limit is NOT a C-artifact cap either.
Observe/bind the needed actual physical types and bytes before the old artifact
owners load them, but preserve existing JSON/D2 admission. Native AS/RSS may
still produce a necessary STOP; this task does not claim that A1/D2 fully
streams. State any real unresolved allocation issue explicitly.

The existing C2 non-observation header cap is 1MiB; it may bound the actual
canonical feature header. Full tour histories/observation references must
stream and must not be collected because the small differential fixture fits.

Root's recorded implementation ruling: a bounded read-only physical metadata
scan over the actual artifact/manifest rows may precede the existing recursive
artifact owners. Bind rowids, actual SQLite types, byte lengths and framing
incrementally; do not collect all payloads/keys or treat that metadata digest
as D2 authority. The held Source's complete file identity remains the byte
binding, and the old owners retain actual consumed-JSON/type/semantic admission.
Unrelated opaque rows do not acquire a new JSON restriction. Keep source and
transaction lifetime checks through the final operation. This preserves the
old owners without claiming that their full A1/D2 allocations are streaming;
native allocation and the fresh Corpus/D2 integration remain later checks.
The three actual tables use the unchanged closed `context_runtime._SCHEMA`
ordinary rowid definitions; C RawInventory already reads their actual rowids.
Bind those real integer rowids in deterministic traversal. There is no new
WITHOUT ROWID fallback or schema variant in this task.

At continuation the inherited test fixture still called
`con.setlimit(SQLITE_LIMIT_LENGTH, DEFAULT_LIMITS.block_bytes)` even though
the above per-value-cap proposal was rejected. Remove that accidental fixture
admission change and include a relevant real-value boundary test; don't change
the source owner's policy to manufacture a test pass.

## Validation and report

Actual small legacy capture/predict/persist/finish is the independent oracle:
same stored states and native bytes, same unrounded result, Original canonical
bytes/hash, complete features, complete snapshot bytes/key and selection reason.
ATP and WTA, effect/approval absence, ambiguity and wrong-surface outcomes must
remain distinguishable. Existing tests are incomplete TDD, not completion.
Keep legacy Daily/Shadow only as test oracle, never call it from the new bridge.

Use the already working .pytest_tmp/qa-python312-c-01 Python, fresh retained
basetemp/XML paths, disabled external plugin autoload, no cache provider. Record
actual initial RED failures and final commands, hashes, results and limitations
in task-51-report.md. Do not run broad unchanged suites without a named risk.

This is not the entire small Corpus->History->Consumer integration, the global
590553-receipt/199-consumer growth owner, native capacity, empirical injuries/
fatigue acceptance, authenticated B verifier, restore or production release.
Return concise status, report path, test summary and concrete concerns only.

## Independent review fix round 1 — post-footprint input lifetime

Fix BASE is f777e9ea2b6313e187d911877f5669a832ee5786. Read the exact Important
P1 in task-51-independent-review.md. The final consumer input check precedes
`refs._atomic`'s own post-yield filesystem footprint check; that later I/O can
lose a real source/history/feature lifetime before savepoint release.

Root scope ruling: keep the existing shared rollback owner, extending its
private `_atomic` API only if needed with an optional final input validator
after its existing footprint check and before releasing that savepoint. The
ordinary no-validator paths must remain unchanged. A validator failure belongs
inside the same existing rollback/error-conversion scope. Do not duplicate the
transaction mechanism in the new consumer or stack another final footprint
operation after the last input check. The bound consumer guard is a live check,
not a serializable success token or new source/model authority.

In addition to the original three owned files, this round may edit only
`context_storage_v2/refs.py` and `tests/test_context_storage_refs.py` for that
narrow existing-owner seam. No schema/format/default limit changes. Root owns
the brief, ledger, review report and Git. Reproduce the actual late disk-usage
failure first by closing the genuine feature owner, then test full rollback to
the caller's prior marker/no Published result, unchanged caller transaction,
ordinary successful path, one final validator call and validator-error handling.

Cover changed consumer and refs modules plus genuinely affected existing
`test_context_storage_snapshots.py`, `test_context_storage_ref_chunks.py` and
`test_context_storage_snapshot_source.py`. No full704/project rerun merely to
repeat unaffected history/model tests. Keep all initial RED and final artifacts,
exact commands, byte pins and remaining bounds in an appended fix-round report.
Return a coherent freeze/sole-writer handback for scoped independent re-review.
