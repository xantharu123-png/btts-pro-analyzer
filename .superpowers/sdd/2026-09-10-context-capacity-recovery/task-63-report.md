# Task63 descriptor ownership report

Sole implementation writer at BASE4e47314f06a68cbf2e3a3e30dd2e39d10bce4e3d.
Complete Task63 brief read. No unavoidable parent/worker interface conflict:
the existing ExitStack lifetime and plan.json/sample digest persistence can
carry the new owner and observation without changing those modules.

Pre-code declaration: sample_active_inputs adds `descriptors`, null on the
unchanged portable route and a detached bounded runtime observation on Linux:
`{original_soft,desired_soft,hard,baseline,files,directories,required,ceiling,reserve}`.
baseline is B=max actual observed FD+1; required=B+F+U+128, ceiling32768.
The binding privately retains a process-bound owner, never serializable
authority. Linux holds one FD per unique absolute ancestor and input until
the original ExitStack unwinds, freshly hashes from held input FDs at every
sample, and restores original soft only after complete descriptor cleanup.
Inherited child soft is explicitly bounded by the same Root-approved contract;
no hard/CPU/RAM/space/helper/prefix change is made.

## Implemented semantics and self-review

_active_descriptor_reservation is the exact bounded arithmetic/refusal seam.
_ActiveInputOwner observes numeric /proc/self/fd entries, checks canonical
unique numbers/B<=128 and F+U<=30000, reserves128, requires required<=32768,
original soft<=32768 and adequate unchanged hard, then sets only the desired
soft with immediate exact readback. The actual observed descriptor numbers,
not a pathname inventory or count approximation, determine B. Root's planning
F4546/U468/B4 gives required5146; this arithmetic test is not live inventory.

Ownership starts immediately after every successful os.open, before fstat.
The root/unique ancestor union is opened parent-first once, followed by every
file relative to its held parent with no-follow/CLOEXEC/nonblocking flags.
Actual named and held types/links/full seven-field epochs/allocation agree.
Every sample checks the exact complete binding against the plan, freshly seeks
and hashes each held file FD to EOF with bounded reads, checks complete length,
all file/directory/ancestor epochs and physical allocation, and compares actual
NOFILE before/after. No content hash or closed identity is reused as authority.
The returned descriptor observation is detached; the live owner is private.

Original ExitStack ownership remains intact through the existing parent's
admission, copies, worker and final recheck. Unwind checks all held/named nodes
while every parent FD is still available, closes all owned nodes in reverse
order even after validation errors, and restores the exact original tuple only
after the owned FD release is complete. Original error/restoration failure is
never converted into success. If a close raises after releasing its FD, EBADF
is observed and never retried. A single retry is allowed only for a demonstrably
still-live owned inode, with no new FD allocation during this isolated
single-threaded unwind; even successful retry leaves the original close error
fatal. If release remains uncertain, the larger soft reservation is retained
and cleanup fails, rather than restoring under live ownership. No promise of
recovering an arbitrary persistent OS close failure is made.

Hard-limit drift is never repaired by changing hard; it invalidates restoration
and success. Restoration runs from the existing held.close() finalizer, so a
failure there invalidates the external exit even if an earlier report artifact
was written. That existing parent order requires no parent-file modification.

Portable Windows binding/hash behavior remains explicit; descriptors=null and
no resource/openat validation is claimed there. Task62 retained traversal,
manifest/profile/allocation/journal format, parent/worker, prefix, helpers,
budgets, CPU/RAM/space and inherited guard settings were not changed. The child
inherits the newly approved bounded softNOFILE and unchanged hard; this is not
a parent-only claim.

## Focused verification

All local commands used the existing
`.pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -m pytest`,
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, PYTHONDONTWRITEBYTECODE=1,
`-q -p no:cacheprovider`. NAME below supplies exact
`--basetemp=.pytest_tmp/NAME --junitxml=.pytest_tmp/NAME.xml`.
Unless otherwise stated the only target was
`tests/test_native_context_active_descriptors.py`.

