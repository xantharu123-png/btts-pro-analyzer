# Independent D1 source / case / training mechanics review

Date: 9 September 2026. Reviewer: `/root/b3_shared_snapshots_20260909`.
Disposition: **CHANGES REQUIRED — one P2 finding, two public-path reproductions.**
The shipped full suite is green, but does not contain the newly reproduced
legitimate-refresh failure. No other actionable defect was reproduced in this
bounded review. No real causal dataset, empirical fit, CLI or activation is
approved by these mechanics checks.

## Scope and required reading

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-d1-training-20260909`.
Frozen clean commit: `b74e2abd759a952991559709833470b3c3b160c0`.
Delta against previously integrated `2fd9c72`: 11 files, 1559 additions and four
removed module-documentation lines. Existing split implementation is unchanged.

Read completely: approved context specification; D1 brief and preflight;
context-contract and validation-contract decisions; bounded corpus inventory;
the complete new D1 audit; replay, case assembly, training and shared training
contracts; all new test modules/helpers and referenced outcome/identity/config
tests. Inspected the actual B1 receipt checks, native outcome/base normalization,
B4 projection clocks/content identity, raw baseline provenance, B5/B7 comparison
and B2 fitting law. The source is reviewed against the approved case-resolver
interface, not the obsolete plan-only flat row-builder signatures.

The D1 worktree's committed validation decisions precede the controller's later
independently reviewed freeze/open packet. This review does not invent that
packet inside D1, nor silently adopt it as an implementation dependency here.

## F1 / P2 — a valid native identity proof disappears on target refresh

Location: `context_models/replay.py:112`:

```python
identities = resolve_identity_map(identity_map, observations=rows,
                                 event_keys=(event["event_key"],))
