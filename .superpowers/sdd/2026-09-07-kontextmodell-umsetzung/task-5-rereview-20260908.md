# Task 5 / B1 — independent R1–R3 correction re-review

Date: 2026-09-08.

Verdict: **R1, R2 and R3 addressed; no remaining findings in the scoped
correction review.** The B1 software correction is accepted against the
explicit controller contract. This is not source certification, empirical
approval, production activation or an approval of later B/C/D implementation.

## Exact scope and authority

- Checkout: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-b1-20260908`.
- Previous reviewed commit: `9a4e04f7aa65ea5f9f0a1e8e7ef91216951274e6`.
- Exact corrected commit: `22164fdf577190fa17f9aeddebd1b810ca4c59a1`.
- Read the complete appended implementer report and the actual two-file Git
  diff: `context_observations.py` and `tests/test_context_observations.py`,
  169 insertions and 26 deletions. No other source changes belong to this fix.
- Read the current authoritative sibling
  `kontextmodell-20260907/.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/context-contract-decisions.md`
  completely, including **B1 independent-review correction contract**.
- Reviewed the complete corrected `factor_state` and its ordering relative to
  the unchanged receipt selection, identity checks and policy validation.
  The original B1 review and full task/spec context remain applicable outside
  this narrow correction.

Frozen raw SHA-256:

| File | SHA-256 |
| --- | --- |
| `context_observations.py` | `9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226` |
| `tests/test_context_observations.py` | `5699044e9073a428376163f3433ef9b2d2d76dd549df0593fde27c550e849352` |

## Disposition of original findings

### B1-R1 — addressed

Anchors: `context_observations.py:302-304`, `313-322`, `333-363`,
`370-394`, `411-413`.

The interface now explicitly separates `refs` (audit-only inspected receipts,
including relevant event-status evidence) from `usable_refs` (sorted unique
receipts actually supporting the available factor). Unavailable results have
an empty usable list. The final usable collection supplies reference identity,
coverage and freshness metadata together.

The original five R1 examples now retain their audit records while excluding
future-retrospective, wrong-revision, stale and precedence-discarded records
from usable provenance. Mixed native-event input is rejected before any state
is returned. This is the explicitly approved audit/usable split, not a removal
of diagnostic history or a relaxed causal requirement. Future feature builders
must consume `usable_refs`, never promote audit `refs` to numeric provenance.

### B1-R2 — addressed

Anchors: `context_observations.py:311-314`, `324-334`.

Every supplied row is identity-checked, then native event, sport, competition
and format are checked together before policy, kickoff or status early return.
Foreign status evidence cannot disable another event. Status invalidation is
limited to the current schedule, prospective receipt at/before cutoff and an
applicable half-open validity interval. Its receipt remains in audit history;
the resulting unavailable factor has no usable numeric references.

Original foreign `cancelled`/`started`/`completed` and future/expired validity
reproductions pass. Additional independent checks require typed scope errors
even when policy cancellation or kickoff would otherwise return early. A
current same-event cancellation still correctly invalidates the factor.

### B1-R3 — addressed

Anchors: `context_observations.py:337-365`, `370-413`.

Applicable fresh candidates are selected by source precedence before their
actual factual content, required completeness and result metadata are derived.
An expired fact can no longer lend substance to a fresh empty player receipt;
a discarded complete source can no longer certify a selected incomplete
collection. Same-source simultaneous empty/factual revisions remain a conflict
instead of silently losing the empty alternative.

The original missingness/completeness cases pass. Independent permutation and
duplicate-input checks confirm that excluded sources cannot alter usable refs,
coverage or the selected source's deadline. Agreeing sources remain jointly
usable where no precedence was declared; legitimate forecast-validity handling
is preserved for weather.

## Independent verification

All commands ran from the frozen B1 checkout with the quality interpreter,
`-B`, no pytest cache, and independently named basetemp children checked absent
before each run. Every database is synthetic and isolated under those children.

### Focused implementation and foundation regression

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider tests/test_context_observations.py tests/test_context_contracts.py tests/test_context_coverage.py tests/test_model_artifacts.py tests/test_runtime_paths.py --basetemp=.pytest_tmp/b1-rereview-focus-20260908-01
```

**240 passed, 4 skipped in 3.02s**, exit 0. The four platform-specific skips
remain skips, not locally demonstrated Linux permission behavior.

### Preserved original reproductions, owned contract-adapted copy

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider '.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-5-rereview-repros-20260908.py' --basetemp=.pytest_tmp/b1-rereview-original-edges-20260908-01 --tb=short
```

**18 passed in 0.54s**, exit 0. This new owned copy preserves all six original
positive controls and original R2/R3 cases. Only R1's assertions were adapted
to require both retained audit `refs` and exact `usable_refs`, plus the newly
explicit typed rejection of its mixed-event case. The original reproduction
and original review report were not edited.

### Additional bounded independent edge checks

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider '.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-5-rereview-extra-20260908.py' --basetemp=.pytest_tmp/b1-rereview-new-edges-20260908-01 --tb=short
```

**23 passed in 0.68s**, exit 0:

- Six input permutations, duplicated receipt input and no caller-input mutation;
  only the selected real source determines usable metadata and its deadline.
- Simultaneous same-source empty/factual conflicts, with and without an
  explicit source-precedence entry.
- All four declared event-scope dimensions before both policy and kickoff
  early-return paths (eight cases).
- Empty usable provenance for stale, future-valid, wrong-schedule, walkover and
  unfinished-workload states.
- Future forecast validity covering kickoff remains valid weather evidence;
  it is not incorrectly treated as a future status invalidation.
- Agreeing fresh sources both remain usable without invented precedence.

Total independently executed in this re-review: **281 passed, 4 skipped**.
The implementer's separate full-suite **2079 passed / 15 skipped / 97 subtests**
was read as reported evidence, not rerun or represented as the reviewer's own
full-suite result. No failing independent cases remain.

## Preservation and remaining boundaries

Original independent evidence remains byte-identical:

- `task-5-independent-review.md`:
  `3cb7f832d93695b40794017eeffa7254024ddb038f9af1ec3619ed885a5b1b8e`.
- `task-5-review-repros.py`:
  `bdc4c2a31bf9338e770f5e20e92126f8051b2bbb41d12fb994698296712d7ac7`.

Only the two new owned test files and this separate re-review report were
created. No source edit, Git mutation, source/provider access, VPS operation,
subagent or production-data write was performed. The inherited staging-helper
status was untouched; its pinned SHA-256 remains
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

No archive/source certification, real causal dataset, learned numeric effect,
empirical validation, backup/restore, deployment or live-use approval follows
from this result. Integration must preserve the exact reviewed source and the
explicit audit-versus-usable consumer contract. Those later boundaries remain
separate work, not new defects in this accepted B1 correction.
