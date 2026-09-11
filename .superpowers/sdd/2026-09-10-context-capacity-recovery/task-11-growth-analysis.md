# Task11 growth feasibility: original overflow and repeated prefixes

Date: 2026-09-11. Diagnosis/proposal only, **not implementation approval**.
Inspected current source against exact `72421d3bdbec4ab15a3d2953cb153e867e7e340a`;
`git diff --name-only` for cache/Tennis replay/original-query modules is empty.
Current HEAD0f074a2 is a later documentation checkpoint, not different inspected
product bytes. Only this report is authored. No product/test/helper/index edit,
SSH, fullsuite, native job or subagent by this worker.

## Decision

**After actual G1 attribution: no demonstrated material optimization remains
that preserves the literal before/after/final check frequency for every
consumer.** The measured overflow-original opportunity is only1.360743CPU
seconds total. Rolling batches must still perform that first scan. The larger
prefix opportunity would change repeat consumers from covering reconstruction
to the existing exact-hit contract; it cannot be represented as unchanged
per-consumer check frequency. See the final attribution/ruling section below.

The previous rolling-query-batch idea is **not a defensible primary G1 fix**:
with one overflow query it still needs one complete basis traversal. It can
share that traversal only when multiple excess keys exist. Do not describe the
current overflow as repeated cold source validation: it normally consumes a
complete owned encoding without another cold validator pass.

There is a separate, structurally material candidate: learn bounded,
non-owning **exact-prefix derivation metadata** after a successful full covering
lookup, then let a repeated identical cutoff use the existing exact-cache-hit
contract. Preserve the first covering traversal and every snapshot's fresh
tuple, refs, full feature/witness/transport call. No duplicate encoded pool,
decoded cache, new source seal, result cache or larger resource cap is needed.
This requires an explicit internal proof/lookup-contract amendment, detailed
below. If the instruction instead requires every later same-cutoff invocation
to retain all covering per-row checks, this proposal is out of scope: its
saving comes precisely from an already-completed prefix becoming an exact hit.

Neither proposal has proved a300second pass. The completed bounded diagnostic
below does not supply a full G1 runtime or the removable repeated-prefix
fraction; all31/32/33controls must still pass separately.

## Current evidence and exact cost paths

Controller's complete uninstrumented native outcomes on exact72421d3:

- Actual30:288.095CPU/288.261wall,485440KiB, complete PASS.
- Strong G1,31distinct keys:299.975CPU/300.165wall,485792KiB, child-9,
  **no report**, exact input SHA04e7db...94b unchanged. This is a right-censored
  failure, not a completed300second runtime. G2/G3 D4 results are not supplied.

`context_runtime_history_cache.py:269-311` plans at most30 distinct
`(event_key,cutoff,tour)` queries but still validates all originals and discovers
both tour maxima. `:536-560` returns no projection for a missing reservation.
`context_runtime_tennis.py:110-129` then calls
`context_runtime_history_cache.py:562-593` to decode the entire owned causal
prefix, perform per-row/final lifetime checks, sum every canonical byte and
return the full tuple. Only absent suitable owned evidence reaches real cold
selection. Native multiplicity is then selected from that complete tuple.

A new later-cutoff consumer also advances the shared basis maximum. Previous
maximum-cutoff snapshots cease to be exact hits (`cache:595-611`) and become
covering lookups (`cache:613-640`). The former deserializes a fresh tuple with
edge checks; the latter additionally checks before/after each row. Therefore
G1 adds more than one original and one snapshot: it can make old snapshots
more expensive even when their own causal histories are byte-identical.

## Two bounded read-only local checks

Used actual persisted fixtures, SQLite URI `mode=ro`, query_only and held
`TrackedConnection`; delegating spies counted existing owners. No validator or
result was replaced with an accepting mock, and no candidate code was installed.

1. `.pytest_tmp/task9-complete-new-1/test_all_excess_persisted_orig0/context.db`:
   actual coordinated preparation plus every original native candidate gave
   37distinct keys,30planned queries,2owned bases,7owned-full calls and **zero
   cold calls**. All native receipt identities matched. The tiny fixture has
   one row per relevant history, so its time is not a production-cost estimate.
   Input SHA was unchanged. None of its missing keys had an existing same-cutoff
   query or was the basis maximum: such reuse cannot be assumed universally.
