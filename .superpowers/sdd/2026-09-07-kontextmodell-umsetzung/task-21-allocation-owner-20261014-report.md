# Task 21 actual guard allocation: scoped GREEN, frozen for controller review

Canonical checkout: `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`.
Controller-supplied source base: `74f8e0d6d5c520b577596bdf0bc3f71cb531ab07`.
Evidence root: `C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner`.
Runtime: Python 3.12.14, Windows-11-10.0.26200-SP0, SQLite 3.53.1.

## Exact change and protected admission

Only the last member of `refs._generation` changed: the generated six `(name,
value)` pairs and `fields(StorageLimits)` call became a literal tuple of all six
values in declaration order: input, tour history, block, workspace, minimum free,
blocks per set. The outer 12-member tuple retains the exact limit instance at
index 10 and its value snapshot at index 11. `StorageLimits` exact-type validation,
fixed `StorageLimits.__post_init__`, every SQL pragma, every generation invocation,
schema/descriptor/footprint verification and pre/post/terminal check are unchanged.
The `fields` import remains because the separate descriptor manifest uses it.

This removes repeated unknown-length tuple/reflection construction at the real
owning boundary; no cached/memoized answer or skipped check was introduced. It
changes an internal ephemeral token, not the persistent format or public API.

New owning test file has 14 cases: one literal six-value default snapshot (and
outer layout/limit identity), one exact six-declaration completeness review guard,
and six independently parameterized valid tightening mutations in both scalar and
chunk readers. Each mutation still satisfies the fixed real limit validator and
must raise the generation integrity error before the next output, then close the
iterator. The private fixture leaves max-page admission headroom so a one-byte
tightening does not pass merely because a separate resource quota fails.
The layout guard makes a future added/reordered declaration require explicit
snapshot/test review rather than silently leaving it out. Literal expected values
are independently stated, not derived by the production snapshot/helper.

## TDD and exact verification results

The new test was written and run before the source change. RED failed for the
expected missing shape: `('input_bytes', 4294967296) != 4294967296`; the 13 existing-
behavior/layout sibling cases passed. Then the one last-member source change was
made and the same focused file passed. TDD and writing-good-tests were read; the
controller's explicit no-full-suite scope bounds the skill's general full-suite
recommendation. Verification-before-completion was also read before final handoff.

| Run | Exit | Exact pytest summary | Log/XML stem |
| --- | --- | --- | --- |
| New-file RED before implementation | 1 | 1 failed, 13 passed in 3.18s | red |
| New-file GREEN | 0 | 14 passed in 0.92s | green |
| Unchanged isolated cold owning memory test | 0 | 1 passed in 2.87s | cold |
| Complete unchanged ref_chunks module | 0 | 71 passed in 6.25s | module |
| Owning generation/resource neighbors, sandbox | 1 | 1 failed, 279 passed, 1 skipped in 30.16s | neighbors |
| Same neighbor modules, scoped filesystem escalation | 0 | 281 passed in 17.60s | neighbors-escalated |

Cold and complete-module verification ran in two separate fresh processes after
implementation; neither was retried or warmed. The original memory test remained
byte-identical, including its real `tracemalloc` getter and strict `peak < 524288`
assertion, 12000 references, 4096-byte blocks, 1024-byte chunks, digest/byte-count,
chunk-count and multiblock checks. Successful original tests do not print or store
their exact peaks; the retained evidence establishes only the unchanged bound
passed, not an exact numeric reduction or a native RSS result.

Negative events are preserved, not hidden: sandbox neighbor failure was
`tests/test_context_storage_workspace_budget.py::test_hardlink_is_not_a_new_budget_slot`
at real `os.link`, WinError 5. The same sandbox prevented the existing native
hardlink profile test (`test_real_hardlink_added_during_build_invalidates`), whose
existing policy skipped it. The same complete four-module selection then passed
all 281 cases with no skips after the brief-permitted scoped filesystem escalation,
in a new private directory. No test/production workaround was added. The original
failure/skip log and XML remain in place.

## Full commands and artifact mapping

Every command used canonical cwd above and the existing offline launcher, whose
external socket-connect block remained active, including the escalated run. Each
run was a new invocation, not one persistent Python process. Shared PowerShell
prefix below was executed before EACH listed test command; `RUN` was replaced
literally with that command's stem (`red`, `green`, `cold`, `module`, `neighbors`,
`neighbors-escalated`). No standard home/runtime variable was repurposed.

```powershell
$env:DJANGO_SETTINGS_MODULE='siteconfig.qa_settings'
$env:PYTHONPATH='C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013/portal'
$env:TMP='C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/RUN-env'
$env:TEMP=$env:TMP
New-Item -ItemType Directory -Path $env:TMP -Force | Out-Null
```

