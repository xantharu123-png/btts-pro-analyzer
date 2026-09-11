# Fresh30 capacity: bounded read-only analysis

Date: 2026-09-11. Inspected HEAD `bc9d268d1e70fa89dd1cfa387667ee32a04aa421`;
product remains `1c65ada`. Only this report is authored. No product/test edits,
index operation, commit, push, VPS access, broad test or native job by this
worker. Parent owns the separate native diagnostic and all acceptance.

## Decision

There are two distinct issues, which should not be conflated:

1. Current full-snapshot replay still repeats required row matching and
   lifecycle checks. Small strictly equivalent dispatch savings remain inside
   the existing five-file scope, but no measurement here proves enough margin
   for the fresh actual input. Removing checks or reusing decoded histories is
   not an admissible shortcut.
2. Beyond 30 distinct original query keys there is an additional **complete
   owned-prefix materialization** fallback. It is not automatically a cold
   source-validation fallback. A bounded rolling query-batch owner is a
   defensible follow-up design, preserving all caps and full snapshot calls,
   but needs an explicit internal scope/proof amendment and RED evidence.

No safe material current-input fix is established by this report. The latest
complete exact run remains failed, notwithstanding previous passing reviews,
fullsuite or the older26-snapshot input. Neither proposal is an arbitrary
future-growth guarantee.

## Inputs and boundaries actually inspected

Read complete Task9 brief/design/report/native evidence, recovery global and
capacity constraints, and the relevant current implementations of inventory,
cache, Tennis replay, source tail, v3 feature history, canonical encoding,
tracked SQLite lifecycle and original-query fold. Read earlier Task4/6/8
mechanism descriptions and relevant current tests. No applicable on-disk
AGENTS.md was found at the workspace/repository/worktree ancestors or within
the inspected source/test/SDD directories; the user-supplied instructions and
the dispatched read-only boundary apply. Historical memory was searched only
for project routing; no old checkout/deployment state is used as current proof.

Parent-supplied current evidence: exact265793536B/99774receipts/32artifacts/
30snapshots fails299.978CPU/300.233wall, child-9, no report, input unchanged;
peak486496KiB. Earlier26-snapshot actual253333504B input passed262.690CPU/
262.838wall. These are different inputs. Final fullsuite7292passed/30skips/
97subtests/1792s and approved final reviews do not override fresh native failure.

Parent's subsequent bounded native diagnostic, same source/input: first full
feature call entered after109.913seconds,20501rows, cProfile duration4.3025s.
Witness `_matches` cumulative4.0275;41002 selected-proof calls1.7058;
41002 inventory stamps1.5126; `_plain_json`945724recursive/20501root calls
1.3226 (all/generator work approximately1.2);20975 canonical calls0.8704;
82004 connection executes1.166, cursor construction0.2119. Unchanged feature
math was0.0576. These nested/profiled values are NOT additive or an
uninstrumented runtime forecast. The diagnostic ended after that complete
feature at116.634CPU/115.216wall (resource includes startup),346424KiB peak,
input unchanged. It grounds the dispatch/guard seam in actual cost, but is
neither a complete verifier result nor proof of a300second pass.

Frozen obligations: every original validates its actual publication/state/
native/capture and invokes its real predictor; every snapshot gets a fresh
complete tuple, all refs and unchanged feature/transport calls; physical/source
checks and independent cold seal remain complete. Caps stay1GiB input,
256MiB consumer history,64MiB aggregate retained+pending cache,30queries/
32aggregate slots, UID997/AS2GiB/CPU300/wall600/output1MiB and measured
CPU/wall<300/RSS<1GiB. No model/data/schema/helper change is proposed.

## Current repeated snapshot path

- `context_runtime_tennis.py:212-245`: `verify_live_snapshot` reloads its real
  original, obtains `_replay_history`, verifies all receipt refs, calls the
  unchanged `tennis_features_v3` inside the witness, then checks features and
  invokes real transport. All of this still executes for each snapshot.
