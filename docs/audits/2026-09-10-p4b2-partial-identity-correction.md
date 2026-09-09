# P4b2 F1 — preserve known contradictions inside partial native identity

## Bounded finding and unchanged originals

Independent review found a P3 diagnostic/closed-contract defect on
`ba73dc9ef0da65b97f5d581e38ebf34a55c18292`. A native status receipt with one
unknown participant and a separately known wrong opponent was excluded by
`projection.issues` before `_compare`. Its current status correctly stayed
unknown, but the known participant contradiction disappeared from `match_state`
and reasons.

This never produced a usable Event, false matching receipt, altered prediction,
source approval, context effect or bet. The correction must not be described
as repairing an observed wrong betting decision. Unknown-only input remains
unknown; independently known impossible association is now retained explicitly.

Work proceeds in the separate `kontext-team-sports-binding-f1-20260910` worktree
on exactly that parent. The original resolver worktree remains unchanged for
the reviewer's continuing checks. The entire independent F1 addendum and probe
were read and copied byte-for-byte with the original RED XML. They are not
edited or relabeled as successful original evidence.

## Narrow implementation

The existing raw/native comparison is performed before the existing unusable
receipt branch. That branch retains **only** independently comparable
`native-participants-conflict` and participant-availability diagnostics. It
still unconditionally excludes the partial/simultaneously ambiguous receipt
from matching. No unknown status is reinterpreted as a known status conflict.

Where a current partial revision has a known participant contradiction, its
reason remains visible even when an older actual matching receipt is preserved
as documentary history. That older `matched` label and reference are not
rewritten into a current source approval. A later consistent current revision
removes the obsolete active contradiction; all old lineage receipts remain.

No alias graph, receipt clock, scope rule, format routing, current-state
selector, Event eligibility, original calculation or reference schema changed.
No public feature/model version changed: this corrects diagnostics within the
existing binding contract, not probability or source-qualification semantics.
Old helpers, native capture/validators, P4a, C2/C3, Cricket and money are untouched.

## Actual tests

All fixtures are synthetic source-shaped inputs normalized into real temporary
B1 SQLite, read through the actual owning reader, and compared with a same-call
P3 original. This is real local mechanics verification, not new live evidence.

- Exact unchanged original probe: **6 failed / 6 passed / exit 1**, 1.75s.
- New permanent tests before the fix: **21 failed / 15 passed / exit 1**, 2.29s.
  The same F1 diagnostic appears across all three sources, both sides, target
  and original raw-history positions; additional cases cover a known opponent
  under unknown lifecycle and a partial current revision after an older match.
- The 36 permanent tests also keep unknown-only cases unknown, preserve exact
  original probabilities, prohibit new matched refs/Event, retain original
  indices/lineage and test later consistent recovery. Their assertions were not
  changed after implementation.
- Final focused run: **871 passed, 0 skipped, exit 0, 38.50s**. Includes the
  unchanged independent 12 cases, all new 36, original binding/P4a/P4b1 suites,
  actual original/default/Cricket parity, C2/C3, context contracts and completed
  history. No complete repository suite, provider call or live activation.

Command shape: existing quality Python, `-B -m pytest -q -p no:cacheprovider`,
`-o "pythonpath=. tests"`, unique `.pytest_tmp` base and JUnit per run.
Every command explicitly captured and returned `$LASTEXITCODE`.

## Frozen hashes

```text
Independent F1 addendum        48ef0eb3f076af34f3fd56ac9e23654c9afc720b172e50bcff60ee286767b9eb
Independent original probe    97f67983baf822a63465ce9a8729fec10838414ce9fc61827a90a759d71e3818
Independent original RED XML  858b7c061208bbd8aaf639dd60a960ea12ed096994c30139bb1ac50f396055a9
Own exact original RED XML    6a312b61f132540bbabecf15a59477ec163e59485ab747f7d314c739596bb3d5
Own permanent RED XML         3c0c14da5825721741beb90e315fd95122bc02fef67209dd554cb61ce8af1b07
Own final focused GREEN XML   e1e38a1660c3d16b5caa8ecea5e2fe42da62e16335cb8465ff0f07498615a6b9

context_sources/team_sports_binding.py
204bf8e3f836a5ebbc2644ebf7da29afeab8a8ae8c0b8a53c09b62794faf08d9
tests/test_team_sports_binding_partial_identity.py
dfe76354456584e9b58e18e98d82097394dfd431d9fd6c566e78adfa1f8b4e82
Unchanged tests/test_team_sports_binding.py
951bee6afeaca9013bf7f9d2b4702f2aca80ba7dca857d1eba937ebfdd022a78
```

The previous P4b2 report remains unchanged and retains the broader packet's
source/history/producer limitations. Independent final review is separate;
P4b worker/consumer/transport/restore integration and actual D1/D2 authority are
not completed by F1. No push, server operation or deployment occurred.
