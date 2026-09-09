# P4a — same-call Basketball/Hockey originals

Controller-approved bounded packet, based on
`1b77286d06f9731c1ffa38ba3d408f20fff1b02e`, 9 September 2026.

## Contract fixed before implementation

- New base versions: `basketball-live-original-margin-v1` and
  `hockey-live-original-poisson-v1`.
- New reference kinds: `basketball-live-margin-origin-v1` and
  `hockey-live-poisson-origin-v1`; captured payload kind
  `team-sports-live-original-v1`.
- Builders consume the actual `OriginalPrematch` from the same calculation,
  not a second `predict_prematch`, target `_fit` or target `_predict`.
  Basketball may calculate signed auxiliary Ridge influences; Hockey may
  evaluate the existing forward distribution from the actual original rates.
- `CapturedTeamSportOriginal` returns `original`, optional `base`, and
  `context_unavailable_reason`. Missing native Event/context provenance does
  not discard the pure captured original or change the legacy prediction.
- Receipt binding is closed: schema 1, kind
  `team-sports-live-receipt-refs-v1`, nullable `event_receipt`, indexed
  `history_receipts` (`input_index`, `receipt`) and `artifact_refs`. These are
  unresolved references, not source-verification flags. Actual A1/B1 resolution
  belongs to P4b/D4; the new base has no certified `history_refs` in this v1.
- Pure reference/original validators check the declared captured computation
  and exact forward law. A separate explicit offline replay checks the fitted
  baseline. Neither alone establishes a provider receipt's source truth or D2.
- Native raw metadata and the unchanged legacy normalization/defaults remain
  distinct. Unknown neutral-site, season or rules cannot become known from the
  canonical fit. No implicit C3 2026/27 or preseason approval.
- No prices or bookmaker fields enter the captured model/original identity.
  An inline fit hash is not a previously published A1 model. Publication and
  actual receipt-clock resolution remain later owning worker responsibilities.
- Old C2/C3 versions and validators retain their semantics. No Consumer,
  Transport, D4, source-loader, Cricket, money or production changes.

The raw original source before edits is
`sports_prematch.py` SHA-256
`1d908a32d4decdd508477526af9802f3a81bd9054f93636e4df8c63675b9a07d`,
Git blob `974f6d106ddaed2131690bdc83bc9af1ceaf75ca`.
The independent same-CPU legacy fixture remains SHA-256
`b4e44d03d09a6c8f22ce52568ea36f9af1c7e563d094af98c135703a0a204677`.

Implementation, RED/GREEN evidence and independent review are pending at this
initial contract note. No completed P4b source integration or empirical effect
activation is claimed.

## Implemented P4a boundary

The new module provides:

- `build_basketball_live_original(original, *, event=None, receipt_binding=None)`
  and `build_hockey_live_original(...)`, returning the frozen three-field
  `CapturedTeamSportOriginal`. Its two JSON objects are detached both from the
  captured input and from each other. The old prediction object is never changed.
- `validate_captured_team_sport_original`,
  `validate_team_sport_live_reference` and `validate_team_sport_live_origin`:
  pure, typed, closed internal/forward consistency checks, with no runtime file,
  database, provider, optimizer, target `_fit` or target `_predict` access.
- `replay_team_sport_live_origin(base)`: explicitly fresh offline target fit
  using the owning original `_fit.__wrapped__`, followed by the old forward
  predictor. It does not present an LRU cache hit as fitted provenance. It
  returns the same original base on exact agreement and raises on divergence.

The original stores the price-free projection of the actual raw input inventory,
not an unrestricted provider blob. Projection retains whole supplied historical
revision order, including invalidated/ignored rows; `input_index` refers to this
raw inventory, not a zip over the selected `_Match` rows. Full projected inputs,
the complete supplied canonical native Event, the actual normalized model input
hash, ordered selected model rows, captured fit, unrounded outputs and receipt
links are bound separately. Irrelevant top-level and nested rule-price fields
are excluded. Model hash excludes receipt-link changes as well as all prices.