- `context_runtime_history_cache.py:559-604`: exact lookup deserializes a fresh
  tuple; covering lookup deserializes each prefix row and checks before/after
  each decode plus final/empty completion. The prefix is not a retained cache.
- `context_models/tennis_v3.py:36-42,132-146`: the feature owner validates every
  input row before participant/event selection. Its later grouping/math is
  frozen; do not pre-prune the input or memoize its result.
- `context_runtime_history_cache.py:25-64`: each witness match performs the
  before-check, exact builtin JSON-tree eligibility, **full canonical bytes
  equality**, after-check and current entry/serial check. No row/digest-only
  witness can replace this.
- `context_runtime_history_cache.py:131-157` and
  `context_runtime_inventory.py:73-88`: each completed proof boundary asks the
  owning inventory for fresh transaction/write/main+temp schema state. The
  existing completed-proof branch already avoids a second duplicate cache
  schema read in that same boundary. Do not propose that prior optimization
  again, or batch/remove the actual before/after boundaries.

## Seam1: same checks, less Python dispatch

### Exact plain-tree guard

Location: `context_runtime_history_cache.py:25-32` only. Replace the recursive
`all(generator)` bodies with same-order recursive `for` loops and early False;
optionally hoist the fixed exact-builtin leaf-type tuple. Retain actual
`canonical_bytes(row) == raw` at line58, every source/cold validator, all
scope/proof/serial checks and the miss path unchanged.

Equivalence is local: dict keys still require `type(key) is str`; every value
and list element is still visited in the same order until the first False;
leaf membership is exactly the same five builtin leaf types (seven JSON
types including dict/list). No normalization,
numeric equality, hash-only comparison or caller authority is introduced. All
nonplain aliases remain optimization misses governed by the unchanged cold
owner. A recursive implementation retains no traversal stack outside its
call; do not replace it with an unbounded retained worklist or decoded pool.

Read-only Windows microbenchmark, quality Python with `-B`, using one real
persisted `_decode_receipt` result from
`.pytest_tmp/task9-new-3/test_wrong_or_prior_physical_p3/context.db` opened by
SQLite URI `mode=ro`. The actual1369B ESPN status row was augmented only with
the existing prospective evidence literals.100000 successful guard+canonical
comparisons, no monkeypatch or product edit:

| Variant | CPU seconds |
| --- | ---: |
| Existing recursive generators + unchanged canonical comparison |1.421875|
| Same recursive loops + unchanged canonical comparison |1.234375|
| Guard alone, existing / loops |0.593750 /0.453125|
| Separate repeat, existing / loops with fixed leaf-type tuple |1.359375 /1.125000|

Additional bounded read-only experiment used14 real persisted source rows
(4status,10workload,1272-1498canonical bytes) from these existing fixtures:
`.pytest_tmp/task9-exact-focus-1/test_whole_event_participant_a0/history.db`,
`test_duplicate_genuine_respons0/history.db` and
`test_later_terminal_status_wit0/history.db` under that same parent. Every row
passed the actual physical decoder and full selected cold owner before timing.
100000 comparisons, two repeats per subset:

| Subset | Existing CPU, repeats1/2 | Loop + fixed types CPU, repeats1/2 |
| --- | --- | --- |
| Mixed14rows |1.375000 /1.390625|1.109375 /1.125000|
| Status4rows |1.406250 /1.437500|1.203125 /1.468750|
| Workload10rows |1.515625 /1.562500|1.218750 /1.187500|

The second status repeat was slower, not hidden as an outlier or assigned an
unmeasured cause. These are local fixtures, not actual production rows, a
native workload mix, confidence interval or acceptance result. The dispatch
reduction is plausible but a robust native gain remains to be measured.
No time threshold belongs in a committed unit test. Appropriate RED is a
bounded delegating profile/call-count probe for eliminated generator dispatch,
plus independent exact guard outcome expectations; do not manufacture a new
semantic failure in already-correct source just to label it RED. Re-run the
existing actual wrapper/witness matrix for top-level/nested key/value aliases,
tuple/list/dict/string/int/float subclasses, accepted metadata aliases,
signedzero/bool/nonfinite, recursion/cycles and cold fallback, before/after
mutation, replacement, eviction, final/empty and exception deactivation.

