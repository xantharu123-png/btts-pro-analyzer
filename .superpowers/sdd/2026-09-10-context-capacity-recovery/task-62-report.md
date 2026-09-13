# Task62 held-FD retained traversal report

Sole writer accepted at BASE68c1ff89042d26a9c9454a308e3fe65defa8947a.
Read complete Task62 brief and Task61 native preparation evidence. No native
success inferred from the signal9/SSH137/outer1 preparation STOP; exact last
root remains unknown. All preparation artifacts/costs remain retained.

Pre-code declaration: public retained_root(path) and its exact output stay
unchanged. New private _retained_root_linux(path) holds the reviewed root entry
once and opens descendants relative to held directory FDs. The previous body
is retained unchanged as _retained_root_portable(path). Only retained traversal
and tightly local support change; no builder reuse, cache, helper/pin/limit or
parent/worker change. Linux native tests are explicit skips on Windows; a
separately labeled modeled-FD adapter checks control flow with real local file
bytes, but cannot prove native openat/DAC/no-follow semantics.

## Implementation / self-review

The Linux branch calls the unchanged reviewed opened(root,directory=True)
exactly once. That helper retains the absolute ancestor/root chain. Descendant
directories/files are opened by name with dir_fd pointing at their live parent,
O_NOFOLLOW/O_NONBLOCK/O_CLOEXEC (plus O_DIRECTORY for directories). The maximum
held child stack is bounded by existing depth32; ancestors are not reopened for
each descendant. No old helper is modified. Each child FD has a try/finally
close covering its fstat, read, recursive visit and final named-binding checks.

Every regular path, including every hardlink alias, still reads through EOF in
bounded1MiB pieces, verifies the complete length and hashes all bytes. There is
no digest reuse or read-buffer optimization in this patch. Every native regular
file gets complete seven-field named/held epoch comparisons and allocation
comparison before/after reading. Symlinks use raw byte readlink targets and
no-follow named stats, never an opened target. Directories get sorted complete
membership enumeration before/after, held epoch/allocation checks and final
named binding while the parent remains held. Root named/held comparison and
the old helper's final ancestor checks remain intact.

The original portable body is retained verbatim under its private route; only
the public dispatcher is new. Native canonical output uses identical record
keys, serialization order, counts, raw identities, allocation and SHA algorithms.
The new scanner repeats directory enumeration to explicitly verify membership;
this is additional checking cost, not a claimed timing optimization. All existing
file8GiB/total64GiB/entries200000/child50000/depth32/path2048 limits are unchanged.
No journal, allocation-plan, second-pass, parent, worker or resource-limit code
was changed. No approval to retry the stopped preparation is implied.

## Focused tests and limitations

The modeled adapter uses actual Windows file contents/stats and deliberately
modeled directory-FD operations. It substitutes mtime for ctime in its seven
identity fields because Windows fstat differs; it is NOT native epoch/openat
proof. Native tests use actual OS dir_fd calls and all original identity fields.

Coverage includes canonical inventory equivalence on branching/deep trees,
empty/large/mixed-name files, exact single root-entry/relative descendant opens,
FD cleanup on read/stat/scandir/close errors, held/named file epoch changes,
directory epoch/replacement, membership change, grow/shrink and unsupported
types. Close-error injection releases the descriptor and then raises, verifying
that the error propagates and the remaining owned stack unwinds; it is not a
promise to recover arbitrary permanent failures of an OS close operation.
Bounds cover child count, whole entry count, depth, path, file size and aggregate
allocation. Native-only cases additionally cover actual symlink/file/directory/
root replacement, FIFO refusal, exact old/new canonical equivalence, per-alias
full reads across fresh calls, and /proc/self/fd leak checks.

The native ancestor-open-scaling test is runnable against the previous catalogue
as well as the new one: its original-algorithm comparison falls back to public
retained_root, so the actual old-code failure is excess absolute root opens,
not a missing private symbol. That native RED/GREEN was NOT executed here.
Root's later isolated Linux test must establish it; Windows skips are explicit.

All local commands used the existing interpreter
`.pytest_tmp/qa-python312-c-01/Scripts/python.exe`, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1,
PYTHONDONTWRITEBYTECODE=1, `-B -m pytest -q -p no:cacheprovider`, and only
`tests/test_native_context_receipt_retained_walk.py` unless stated below.
Basename NAME means exact `--basetemp=.pytest_tmp/NAME` and
`--junitxml=.pytest_tmp/NAME.xml`.

- task62-red-01, chunkba3d08, actual exit1:
  `1 failed, 1 passed, 1 skipped in 0.36s`. The modeled relative-FD path did not
  exist (AttributeError for _retained_root_linux); native scaling skipped.
- task62-green-01, chunka1f9be, actual exit0:
  `2 passed, 1 skipped in 0.32s`.
- task62-errors-01, chunk69a943, actual exit0:
  `16 passed, 20 skipped in 0.80s`.
- task62-bounds-01, session95445/terminal9c4fe7, actual exit0:
  `22 passed, 21 skipped in 9.57s`.
