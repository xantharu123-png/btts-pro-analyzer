# Task 5 / B1 — independent frozen-source review

Date: 2026-09-08. Verdict: **NOT APPROVED — three P2 findings remain.**

The causal storage foundation is substantially implemented, but `factor_state`
does not yet provide a reliable boundary between inspected records and usable
factor evidence. Two findings additionally reproduce incorrect factor states,
not merely confusing diagnostic references. Fix and independent re-review are
required before accepting B1 for downstream numerical consumption.

## Exact reviewed scope

- Checkout: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-b1-20260908`.
- Base: `156ba46a610f690ff792b1bee752ba3692d11dff`.
- Reviewed HEAD: `9a4e04f7aa65ea5f9f0a1e8e7ef91216951274e6`.
- Exact diff: five new files, 1,787 added lines, no existing source changes:
  `context_models/__init__.py`, `context_models/contracts.py`,
  `context_observations.py`, `tests/test_context_contracts.py`, and
  `tests/test_context_observations.py`.
- The complete implementer report, authoritative task-5 brief, current
  `context-contract-decisions.md`, `validation-contract-decisions.md`, and
  approved design specification were read. Authoritative contracts came from
  sibling `kontextmodell-20260907`, not potentially stale copied briefs.
- Read the new implementation/tests and relevant unchanged A1 decoder,
  connection and runtime trust checks. No production caller of the three new
  observation functions exists in this frozen checkout; B3/B4 remain future
  consumers. This review therefore does **not** claim an observed live forecast
  or actual training-data leak.

The five raw SHA-256 values were independently checked and match the report:

| File | SHA-256 |
| --- | --- |
| `context_observations.py` | `e8c704de8c74abd61c9d7124deff76311f45b3897fb3009283513fe6247b09f8` |
| `context_models/__init__.py` | `3b2c557620c83acbbdecc9422ef3b00d83ae0006a710b761683f4eed8747a91f` |
| `context_models/contracts.py` | `8c8d57214bb4c7ff5c46583b0adc13e2e191bf43760d11a083dd66392aceefdd` |
| `tests/test_context_observations.py` | `4251684b5337fe1940badd3abc7c4b05d3ff8538e189caf638a51f347be6200f` |
| `tests/test_context_contracts.py` | `720c29fd3b813ff6bd3396afb936abadc63dc0ba6fa84129063560371020aca4` |

## Findings

### B1-R1 / P2 — distinguish inspected references from usable factor evidence

Anchor: `context_observations.py:310-315`, with filtering at `324-325`,
`340-369` and source-precedence selection at `381-383`.

`refs` is constructed from every input row of the requested kind, before
schedule, receipt/evidence class, validity, freshness or source precedence is
checked. The same unqualified list is returned with `state="available"`.
Consequently, an otherwise valid available factor includes hashes of:

1. A next-day, explicitly retrospective correction returned by the legitimate
   historical reader at the original decision time.
2. An observation for a different schedule revision.
3. An unrelated event with a different schedule revision, bypassing the later
   eligible-only event consistency check.
4. An expired secondary source.
5. A contradictory source explicitly discarded by configured precedence.

Minimal primary reproduction: append one availability receipt at 2026-09-07
12:00Z and its corrected receipt a day later; query `mode="historical"` at the
first cutoff, then call `factor_state` at that cutoff. The result is available
and `refs` contains both the causal and retrospective receipt hashes, with no
per-reference eligibility distinction.

The stored receipts and reader classifications are correct; the loss of that
distinction happens in the factor result. Retaining rejected records as audit
evidence is legitimate, including in the brief's `missing` example. The defect
is presenting only this undifferentiated collection at the boundary expected
to feed feature provenance. An `available` flag must not make all those hashes
look consumable. Preserve audit references separately, or explicitly define
the existing list as audit-only and supply a separately validated usable
selection to downstream feature construction. Do not simply erase audit
history. All usable references and associated metadata must come from the
final same-event/schedule, causal, fresh, precedence-selected rows.

Reproduction: `task-5-review-repros.py:50-88`,
`test_available_refs_exclude_nonconsumed_observations` — all five cases fail.
These assertions encode the required usable-reference separation. A reviewed
interface that explicitly separates audit/usable refs may adapt their field
names; preserving the old ambiguous result alone does not resolve the issue.

### B1-R2 / P2 — validate event status scope and validity before early return

Anchor: `context_observations.py:319-322`.

An `event_status` row bypasses the event/sport/competition/format consistency
check because the early return occurs before `eligible` is built and that
check only considers rows of the requested factor kind. Matching schedule
revision text is not matching native event identity. Its validity interval is
also ignored.

Minimal reproduction: append a healthy availability fact for native event 1
and a cancellation for native event 2, both with `schedule_revision="s1"` and
receipt at the same cutoff. Combine the two public query results. Evaluating
event 1's availability returns `not_applicable`, rather than rejecting mixed
event input or ignoring event 2. The same issue reproduces for `started` and
`completed`.

A second same-event reproduction uses a cancellation observed now but valid
only one hour later, or a cancellation whose half-open validity interval ends
exactly at the decision. Both also return `not_applicable` now. These are
fully hash-valid records created and read through public B1 functions.

Bind status observations to the same native event and full declared scope,
schedule, causal decision and applicable validity interval before allowing
them to change factor state. Preserve the actual status evidence as audit
provenance of the invalidation; currently returned `refs` contain only the
availability fact, not the status responsible for the decision.

Reproductions: `task-5-review-repros.py:91-121`,
`test_unrelated_event_status_cannot_disable_current_event` (three failures),
`test_status_outside_its_valid_interval_cannot_disable_current_event` (two
failures). The positive same-event current-cancellation control passes.

### B1-R3 / P2 — recompute missingness/completeness on the final selected rows

Anchors: `context_observations.py:330-333`, `372-392`.

The actual-fact check runs before stale rows are discarded; completeness is
checked before precedence is applied. Precedence only changes a local list
used for conflict detection, not the collection used for the final state.
This lets excluded evidence authorize an otherwise unusable remaining input.

Two minimal public-path reproductions:

- At 12:00Z, the only actual player fact was received at 05:00Z and has expired
  under the unchanged six-hour policy. A second source received at 12:00Z has
  `complete=False, payload={"status": None}`. The stale first row passes the
  early actual-fact check, the empty second row supplies freshness, and the
  result is **available** with a new 18:00Z deadline. No fresh reported fact
  exists. This must remain missing/stale, not available.
- A fresh but incomplete official team collection wins explicit source
  precedence over a fresh complete secondary collection for the same subject.
  With `requires_complete=True`, the discarded source satisfies the earlier
  `any(complete)` test. The selected incomplete collection is then returned as
  **available / incomplete**, despite the explicit complete-collection
  requirement. It must remain missing/incomplete unless the actually selected
  evidence establishes the required complete collection.

Compute fact presence, required completeness, coverage, usable references and
freshness metadata consistently from the final source-selected usable rows.
Do not convert an empty player fact into a healthy/status observation, and do
not borrow completeness from a source excluded by the declared precedence.

Reproductions: `task-5-review-repros.py:124-155`,
`test_stale_fact_cannot_make_fresh_empty_player_payload_available` and
`test_precedence_loser_cannot_supply_required_collection_completeness` — both
fail against the frozen commit.

## Independent test evidence

Commands below were executed from the B1 checkout. Each basetemp child was
verified absent before invocation. No existing test directory was overwritten.

Focused implementation and foundation suite:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider tests/test_context_observations.py tests/test_context_contracts.py tests/test_context_coverage.py tests/test_model_artifacts.py tests/test_runtime_paths.py --basetemp=.pytest_tmp/b1-independent-focus-20260908-01
```