### Optional companion: one local tracked cursor per schema boundary

Locations: `context_runtime_inventory.py:73-78` and the corresponding
`context_runtime_history_cache.py:106-111` cache schema reader. Present calls
to `connection.execute` each allocate a fresh `TrackedCursor` through unchanged
`context_runtime_transaction.py:49-56`. A short-lived local tracked cursor can
execute the same main then temp PRAGMAs, fetching both results and closing
before returning. Every SQL statement still passes through the unchanged
tracked cursor owner; every existing boundary still reads both fresh cookies.
This is allocation reduction, not stamp caching or fewer checks.

100000 in-memory checks with actual `TrackedConnection`, held transaction:
two-cursor path0.406250CPU, one-local-cursor path0.343750CPU; equal stamp output.
This tiny local experiment does not prove a material native saving. Retain the
old route for connection/mapping subclasses if their overridden dispatch would
otherwise be bypassed; exact internal-owner applicability needs review. Test
actual closed connections, main/temp DDL, rollback/restart/commit, interrupts
between cookies, cursor cleanup/reentrancy and permanently revoked proofs.
No shared long-lived cursor, raw untracked cursor, changed transaction module,
or substituted table-valued-PRAGMA SQL is proposed. The latter is not assumed
equivalent to real PRAGMA name resolution/shadowing/security semantics.

## Seam2: bounded rolling demand for original projections above30 keys

### What the code proves now

`context_runtime_history_cache.py:233-275` discovers/validates **every** actual
original and both tour maxima even after query space is exhausted. Only the
first fitting30 distinct `(event_key, cutoff, tour)` keys receive reservations.
Duplicate original references or snapshots need not consume distinct keys;
there is no proof from snapshot count alone that the31st snapshot crosses the
query cap. Byte pressure can drop queries even below30.

The complete basis still includes rows needed by excess originals. A missing
query returns None at `context_runtime_history_cache.py:500-507`.
`context_runtime_tennis.py:110-129` then requests
`_lookup_owned_original_history` (`context_runtime_history_cache.py:526-557`):
it deserializes the entire proved causal prefix, sums every canonical row size,
checks ownership before/after each row and completion, and returns a fresh
full tuple. The original then computes its target's newest multiplicity from
that tuple. This repeats for each unplanned original. It is **not** a full
cold source scan while a suitable owned basis survives. Full cold selection
is the later fallback only when that owned history is unavailable.

Existing tests prove correctness, not cheap excess processing:
`tests/test_context_runtime_coordinated_tennis.py:423-446` has37 real persisted
originals,30queries, two tour slots and37 predictors;
`tests/test_context_runtime_original_projection.py:598-615` has45 originals,
all45 predictors and still30queries. Thus raising caps is neither necessary
for correctness nor authorized, but this fallback can add replay work.

### Principled new owner, not an implemented mechanism

After an initial projected batch has been consumed, the fixed original
orchestrator could release its query metadata and prepare at most30 next
distinct actual-publication keys. Fold those requests together over each
existing complete, source-sealed **owned** tour basis using the unchanged
`_OriginalQuery.fold` (`context_runtime_original_projection.py:25-39`). Decode
one encoded row at a time, include all eligible bytes in each query's prefix
admission total, retain only its bounded scalar fold and candidate ordinal.
Bind queries to the exact current basis serial only after the whole fold and
final/empty lifetime checks succeed. Original actual native/state/predictor
checks stay at their existing individual replay positions. Full snapshots are
entirely unchanged. No new source seal or completeness marker is invented.

The first query batch is already folded during Task9's independent seal;
this proposal concerns **subsequent** demand only. A per-missing-query full
materialization is not the proposal, and blindly re-running the existing
planner merely fills the same first30 keys again.

This needs a controller scope/proof amendment before implementation. Required
design issues and RED boundaries:

