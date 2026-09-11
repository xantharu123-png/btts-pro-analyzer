# Scoped rereview: SQL opaque-binding test order

Date: 2026-09-11. Reviewer: `/root/capacity_whole_branch_review`.

## Verdict and exact scope

**APPROVED. The whole-branch review's one Minor is addressed.**
No new Critical, Important or Minor finding in this delta. This is only the
requested scoped rereview, not a second whole-branch review or release approval.
The original `final-whole-branch-review.md` is preserved unchanged.

- BASE: `194155d7b86f0ef6c8f64bd53608f9a9c706aa6b`.
- HEAD: `bc9d268d1e70fa89dd1cfa387667ee32a04aa421`.
- Complete immutable package read: `.pytest_tmp/review-194155d..bc9d268.diff`,
  7,921 bytes; independently verified SHA256
  `6614a48bb6576ebd731039568c7030f31ca899e1eea06ff65720824049860bbf`.
- Exactly two committed paths changed: `tests/test_context_dataset.py` and
  `sql-order-test-fix-report.md`. No product, deployment, model or data change.
- Test file working-byte SHA256 independently matches the author's final hash:
  `9b1281b909bf4ecd6c771846e78e9c0f19895784701971faed3963622c1d5f8a`.

## Finding closure

The fixture is still the real valid stored dataset, copied through SQLite's
backup API. The capture connection delegates all calls to actual SQLite before
recording named parameters. The protected receipt-body decoder remains a
failing guard while the real physical preflight executes successfully.

The original table-scan variant is retained. The added covering-index variant
creates only a test-local payload index, verifies real query plans, and asserts
that the actual two opaque sequences differ. Its passing final assertion is
therefore evidence that the prior ordered-list premise was removed, not a
fixture that happens to retain the same order. Production SQL is unchanged.

The correction independently checks every captured mapping's exact key set
against `{'opaque'}` and compares the BLOB values using `Counter`. Extra keys,
missing/extra values and incorrect multiplicities cannot pass merely because
the distinct-value sets match. Byte identity is retained; there is no decoding,
normalization, sorting of production rows or weakened physical acceptance.

The author's recorded real RED (one failing covering-index variant, one passing
table-scan variant) and 33-case full-module GREEN were inspected as author
evidence. They are not relabeled as independent reviewer reruns.

## Independent checks

Executed from the same review worktree, with UTF-8/bytecode settings and all
five numerical-thread environment variables fixed to the author's values:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe
  -B -m pytest -q -p no:cacheprovider -W error
  tests/test_context_dataset.py -k outer_projection
  --basetemp=.pytest_tmp/sql-order-independent-20260911-01
```

Result: **3 passed, 30 deselected, no skips, 53.09s, exit 0**. This includes
both binding/planner variants and the real outer-projection capability-failure
boundary. Warnings were errors, not suppressed. Scoped BASE-to-HEAD
`git diff --check` passed; the test file remained exact HEAD and the index was
empty. Existing controller changes in the ledger, native evidence and handoff
were left untouched.

Only this review file was authored. No test/product edit, commit, index change,
subagent, full repository run, SSH/VPS action or deployment was performed.

## Operational boundary

The parent reports that the earlier exact-product current/G1-G3/historical-
largest and native DAC/race gates now pass. It also reports a newer fresh
88-database backup/actual restore/HMAC pass, but the context input has changed
to 265,793,536 bytes. That new input still needs its own controller-owned exact
verification; this test-only approval cannot substitute the older input pass.
Linux integration/full-suite, publication, updater exchange and separate exact
application deployment remain controller-owned gates. No operational or
empirical/model approval is inferred here.

Final scoped status: **APPROVED; Minor closed, zero open findings in this delta.**