Result: **218 passed, 4 skipped in 2.16s**, exit 0. These are independently
executed results, not the implementer's reported 2,057-test run. The four
platform-specific skips are not asserted to have passed on Windows.

Independent adversarial regression file, retained beside this report:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider '.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-5-review-repros.py' --basetemp=.pytest_tmp/b1-independent-edges-20260908-01 --tb=short
```

Result: **12 failed, 6 passed in 0.60s**, exit 1. Failures correspond exactly
to the 5 + 5 + 2 cases above. All use isolated SQLite files and real public
append/query/factor paths, not forged in-memory hashes or patched product
behavior. Six controls pass:

- A current same-event cancellation legitimately disables its factor.
- A future receipt alone is omitted prospectively, labelled retrospective
  historically, and cannot make a live factor available.
- Exact receipt retry is idempotent; a real recheck adds a receipt without
  modifying the original content/receipt or earlier query result.
- Corrupt content is rejected by both the public reader and append retry.
- Both public B1 database paths preserve the A1 symlink trust guard. The two
  Windows-safe guard tests simulate only the unsafe filesystem metadata; they
  do not create a real external symlink or claim a Linux permission exercise.

## Other reviewed boundaries and limitations

No additional findings were identified in this bounded review of canonical
receipt/content hashing and atomic retry, empty real archive registry,
separate prospective/retrospective query groups, the closed JSON/model/head
contracts, explicit population membership, ordered features, or reused A1
path trust and strict persisted decoder. Future-only archive and retrospective
records are not numerically eligible merely because they can be inspected.
Typed contract acceptance remains distinct from certified source truth.

No coefficient fitting, real provider/archival validation, numerical effect,
D1/D2 empirical approval, supported new market catalog, production backup,
deployment or live activation was tested or approved. A1's known Linux-only
checks remain a separate platform gate. The inherited A4 base is not the scope
of this five-file review and no A4 change was made.

No product/source edits, Git mutations, provider/network/VPS calls, subagents
or production database writes were performed. Only this report and the review
reproduction file were created, with test data under the two unique basetemps.
The inherited `scripts/stage_runtime_databases.py` status was left untouched;
its pinned raw SHA-256 remains
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
