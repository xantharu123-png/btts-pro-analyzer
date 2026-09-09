# Independent D3 public-copy review — 9 September 2026

## Decision

**PASS within the explicitly bounded pure-projection contract. No actionable
finding reproduced in the two frozen review targets.** This is not approval
of the D3 transport, worker integration, data provenance, empirical activation,
renderer escaping or actual browser behavior.

Reviewer: `worker_failures_20260909`, independent of the Root implementation.
The C4 worktree/commit `26e891096ecee78ac962b5090a8294deefd7d395` was preserved.
No production file, owning test, Git state, worker/UI source, provider or VPS
was changed. Only this review packet and isolated pytest output were added.

Root worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Observed HEAD at final review check: `d0cceb6d9c4bbdebe7a980a197c5f8d767050985`.
The review identity is the exact file hashes below, not an assertion that all
other concurrent Root work was frozen or reviewed.

## Read contracts and exact scope

Read in full:

- the approved `docs/superpowers/specs/2026-09-07-kontextmodell-design.md`;
- `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-18-brief.md`, including
  its full inherited constraints and D3 workflow/browser acceptance boundaries;
- that directory's complete `context-contract-decisions.md`;
- its complete `task-18-controller-rulings-20260909.md`, using only the settled
  public-copy decisions as the implementation criterion;
- both complete review target files.

The shared text/number/market validators were inspected narrowly to determine
what their existing typed display checks actually guarantee. They were not
expanded or treated as a new independent family/source review. The concurrently
edited `context_transport.py` was not inspected, frozen or reviewed.

This function intentionally receives a **worker-verified** result and an owning
explicit grouping. It is not a provider resolver or D2 approval authority.
Therefore absence of cryptographic/source/approval replay inside this function
is not reported as a defect or replaced with a new free `verified` mechanism.
The review instead attacks its stated closed display contract.

## Frozen bytes

| File | SHA-256 |
| --- | --- |
| `context_copy.py` | `f69678e5888aeddc21177d5660ca6bf9e220413a2653a3b2445efee4bab88683` |
| `tests/test_context_copy.py` | `d9500369a2821a0f633613a560bcda52e4e372050e985bd6e59ddabfc5cdb73a` |
| `.pytest_tmp/d3-copy-independent-20260909/test_d3_copy_independent.py` | `959953697f2e3034d181c67d98d3d507a1c934a540bfd73b4d8e5f13d08d9931` |

Both target hashes matched the controller-provided values before and after the
review. The independent test file also asserts these exact target hashes, so a
different source cannot silently inherit this recorded pass.

## Own executions and probes

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Every execution used `-B -m pytest -q -p no:cacheprovider` from the Root worktree.

1. `--basetemp=.pytest_tmp/d3-copy-independent-owning-01 tests/test_context_copy.py`:
   **33 passed**, 0.10 s, exit 0.
2. `--basetemp=.pytest_tmp/d3-copy-independent-probes-01
   .pytest_tmp/d3-copy-independent-20260909/test_d3_copy_independent.py
   tests/test_context_copy.py`: **178 passed**, 0.25 s, exit 0.
3. Final exact probe bytes, after only clarifying one probe function's name:
   same two test paths with
   `--basetemp=.pytest_tmp/d3-copy-independent-probes-02`:
   **178 passed**, 0.24 s, exit 0.

The final 178 comprise **145 independently written cases and 33 owning cases**.
No production source or owning test was patched to obtain this result. The
controller's larger workflow/full-suite counts were not rerun here and are not
presented as this reviewer's evidence.

## Verified behavior

- **Data state versus numerical role:** full 3 overall roles × 3 leaf roles ×
  5 legal data states. A leaf cannot outrank the overall role. Missing, stale,
  conflicting or not-applicable leaves cannot claim a modeled effect. Available
  but unconsumed/experimental leaves remain known with `Wirkung offen`, not
  `eingerechnet` (`context_copy.py:63`). Per the settled compact-copy policy,
  unavailable grouped data receives a missing-data caveat, not a false healthy,
  known or numerically included statement.
- **Partial is a grouping result, not a new leaf state:** mixed consumed and
  unconsumed members are `teilweise eingerechnet`; missing group members retain
  a data-gap caveat. Illegal `partial`, `healthy`, `checked`, bool, null and
  object leaf states are rejected. Duplicate/unknown group members and non-owning
  labels are rejected (`context_copy.py:75`, `:85`).
- **Exact selected orientation:** home, away and draw were independently selected
  across all roles with differently ordered dictionaries. Base/used probability
  and signed percentage-point delta are exact selected values, not the first
  entry or a rounded/corrected substitute. One-ULP changes remain nonzero stored
  values. Distribution/delta/role contradictions are rejected (`:52`).
- **No invented individual attribution:** an exactly cancelling aggregate with
  several applied factors says only `Gesamtprognose unverändert`; it does not
  say an individual injury/workload factor had zero effect. This projection is
  per selected market, as specified: a selected draw can have zero change while
  home/away markets changed. The function does not derive counterfactuals or
  assert an additive decomposition (`:106`).
- **Closed, non-numeric public narrative:** arbitrary technical names containing
  `injury` or `weather` do not manufacture an injury/weather explanation without
  an owning explicit group. Only the static vocabulary enters public summary
  and missing-data strings. HTML-like market, feature and group identifiers are
  rejected; no team/display-name field is accepted as an extra public input.
- **Numeric corruption:** 44 independent probability/delta mutations included
  booleans, null, strings, NaN, infinities, containers, complex numbers and an
  overflowing integer. All raise the owning contract error rather than leaking
  malformed values or a raw conversion exception.
- **Admin separation and immutability:** raw limitations deliberately containing
  HTML and technical/provider diagnostics are retained only in detached
  `admin_details`. Public fields contain none of those bytes or optional raw
  hashes/refs. Mutating returned admin roles, states, member lists, limitations
  and the returned missing list leaves the complete original input unchanged
  (`:109`). Price/bookmaker/raw-provider fields are rejected as extra copy input.

## Boundaries retained for later D3 review

- This does not establish that an actual worker supplied truthful group semantics,
  rebuilt features from causal B1 receipts, resolved real A1/D2 approvals, selected
  a valid current event revision or performed upstream work exactly once.
- Worker and UI adapters are not proved wired by a successful call to this pure
  function. Optional legacy fields, immutable prediction/ticket bytes, price-only
  refresh identity and both actual tab paths require the separate workflow review.
- The function intentionally emits no public dynamic HTML. This proves absence
  of those raw strings in **this projection**, not that later Streamlit/card/admin
  renderers escape all content. `admin_details` is raw administrative data and
  must never be rendered wholesale as public copy. No browser was opened and no
  responsive, accessibility, console or rendered UX acceptance is claimed.
- Statistical/causal effect truth, untouched cohorts, source coverage and runtime
  activation remain their existing separate requirements. Synthetic projection
  tests cannot satisfy those requirements or certify any sport market.

The packet is ready for controller reading. The copy-source freeze is intact;
no additional implementation change is requested by this bounded review.