- task63-red-01, chunk2f10f2, actual exit1:
  `2 failed, 1 skipped in 0.29s`. Missing arithmetic API and missing explicit
  descriptors field; the actual Linux test was skipped, not simulated.
- task63-green-01, chunkf3c643, actual exit0:
  `2 passed, 1 skipped in 0.24s`.
- task63-model-01, chunk9adc64, actual exit0:
  `18 passed, 1 skipped in 0.65s`.
- task63-adjacent-01, chunk6f8679, actual exit0:
  `25 passed, 4 skipped, 45 deselected in 1.14s`. Targets were the new module
  plus tests/test_native_context_receipt_diagnostic.py with selector
  `descriptor or active_input_binding or actual_main_rejects_active or rejected_admission`.
- task63-native-gaps-01, chunk838371, actual exit0:
  `18 passed, 16 skipped in 0.70s`.
- task63-close-red-01, chunk00834a, actual exit1:
  `1 failed, 1 passed, 34 deselected in 0.33s`, selector
  `preclose or public_path_bounds`. The controlled one-shot pre-release close
  fault left an owned FD live, demonstrating the missing cleanup case.
- task63-close-green-01, chunka49a58, actual exit0:
  `2 passed, 34 deselected in 0.26s`, same selector, after bounded owned-inode
  cleanup retry was implemented without suppressing the original failure.

The labeled Windows FD/limit model uses actual held file contents but modeled
directory FDs and mtime in place of native ctime. It checks reservation ordering,
whole ownership, fresh hashes/no reopening, restore-after-close, hard/high-B/
invalid-number/denial/readback refusal, limit drift, same-size edits, directory
epoch, physical allocation, read/stat/open/close/restore and caller-error paths.
These model checks are not native acceptance.

## Explicit native gates and minimal QA set

The native cases are retained but unexecuted here:

- Fresh ordinary-UID -I -S -B subprocess fixtures set initial soft1024 with
  unchanged existing hard, then use1100 actual files. One runs the exact prior
  multi-chain ownership loops with the actual pinned old opened() and requires
  EMFILE plus no leak. The new cases require all1100 FDs and unique ancestors
  held, full repeated hashes, no pathname reopen, exact desired soft/hard,
  restoration to1024 only after unwind, and /proc/self/fd equality.
- A separate fresh case uses the actual unchanged supervisor _child_run_python
  FD-closing implementation. Its test-only child chdir callback observes the
  point immediately AFTER the real inherited-FD closure, verifies bounded
  inherited NOFILE and only stdio/observation FDs, then exits before UID drop or
  guard installation. Actual child terminal status and both pipes are checked;
  parent retained bindings are sampled again. This proves only that boundary
  when run, not native capability/guard/SIGSTOP acceptance or a receipt worker.
- Native binding/failure cases use actual Linux FDs and seven-field epochs with
  an explicitly modeled limit provider for injected failures. They compare full
  output with the previous path-based sampler and exercise hardlink/symlink,
  same-size edit, file/directory replacement, read/stat/open/close, drift and
  restoration failures with actual /proc/self/fd leak checks.
- The small in-process native success case explicitly skips an initial
  soft>32768 instead of relaxing the production contract. The fresh subprocess
  cases provide the controlled1024 success coverage independently.

Minimal future isolated native test layout: this new test module, the new
catalogue, unchanged tests/native_context_chain_catalogue.py and unchanged
context_preparation_supervisor.py (needed only for the closure case). Imports
are pytest and stdlib, no product modules, Task62 test module, admission/budget
owner, baseline, retained corpus or Root instrument. The supervisor bytes are
checked against their existing pin before compilation. Normal QA UID1000 with
an existing pytest/Python3.12 environment and own fresh writable fixture root
is sufficient; no root pytest or installation is needed. Existing hard>=2048
is required by the small native fixture and is checked, not increased.