2. `.pytest_tmp/task9-complete-new-1/test_full_verification_decodes0/context.db`:
   complete real `_verify_connection` checked11artifacts/10receipts/10snapshots.
   Five cutoffs occur twice, deliberately interleaved. There were8covering and
   2exact history calls. Each10-row covering made22cache `_check` calls versus
   2for an exact hit; the covering's additional inventory validation remains
   separate. Four repeated covering derivations are observable redundant work
   if complete exact-prefix metadata may be memoized. No native time or full
   production equivalence is inferred from this10-row fixture.

## Proposal A: rolling query batches, with an honest ceiling

Keep initial30queries folded during the existing independent cold seal. After
a verified original batch is consumed, a fixed actual-publication owner could
release its reservations and fold a next batch of at most30keys together over
the existing complete source-sealed owned basis, using unchanged
`context_runtime_original_projection._OriginalQuery.fold` (`:25-39`). All
physical/source/cold seals already required still execute unchanged.

For `m` missing keys within one tour, the present fallback performs approximately
`m` prefix decodes. A subsequent batch still performs at least one basis decode;
its maximum scan saving is the eliminated `m-1` traversals, minus planning,
folding, metadata and candidate-decode cost. For G1 with one missing key this
ceiling is approximately zero **traversals**, not one avoided cold pass. It
may save full-tuple retention/target-list allocation, but that alone is not
evidence of a material G1 fix. For G2/G3, at most two/three missing distinct
queries under the no-pressure assumption, at most one/two shared traversals
can disappear. Different tours/cutoffs or pressure can reduce that benefit.

Required design: only actual validated publications/same mapping/generation
supply requests; retain no all-future-publication queue; do not replan the same
first30 forever. Preserve original/predictor order and duplicate-key semantics.
All pending records, keys, serial widths and both bases share64MiB/30queries/
32slots. End discarded key/query/iterator frames before uncharging. Bind a fold
only after every row and final/empty owner/serial/lifetime check. Eviction,
same-byte replacement, reentrancy, domain/resource/lifecycle failure and
no-owned-basis paths remain cancellation/rejection/full fallback, never partial
query authority. Full-prefix admission still precedes native absence/ambiguity.

This is a possible G2/G3 growth-cost control, not the recommended first G1
repair. Do not implement it just to demonstrate progress while the dominant
mandatory snapshot cost remains unmeasured.

## Proposal B: non-owning, learned exact-prefix metadata

### Core seam and provenance

At present `_replay_history` (`tennis:92-107`) finds no exact earlier key, calls
`_lookup_covering`, then returns that full fresh tuple immediately when a
prepared maximum basis exists. It deliberately does not duplicate/store the
encoded prefix. Consequently the second event at the same cutoff repeats the
same boundary search and per-row reconstruction checks.

A new optional descriptor can contain only canonical cutoff/tour, **parent
entry key and exact completed serial**, prefix row count and complete prefix
canonical-byte count. The parent remains the sole owner of all immutable row
bytes. No byte slices, encoded tuple, decoded tuple, row references, iterator,
per-row index or new completeness seal is retained by a descriptor.

Create this metadata only within the fixed owning cache operation, after the
existing full first covering derivation has actually completed with all its
before/after-row, admission, final/empty and serial/lifetime boundaries. Require
the exact parent to remain both source-sealed and **owned complete**, not merely
physically proved or directly `_store`-sealed. No caller-provided prefix length,
byte total, history, callback, row list or completion flag confers authority.
The descriptor remembers an established deterministic slice of an already
complete immutable source result; it does not establish new source truth.

On a later identical cutoff, check the exact owned parent/serial/generation/
schema/write/proof at entry, admit using the previously proved complete byte
count, deserialize all prefix rows into a new real tuple, then check parent
authority/lifetime again before return. Every feature witness still validates
each fresh row against the same parent bytes, with its existing before/after
checks, and full refs/features/transport remain unchanged. A descriptor is not
a feature cache and cannot authorize a partial tuple.

This is analogous to existing exact-key cache reconstruction, not permission
to drop checks from a still-unproved covering traversal. The new exact-hit
classification and its mutation/exception behavior need explicit approval and
review. Old covering checks must remain on every first derivation and every
miss/invalidated view. If that equivalence cannot be established, do not use it.

### Lifecycle, accounting and phase transition

- The safe phase seam is `context_runtime._verify_connection:532-535`, after
  successful `verify_live_originals` and before `_verify_snapshots`. Only the
  actual completed original phase can release consumed query metadata. Do not
  evict query state during original validation just to buy snapshot views.
