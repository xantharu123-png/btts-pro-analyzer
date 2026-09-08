# Task 5 / B1 — causal observations and closed context contracts

Date: 2026-09-08. Status: implementation, focused self-review and frozen full
regression complete. Independent review and integration are pending.
This is not source certification, empirical approval or production activation.

## Scope and exact source

- Checkout: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-b1-20260908`.
- Branch: `codex/kontext-b1-20260908`.
- Exact inherited base: `156ba46a610f690ff792b1bee752ba3692d11dff`.
- Source commit: `9a4e04f7aa65ea5f9f0a1e8e7ef91216951274e6`.
- Five new source/test files only; no existing source was changed.
- Authoritative task-5 brief, full approved specification, and full controller
  decisions including the 2026-09-08 B1 clarification were read from the
  separate `kontextmodell-20260907` checkout. That checkout was not edited.
- `context_sources/__init__.py` was unnecessary and was not created.

SHA-256 of the exact frozen local bytes:

| File | SHA-256 |
| --- | --- |
| `context_observations.py` | `e8c704de8c74abd61c9d7124deff76311f45b3897fb3009283513fe6247b09f8` |
| `context_models/__init__.py` | `3b2c557620c83acbbdecc9422ef3b00d83ae0006a710b761683f4eed8747a91f` |
| `context_models/contracts.py` | `8c8d57214bb4c7ff5c46583b0adc13e2e191bf43760d11a083dd66392aceefdd` |
| `tests/test_context_observations.py` | `4251684b5337fe1940badd3abc7c4b05d3ff8538e189caf638a51f347be6200f` |
| `tests/test_context_contracts.py` | `720c29fd3b813ff6bd3396afb936abadc63dc0ba6fa84129063560371020aca4` |

The inherited false Git modification of `scripts/stage_runtime_databases.py`
was not edited or staged. Its pinned raw hash remains
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

## Implemented B1 behavior

- A1's unchanged SQLite connection and trusted runtime-path checks are reused.
  Content is stored separately from actual ingestion receipts. Content identity
  includes every normalized record field; receipt identity includes content
  hash and canonical UTC microsecond observation time. Exact receipt retries
  are idempotent, while actual later rechecks preserve old receipts and add new
  ones. No public update/delete or replacement operation exists.
- Publication/validity clocks normalize before hashing/comparison. Naive clocks,
  future publication relative to receipt, nonfinite/non-JSON values, unknown
  outer keys and price/bookmaker fields at any payload depth are rejected.
- Prospective reads select by actual receipt <= cutoff and exact schedule
  revision. Equal-time differing revisions are retained, not lexically picked.
  Historical reads select causal and retrospective classes independently;
  an unverified late correction cannot displace an earlier known fact.
- The real archive resolver registry is EMPTY. A caller may name a registered
  source-specific local resolver, not provide arbitrary callbacks. A recognized
  resolution binds exact content, publication, resolver version, secured
  evidence digest/locator and its resolution hash. Provider `verified` flags,
  self-issued proof and unknown resolvers do not authorize historical use.
- Operational freshness is explicitly separate from model role and versioned
  model coverage. Availability/expected lineup use 6 hours, tightening to 30
  minutes within 2 hours of kickoff; weather uses 3 hours and a validity interval
  covering kickoff; confirmed lineup expires at kickoff or a stricter source
  deadline. Changed standard durations require a different policy version.
  Completed workload facts do not acquire a wall-clock expiry, but uncompleted
  matches cannot claim completed workload, coverage has its own expiring factor,
  and a walkover is not treated as a normal played match.
- Empty incomplete collections and empty purported individual facts are
  missing. An actually reported player fact can be available while the team's
  collection coverage stays incomplete. Explicit source precedence is required
  to resolve disagreeing sources; it cannot resolve an internal equal-time
  conflict. Rescheduling and cancellation invalidate event-bound facts.
- Fixed validators cover Event, FeatureVector, BaseDistribution, EffectArtifact,
  ContextResult and TrainingRow. Real JSON types, native identity namespaces,
  exact feature/ref/state names, ordered head feature vectors, family/head
  routing and finite dimensions are checked. Scope is a normalized closed set
  object with no wildcard, empty set or implied transfer. Model coverage is the
  closed `{version, case}` identity, not a completeness certificate.
- The three approved B families have explicit parameter forms. Tennis winner
  endpoint probabilities remain legal bases, with exact complementary winner
  markets. Serve parameters require actual integer best-of 3/5. Other families
  are not prematurely implemented. Typed non-winner market storage does not
  certify an owning adapter's supported catalog; B5/B7 must do that validation.
- Football reference structure preserves the declared actual venue/form and
  attack/defense weights, separate goal/xG samples and normalized prior terms.
  Unresolved CSV/native roster links remain explicit and preserve a valid base;
  they do not become verified player evidence. No roster feature is computed.

## RED / GREEN and own review

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
All runs used `-B -m pytest -q -p no:cacheprovider` and a unique isolated
`.pytest_tmp` child. No runtime database outside these tests was written.

1. Initial `b1-red-01`: collection failed as expected with missing
   `context_observations` module; the late-correction regression was the first
   failing test.
2. Initial green attempt exposed a missing parent `.pytest_tmp` directory, not
   a product failure. After explicitly creating that parent, `b1-green-02`
   passed 38 tests with 4 inherited A1 platform skips.
3. `b1-contracts-red-01`: missing `normalize_population`/validator exports were
   reproduced before implementing the fixed contract interfaces.
4. Observation regressions reproduced stricter-lineup-source expiry and a stale
   secondary source incorrectly setting an already-expired `fresh_until`.
   Both were fixed and all 51 then-current B1 tests passed.
5. Contract regressions reproduced same-team reference aliasing, the legitimate
   unresolved negative CSV ID boundary, winner parameter/market disagreement
   and missing consumed factor state. All were corrected without fake joins.
6. Own adversarial cases covered false empty-fact availability, unfinished
   workload, typed malformed policy statuses, silent policy-version drift,
   actual `ice_hockey` namespace, corrupted/colliding stored identities,
   canonical-time mutation, unknown archive proofs and concurrent ingestion.
7. A partial broad run was intentionally interrupted (exit 1) before completion
   when a separate read-only check reproduced camelCase `bestOdds` bypassing the
   initial price-name guard. Ten dedicated tests then failed on camelCase,
   concatenated, spaced or numbered price names. The guard was corrected before
   freezing the final source. That interrupted run is NOT reported as passing.
8. Final frozen focus `b1-final-freeze-focused`: **209 passed, 4 skipped** in
   3.51 seconds, covering the new B1 files plus existing A1/context coverage.
9. Final frozen complete suite `b1-final-frozen-full`: **2057 passed, 15 skipped,
   97 subtests passed** in 116.72 seconds. Exit code 0. No source changes followed
   this frozen run; only this handoff report was completed afterward.
10. Exact five-file staging allowlist and `git diff --cached --check` passed;
    narrow source commit created. This report stays untracked for the controller
    to preserve together with the independent review; no push was attempted.

## Explicit remaining boundaries

- No real source/proof adapter or causal historical archive has been certified.
  Synthetic fixtures and test-only resolver registration prove mechanics only.
- No model training, numerical injury/fatigue adjustment, B2/B3 snapshot consumer,
  B4/B6 source adapter, supported new market catalog, empirical D1/D2 validation
  or live application is part of B1. Source-specific payload allowlists remain
  mandatory at their owning producer before numeric use. Names alone cannot
  prove a field is sport-only or historically available.
- No provider/network call, VPS operation, timer change, push, Cricket change,
  price/ranking change, ticket/account/15K/settlement change or A4 source edit
  was performed. Only the controller integrates and pushes after independent
  review. The separate pending A4 fix is not included in this B1 base/commit.
- A1's existing path tests run locally; this B1 task did not perform a new Linux
  permission exercise or production backup/restore. Production schema/backup
  rollout remains part of D4/D5, not implied by a passing local SQLite test.

## Independent review correction R1–R3 — 2026-09-08

The original independent verdict for `9a4e04f` is NOT APPROVED. Its report and
reproduction source were read completely and remain unchanged. This section
documents the scoped correction, not an independent approval of that correction.

The controller's new **B1 independent-review correction contract** in the
authoritative sibling checkout was read in full. It explicitly preserves
diagnostic history while adding a distinct consumable-reference output.

Changed scope: only `context_observations.py`, its focused production test file
and this report. No shared contract seam, A4 or other task source was changed.

- R1: `refs` is now explicitly audit-only and includes inspected factor and
  event-status receipts. New `usable_refs` is sorted/unique and empty unless
  the factor is available. Only its final same-scope, same-schedule, prospective,
  applicable, fresh, source-selected factual receipts appear there. Downstream
  feature builders must use `usable_refs`, never treat audit refs as consumed.
- R2: Every supplied row's native event/sport/competition/format is checked
  before policy/status early returns. Mixed scope is a typed error. Status
  invalidation requires exact schedule, prospective receipt <= cutoff and a
  validity interval containing cutoff. Status receipts remain in audit refs;
  invalidation and other unavailable states have no usable numeric provenance.
- R3: Fresh candidates are source-precedence-selected before factual presence,
  required completeness, coverage or usable metadata is derived. Stale facts,
  empty receipts and precedence losers cannot supply missing substance,
  completeness or deadlines. Internal simultaneous revisions remain conflicting;
  source precedence cannot quietly remove a same-source conflict.

### Reproduction and focused verification

- Original unmodified independent repro file, `b1-own-r1-r3-original-red`:
  **12 failed, 6 passed**, reproducing all original findings on `9a4e04f`.
- Owned product regressions, `b1-r1-r3-owned-red`: **20 failed**, including all
  12 original cases under the controller-approved audit/usable split, exact
  scope rejection, status validity and source-selected metadata controls.
- Two additional selection controls cover an explicitly preferred empty
  incomplete source versus an unranked empty secondary source; neither may
  contribute usable references or lend substantive facts.
- Final focused run `b1-r1-r3-final-focused`: **240 passed, 4 existing platform
  skips**, 3.03 seconds (B1, A1, context coverage and runtime path tests).
- Original, unmodified R2/R3 reproductions plus all six original positive
  controls, `b1-r1-r3-original-unadapted-controls`: **13 passed, 5 deselected**,
  0.37 seconds. The five original R1 assertions refer to the old undifferentiated
  field; all five are now represented by owned regression cases enforcing both
  retained audit refs and exact usable refs, or typed mixed-event rejection.
  No independent assertion/report was edited to manufacture a pass.
- Frozen full suite `b1-r1-r3-final-frozen-full`: **2079 passed, 15 existing
  skips, 97 subtests passed**, 76.65 seconds, exit 0. No source/test edit followed.
- Correction commit: `22164fdf577190fa17f9aeddebd1b810ca4c59a1`, parent
  `9a4e04f7aa65ea5f9f0a1e8e7ef91216951274e6`. Exactly two source/test files;
  staged diff-check passed. This completed report remains untracked with the
  preserved review evidence for controller integration. No push was attempted.

Frozen correction raw SHA-256:

| File | SHA-256 |
| --- | --- |
| `context_observations.py` | `9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226` |
| `tests/test_context_observations.py` | `5699044e9073a428376163f3433ef9b2d2d76dd549df0593fde27c550e849352` |

Preserved independent evidence raw SHA-256:

- `task-5-independent-review.md`: `3cb7f832d93695b40794017eeffa7254024ddb038f9af1ec3619ed885a5b1b8e`.
- `task-5-review-repros.py`: `bdc4c2a31bf9338e770f5e20e92126f8051b2bbb41d12fb994698296712d7ac7`.

Independent rereview is required. No provider, registry certification, numerical
effect, empirical approval, push or VPS operation has been added by this fix.