- task62-final-01, session24410/terminalf53f2e, actual child/outer0,
  `23 passed, 21 skipped in 10.10s`, stderr empty, wall10.71900000000096.
  It included the adjacent historical-hardlink test below. Afterwards only the
  new test's native baseline comparison was made compatible with the pre-patch
  catalogue; no implementation change. The final freeze was rerun below.

No Task58, entire Task61 module, repository suite, native execution, VPS/network,
Git/index, installation, cleanup or subagent operation was performed.

## Minimal future isolated Linux QA input set

Exactly these three source files preserve their relative layout:

1. tests/test_native_context_receipt_retained_walk.py
2. tests/native_context_receipt_diagnostic_catalogue.py
3. tests/native_context_chain_catalogue.py (unchanged pinned SHA
   48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935)

Imports are pytest plus stdlib. No product modules, helpers, seed, archive,
retained data, database, Task61 parent/worker or conftest is required for this
new module. Python3.12 and the already selected pytest runtime suffice. Normal
QA UID1000 needs only its own fresh writable fixture/output root and readable
/proc/self/fd; native tests create their own hardlinks, inert symlinks and FIFO.
Root rights are NOT required, and importing pytest as Root is not requested.

Suggested isolated command (future Root-controlled operation, NOT executed here):

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest --noconftest -q -p no:cacheprovider tests/test_native_context_receipt_retained_walk.py --basetemp=FRESH_QA_PATH --junitxml=FRESH_XML_PATH
```

Use the known ordinary-user pytest environment, no installation. The optional
adjacent historical-hardlink regression below requires the fourth test module;
it is not necessary in the minimal three-file native transport. No wall-time,
capacity, full-C/B or release success is promised by this input declaration.

## Final focused freeze

Exact bounded final command from the dispatch worktree:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& .pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -c 'import os,subprocess,sys,json,time; env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",PYTHONDONTWRITEBYTECODE="1"); command=[sys.executable,"-B","-m","pytest","tests/test_native_context_receipt_retained_walk.py","tests/test_native_context_receipt_diagnostic.py::test_historical_hardlink_occupancy_is_inert_but_active_slots_reject_it","-q","-p","no:cacheprovider","--basetemp=.pytest_tmp/task62-final-02","--junitxml=.pytest_tmp/task62-final-02.xml"]; start=time.monotonic(); result=subprocess.run(command,env=env,capture_output=True,timeout=120); print(json.dumps(dict(command=command,child_exit=result.returncode,stdout=result.stdout.decode("utf-8",errors="replace"),stderr=result.stderr.decode("utf-8",errors="replace"),wall_seconds=time.monotonic()-start),sort_keys=True)); sys.exit(result.returncode)'
```

Actual launch chunkcf1b73/session75112, terminal chunka16f74:

```text
child_exit: 0
outer/tool exit: 0
stdout:
..s..............sssssssssssssssssss......s.                             [100%]
23 passed, 21 skipped in 11.23s
stderr: empty
outer wall_seconds: 11.90599999999904
```

Post-run readback chunk752f1a, actual exit0:

| Frozen artifact | SHA256 |
| --- | --- |
| tests/native_context_receipt_diagnostic_catalogue.py | a17c62e6fec58735974f74be59e16dfd2d7ac9061da58239eac35a4f3a202185 |
| tests/test_native_context_receipt_retained_walk.py | d71f669ded5272ef18e3907f7f1d5b628a72e1a35c4aa604d55cfe9a9438a68e |
| .pytest_tmp/task62-final-02.xml | 89da0b0cfbd71566930355f95a28d3836eae6ef024d2fc699e1906bbfeda5846 |

Intermediate retained XML hashes:

| XML under .pytest_tmp | SHA256 |
| --- | --- |
| task62-red-01.xml | 42318b2a921b665f93d4556360d242df54f2b5a45396f71474907759b9d79475 |
| task62-green-01.xml | 839ace94a422d29a26eb6b8ce4eb0436c41715e50160f25fd2aedaadc0bc3adc |
| task62-errors-01.xml | bb648d4299be719acee3b7c337ed15a1564c7f0560cf82403aba89a833b2d2bc |
| task62-bounds-01.xml | f91cb8271abcfb668b33460ead7227e7e2b36f640c51cf3f4d444cd43ba5b69a |
| task62-final-01.xml | 1035cccecd38d17bf2a5141e719a5d22ddccf650b53dff2059b8ef702bb3df8a |

No source/test changes followed final-02; only this report was completed.
Native RED/GREEN and actual metadata/FD semantics remain unexecuted gates;
23 portable/model passes are not Linux acceptance. Actual retained-union
performance under unchanged60/240/300 and1800/3600 limits remains unknown.

Sole-writer return: ownership of the catalogue's Task62 retained slice, the
new focused test module and this report is explicitly returned to Root.
I will make no further writes without dispatch. Root owns independent review,
Git/index, all transport/pin changes and any separately authorized native QA
or measurement. All prior artifacts/costs and empty diagnostic job/registry
remain outside this local-only implementation; no cleanup/retry was performed.
