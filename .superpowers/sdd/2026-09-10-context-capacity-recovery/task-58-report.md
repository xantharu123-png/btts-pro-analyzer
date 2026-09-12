# Task58 — actual dual-reader timezone binding prerequisite

Status: **DONE_WITH_CONCERNS — implemented and locally verified; final outer
process exit/console observation is missing, and native acceptance remains
Root's mandatory next step.** Sole implementation writer: delegated
`c_timezone_reader_binding`. Root supplied BASE
`0aa6e23c684ea9bb87c9bead6132f4bc8f2226e0` and branch
`codex/context-capacity-recovery-20260910`; this writer made no Git query or
mutation. No network, SSH, install, deletion, server operation or subagent.

## Requirements, finding and exact edit surface

Read Task58 first, verified its SHA256
`8da08ac0c77a03d995cce5cbf470c489155121335e71ca254f94f78aff4292ca`, then the
original Task57 brief, FIX5 finding/ruling and final FIX5 report appendix.
Followed the implementer, TDD/writing-good-tests, systematic-debugging and
verification instructions. Only relevant worker/tests and actual dateutil
reader/resource-loader implementation were inspected. An initial attempted
dependency lookup inside the QA venv found no dateutil there; its existing
`.pth` resolves to `C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages`.
No dependency was installed or newly admitted to the native catalogue.

Declared before editing and actually edited only:

- `tests/native_context_chain_worker.py`: real dual-reader configuration and
  deny-before-generic-admission enforcement for dateutil's bundled fallback.
- `tests/test_native_context_chain.py`: legitimate TZif fixture adaptation,
  existing-dependency fixture copying and existing binding/ordering tests.
- `tests/test_native_context_timezones.py`: new focused real-reader tests.
- This report.

Freshly verified actual supplied diagnostic pins:

```text
evidence/task57-timezone-route-diagnostic.py
50bfe280658c57c95e3528909c917cfb8b8da0ec1f0bca9f7846eeaa75c1c216
evidence/task57-timezone-route-diagnostic-01.json
bf49a28b4b6eda232da27fc0bc7b4e6d9968235bf87b8166f07be6f408b067a7
```

That retained ordinary-UID1000 Linux diagnostic, not guarded acceptance,
demonstrates Pandas' compiled timezone initialization calling real dateutil
gettz/tzfile against `/usr/share/zoneinfo/UTC` after ZoneInfo was already bound.
It ran with CPU15s/AS2GiB/wall25s and did not enter Task54. The locally inspected
dateutil `tz/tz.py` SHA256 is
`1149c474c7de4e15e263a978b21f7205a6d9eb7fcf3b3cb4d734ac87db619f5a`, exactly
matching the supplied actual native catalogue/seal observation. Inspection
confirmed independent `TZPATHS`/`TZFILES`, actual `gettz.cache_clear`, and the
missing-key path through `dateutil.zoneinfo.get_zonefile_instance` to
`pkgutil.get_data`/loader `get_data` and the already-catalogued tar.gz archive.

## Implementation and unchanged boundaries

The worker still verifies the actual guard first, loads fixed control data,
then installs the existing exact Python file audit. Binding rejects any
preloaded `zoneinfo`/`_zoneinfo`, `tzdata` or `dateutil` module state before
changing search paths or loading either reader. This conservatively rejects
real cached/held timezone objects instead of claiming they were rebased.
It checks exact admission of the dateutil package/tz entrypoints, retains the
actual complete readonly timezone-copy identity check, and retains real
ZoneInfo TZPATH reset/cache clearing.

Only then does binding expose the already-existing sealed dependency search
path and import dateutil to configure itself. The actual tz module origin must
be `seal/dependencies/dateutil/tz/tz.py`. Its existing `TZPATHS` becomes exactly
the same sealed directory, `TZFILES` becomes empty, and its actual cache is
cleared. Project/test search paths and product/pytest imports follow binding.
The dependency path is no longer inserted a second time by the worker run.
No reader, method, timezone object, import machinery, Pandas UTC constant,
product clock, math or acceptance validator is replaced or fabricated.

