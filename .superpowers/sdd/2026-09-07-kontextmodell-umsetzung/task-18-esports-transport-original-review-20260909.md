# Independent D3 E-Sport transport review

## Disposition

**REQUEST CHANGES: one P2 original-event binding defect.** The frozen adapter is
not ready for integration until this owning fallback check is closed. Nine RED
cases reproduce the same defect across absent/ineligible effect and read/replay
boundaries; they are not nine separate findings.

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-d3-esports-review-20260909`.
Commit: `82f1e2d474018515496466a0a24fb1982b6b59d4`.
Parent: `e7911e0d052df68465d98c715c2ae78671b046cc`.
Reviewed all three complete changed files/diffs: `context_transport.py` (eight
additive lines), `tests/test_context_transport_esports.py`, and the owning audit.
Complete Task 15/C4 and Task 18/D3 briefs/rulings were read. The previously read
approved specification and B1/B3 approval/identity contract remain governing;
owning C4 Base/reference/feature/application and B3 dispatch/selection code was
inspected directly. This is a bounded pure-transport review, not a repeat claim
of real source, model or live worker acceptance.

## F1 — P2: rehashed features can relabel an original series when no effect runs

Location: `context_transport.py:59-63`, new E-Sport `_feature_binding` branch,
and its callers before `_eligible`/`_comparison`.

The new branch proves only that a caller's feature reference hashes the supplied
outer Event and Base. It never compares that outer Event with the **already
embedded, source-bound `original.reference_weights.event`**. Full base validation
replays the original using the inner Event, independently of the outer one.
With no effect, or an ineligible effect, `apply_esports_effect` is not called,
so its existing full original-event check is skipped.

Reproduction, using the actual C4 native-shaped B1 SQLite fixture and original
Base produced by the existing exporter:

1. Keep the entire original Base/receipts/parameters unchanged.
2. Swap outer home/away native IDs (team 7 and team 8), or change only the outer
   schedule, competition or best-of format.
3. Recompute only the FeatureVector reference hash with the documented
   `esports-context-reference-v1` formula. The base recipe still contains its
   original Event. No source receipt or owning source is modified.
4. `esports_features` correctly rejects these inputs as an original Event/Base
   contradiction. `calculate_context_payload(..., effect_artifact=None)` does
   not: it publishes the old oriented winner probability under the new Event.
5. The same acceptance occurs with a present but after-cutoff, missing-feature
   or foreign-population effect. Recomputing the input key and payload digest
   also makes the internally contradictory fallback survive full transport
   replay and light market projection.

This is a directly visible contradiction **within one claimed original-input
envelope**, not the general limitation that a content hash cannot prove provider
truth. No real provider, empirical approval or complete D3 coordinator is needed
to detect it. The reversed-team case can label team 7's original probability as
team 8's; a changed BO3/BO5 or schedule can similarly misdescribe the basis.
No such live production occurrence is claimed by these controlled tests.

Frozen reproductions:

- `test_independent_esports_fallback_binding.py`: four RED cases (orientation,
  schedule, competition, format), **one GREEN positive control**. The control
  constructs the legitimate original with genuinely unavailable native
  reference and preserves its existing baseline without an effect.
- `test_independent_esports_fallback_controls.py`: five RED cases (three
  ineligible effects, full replay, light projection). Every failure is
  `DID NOT RAISE ContextContractError`, not a setup/import/assertion-shape error.

Minimal repair boundary accepted by controller: in the owning E-Sport transport
path, before any effect-eligibility fallback and consistently in read/full
validation, require canonical equality of the embedded known original Event and
the outer Event. Keep the legitimate `kind='unavailable'` baseline path. Do not
call a fit/replayer during card projection, invent a new provider proof, ban a
market, mutate B1, or relax the actual C4 source/model guards. Re-run all frozen
probes unchanged plus permanent absent/ineligible/matching/unavailable controls.
No source correction was made during this independent review.

## Independent executed evidence

All commands used shared quality Python with `-B -m pytest -q -p no:cacheprovider`
and unique ignored basetemps. No test/probe assertion was changed after its first
execution. No original owning test was edited.

| Independent run | Actual outcome |
| --- | --- |
| 40 new adversarial/control probes + 12 owning new transport tests | 52 passed, 0 skipped, 15.00 s |
| Unchanged C4/B1/B3/all previous D3 transport focus | 588 passed, 0 skipped, 96.78 s |
| Four original-event attacks + unavailable-reference control | 4 failed, 1 passed, 2.27 s |
| Five fallback/read/replay qualification attacks | 5 failed, 0 passed, 2.54 s |

Total: **641 passed, 9 failed, 0 skipped**. Of 50 independently authored cases,
41 passed and nine demonstrate F1. All 600 selected owning tests passed. This
review did not execute the full repository suite; no owner result is recounted
as independent full-suite evidence.

Broader exact files: the six `test_esports_context*` files, `test_context_contracts`,
`test_context_snapshots`, `test_context_transport`, `test_context_transport_bytes`,
and `test_context_transport_hockey`. Tests use the actual local original exporter,
internal native-shaped B1 fixtures, real A1 storage and B3 callback mechanics.
They do not prove the internal native source transport is an available live feed.

## Other tested boundaries that passed

- Exact family/feature-version pair and no named preprocessing in this C4 v1.
  Missing, duplicate and retyped feature receipt references fail. An additional
  inspected-but-unused receipt changes the full input key without changing the
  distribution; resolving that receipt still belongs to the actual worker/D4.
- Untouched-reference Event/Base mutations are rejected (all twelve tested
  event/start/status/competition/format/team/model/history/code/parameter changes).
  F1 specifically requires rebinding the FV hash while preserving a contradictory
  inner original Event, which the owning twelve new tests did not cover.
- Missing/stale/conflicting consumed features do not execute the effect and keep
  exact original parameters/markets with empty certification. Synthetic approvals
  with future evaluation, other base version/coverage/population remain inapplicable.
  A synthetic single-market certificate does not certify the complementary market.
- Actual zero coefficients (integer zero, positive and negative floating zero)
  preserve original parameter/market bytes even under the synthetic applied role.
  Numerically saturated output is a typed unavailable comparison, not clipping,
  an invented zero effect, a hidden baseline or a quote gate.
- An independently changed/rehashed **comparison output** is rejected by full
  owning numerical replay; its old consumer reference is also rejected. A light
  identity validator alone is deliberately not arithmetic/source authority. That
  documented distinction does not excuse F1's contradictory original inputs.
- Card reads are detached and still pass with owning replay/application/offset/
  Elo, SQLite, sockets, built-in file open and Path reads forbidden. They do not
  fit or fetch. Full worker validation remains separate from this light read.
- A genuinely stored and loaded A1 effect plus two barrier-synchronized B3
  consumers executes the actual `apply_esports_effect` callback once, produces
  identical immutable payloads, and stays experimental without an approval.
  The key is formed directly from inputs, with no discarded comparison call.
  This establishes the B3 callback, not once-only upstream provider/base work.
- Explicit BO1 and BO5 baseline transports preserve original values. Unchanged
  C4 tests include original post-IID-roundtrip, fitting, lifecycle, exact-delta,
  and frozen legacy/Cricket parity regressions. No IID/Map law was substituted.

## No scope expansion / open integrations

This three-file packet does not change the C4 model, native source, participation
definition, baseline fitting, source capture, D2 approvals, Cricket or 15K rules.
Matching synthetic CPU approval envelopes demonstrate selection semantics only;
they are not actual D2 evidence. There is still no newly qualified roster/patch/
map-time feed, complete observed exposure, real E-Sport D1/D2 dataset, empirical
>=200-event approval, source-aware D4 replay, complete live D3 consumer pipeline,
browser acceptance, push or VPS deployment in this review.

The analogous C3 path already calls its owning binding validator in B3 before
missing-effect fallback. C2 was not expanded into a new review here; no separate
C2 finding is asserted without its own reproduction. Root owns cross-family
integration separately. None of these boundaries permits weakening F1.

## Frozen raw hashes

Actual Windows SHA-256, not a cross-platform source-byte equivalence claim:

| File | SHA-256 |
| --- | --- |
| `context_transport.py` | `2135afbcfab2519d496ed04a88ec9c320caf63a6105d73daf292a78e239103e6` |
| `tests/test_context_transport_esports.py` | `2208436ca7d381c7ba869f10e5eeeb565617e334ec4fce29ff8dd555e219d166` |
| Owning audit | `14d9d9fe21c1f1bc186dab876bd679fbdf14949804a97f2c4be28b05b742b852` |
| `context_models/esports.py` (unchanged) | `d2c95016828fde4b0c30f7849f239b647cdd12c1b97fa7a0fb7c8a287bf26e33` |
| `context_sources/esports.py` (unchanged) | `6719a39df1578e59e5c20197b6f2f6057253eee0fc4063bc1048b4de84beb567` |
| `context_snapshots.py` (unchanged) | `de9d8146917f568e1567cd8a92b92b64af1b33157f2afadf3c91c27a153de1da` |
| `context_models/contracts.py` (unchanged) | `5f810f023946021548f969adbbacfbb4b27a16d21e00c1b351f67300ca510b29` |
| `esports_elo.py` (unchanged) | `bd431e06926a319a68d5803749771595bbf72bb8561d39da2b8ee841d2af7140` |
| `multi_sport_recommendations.py` (unchanged) | `80c545cf82a577bd4d1540bbd2619a12171662781373161d6db4c80ba38615c5` |
| `test_independent_esports_transport.py` | `f3b91562ebcf8f78152174b9a540068f38edef95ea11968f533bd774e2745548` |
| `test_independent_esports_fallback_binding.py` | `d42c08961f507061c44ebc1bbf4ce6d72e38e678aa3d5dcfa312af760e07af32` |
| `test_independent_esports_fallback_controls.py` | `52c237fd4ea923ad19aff94b76bae775eb2cdf2db931f4fb9dae7c34c6b1bc5e` |
| `probes-01.xml` | `813a3af0b93268a6ce45b146aa8aea6545a4f65f8741b925ad9a8ef4bc72f9fe` |
| `focus-01.xml` | `183243550f5449b620b4abe4dfce5b9f327a5685732c4a7f8c3dd9f9b7e349a5` |
| `fallback-01.xml` | `b278d8a637539cd5017d396982fde86d9490acfa74329a01c0e5713d213b1812` |
| `boundaries-01.xml` | `ff8e74f0d05fce63c65d073f04278b32f79226dc1893030f64e3d8806625e9b5` |

The unchanged raw Elo file has Git blob identity
`ca390bc51976a5ce598c9a2a952568cd25439ca2`; no line-ending normalization was done.
Source/owning tests/audit hashes and clean Git status were rechecked after all
runs. Only this new ignored report, three independent probe files, JUnit and
their isolated temporary data were created. No source/Git/provider/VPS writes.
