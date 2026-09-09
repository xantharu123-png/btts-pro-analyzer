# Independent C4 R1b follow-up — 9 September 2026

**Disposition: the requested cancellation-retention fix passes its unchanged
reproductions; one adjacent P2 whole-scope partial-revision defect remains.
Request changes before accepting the full C4 source-revision boundary.**

This is a source/mechanism review, not empirical or production acceptance.
The exact frozen model and source bytes were never edited. Only this new ignored
directory and new isolated pytest outputs were written by the reviewer.

## Target and actual review scope

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c4-esports-20260909`.
Initial HEAD: `79763a179b3efdd67c9f6d8ae6bd1c0d2032e3a2` with the two disclosed
Root R1b source/test changes. During review the controller committed these exact
bytes and its new audit as `be45dab58c38f781554e0671c4205c753f343d35`.
Final Git status is clean; the source hashes below remained identical.

The complete b6 rereview, unchanged ten lifecycle probes, complete Root diff,
all sixteen new permanent regressions, complete current native source normalizer,
whole-fact/event selector, feature assembly and relevant application/B3 paths were
read. The approved Task15 and controller rulings were reread. The earlier full
C4 specification, implementation and reports had already been reviewed by this
same agent. The newly committed `2026-09-09-c4-cancel-retention.md` was also read
completely. No source contract, complete/partial meaning or old assertion was
changed to obtain a test result.

## Confirmed R1b behavior

An independently executed combined run produced **259 passed in 97.50 seconds**,
without skips: all 182 current C4 tests, the unchanged 67 original independent
cases and the unchanged 10 b6 follow-up cases. In particular all four old R1b
negative cases now pass, as do the six controls. This is distinct from the
controller's previously reported 176 focused and 4205 full-suite results.

The additional first independent packet produced **1 failed / 22 passed in
16.72 seconds**. Its single failure led to the isolated finding below. The 22
positive controls verify:

- current map, observed-lineup and direct-series cancellations on each target
  team retain unknown series counts and exact/minimum recovery; the other target
  participant's values stay unchanged;
- an owning completed series must arrive strictly after cancellation: equal
  receipt time conflicts, one microsecond before stays withdrawn, one after can
  restore its own consistent end;
- expiry of unrelated refreshed metadata does not erase the retraction;
- partial replacement with changed participants or schedule does not assert zero;
- a genuine new terminal outcome with unknown actual end stays a receipt-only
  bound: no exact end or exact rest is invented;
- a second cancellation after an earlier genuine restoration requires another
  owning completed-series revision, not a later map; actual completed maps remain
  countable;
- cancelled payloads with retained winner, clock or player data, invented
  `valid_from`, or non-native participant identity are typed contract errors;
- cancellation involving wholly unrelated native teams does not change target
  features;
- unavailable load sent through the actual B3 wrapper remains `not_applied`,
  preserves original parameter/market bytes, and creates no approval/certified
  market. The original base object is not mutated.

## P2 C4-R1c: incomplete own season revision erases old scope uncertainty

Owning location: `context_models/esports.py:134-143`, with propagation through
the same-title/season filter at lines 484-487 and count/recovery assembly at
lines 514-533.

The per-fact revision selector retains uncertainty for an incomplete current
record only when its participant set differs from the prior participant set.
It does not apply that same whole-revision rule to a changed native scope.
Consequently a newer `series` record with identical participants, changed
`season_id` and every outcome/time field null replaces the old series in the
selector, is filtered out of the target's season, and leaves no series ambiguity.
The full series receipt pool still contains both native scope revisions; this
is not a B1 lost-row problem, free verified flag, stale external assumption or
forged source payload.

Exact normalizer -> temporary B1 SQLite -> `observations_as_of` -> feature
reproduction at cutoff 2026-09-09 12:00 UTC, target start 18:00 UTC:

1. A native series for target team 7 (or 8) ends 09:00 and is received 09:01.
   An earlier known series in the actual base history ended six days earlier.
2. The cancellation variant receives a correctly empty cancelled map at 10:00
   and later ordinary completed map metadata at 11:00. The R1b fix correctly
   keeps series count and rest unknown at this point.
3. At 11:30 a new owning series receipt changes only native season 2026 -> 2027
   in scope and supplies `winner_id`, `score_a`, `score_b`, `actual_start` and
   `actual_end` all as null. It is valid closed source input and genuinely
   normalizes to `complete=False`; both 2026/2027 receipts remain in real SQLite.
4. Current output becomes `observed_series_count_1d_<side>=0`, corresponding
   window completeness `1`, and `observed_recovery_exact_hours_<side>=150.0`,
   all **available**. The newer partial record did not establish a complete
   replacement or a new actual last completion. Missing data has become an
   affirmative empty window and the old six-day completion is now called exact.

The isolated eight-case packet produces **4 failed / 4 passed in 7.84 seconds**:
both target sides, each with and without the intermediate cancellation. All
four partial cases fail with exactly the above 0 / 1 / 150 values. All four
complete replacement controls pass: retaining the actual native winner, score
and times in a full new-scope revision may legitimately retire its old-scope
record and return 0 / 150. This is not a proposal to ban genuine corrections.
The source also correctly retains uncertainty for the adjacent participant and
schedule variants in the first packet. The five failing test instances describe
one defect, not five separate findings.

The direct no-cancellation variant shows that this is an adjacent pre-existing
whole-scope selection gap exposed by the review, not a regression proven to be
introduced by the two-line R1b lifecycle extension. In that direct variant, the
new partial scope revision is not even included among the numeric count refs.
In the cancellation variant its digest is incidentally present through map
ambiguity proof, but the *series* state is still incorrectly available. Mere
presence of a digest does not resolve the incorrect feature state.

### Smallest repair boundary

Keep the current full-vs-partial native revision semantics and owning source-v2.
At the per-fact selector, an incomplete whole replacement must preserve prior
scope/identity uncertainty as well as prior participants, so filtering the
partial replacement out of the target season cannot certify an empty history.
Use actual retained source proofs and owning causal bounds; do not infer an
actual end from receipt, normalize missing outcome into healthy/zero, revive
the old withdrawn series, or change generic B1 selection/schema. A full new
native scope revision must remain able to retire the previous scope, as the
four unchanged positive controls show. The existing retraction, true restoration,
half-open windows, unmodified base and no-D2 boundaries must stay intact.

The repair itself is not implemented or authorized by this review. No claim is
made that a wrong feature has been applied in production or to money/tickets.

## Reproduction commands and frozen new evidence

From the worktree above, use the project's quality Python with `-B -m pytest -q
-p no:cacheprovider`, each time a new `--basetemp=.pytest_tmp/<unique>`:

- Original/current focus: `tests/test_esports_context.py`,
  `tests/test_esports_context_model.py`, `tests/test_esports_context_revisions.py`,
  `tests/test_esports_context_corrections.py`,
  `tests/test_esports_context_retractions.py`, both unchanged original independent
  probe files and the unchanged b6 `test_c4_lifecycle_edges.py`.
- First new packet: `.pytest_tmp/c4-second-independent-20260909/test_second_c4.py`.
- Isolated scope matrix: `.pytest_tmp/c4-second-independent-20260909/test_scope_revision.py`;
  add `-s` to see the actual state/count/rest and receipt-ref diagnostics.

All new assertions remain byte-identical to their first execution. No collection
error, harness correction, skip, relaxed assertion or source edit occurred in
these two new packets.

```text
ddd7be0707ded720d546af78cb11c082c03ee0b462705d46c1dbce77a1a47a7c  context_models/esports.py
e5ef10ae444e6947b4841eef832ee8f4109f35c8d765918c4d503b8d96242901  tests/test_esports_context_retractions.py
6719a39df1578e59e5c20197b6f2f6057253eee0fc4063bc1048b4de84beb567  context_sources/esports.py
57b1270062de31224551bb90eff148104834b32a76a2676e1d86a4364da1cc74  tests/test_esports_context_corrections.py
bd431e06926a319a68d5803749771595bbf72bb8561d39da2b8ee841d2af7140  esports_elo.py (actual raw loaded bytes, unchanged)
559a76a253c3e8fdf9a094d62c294291c9992d94cb83bd81df2d798470ddd21b  docs/audits/2026-09-09-c4-cancel-retention.md
30a2b0341a5337526edc8c64a68ab93bc46f914f7b6ea151dc1ee1e328d985ab  new test_second_c4.py
b7d6eed5c08e3296ffff413d3a6fe38a838503bcd12f95f25c0c3e5c947cbdaf  new test_scope_revision.py
f4d41b554b572cdcda9885a0e623b5a9483c6a94a58bd323324d65dee6813c1f  .pytest_tmp/c4-second-focus-01.xml (259 passed)
f5dbffebf6582f0fb07c10ea41d6798f354a3446116cf1990f3212d04d32b619  new probes-01.xml (1 failed / 22 passed)
9a3fdebcB4bac18c6510d96806bbbe23a5a4e2a4e5e55b7cd89cba505d6da546  new scope-01.xml (4 failed / 4 passed)
```

`new` paths are beneath `.pytest_tmp/c4-second-independent-20260909`.
Unchanged previous evidence, freshly rehashed:

```text
201130cf5ba5a009c98c08df0f59aa79759b1c9605b47035d9ee7017a1f3f722  .pytest_tmp/c4-independent-20260909/REVIEW.md
1504b746aa9e19eaf44a485cf0ad391414adacfd091559a1e90cba164371bd2b  .pytest_tmp/c4-independent-20260909/test_independent_c4.py
777cd1c2aabcf54777ee4df9b4395a68076d19738a2dc428e96e699bd9f0df5e  .pytest_tmp/c4-independent-20260909/test_additional_c4.py
5eba9ee2120724513b64ff998a3acc2c6a12b4577c53aad0e579a9edcd6ca686  .pytest_tmp/c4-final-independent-20260909/REREVIEW.md
1ce6f4d68509267720bf5445964d2a61ccea272ef7d0c9b8bffab585c5b7fb72  .pytest_tmp/c4-final-independent-20260909/test_c4_lifecycle_edges.py
```

## Explicit limits

No independent new full-repository run was claimed: the actual reviewer evidence
is the 259-test focus and 31 additional cases above. All native-shaped inputs
are synthetic local mechanics; there were zero provider requests, real source
captures, corpus/empirical claims, new fitted population/approval decisions,
worker/UI/browser integration checks or VPS/production actions. The existing
raw Elo line-ending/source-byte boundary remains unchanged and is not called
cross-platform recipe equality. No changes to legacy default output, Cricket,
quote/ranking, money, 15K, settlement, old snapshots or tickets are authorized
or performed. Absence of D2 approval still leaves the original model in use.
