# Task21: native footprint allocation owner, 14 October 2026

## Scope and causal evidence

Canonical checkout:
`C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`.
Controller-owned brief: `task-21-native-footprint-20261014-brief.md`.
Implementer-owned changes are only `context_storage_v2/refs.py`, new
`tests/test_context_storage_native_footprint.py` and this report.

The controller's complete QA03 and exact combined-prefix reproduction retained
the original unmodified memory test's RED: peaks 7720876 and 7720933 versus its
strict 524288-byte ceiling. The supplied allocation trace attributes 7689584
bytes to the stdlib `pathlib.py` `sys.intern` dictionary table allocation/rebuild;
this is not a claim of inevitable table growth or unbounded stream buffering.
The earlier six-value generation allocation repair remains unchanged here.

The repair extracts the existing exact connection/limits/transaction/text/row/
attached-database/TEMP admission into `_require_connection_path`, returning the
SQLite native filename. Every existing check and query remains in the same
order. `_require_connection` still constructs and returns the same `Path`, so
cold admissions do not change their API. `_check_footprint` alone uses the raw
filename for native `os.stat` and the parent-directory free-space measurement.

All three companion suffixes remain `-wal`, `-shm`, `-journal`; existence is
followed by a second stat as before, including its disappearance/error race.
`_native_exists` matches the inspected CPython 3.12 `Path.exists` policy exactly:
only ENOENT/ENOTDIR/EBADF/ELOOP, WinError 21/123/1921, or existence-time ValueError
mean absent. PermissionError and other OSError still reach the unchanged owning
StorageIntegrityError. A ValueError on the second stat still propagates unchanged.
All native stats explicitly follow symlinks, as the prior `Path.stat` did.

The controller's review identified the private relative-filename compatibility
edge. The dedicated real tracked SQLite test keeps every other SQLite query
real and overrides only the reported main filename using a real
`pragma_database_list` SQL projection. It reproduced `disk_usage('')` instead of
the prior `Path('native.sqlite').parent == '.'`. The final implementation uses
`os.path.dirname(path) or os.curdir`, retaining that behavior without parsing.

Logical/page/physical/companion/free-reserve/input/workspace/max-page/cache/mmap
checks, exception conversion, public chunk boundaries, transaction epochs,
schema/data-version checks, clocks, output bytes, persisted schemas/identities
and all budgets remain unchanged. There is no metadata cache, remembered proof,
warmup, GC reset, threshold increase, filter or reduced test.

## Caller compatibility inspected

- `snapshot_source._admit_pair` receives the cold wrapper's Path and compares
  `Path(source_path).samefile(output_path)`; its behavior is unchanged.
- `tennis_consumer.put_tennis_consumer` invokes `output_path.samefile` against
  held source/history/features; its returned Path and lifetime remain unchanged.
- `snapshots` and `ref_chunks` use the old cold admission at initial admission
  and the hot owner at existing resource boundaries; no caller changed.
- The focused test checks actual `Path.samefile` against its actual SQLite file,
  rather than asserting only a return annotation or mocking samefile.

## Fresh TDD and local verification

Evidence root:
`C:/Projekt/BetBoy/output/context-completion-20261014/native-footprint`.
Every invocation was a fresh Python process using the existing offline launcher.
There was no full-suite rerun, Git mutation, API/VPS access or production data copy
by this implementer. The controller owns the full-suite disposition and exact
combined-prefix comparison after this freeze.

| Evidence stem | Exit | Actual result | Code state |
| --- | --- | --- | --- |
| `red` | 1 | First exploratory run hit a test-side observer INTERNALERROR during pytest failure reporting after the genuine hot Path failure | no production repair yet |
| `red2` | 1 | 2 failed, 51 passed in 2.90s; both failures are hot Path parsing/native Path-valued stat arguments | no production repair yet |
| `green` | 0 | 53 passed in 1.17s | first raw-path implementation |
| `cold` | 0 | Unchanged isolated original memory case: 1 passed in 2.36s | before relative fallback |
| `module` | 0 | Complete original chunks module: 71 passed in 6.98s | before relative fallback |
| `neighbors` | 1 | 279 passed, 1 failed, 1 skipped in 39.12s | before relative fallback |
| `neighbors-escalated` | 0 | Same complete four modules: 281 passed in 24.38s | before relative fallback |
| `relative-red` | 1 | 1 failed in 2.68s, empty-string parent measurement instead of `.` | before relative fallback |
| `final-green` | 0 | 54 passed, 1 skipped in 1.23s | final frozen source |
| `final-green-escalated` | 0 | 54 passed, 1 skipped in 0.82s | final frozen source |
| `final-cold` | 0 | Unchanged isolated original memory case: 1 passed in 2.60s | final frozen source |
| `final-module` | 0 | Complete original chunks module: 71 passed in 6.65s | final frozen source |
| `final-neighbors` | 0 | Same complete four owning neighbor modules: 281 passed in 27.62s | final frozen source |

The first observer had asserted string-only arguments for unrelated pytest
`os.stat` calls too. It was narrowed to the actual database/companion paths;
the initial error remains in `red.log`/`red.xml`. `red2` is the clean genuine
pre-implementation RED, not a setup/import failure. No production code was
written before `red2`.

The sandbox neighbor failure was the existing
`tests/test_context_storage_workspace_budget.py::test_hardlink_is_not_a_new_budget_slot`
at real `os.link`, WinError 5. The existing native hardlink profile test also
skipped under the same sandbox. Both same complete modules passed after scoped
filesystem escalation in fresh directories; the failed sandbox artifacts remain.