- Requests come only from actual validated persisted publications of the fixed
  artifact mapping/generation. A direct `_lookup_original_native` call, cache
  object, caller key list or supplied completion flag cannot mint new query
  authority. Generic `_store` row seals remain insufficient.
- Advance a bounded planner without retaining all future publications/keys or
  changing original/predictor order. Reuse the already-required `checked`
  descriptor mapping as processed-reference membership, or a carefully owned
  resumable scan; define duplicate-key behavior across batches explicitly.
  Do not assume arbitrary SQL scan order or retain an uncharged future queue.
- At most30 live/pending query records and32 total slots, with both bases and
  all pending/query/key/serial/iterator metadata charged to the same64MiB pool.
  End old query/key/iterator frames before uncharging and reuse. No old batch
  aliases, decoded prefix, candidate pool or second encoding may survive.
- Every fold preserves before/after-row, before/after-fold and final/empty
  proof checks. Entry eviction, identical-byte replacement, main/temp DDL,
  write/end/restart/close, reentrant demand/store and interruption cancel or
  reject safely; no partial fold becomes query authority.
- Full-prefix admission must still precede absent/ambiguous-native rejection.
  Rows for other events, newer correction/status/workload/tour boundaries,
  equal timestamps and duplicate refs retain the existing exact fold semantics.
- RED with31/37/61+ distinct real originals must count one basis traversal per
  bounded new batch, not per missing original, while preserving all predictors,
  complete snapshot tuples/ref sets/features/transport and cold outcome parity.
  Keep pressure/no-owned-basis/query-zero fallback real and test longkeys,
  same-key repeats across batch boundaries and malformed excess publications.

This removes an avoidable *additional original* cost slope beyond query
capacity; it does not eliminate the mandatory per-snapshot cost or establish
that growing input remains below300seconds. A fresh30-key native failure may
occur entirely before this seam is relevant.

## Explicitly rejected substitutes and handoff

Do not repeat already implemented max-tour basis reuse, Task6 source witnesses,
Task8 initial original projections or Task9 physical/source co-traversal as
new findings. Do not remove the independent cold seal, cache features/results,
reuse decoded full tuples, trust identity/digest alone, lower validation
frequency, or change source/model/owner hashes dishonestly.

A second measured alternative compared the candidate recursively against a
fresh `json.loads(sealed_raw)` result: exact scalar/container types and string
key types, dict key-set equality independent of insertion order, exact list
length/order, finite floats with signedzero distinction. It has no retained
decoded pool. The same14 real persisted rows above,100000comparisons twice:

| Subset | Existing CPU, repeats1/2 | Typed comparison + decode CPU, repeats1/2 |
| --- | --- | --- |
| Mixed14rows |1.375000 /1.406250|1.156250 /1.281250|
| Status4rows |1.406250 /1.484375|1.250000 /1.250000|
| Workload10rows |1.296875 /1.328125|1.218750 /1.218750|

All timed comparisons matched, but no complete adversarial equivalence matrix
was claimed. This alternative was **not consistently better than the simpler
loop guard retaining real canonical-byte equality**. It replaces the literal
current witness contract and would require an explicit internal amendment and
new proof for scalar encoding injectivity, finite/signedzero float semantics,
every alias/exception case and transient row/byte lifetime during replacement.
No product use or equivalent acceptance is claimed; the additional proof scope
is not justified by these measurements. Likewise the previously
identified generic raw-payload reserialization opportunity is frozen and not
the proposal here.

Next decision belongs to the parent after its current exact native diagnostic:
attribute residual CPU first; choose the narrow dispatch optimization only if
its measured ceiling is useful, and treat rolling query batches separately as
growth-cost control. If unchanged full snapshot/feature work dominates and
these permitted savings cannot provide margin, report no demonstrated safe
capacity solution in the allowed scope; do not relabel the fresh failure or
increase limits. Exact current-first native acceptance, retained growth cases,
fresh final tests/review, backup/restore/HMAC and release gates remain required.