The audit rejects `dateutil.zoneinfo` imports and all actual file opens under
its fixed sealed fallback subtree, including its source, bytecode probes and
bundled archive, **before** generic dependency/stdlib/work admission. Lexical
absolute normalization catches relative traversal into the same subtree.
This is a denial, not a new permitted data root or record. Real importlib
module loading and SourceFileLoader resource opens are tested; enforcement
does not depend on an import audit event. ChainError is not dateutil's caught
IOError/OSError, so it cannot silently continue with an alternate source.

Parent/catalogue/helpers/Task54/product/frozen specifications are unchanged.
The exact native data records remain Europe/Zurich1909bytes SHA256
`2b9418ed48e3d9551c84a4786e185bd2181d009866c040fbd729170d038629ef` and
UTC114bytes SHA256
`8b85846791ab2c8a5463c83a5be3c043e2570d7448434d41398969ed47e3e6f2`.
Canonical originals, copied keys, owner/mode/size/hash/held-custody validation,
source+copy accounting and rechecks are untouched. This writer did not claim
to freshly read the native files; Root's actual independent readback owns
that proof. No extra native package, timezone key or source permission.

Actual Task54 invocation, Source/D2/History/features/consumer/rollback and
guard/readback are unchanged. All fixed bounds remain parent90CPU,
ATP90CPU/WTA90CPU, retained300CPU, total600wall, AS2GiB, RSS<1GiB, output1MiB,
4GiB active/8GiB new work/4GiB actual free reserve. No retry/reset/settlement
or cleanup was added.

## Real tests, fixture corrections and TDD evidence

New tests use real `-I -S -B` subprocesses with 20second timeouts, real copied
existing dateutil/six bytes, real ZoneInfo/dateutil readers and actual audit
hooks. The actual bundled archive is present and otherwise catalogued in the
fixture. A separate unguarded clean subprocess first proves its real cache can
return America/New_York, then a fresh subprocess verifies missing-key,
importlib module, absolute loader-resource and relative loader-resource
denials. No module/cache is removed to pretend a used interpreter was clean.

Windows dateutil initializes no system TZPATHS, so the portable old-path
characterization configures its actual existing path variable to a real
unadmitted `old-system/UTC` fixture. After only ZoneInfo reset, actual gettz
still tries that old file and is denied. This is portable independent-reader
evidence, **not** reproduction of the Linux original absolute path. The exact
Linux original route is proven by the separately pinned supplied diagnostic.

Both real readers open the same sealed UTC/Zurich files and satisfy literal
UTC0, winter+01:00, summer+02:00 and both October2026 fold expectations, plus
normal UTC roundtrips. Actual dateutil cache clearing is observed by a profile
callback without replacing the method. Actual dateutil reader/cache, bundled
cache and ZoneInfo cache preloads are rejected. Missing dependency admission,
unlisted keys, system paths, relative traversal alias and readonly data writes
are rejected; numeric `tzoffset` arithmetic/conversion remains normal.

The old TZif fixture used only a POSIX tail; dateutil reads the first TZif
block rather than that tail. Root explicitly approved adding literal2026
transitions to this existing legitimate fixture. A later fold failure exposed
that dateutil derives the first DST delta from the previous standard entry:
the final fixture therefore includes 2026-01-01 00:00Z CET, 2026-03-29 01:00Z
CEST and 2026-10-25 01:00Z CET in both 32/64-bit TZif blocks. The POSIX tail and
independent expected offsets/folds remain unchanged. These bytes are **not
native tzdb-byte equivalence**, and no selectable-date limit was introduced.

Two earlier test-observation failures were not implementation regressions:
the first incorrectly counted custody validation and readers as identical
audit path spellings; the next showed Windows readers preserve `/` inside an
IANA key. The final assertion compares actual Path identity and requires
exactly two new opens after the binding baseline. Another new denial check
initially demanded ChainError for an absent ZoneInfo key with no installed
tzdata; it correctly returns ZoneInfoNotFoundError. Both specific rejection
types are now recognized; the existing present-tzdata fallback test remains.
No worker code was changed during these fixture/assertion corrections.

Actual unprotected worker run is rejected by its real guard checks before
dateutil/ZoneInfo/product imports. The positive run-order test executes the
real worker, actual audit and binding to a product-boundary sentinel with a
labelled portable guard seam and fixture catalogue constants. It demonstrates
guard -> audit -> dependency configuration -> product order, **not** native
kernel guard installation or a fabricated Task54 success. The real native
guard chain remains Root's job.