The new real-symlink test
`tests/test_context_storage_native_footprint.py::test_native_physical_measurement_follows_real_database_symlink`
could not create its fixture: Windows returned WinError 1314 (symlink creation
privilege unavailable). Its explicit platform skip remains both in the sandbox
and the one scoped filesystem retry. It is **not a symlink PASS**, not one of the
old 97 baseline skips, and must be counted as one additional explicit new
platform skip if the full inventory includes this new file. No OS privilege,
Developer Mode setting, fake symlink fixture or permission fallback was used.

The 55 collected focused cases cover real exact-type admission and invalid
connection/limits states, cold Path API, zero hot Path construction, exact native
measurement order, ignored and strict errno/WinError branches, existence-time
ValueError, each companion's second size, second-stat disappearance/permission/
ValueError race, relative filename and live physical/free-space changes. The
unmodified neighboring tests cover the existing SQL/resource/lifetime guards.

The original memory test and module are byte-identical: 12000 refs, 4096-byte
blocks, 1024-byte chunks, strict `peak < 512 * 1024`, full count/digest checks.
Their successful runs establish the unchanged cold/module bound only. They do
not print the exact successful peak and do not establish the controller's
combined-prefix allocation gate or native RSS/CPU acceptance by themselves.

## Reproducible command inventory

For each stem below, this shared prefix was applied separately; `STEM` is
literally replaced by that row's stem. All directories were fresh and distinct.

```powershell
$env:DJANGO_SETTINGS_MODULE='siteconfig.qa_settings'
$env:PYTHONPATH='C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013/portal'
$env:TMP='C:/Projekt/BetBoy/output/context-completion-20261014/native-footprint/STEM-env'
$env:TEMP=$env:TMP
New-Item -ItemType Directory -Path $env:TMP -Force | Out-Null
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe' -B 'C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py' -q SELECTION --basetemp=C:/Projekt/BetBoy/output/context-completion-20261014/native-footprint/STEM-tmp --junitxml=C:/Projekt/BetBoy/output/context-completion-20261014/native-footprint/STEM.xml -o junit_family=xunit1 -o junit_logging=all --tb=short 2>&1 | Tee-Object -FilePath 'C:/Projekt/BetBoy/output/context-completion-20261014/native-footprint/STEM.log'
exit $LASTEXITCODE
```

Exact selections:

- `red`, `red2`, `green`, `final-green`, `final-green-escalated`:
  `tests/test_context_storage_native_footprint.py`
- `relative-red`:
  `tests/test_context_storage_native_footprint.py::test_relative_native_filename_measures_current_directory`
- `cold`, `final-cold`:
  `tests/test_context_storage_ref_chunks.py::test_full_stream_uses_bounded_python_buffers_separately_from_timing`
- `module`, `final-module`: `tests/test_context_storage_ref_chunks.py`
- `neighbors`, `neighbors-escalated`, `final-neighbors`:
  `tests/test_context_storage_generation_values.py tests/test_context_storage_refs.py tests/test_context_storage_workspace_budget.py tests/test_context_storage_sqlite_profile.py`

Only `neighbors-escalated`, `final-green-escalated`, `final-neighbors` used scoped
filesystem escalation. The external socket-connect block stayed active in every
run, including escalated commands. No duplicate full-suite process was launched.

## SHA256 freeze

Final source/test hashes verified after all final owning runs:

- `context_storage_v2/refs.py`:
  `9ACF8B545B14B0847EB36BB2D3B7DF885FE4F09E671001F0AEA9A7EEAE9F0A2C`
- `tests/test_context_storage_native_footprint.py`:
  `06F28CF6128F713ECBD5E9BE6D3BBD0835A5B34BE5B141E108823A9E8CF620A0`
- Unchanged `tests/test_context_storage_ref_chunks.py`:
  `584E222734E84D6248EDB04FFD6E8A21910DF949FEF96A1BEE1C593C0584C044`
- Unchanged `context_storage_v2/ref_chunks.py`:
  `CC951719E535492DA48017A489B3775B8ACE96BCF4C62FE35FAF1103B853821A`
- Unchanged `context_storage_v2/contracts.py`:
  `6D85802DF2692C9FBB50856B1F28B60CE8B4DECE3AE6A668C8F71515B8760A40`
- Pre-this-task `refs.py`:
  `68A11613CF75AADDBD195E55E535C609F5FEE56E782FE3633A6BF7AFB9D85AC3`

Final and decisive RED JUnit hashes:

- `red2.xml`: `D74D89F62A9871AA07DD4C02A008CBD35CC06399D2936D4017F1A49D35401E77`
- `relative-red.xml`: `791C9D9B5B0F8F8D48CADD57FC2684D7949FA4EC513C1DB0A0C0E954FF7671B1`
- `final-green.xml`: `77ECFF5B4F606E83465E3907EE689A8801B8623A07A99400562EDA77D4E0587F`
- `final-green-escalated.xml`: `348BA589687C8150625A8F6E61BA40A56B5FE7304310A89121D81E5D04477C39`
- `final-cold.xml`: `4DB71EAB5A7E92630E322C17DF101241032D1510CBF418F3623BE1A4B4EED2D3`
- `final-module.xml`: `FCD75D3580996769749256A9D9BA2EF7F5BC425A3D22EECF47C060B79E9ECC26`
- `final-neighbors.xml`: `073EFC0C2C236ACBEC0AB1ED0365026077B85DE89BC0566C806DD0AF29237005`

## Next gate / claims boundary

This narrowly scoped local repair is frozen for independent controller review.
The controller must run the identical combined-prefix original memory comparison
and record the full QA disposition, then decide any explicit Git/VPS release.
No claim that all model work is complete, any context effect is numerically
applied/validated, or betting quality improved follows from these storage tests.