Use PYTEST_DISABLE_PLUGIN_AUTOLOAD=1/PYTHONDONTWRITEBYTECODE=1 with
`python3 -B -m pytest --noconftest -q -p no:cacheprovider tests/test_native_context_active_descriptors.py`
and fresh explicit basetemp/XML paths. Root controls that future execution.
No native subprocess/fork, VPS operation, Task62 suite, Task58, real baseline/
retained scan, repository suite, Git/index, install, cleanup or subagent was
executed by this implementation turn.

## Frozen final command and actual output

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& .pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -c 'import os,subprocess,sys,json,time; env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",PYTHONDONTWRITEBYTECODE="1"); command=[sys.executable,"-B","-m","pytest","tests/test_native_context_active_descriptors.py","tests/test_native_context_receipt_diagnostic.py","-q","-p","no:cacheprovider","-k","descriptor or active_input_binding or actual_main_rejects_active or rejected_admission","--basetemp=.pytest_tmp/task63-final-01","--junitxml=.pytest_tmp/task63-final-01.xml"]; start=time.monotonic(); result=subprocess.run(command,env=env,capture_output=True,timeout=120); print(json.dumps(dict(command=command,child_exit=result.returncode,stdout=result.stdout.decode("utf-8",errors="replace"),stderr=result.stderr.decode("utf-8",errors="replace"),wall_seconds=time.monotonic()-start),sort_keys=True)); sys.exit(result.returncode)'
```

Actual chunk075728:

```text
child_exit: 0
outer/tool exit: 0
stdout:
....................ssssssssssssssss.......                              [100%]
27 passed, 16 skipped, 45 deselected in 1.11s
stderr: empty
outer wall_seconds: 1.5629999999982829
```

Hashes read before the run and confirmed unchanged afterwards in chunkc3f3ef,
actual exit0. No source/test change followed the final run; only this report.

| Artifact | SHA256 |
| --- | --- |
| tests/native_context_receipt_diagnostic_catalogue.py | 69a7300536b81d78c38fd6a7d4701f451b1d1468f546ba892908896311dc7f7b |
| tests/test_native_context_active_descriptors.py | aeb378e3bf9bb79fdb8793ba382780724a7cc116c9eb682bb67c67c2cac6e69c |
| .pytest_tmp/task63-final-01.xml | 65f12e24226368d292283dab5fa7ed94d385d18c7fd6bb19ee708ca51197f76c |
| .pytest_tmp/task63-red-01.xml | 70ac4b5a5e5f35097505bbbb72edafae84be04998e5a00592c45cdb233329380 |
| .pytest_tmp/task63-green-01.xml | a9bb25e5e863e9fcc41aee5e13a436ae5c75cef85a21f2963c40a2a18597a605 |
| .pytest_tmp/task63-model-01.xml | 35e23b78ff88e59e2d1f6a7fa836db626cfcf784b6bd9748331220355919a213 |
| .pytest_tmp/task63-adjacent-01.xml | 9e3b54724b0ee34b92cbf307bc0f76742dcc6eed17413198f9d02cdc2bc9cc0c |
| .pytest_tmp/task63-native-gaps-01.xml | 251a54cedfb3aa8eed5dd22d961fbb579b05f61ac0fe3a6e463a4dda9526dd6e |
| .pytest_tmp/task63-close-red-01.xml | 158cef561cda72eebd4743e4b4c176fa50c189b317027f653a6e6a26c3046d03 |
| .pytest_tmp/task63-close-green-01.xml | 24a23d15f14a93e4aa3b1f9b7b465fb900a32c9875a6c20bc7370a4ce47cca6a |

Sole-writer return: the catalogue Task63 active-input slice, new focused test
module and this report are explicitly returned to Root. No further writes
without dispatch. Independent review, all actual native tests/measurement,
transport/pin updates and Git/index remain Root-owned. No full-C/B, capacity,
restoration/deployment/release or native diagnostic success is claimed.