Exact test commands (each pipeline was followed by `exit $LASTEXITCODE`):

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe' -B 'C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py' -q tests/test_context_storage_generation_values.py --basetemp=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/red-tmp --junitxml=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/red.xml -o junit_family=xunit1 -o junit_logging=all --tb=short 2>&1 | Tee-Object -FilePath 'C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/red.log'
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe' -B 'C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py' -q tests/test_context_storage_generation_values.py --basetemp=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/green-tmp --junitxml=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/green.xml -o junit_family=xunit1 -o junit_logging=all --tb=short 2>&1 | Tee-Object -FilePath 'C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/green.log'
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe' -B 'C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py' -q tests/test_context_storage_ref_chunks.py::test_full_stream_uses_bounded_python_buffers_separately_from_timing --basetemp=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/cold-tmp --junitxml=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/cold.xml -o junit_family=xunit1 -o junit_logging=all --tb=short 2>&1 | Tee-Object -FilePath 'C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/cold.log'
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe' -B 'C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py' -q tests/test_context_storage_ref_chunks.py --basetemp=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/module-tmp --junitxml=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/module.xml -o junit_family=xunit1 -o junit_logging=all --tb=short 2>&1 | Tee-Object -FilePath 'C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/module.log'
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe' -B 'C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py' -q tests/test_context_storage_generation_values.py tests/test_context_storage_refs.py tests/test_context_storage_workspace_budget.py tests/test_context_storage_sqlite_profile.py --basetemp=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/neighbors-tmp --junitxml=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/neighbors.xml -o junit_family=xunit1 -o junit_logging=all --tb=short 2>&1 | Tee-Object -FilePath 'C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/neighbors.log'
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe' -B 'C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py' -q tests/test_context_storage_generation_values.py tests/test_context_storage_refs.py tests/test_context_storage_workspace_budget.py tests/test_context_storage_sqlite_profile.py --basetemp=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/neighbors-escalated-tmp --junitxml=C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/neighbors-escalated.xml -o junit_family=xunit1 -o junit_logging=all --tb=short 2>&1 | Tee-Object -FilePath 'C:/Projekt/BetBoy/output/context-completion-20261014/allocation-owner/neighbors-escalated.log'
```

Each `*.xml` and `*.log` is under the evidence root. `neighbors-escalated` was
the only `require_escalated` test command. This was a filesystem-access retry,
not a memory test retry-until-green, modified threshold or different test selection.

## SHA256 freeze

Final source/test hashes, checked unchanged after all scoped verification:

- `context_storage_v2/refs.py`: `68A11613CF75AADDBD195E55E535C609F5FEE56E782FE3633A6BF7AFB9D85AC3`
- `tests/test_context_storage_generation_values.py`: `69D4D3E1B4115EB592BC31E70308CCC87C63EB56521CBA36DD845F694EC84AA7`
- Unchanged `tests/test_context_storage_ref_chunks.py`: `584E222734E84D6248EDB04FFD6E8A21910DF949FEF96A1BEE1C593C0584C044`
- Unchanged `context_storage_v2/ref_chunks.py`: `CC951719E535492DA48017A489B3775B8ACE96BCF4C62FE35FAF1103B853821A`
- Unchanged `context_storage_v2/contracts.py`: `6D85802DF2692C9FBB50856B1F28B60CE8B4DECE3AE6A668C8F71515B8760A40`
- Base `refs.py` before implementation: `605CE25B80D800ADF6EC4F2A1E5D9C04AE84C3E0A7961705BB371AD6390755CD`
- Existing offline launcher: `32536A8413EC9D4837F3AFD9F42A88BDDA9DB03592E7095B21EB71012B9FA4A9`

JUnit evidence hashes:

- `red.xml`: `50688D0AA88ECA487BEE606D7EAA79F28F5DD081E6329A6AEE9BDF46823EB187`
- `green.xml`: `D2B76E6A692B1F453979C917FDAA2EBEC4693381939CA17B1CBEDF0C478E1109`
- `cold.xml`: `CDB1908CDE2EC6AC2D5173FA5C6D4A87F9EF7D721742889E5C423529C53D9F14`
- `module.xml`: `83BE5EBB271E245E11679AE578306AB52874AB4C4568DB760ED0EE45830FA152`
- `neighbors.xml`: `C7B44372A41457CA88D043A554A68B2EEE7B1A7F32B3050DFDC40DEE68359D11`
- `neighbors-escalated.xml`: `21D590116E9B95FB40B461493B67F14647476094709E638DA1A0C89403969876`

## Scope and next gate

Frozen for controller review: owned changes are only the generation last member,
new focused tests, and this report. No production caller/math/context-effect,
ref_chunks/schema/contract/clock/resource changes, baseline test edits, warmup,
GC/reset/filter/threshold manipulation, API/VPS/backup access, spawned agents,
full-suite execution, commit, Git/index action or broad cleanup occurred.
The existing supplied causal report was read but not changed.

Scoped local gate is GREEN, not overall acceptance. Controller still owns the
full source freeze, independent review, full regression, Git and publication.
These synthetic local storage tests establish neither native resource admission
nor any actual numerical sport-model context effect or live-source coverage.