The native Event is optional and must match the actual raw known target ID,
participants, competition and schedule when supplied. Native facts are never
borrowed from NFKC/casefold-normalized model identities. `native_scope` describes
only the compatible **current raw declaration**, not a proven receipt, historical
roster scope or source completeness. Missing raw neutral-site remains unknown
even if the inherited baseline executed with neutral=False. Missing IDs preserve
the pure capture with no native base; known contradictory IDs fail explicitly.
Unsupported native format likewise preserves the original, without inventing a
new context population. Unknown rules/season preserve an otherwise compatible
base with `native_scope=None`; new 2026/27 rules are not certified by this path.

Basketball auxiliary values are the actual signed Ridge influence operation
`q @ solve(X.T @ X + diag(penalty), X.T)`, with no target-score RHS,
coefficient solve, residual-scale re-estimation or positive normalization.
The pure validator may repeat this auxiliary operation to check it; it is not
a second target fit. Hockey auxiliary kind is deliberately new:
`hockey-inline-contributing-sample-indices-v1`. It names selected model-row
indices, **not already measured skater/goalie exposure**. It does not reuse the
old C3 exposure variant's schema or invent TOI. The original legacy OT/SO
winning-goal subtraction stays named as an inherited model assumption.

The shared `contracts.py` change is exactly two narrow dispatch additions,
11 lines total, for the two new exact reference kinds and owning families.
The new validator receives the original caller bytes, so normalization cannot
hide changes to an already canonical captured cutoff. There is no generic
`skip`, `verified`, comparison exception, old-version relabel or effect change.
No helper extraction from the old C2/C3 model files was necessary: their source
bytes and all old semantics remain intact.

## Meaning of successful verification — important integration requirement

The receipt binding has no successful source-resolution state in P4a.
`source_resolution` is always `unresolved` and the new BaseDistribution's
`history_refs` is exactly `[]`. Nonexistent or uninspected digest strings cannot
self-certify a native or roster join. P4b/D4 must resolve the actual A1/B1
objects; a caller-created `OriginalPrematch` object is not a cryptographic
capability or independent proof of how a model was trained.

A permanent adversarial control changes a non-target coefficient and recomputes
the new public inline-model hash. Its unchanged forward prediction is internally
consistent, so the **pure** validator correctly still classifies it unresolved.
The explicit fresh offline fit rejects it. An externally pinned original A1
artifact also has a different content hash after this change. Therefore neither
pure shape validation nor a self-recomputed public digest may be used by a future
worker/reader as successful source or fitted-model provenance.

P4b's newly declared EuroLeague B1-only `season:<season>:game:<gameCode>` identity
is not silently converted into an `E<season>_<gameCode>` C2 identifier here.
Without an owning alias resolver, supply no native Event and retain the pure
original. The positive EuroLeague test uses a synthetic explicitly received ID;
it is not evidence of a real source alias or feed availability.

Existing C2/C3 feature/effect versions and B3/Transport/D4 routes are not updated
by this packet. Their activation of the new origin versions, actual source
receipt resolution, publication clocks, shared normal/Risk consumers and real
D2 evaluation remain separate work. No missing odds or source reference removes
an existing legacy prediction, but no new learned effect is claimed either.

## RED/GREEN and final verification

All tests use the isolated worktree and the existing quality Python, no new
source request, source-cache write or production database.

- Initial TDD: 51 expected missing-new-API failures and one passing exact
  Cricket control, 2.02 s. This is an absent-API RED, not 51 production bugs.
  JUnit `.pytest_tmp/p4a-original-red-01.xml`, SHA-256
  `6e8dd192ad4de33cf991a1c5d574ddcc335f76d9cfc06738d761b0aa8f052171`.