- Preserve `_owned`, `_basis_cutoffs`, parent row seals and the coordinated
  artifact mapping pin. `_clear_original_metadata` and `_drop_planning` clear
  more than consumed queries and are not suitable shortcuts; dropping the basis
  plan can make `_replay_history` enter the old per-prefix store/seal route.
- Charge every descriptor/key/serial/pending reservation in the same64MiB pool;
  aggregate existing entries+queries+views+pending slots stay<=32, reserving both
  possible parent bases. Typical supported15-18cutoffs do not imply universal
  fit. Pressure means no memoization/full old fallback, never history rejection.
  Do not evict a complete basis to finance its tiny dependent view.
- Queries/long keys can be uncharged only after helper frames/iterators die,
  following the existing delayed-release pattern. Views hold no bytes, so
  eviction removes the sole byte owner normally. Drop/uncharge all dependent
  view metadata on parent replacement/eviction, even if new bytes are identical.
- No child view may keep a parent tuple/iterator alive across a decode callback
  or after eviction. Decode each requested current row by bounded indexing;
  final parent serial/proof check prevents an expired view becoming a hit.
- Same-connection write, main/temp DDL, class/execute/cursor dispatch changes,
  commit/rollback/restart/closure, proof revocation, nested/reentrant lookup,
  interruption during first derivation/publication/reuse, final/empty and
  exact-budget boundaries must retain existing fail-closed behavior.

### What this can and cannot save

For each cutoff/tour `k` with `r_k` consumers, first derivation cost is unchanged.
At most `r_k-1` subsequent covering reconstructions can become exact-prefix hits.
Let `C_k` be measured existing covering time and `E_k` fresh exact-prefix decode
plus unchanged entry/exit proof cost. The optimistic removable fraction is
`sum((r_k-1)*(C_k-E_k))`, less metadata/bookkeeping and pressure misses.
JSON decoding, complete fresh dictionaries/tuples, feature/witness checks,
all refs, actual predictor and transport costs are **not** saved.

With the baseline's repeated two-events/same-cutoff pattern, this targets many
old consumers rather than just one excess original. The newly unique G1/G2/G3
cutoffs provide no repeat benefit themselves; their complete snapshot work and
first derivations remain. Advancing the basis also retains the first old-max
covering conversion; only its repeat can be memoized.

Root must separately measure exact/covering counts and times by cutoff, actual
projection misses/owned fallback and untouched feature/transport times. G1's
300second kill supplies no completed runtime from which to subtract a guessed
speedup. A passing actual30 with11.739wallseconds margin is not a bound on G1.
Do not turn these symbolic ceilings into promised seconds without the pending
per-cutoff/decode attribution; no safe quantitative G1/G2/G3 pass is established
by the aggregate diagnostic recorded below.

## RED/equivalence gate before either implementation

Real31/32/33distinct-key persisted controls, plus repeated and interleaved
same-cutoff events, must demonstrate the actual removed work while retaining
every original/predictor and full snapshot tuple/ref/feature/transport count.
For prefix views: first covering checks unchanged; repeated learned key uses
fresh exact bytes, distinct nested identities and full scope validation;
arbitrary caller/direct-store/wrong parent/serial/never-completed proofs cannot
mint views. Compare canonical reports/errors with immutable72421d3 and disabled/
pressure/evicted/missing-basis routes. Add actual weakref/refcount and charged
slot/byte checks, empty/final/race/alias/signedzero/nonfinite protections, and
protected-final no-body controls. No timing threshold as a unit assertion.

Only after explicit internal scope approval, focused RED/GREEN and independent
review should root measure the exact committed candidate on actual30, strong
G1/G2/G3 and retained historical controls under unchanged native limits.
If measured removable repeated-prefix/original work cannot provide sufficient
margin, report no demonstrated safe fix within this scope. Do not increase
limits, prune evidence, invent a new seal, cache features or silently suppress
per-row checks on a still-covering lookup.

## Completed real G1 phase attribution and final feasibility ruling

Controller's bounded diagnostic used the correct application venv, exact72421d3
source and G1 SHA04e7db...94b. It stopped at its275CPU diagnostic threshold during
snapshot28 of31; totals277.179CPU/276.087wall/485744KiB include process/startup
accounting. Input unchanged. This is explicitly **not** full D4 acceptance.