```

At this point `rows` already contains only the latest actual native input
revision per event. The complete supplied causal history has been validated,
but an older native target receipt has been removed from this selected tuple.
That receipt can still be the valid source proof named by the frozen global
identity map. Identity is not the same thing as the current lineup revision.

The two independent public-API reproductions use genuine isolated B1 persistence
with explicitly synthetic native football data. They do not edit database rows,
forge verification flags or bypass a validator:

1. An original prematch target receipt proves the native event/home/away IDs and
   is referenced by the whole supplied identity map.
2. Five minutes before the same decision, a second real normalized target receipt
   is persisted. In one case the detail is identical; in the other only one
   lineup position changes. Native event/team/schedule identity stays the same.
3. Both original and newer receipts remain present in the supplied predecision
   history. The recipe is correctly rebuilt to name exactly the latest native
   calculation inputs, not the earlier target version.
4. Replay rejects with `native identity proof receipt is missing or belongs to
   another event`, because it asks the resolver to search only the latest
   calculation rows, not the complete validated causal proof pool.

Thus an ordinary refresh can unnecessarily stop an otherwise eligible replay
and downstream case/training run, or force a pointless global map revision.
It is an over-rejection/availability defect, not a false effect approval or
evidence that the numerical base must use older facts.

Narrow correction, explicitly accepted by the controller during this review:
resolve native identity proof refs from the **complete validated causal receipt
pool**, while calculation/recipe selection remains strictly latest per event.
Keep exact current event/team/schedule checks and source clocks. Do not send the
whole revision pool into the numerical baseline, revive obsolete lineup/minute
values, count duplicate matches, weaken missing/foreign proof rejection, or read
unrequested final-event receipts. The original global map hash remains bound.

Required follow-up: both original reproductions green, permanent corresponding
cases plus stale/future/foreign-identity negatives, fresh focused/full regression
and independent rereview. No source bytes were changed during this review.

## Positive independent checks

The six other source/clock cases pass:

- Two material simultaneous native revisions remain ambiguous regardless of
  input order; an explicitly selected recipe cannot choose one winner.
- A newer native historical receipt with numerically identical minutes still
  requires matching actual B4 projection receipts. Old projected content is not
  enough: its valid_from/result-receipt clock is bound in the content identity.
- Three microsecond boundary cases show that final cases are rejected before
  label assembly; the just-before-final positive control reaches assembly.

Seventeen additional numeric/public-fit cases pass:

- Every one of five winner alphas retains train-only population-std scaling and
  satisfies an independently differentiated binomial/ridge stationary-gradient
  check. Independently reconstructed logit probabilities reproduce complete
  event-mean Brier scores; exact score/larger-alpha selection agrees. Input
  inventories remain unchanged.
- All six permutations of the declared three serve coordinates use exactly one
  joint 8-row fit for four train events. Captured arrays match independent
  mirror routing, targets/trials and offsets. Opposing coefficients/scales are
  the exact signed permutation of that same fit, not a second fitted head.
- Seven varied best-of-3/5 scorelines, including tiebreaks, straight wins and
  reversals, reproduce **every key** of the declared serve catalog against an
  independent integer outcome oracle. This tests pure target projection only;
  modified synthetic scorelines do not pretend to provide observed hold data.
- Three real public Football case/fit calls at train-result cutoff minus/equal/
  plus one microsecond preserve the requested case inventory. A late train
  result becomes a named train exclusion, never a new tuning event.

The unchanged shipped packet additionally covers full baseline/feature rebuild,
actual source correction, missing/vocabulary/preprocessing exclusions, final
label guard, all-alpha failure retention, no partial tuning subset, exact
FitResult partitions and unsupported public Tennis replay. Numerical tests of
the private resolved seam are deliberately not a source-evidence bypass.

## Runs, frozen reproductions and reviewer correction

All runs use designated quality Python with `-B -m pytest -q
-p no:cacheprovider`, new isolated basetemp for every invocation:

| Run | Result | Basetemp |
| --- | --- | --- |
| Complete existing D1 focus, including 34 split tests | 182 passed, 92.22 s | `.pytest_tmp/d1-independent-focus-01` |
| Own public source/clock probes | **2 failed, 6 passed, 7.34 s** | `.pytest_tmp/d1-independent-probes-01` |
| First numeric probe collection | one reviewer import error, no tests executed | `.pytest_tmp/d1-independent-math-01` |
| Numeric/public-fit probes after import correction | 17 passed, 9.98 s | `.pytest_tmp/d1-independent-math-02` |
| Both independent files combined | **2 failed, 23 passed, 17.96 s** | `.pytest_tmp/d1-independent-combined-01` |
| Entire shipped `tests` suite | **3463 passed, 15 expected Windows skips, 97 subtests passed, 162.53 s** | `.pytest_tmp/d1-independent-full-01` |

The collection error was my unused import of `_case_rows` from training instead
of its owning case module. Removing the unused import fixed the reviewer file;
no source/test implementation or acceptance assertion was changed. The eight
source/clock probes were frozen after their first real run and remain identical.
The math file was frozen after its first actual 17-case execution and stayed
identical in the combined run. The full shipped suite does not collect isolated
`.pytest_tmp` reproductions, so its green result does not negate F1.

Reproductions in this report's directory:

| File | SHA-256 |
| --- | --- |
| `test_d1_independent.py` | `5c26c3bf49d2b4b4ab3b109ea73b8d5029a883d899deba0d2367f71dc7123a0c` |
| `test_d1_math_independent.py` | `4a52a1f59408818c06d3645fffc83c64c6ddae0c404d5d0faa34eaa76a219aea` |

## Exact source/test identities

All 15 hashes were independently verified at entry and after the runs. Clean
HEAD remains b74e2ab. Owning audit SHA-256:
`81d1a7ab5b17c9138312e9fa8eee67f5f0d05e3dfc79f70834b2ae368a24a63b`.

```text
e61943527fd764d1017f3c78ae09cd5d1d8bc67db44e19961517bc4b329e6786 context_sources/outcomes.py
38e876e0e82f03290e3fbd76a72239893237ed70865987a63c86f639ac6f89ce context_models/training_contracts.py
13bdb7b4b73b85d3b522411e364577e65f4b2545336e87d7fd94d1ce55ff609e context_models/replay.py
ce05e30b6062a40d76d5b76715fd30375cdb3a582131333adb97a98acbf8eeb1 context_models/training_cases.py
fcf953d738b7f1249c68b65532f55142c8ad77e3b4a6de861c15bcab87efca6a context_models/training.py
09af0fb155011fce193ed76c15962bb713d6645944b730bbd5218c8c110e4cc4 tests/context_training_helpers.py
d378bc787948ead6ed56201f611c32fc9c6d2365bc3fc5ff0d633e346f263673 tests/test_context_training_contracts.py
937c0a2a5d8fd8f0ee84e80a6ac7e2bbcab8fcca4a4961d2e8459d2d8c1f2861 tests/fixtures/context/training/tennis-winner-family-v1.json
849161dcb97a8056a8e96127d68b8c858e261a4539e8ecf0bc600c0f723e8f69 tests/test_context_outcomes.py
c50d5f557a6239bd32c9090dfe0d2b630e8197d28a3255a9c5832420a75b27e5 tests/test_context_training_identity.py
4c71f947094d4b6f9ff6db3a8d92399c76472b7667a8ac222997bb0e741c2b06 tests/test_context_replay.py
bba6aeb14f39f1a9fecc2bcb2ee15a440efd8530196997b20a508a9182a35a4e tests/test_context_training_cases.py
6004affa24b580e8df44000cacf1ab603a61a82eb2317b31603dfd9d86756675 tests/test_context_training_fit.py
899d64f9697c4237d5108653deb5591b9e6c2d4ed19940c7da42cfbfbcde956b tests/test_context_training_reports.py
debc173076f64f2e54fe3051eb959119b0efe288bbf9647c063e46c3681ccac3 tests/test_context_training_tennis_math.py
```

## Unclosed scope

Native Tennis-to-name-state alias resolution and actual participation-training
receipts remain explicitly unsupported. A synthetic successful internal fit
does not enable those public paths. No real source corpus or causal effect
has been measured in this review. CLI, whole experiment evaluation, BH outcome,
approval provenance and productive integration remain separate tasks. The
200-event/three-block/2-percent/distribution/calibration acceptance is unchanged
and not demonstrated by synthetic tests or source freshness.

Only this review and isolated repro/test databases were created. No source edit,
commit, push, provider/API/SSH/VPS action, production-data access, model activation,
money/history rewrite or pinned-helper mutation occurred.