- First implementation: 52 passed, 3.39 s.
- New boundary probes then found 6 RED / 67 GREEN: two noncanonical-clock cases,
  two missing-native-ID capture-preservation cases, and two malformed-tag typed
  errors. Corrected without relaxing native identity or old base contracts.
  JUnit `.pytest_tmp/p4a-original-boundary-red-01.xml`, SHA-256
  `2e6bd4080bb917b342f946aafaa25c76bbbdf0c8b2da651d7ec8c72b8db842d0`.
- Additional type probes found 6 RED / 8 GREEN: nonfinite output JSON and replaced
  dataclass parts raised the wrong exception class. Corrected to typed contract
  errors, no clipping/coercion. JUnit `.pytest_tmp/p4a-original-types-red-01.xml`,
  SHA-256 `3ec8b0729e332312d6d4bba8db110affe904030ce8ef77af8775bd0090793727`.
- Owning 102-test stage: all passed, 5.76 s; first broad focused run:
  1,373 passed / 2 existing Windows skips, 111.96 s. The latter JUnit
  `.pytest_tmp/p4a-original-broad-01.xml` has SHA-256
  `f3bde170bdc9adc9f3e7dbc234879a491528c2c7ac2562c0d9e16c3e88d92cc8`.
- A final semantic-label RED distinguished Hockey model sample indices from
  measured exposure. Two new runtime-IO controls were already green. No old
  C3 source/variant changed. JUnit `.pytest_tmp/p4a-original-aux-label-red-01.xml`,
  SHA-256 `947fe96bdc4e34e56f943a33b80366bd21aa25c8f7fa5a5048301c9587eadc94`.
- **Final frozen-source focused broad run: 1,376 passed, 2 skipped, exit 0,
  109.26 s.** It includes all **105 new owning cases** (confirmed from JUnit),
  existing sports/original-capture, C2/C3, B1/B2/B3, native Event, transport,
  reader trust, domain and Risk adapters. JUnit
  `.pytest_tmp/p4a-original-broad-final-01.xml`, SHA-256
  `d2726e1969fae4054dcdd1afb95d4139489d6398d24e3354e8f77f8f6ed74c73`.
  Skips: existing `test_context_reader_trust.py:188` and
  `test_ice_hockey_revisions.py:220`, both unavailable real Windows symlink
  privilege, not missing new numerical coverage.

Once-spies use actual cold target computation and preserve legitimate historical
prequential folds; builder/validators perform no additional target fit/predict.
An auxiliary-RHS spy distinguishes allowed signed-influence solves from target
coefficient/variance solves. Exact same-CPU frozen Cricket predictions and Risk
IDs are checked, alongside negative clock, raw/native identity, original float
ULP, missing model/neutral/OT, stale/corrected full-history, malformed numerics,
publication-link and price-independence cases. Runtime-IO spies forbid file,
database and provider access during both build and pure validation.

The controller requested no separate complete suite for this packet; the run
above is broad focused regression, not a claim of a new whole-repository full
run. Independent review and later joint integration remain pending.

## Frozen source identity

Checked again after the final run, raw local SHA-256 values:

```text
ca6d4f31a113f656f94934c59b03f07fbf5565626aa7eefa38793fb030212308 context_models/team_sports_live.py
7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8 context_models/contracts.py
033de00e971455918c9d24e6f5b88a549b5eea5795ab25be290baca7869cbc23 tests/test_team_sports_live_original.py
```

Unchanged baseline sources:

```text
1d908a32d4decdd508477526af9802f3a81bd9054f93636e4df8c63675b9a07d sports_prematch.py
6d93c2b77ce5f0085cb1861edcc9524d3064b84faa772b501bf8481fedfb7228 context_models/team_sports.py
5b27b2fc84c354e87e7842e5191658f9aea9f0213f4a9e5e2136270c4f1280d4 context_models/ice_hockey.py
```

No merge, push, provider request, server/deployment, Consumer, Transport, D4,
player-feed, money/ledger or historical-data changes were made by P4a.
