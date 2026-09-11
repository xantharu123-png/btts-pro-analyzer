# SQL opaque-binding test-order correction

Date: 2026-09-11. Author: `/root/sql_order_test_fix`.

## Immutable scope

- Whole-branch BASE: `2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
- Source / immediate parent HEAD: `194155d7b86f0ef6c8f64bd53608f9a9c706aa6b`.
- Branch: `codex/context-capacity-recovery-20260910`.
- Only changed files: `tests/test_context_dataset.py` and this report.
- Applicable ancestor, tests and SDD directory AGENTS.md checks found no files.
  The dispatched whole-branch review was read before changes. Missing
  superpowers tooling was not hunted, invoked or claimed available; the narrow
  manual RED/GREEN and exact-path Git workflow was used.

The final commit identifier is delivered in the author handoff after commit;
it is also the commit returned by `git log -1 --format=%H --` for this report.
An embedded self-referential commit hash is intentionally not invented.

## Change and real RED

The original named-binding regression now runs against both its unchanged
valid copied dataset fixture and a copy with a payload-only covering index.
The latter asserts actual `EXPLAIN QUERY PLAN` evidence: the payload projection
uses `test_covering_payload` as a covering index, while the production two-column
scan does not use that index. It also checks that the actual captured opaque
sequence differs from the expected projection sequence.

Before changing the ordered-list assertion, both variants were executed.
The table-scan case passed; the covering-index case reached and failed precisely
the original assertion at line 309. Capability, real content hashing and physical
receipt validation succeeded first; this was not a synthetic invalid database
or an expected exception replacing a real failing test.

RED test-file SHA256:
`bde5e4676c5abc692b12e72133eeef6dd69d0125dcf5d24037fba5b878640953`.

The correction independently requires every captured mapping to have exactly
the `opaque` key and compares opaque values with `Counter`, preserving both
bytes and multiplicities without assuming traversal order. The protected-body
decoder guard remains active in both variants. Production SQL, including the
absence of `ORDER BY`, and all production/frozen contracts remain unchanged.

Final test-file SHA256:
`9b1281b909bf4ecd6c771846e78e9c0f19895784701971faed3963622c1d5f8a`.

## Commands and results

Working directory for every command:
`C:\Projekt\BetBoy\betboy-app\.worktrees\context-capacity-recovery-20260910`.

Both pytest commands used this exact PowerShell process environment:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$env:VECLIB_MAXIMUM_THREADS='1'
```

RED:

```powershell
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider -W error tests/test_context_dataset.py -k outer_projection_binds_each_opaque --basetemp=.pytest_tmp/sql-order-red-20260911-01
```

Exit 1: **1 failed, 1 passed, 31 deselected in 68.97s**. Sole failure:
`test_outer_projection_binds_each_opaque_receipt_by_named_mapping_without_decoding[covering-payload-index]`,
at the old ordered assertion. Distinct plans and traversal checks passed.

GREEN, after only the Counter/key-set correction:

```powershell
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider -W error tests/test_context_dataset.py --basetemp=.pytest_tmp/sql-order-green-20260911-01
```

Exit 0: **33 passed in 165.27s**; no skips, failures or warnings.

Scoped `git -c core.autocrlf=false diff --check` passed before staging. Only
the exact test and this ignored report were staged (the latter with `git add -f`);
the staged inventory contained exactly those two paths and the staged whitespace
check passed.

## Limits and handoff

This is a narrow test robustness correction after the completed whole-branch
review, not another whole-branch review or product repair. No full repository
suite, native Linux/DAC/resource acceptance, push, SSH, backup, installer exchange,
application deployment, public health check or empirical/model approval was
performed by this author. Those remain controller-owned gates and are not
inferred from local tests. The test's deliberate SQLite planner control is
verified on the local interpreter; other SQLite versions were not tested.

Root-owned tracked WIP in `progress.md`, `task-9-native-evidence.md` and the
subsequently updated `PC_WECHSEL_UEBERGABE.md` was preserved, excluded from
staging and excluded from the commit. No global Git
configuration was changed. Exact scoped diff/index/commit checks are recorded
in the author handoff after completion.
