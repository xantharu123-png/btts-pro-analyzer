# Independent D3 domain-reference review — 9 September 2026

Decision: **REQUEST CHANGES**, one P2 finding. The domain/store identity extension
is otherwise supported by the bounded checks below. This report is against the
original frozen commit, not a corrected successor.

Target: `9de9b52ab096c8c08852460dfe8226854014e789`.
Isolated detached worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-domain-review-20260909`.
No source, owning test, Git commit, provider, VPS or production database changes.
Only ignored probes, local temporary database fixtures and this report were added.

## Read scope

Read the full approved `2026-09-07-kontextmodell-design.md`, task-18 brief,
task-18 controller rulings, context-contract decisions, all eight commit diffs,
the complete owning audit and all 14 new test cases. Examined the concrete
reference validators, ModelSignal serializer and both JSON readers, the full
common model/strict/challenge document comparison, EventModelSnapshot identity,
strict UI hydration, immutable store insertion, transaction/membership checks,
both changed snapshot verification sites and consumer publication/readback.

The packet is optional domain transport, not a provider or empirically approved
worker implementation. Its reference is a two-digest immutable value in the
existing four-field JSON envelope. That alone does not verify actual B1 inputs
or D2 acceptance; the established worker and persisted-context reader own those
different boundaries.

## F1 — P2: common document accepts non-integer reference schema aliases

Location: `ev_signal_sources.py::_load_automated_wettfinder_document`, common
model/strict and model/challenge comparisons around lines 989–1044; the new
individual hydration occurs only later around lines 1431 and 1645.

Reproduction uses the real current-version automatic document fixture, with
its valid football model, price overlay and challenge overlay. Serialize and
deserialize JSON first so the three reference dictionaries really are distinct.
Change only one `context_ref.schema` from integer `1` to JSON `true` or `1.0`.
The owning `ContextReference.from_dict` correctly rejects that shape, but the
shared document loader accepts it: ordinary Python dictionary equality treats
`True == 1 == 1.0`. Altering all three copies also remains accepted at that
common boundary.

Concrete consequence when only the model row has `schema=true`: the forecast
reader returns no model signal, while the strict reader still returns its
`RELEASED` signal with the superficially matching valid integer reference.
The model/price decision is no longer one validated immutable revision.
The challenge overlay is likewise not independently parsed at this boundary.
This is malformed model provenance, not missing bookmaker price, bad source
coverage or a claim of an observed production ledger defect.

Evidence:

- `test_domain_overlay_qualified.py`: three genuine failures for a single
  boolean-schema mutation, 13 passing mutation/concurrency controls.
- `test_domain_reference_type_witness.py`: eight genuine direct-loader failures,
  boolean/float schema × model/price/challenge/all, with a preceding assertion
  that the closed owning reference validator rejects each malformed value.
- Valid distinct digest or missing/null-reference mismatches are already
  rejected; the relevant missing step is closed individual validation before
  numeric Python equality can collapse distinct JSON types.

Smallest correction: parse every actually present optional reference in each
model, strict-price and challenge row through the closed owning validator
before accepting/comparing the common document. A malformed claim must not
reach a release-capable overlay or be relabelled as legacy missing data.

Root explicitly confirmed the existing **whole-document integrity rejection**
semantics for this narrow fix. Do not introduce a partial-loader redesign.
Genuinely absent legacy fields remain allowed. Missing/low bookmaker quotes in
otherwise valid documents still preserve the model forecast; malformed context
identity is a different condition. Permanent positive controls for legacy,
UNAVAILABLE and below-minimum quotes belong in the correction packet.

## Passing independent controls

- Closed reference types: exact lowercase SHA256, no bool/float/object/list
  coercion, required keys, no price/approval/verified/event extras. Agreement
  with the existing persisted-context reference validator.
- Frozen instance, slot storage, hash stability and separately returned JSON;
  mutations of input or returned dictionaries do not change stored identity.
- Actual Git parent domain blob executed independently: all six existing sports,
  including Cricket, retain exact canonical snapshot/candidate/run JSON and IDs
  with no new `context_ref:null` field. Unicode/HTML-like labels are data only.
- Actual SQLite original `UNIQUE(event_key,model_version,input_hash)` remains;
  a changed context with the old input hash rejects and rolls back all rows.
  A separate input revision coexists, exact retries remain idempotent, old
  payloads are unchanged and schema version remains three.
- A real two-thread append race with different contexts and the same original
  input hash persists exactly one entire run; the other reports immutable
  conflict. A subsequent correctly distinct input revision succeeds.
- Canonical rehashed snapshots with removed/changed/invalid/null references
  cannot retain their old snapshot identity in either UI hydration or actual
  database readback. Readback does not modify those temporary corrupt bytes.
- Legacy V1 data uses its existing migration path without introducing a new
  optional context field. No migration was added or source schema altered.
- Separate valid price values and naturally stale quote evidence preserve
  model probability and the same immutable reference. Expired price evidence
  does not remove the model forecast.
- Real B3 `compute_once` temporary SQLite rows, once-only callback, domain JSON
  serialization, normal ModelSignal readback, RiskBetStore publish, strict UI
  hydration and persisted-context market projection were exercised together
  with absent and experimental effects. Both consumers retain the same ref and
  original distribution, including opposite exact canonical markets. Provider
  and owning effect functions were forbidden during final consumer reads.
  These synthetic inputs prove carriage/replay mechanics, not real source truth,
  live worker wiring, a D2 approval or globally once-only upstream provider work.

## Original probe preparation error retained separately

`test_domain_independent.py` initially had six failures in the digest-mismatch
overlay cases. The existing fixture shallow-copies the nested reference;
`deepcopy` preserves shared aliases across that object graph. Mutating one
nested field therefore changed all three rows. The output was internally
consistent, so those six expectations were invalid reviewer preparation, not
source defects. The three remove-field cases and all other 85 checks passed.

The entire original file and first result remain byte-identical. The separate
qualified file uses actual JSON detachment and asserts that both untouched
collections still equal the original reference before reading the artifact.
No failed assertion was weakened or overwritten. The additional real boolean
finding was discovered only in that correctly detached case.

## Independent execution ledger

Python: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
All runs use `-B -m pytest -q -p no:cacheprovider`, distinct `.pytest_tmp`
basetemps/JUnit XMLs. No outcome is borrowed from Root's d280 full suite.

| JUnit file | Actual result | SHA256 |
| --- | --- | --- |
| `domain-owning-01.xml` | 298 passed, 26 subtests, 6.85 s | `933e4501f3c017c8e825cb22a5ba06b203b0a7c206b2e475a67b7a4523b6427c` |
| `domain-independent-01.xml` | 88 passed, 6 reviewer-alias failures, 3.32 s | `f07692fc731a93a5fbaaa301b1ad7483f9877eed5948178f67f5a664c7a495ac` |
| `domain-qualified-01.xml` | 13 passed, 3 genuine failures, 2.32 s | `f6b48a96e438bc0c3062118d9eef51ccfddc0510efdcca4ef91e7cc681e0e913` |
| `domain-type-witness-01.xml` | 8 genuine failures, 2.11 s | `14b19aa315320b01057cc08b2734ffb2fdf7fcb2f87fe9879fd9616b99ecbab0` |
| `domain-integration-01.xml` | 393 passed, 33.52 s | `1b7c3649a73547d03e5f0201e9856e3af630be5ec677d7f4d04e74c1024a71d4` |

The 393-case integration command covered complete RisikoBet automation,
candidates, surface, settlement and settlement-automation suites; all four
context-transport suites; persisted context consumers; Wettfinder surface;
market scope; and Tennis prediction revisions. No skips or deselections in
any of these five independent review runs. All original sources/probes and
results remain frozen. No whole-repository run was performed for this review.

## Exact frozen bytes

| Source / owning test / audit | SHA256 |
| --- | --- |
| `context_links.py` | `9cef750abca4a210c25725cae07412deb3bbd64a2f8dddddf162048fd49cae1d` |
| `ev_signal_sources.py` | `d0778944bff8bcc003aa472c656e2e60af925fde1c7e5ee8243a12656f4cf879` |
| `riskobet_domain.py` | `a4650e19a33220e036fe12602300027f1ecb4e06e949837baf7076687784e762` |
| `riskobet_store.py` | `64d9324c2cb7296666018aadaa867ca601ce9cae32c52fc33b1a940a6dd30948` |
| `riskobet_ui.py` | `7e0178289688c5845178b1ec0ba99f4d9d6778eb0f20c6e0978e5cf232200d51` |
| `wettfinder_automation.py` | `360e4515f6b3a14e3ee523e3b6ac4988a8bd8ba12009dc291af1ce9670fc6367` |
| `tests/test_context_domain_links.py` | `c9dbdf14317377ea2a65f9255f21f84e897b074a8b37ebb3b66955cf65faf9fd` |
| `docs/audits/2026-09-09-d3-domain-links.md` | `85aee5dc4dee21d5c97a8d31b16e8750f3edf0ddfe099c1840741a6487410a23` |

| Unchanged independent probe | SHA256 |
| --- | --- |
| `test_domain_independent.py` | `d6b9f609b748d5152b542efd3939c93b23d2fdacfb408769f1dba0c20a55c8e3` |
| `test_domain_overlay_qualified.py` | `e34d98f55ddf9d75b5adc137498547bae0e7a99888e9c2c2f6d9f0ba0e815991` |
| `test_domain_reference_type_witness.py` | `5dc4bf48712e972a569976018c527a50816d4848e92070515a9c8363d348c410` |

No full-repository, empirical, live-producer, actual source, browser/UX, VPS,
price profitability or 15K approval claim. The earlier reader physical/schema
findings and their separate 4011392 correction are outside this domain package;
the integration controls here do not relabel 9de's original reader as fixed.