### Exact executed test commands

Working directory for all commands:
`C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.
Each command used these environment settings and wrapper. `ARGUMENT_LIST` is
the exact Python list fragment in the following table, substituted literally:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -c 'import subprocess,sys; r=subprocess.run([sys.executable,"-B","-m","pytest","-q",ARGUMENT_LIST],capture_output=True,text=True,timeout=60); print(r.stdout); print(r.stderr); sys.exit(r.returncode)'
```

The fragments below use exact common expansion `COMMON` =
`"-p","no:cacheprovider","-o","junit_family=xunit1"`, `TZ` =
`"tests/test_native_context_timezones.py"`, and `CHAIN` =
`"tests/test_native_context_chain.py"`. `PATHS(stem,N)` expands exactly to
`"--basetemp=.pytest_tmp/task58-stem-bt-N","--junitxml=.pytest_tmp/task58-stem-N.xml"`.
There were no other pytest arguments or changed environment settings.

| Run | Exact argument fragment with expansions above | Actual result |
|---|---|---|
| red01 | `COMMON,TZ,PATHS(red,01)` |9 failed,1 passed in4.68s; missing binding/import path, bundled resource readable, preloads silently rebound |
| red02 | `"--tb=short",COMMON,TZ,PATHS(red,02)` |10 failed,1 passed in7.85s; expected real cache/binding/admission failures; all four actual fallback routes remained readable |
| green03 | `"--tb=short",COMMON,TZ,PATHS(green,03)` |1 failed,10 passed in5.65s; incorrect audit open count assumption |
| green04 | `"--tb=short",COMMON,TZ,"-k","dual_readers",PATHS(green,04)` |1 failed,10 deselected in0.63s; actual Windows mixed-separator audit observations retained in failure |
| green05 | `"--tb=short",COMMON,TZ,"-k","dual_readers",PATHS(green,05)` |1 failed,10 deselected in0.62s; fixture missing prior standard transition, actual dateutil fold mismatch |
| green06 | `"--tb=short",COMMON,TZ,"-k","dual_readers",PATHS(green,06)` |1 passed,10 deselected in0.61s; both real readers/offsets/folds and cache call passed |
| green07 | `"--tb=short",COMMON,TZ,CHAIN,"-k","dual_readers or real_readers_reject or real_unprotected or real_binding_rejects_writable",PATHS(green,07)` |1 failed,6 passed,66 deselected in2.65s; absent ZoneInfo key returned its actual NotFoundError |
| green08 | `"--tb=short",COMMON,TZ,CHAIN,"-k","timezone or real_unprotected",PATHS(green,08)` |37 passed,36 deselected in7.35s |
| final09 | `"--tb=short",COMMON,CHAIN,TZ,PATHS(final,09)` |Fresh complete XML:73 tests,0 failures,0 errors,0 skipped,16.939s; final outer console/exit not recovered, see below |

RED02 preceded all worker implementation edits and is the decisive correct
RED. Runs03-08 were focused iteration checks. Run09 was the **single final
complete amended two-module run**, including the unchanged local Task54
adapter test once. No whole repository or unchanged guard suite was run.
No executable/test edit or further test execution followed run09.

### Final evidence custody limitation — do not infer exit0

Run09 exceeded the initial10second shell-tool yield. The orchestration printed
only the result's output field and inadvertently discarded its session ID.
Therefore its final console summary and outer process exit status were not
directly recovered. The complete fresh XML was independently reopened and
parsed as73/0/0/0,16.939s; this alone is **not evidence of a clean outer terminal
exit**, and no exit0 or pristine-final-console claim is made. The final suite
was not rerun to conceal this gap.

All17 new-reader subprocess result JSONs retained under
`.pytest_tmp/task58-final-bt-09/*/reader-result-*.json` were independently
reopened: each contains exact argv/script, returncode0 and empty stderr.
Those are direct child result observations, not the missing final outer exit.
The new helper began retaining result JSONs at run07; earlier runs retain
fixtures and XML failure output but no separate success-result JSON files.
A read-only `Get-CimInstance Win32_Process` lookup was sandbox-denied. A later
read-only `Get-Process python` query returned no rows; it is not terminal-wait
custody or proof of the missing exit. No process was controlled, killed or
restarted. Root was promptly informed, required no rerun/no inferred exit0,
and owns any independent process-state check.