| Observed phase | Actual result |
| --- | --- |
| Before originals / before snapshots |94.407s /110.785s elapsed|
| All31 originals |16.374CPU|
|31 native projection lookups,30hits |0.006216CPU across all31invocations, not isolated hit timing|
|One overflow owned-full prefix |1.360743CPU; enclosing native call1.427CPU|
|Covering snapshot histories |27completed of28calls;48.002107CPU cumulative including interrupted28th invocation|
|Exact snapshot hits |0 in the completed sample|
|Snapshot workers |27completed of28calls;162.07556CPU cumulative including interrupted28th invocation;27th complete at272.337s|
|Snapshots1-18 |history replay1.05-1.54CPU; features1.70-2.01CPU each|
|Snapshots19-27 |history replay2.34-3.09CPU; features3.51-3.98CPU each|
|Cache |1entry,58392186encoded bytes,58401081total charged bytes,31metadata slots; no eviction/bypass|

Worker, feature, history and native values are nested, not independent additive
phases. Both48.002107CPU covering and162.07556CPU worker totals include the
interrupted28th invocation. The28th in-flight call is not a completed observation; the last four
full snapshots and final work must not be assigned fabricated measured times.

### Actual ceilings, rather than optimistic extrapolation

1. **Overflow originals:** even impossible zero-cost elimination of the entire
   measured owned-full fallback would save only1.360743CPU seconds, about0.45%
   of300seconds. A real rolling batch must decode/check a corresponding whole
   basis once, so its G1 scan saving remains zero; only a subset of list/tuple/
   target-allocation overhead might disappear. The31native projection lookups
   with30hits cost0.006216CPU in aggregate, not the30hits in isolation. This is
   not evidence for another material original-projection repair or a31/32/33
   release strategy.
2. **Covering histories:**48.002107CPU includes the interrupted28th covering call,
   not redundant work. All first derivations, all fresh JSON decoding and tuple
   construction, and required first/final checks survive prefix memoization.
   Only repeat-cutoff guard/search overhead could disappear after an approved
   exact-prefix derivation. Aggregate timings do not separate that component;
   claiming a48second saving, or even half of it, is unsupported.
3. **Features and later snapshots:** every measured feature call and every
   unchanged predictor/transport remains. Late snapshots are materially more
   expensive than early ones. Neither query batching nor prefix metadata removes
   newly unique G1/G2/G3 snapshot features. A censored300second failure cannot
   establish how many seconds the final accepted candidate must actually save.
4. **Encoding headroom:** actual encoded basis58392186bytes already occupies
   most of64MiB; total spare charged capacity is8707783bytes. Ordinary copying
   of a whole large earlier prefix cannot be presumed to fit. The descriptor
   proposal deliberately adds no second encoding and would need explicit
   provenance/accounting approval, not an increased cache allowance.

### Frozen-frequency ruling

The literal current requirement is that existing before/after/final check
frequencies remain unchanged. Under that rule, a later learned-prefix hit must
still execute the same per-row boundary checks as its former covering lookup.
Storing only its length/byte count cannot then remove the dominant repeated
guards or fresh JSON reconstruction; its remaining saved comparisons/counter
updates have no demonstrated material ceiling. No implementation is justified
on that basis.

It is plausible to propose a **different checking contract**: once the exact
prefix has been completely derived from its still-owned sealed parent, later
consumers qualify for the same edge-checked reconstruction already used by
existing exact keys. That precedent is a design argument, not current
authorization or proof. It changes which runtime boundary checks are executed
for those later consumers and must not be sold as unchanged frequency. It
requires the parent-serial/provenance/lifetime/pressure proof and adversarial
tests described above, plus actual savings measurement. It still must not
create source truth from generic cache rows or cache any feature/model result.

Therefore the next decision is a boundary decision, not another speculative
micro-optimization: determine whether the frozen per-consumer frequency is a
binding user condition. If it is, seek explicit user direction before changing
that contract; otherwise keep release HOLD and report no demonstrated safe
capacity solution in the allowed scope. If the controller is authorized to
amend this internal exact-prefix classification, record that narrow amendment
explicitly and review/test it before implementation or any performance claim.
Neither path permits caps/history/model/source-predicate changes.

Same-count cursor/dispatch rewrites or a new JSON comparator have no new actual
profile/equivalence evidence sufficient to support another material Task11.
Task10 already applied the measured loop/cursor improvements; the earlier typed
comparison benchmark was not consistently better than its unchanged-canonical
alternative. Do not revive either as a promised fix, reuse identity in place
of current canonical row comparison, or silently widen the frozen helper scope.

No code/test/index edit or further execution accompanied this attribution
update. It records the controller's actual diagnostic and the resulting limit
of the present proposal, not an approval to implement Task11.