### Fresh exact hashes

```text
tests/native_context_chain_worker.py    15689 bytes 210226b3fd40a9c9bbe8090c9c52a0a56840827e8e75bcd610e4544826d5b209
tests/test_native_context_chain.py      57702 bytes 9fb3212ec6e440636590c387b08f049c47b8e00379e339fa07f4e56675f28c2c
tests/test_native_context_timezones.py  12720 bytes 4184311baf68d942449c337d4295dcc739f75012246509e46d6c18c29e119ee1

.pytest_tmp/task58-red-01.xml    d579e0ac257ab1b107c87750e00db67b574b7697358a5c3b7f4df1a9f761f364
.pytest_tmp/task58-red-02.xml    a656cb950127bf5959205fd7c26733f3dc726f99416a7857c13136360b9496d8
.pytest_tmp/task58-green-03.xml  d7b2df498c70869e956c8d4ebfdad26ccceb21b7e7eb980d1a039f2d550a1fcc
.pytest_tmp/task58-green-04.xml  f87ab4e688c590b7146d73daacd0f8bea705c2f03185ad2b8197ea479539de08
.pytest_tmp/task58-green-05.xml  14a90fa51a733c6ac9f095606bf3e7c40aaab5b09c5f0d98dcff3a9a296f9f9f
.pytest_tmp/task58-green-06.xml  25d46405b9f417482a7d1c0f06f61473f14ef37a84d42efb853ab3f1071e5582
.pytest_tmp/task58-green-07.xml  510746a61d50d5bee8eb4f2fd66458ddbfb46e8d514adddeaeea412078cdb810
.pytest_tmp/task58-green-08.xml  8015275bb9d45db5abb1706de016604090ee74cfab5a443415fce2e0e411dde7
.pytest_tmp/task58-final-09.xml  09d7d9e6d8447baebb57a2c8493dea9b0358259325eab49eb75fe822f6966ab4
```

Freshly rechecked unchanged owner hashes:

```text
tests/native_context_chain.py                73befce90e1087c27350258387c1454527838b7242b767227bafd69cb4f3fff7
tests/native_context_chain_catalogue.py      48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935
tests/test_context_storage_corpus_consumer.py 5a59f75d0a3093238031159a813ce81b6c633c63105cab0338ed376a7bac7649
context_preparation_process_guard.py         62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4
context_preparation_budget.py                fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478
context_preparation_supervisor.py            c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8
```

Inspected existing local fallback source/archive hashes (fixture provenance,
not newly admitted native inputs):

```text
dateutil/zoneinfo/__init__.py 298834a6d842323729e4c5d21220499f79cc8d978d65abfbae5270e7eb73d52e
dateutil/zoneinfo/dateutil-zoneinfo.tar.gz d3ea52e7b6e968de0d884df1288193596fa95b803db4f92a18279a7398004475
```

## Self-review, remaining gates and sole-writer return

Self-review found no additional known implementation defect. The final
dependency-only import order, deny-before-admission fallback route, real
reader/cache behavior and unchanged-owner pins were rechecked. The existing
large harness test module was not restructured; new specialized tests were
kept in the explicitly owned focused module.

This is only the smallest actual reader-binding prerequisite. Independent
task-scoped spec/quality review, exact diff/archive/catalogue/stdin pinning and
the unchanged isolated native ATP/WTA chain with complete source/copy/kernel/
terminal readback remain Root's job. The known unrelated local PyArrow import
difference was not installed, admitted or used to claim native/full Task54
success. This does not establish transitive runtime closure, protected global
whole-C/B cost accounting, full-growth/empirical acceptance, B/restore/whole
suite/main/VPS deployment, device/store or release readiness. Original M1 and
other deferred minors remain open. Cricket/A0/P4b3/daily-job/product semantics
remain unchanged.

**I explicitly return sole implementation-writer authority to Root.** The
three executable/test files are frozen at the hashes above. Only this report
was written after final09. No further edits, tests or operations are pending
from this writer. No commit was created; Git/index/commits and all native
operations remain exclusively Root-owned.
