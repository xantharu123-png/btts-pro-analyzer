# Task 2 Unicode discovery parity - native acceptance pending

Date: 2026-09-10. Base: `ffce3c224b9b5b6d0f4ad0ec474ec3ee6fdbc033`. Code commit: `690dd16c048db8c66a05936fffcb6aca55ab8a95`.

Scope: the controller authorized one remaining independent-review finding, without helper changes. Review reception/TDD/fresh verification guided the fix. This report is not native acceptance or deployment authorization. Writer control returns after this report commit; Task 3 RED files and root reports remain untouched.

## Finding and implementation

Python's existing `Path.suffix.casefold()` discovery accepts `Historical.ſQLite` (U+017F long s), but GNU find `-iname '*.sqlite'` under C/C.UTF-8 does not provide equivalent Unicode folding. The producer and unchanged helpers could therefore include a DB that byte admission and both later metadata/DAC lists silently omitted.

The installed updater now has one small stdlib `enumerate_backup_sources` seam, called by all three former find-pattern consumers. It uses Python Unicode case folding and suffix recognition for databases plus WAL/SHM/journal companions, and retains the original path spelling in NUL-delimited output. There is no character exception list and no unsupported-Unicode omission fallback.

The seam uses the fixed isolated system Python, imports only `os`, `pathlib`, `stat`, and `sys`, and performs no application/venv import. Both modes traverse without a same-filesystem restriction and raise on traversal errors, unsafe directory links, or nonregular/multiply-linked selected files. Byte mode remains conservative with no excluded trees; path mode retains the existing named excluded components used by the metadata/DAC inventory. The complete producer/context/rollback inventory code already uses Unicode case folding and remains unchanged here.

The two path consumers continue to create exclusive root-private inventory files and reject the enumeration status before processing any partial list. Byte mode emits its final total only after successful traversal. The separate source symlink scan still uses find, but it has no suffix-matching decision and therefore no Unicode suffix parity dependency.

## RED / GREEN evidence

- `.pytest_tmp/task2-unicode-red-01.xml`: **3 expected failures**, 334 deselected, 2.63s. Actual preflight counting omitted the new 2-KiB Unicode file (7 instead of 9 KiB total); both actual metadata/DAC callers omitted its path. The GNU find calls ran with `LC_ALL=C`; real filesystem bytes and the actual shell consumers were exercised.
- Existing real producer and context-inventory fixtures were extended with the same U+017F name as positive discovery/transport controls.
- The final Unicode regression also includes real Unicode-named WAL, SHM and journal companions: expected total is 12 KiB, and every original path reaches both consumers.
- Shared-enumerator EACCES tests execute its actual Python walk with an injected `os.scandir` denial. Partial-list/status rejection remains covered at both shell consumers. Existing ordinary mixed-case, producer initial/final traversal, output integrity, two-phase recovery and cross-device-query regressions remain green. Host tests substitute only the trusted interpreter location for `/usr/bin/python3`; no production account or helper permissions are changed.

Final command:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/task2-unicode-green-02 --tb=short --junitxml=.pytest_tmp/task2-unicode-green-02.xml
```

**339 passed in 47.57s**, exit 0. Bash syntax and exact two-file diff checks returned 0 immediately before the code commit.

## Remaining gates / preserved work

Independent review and native exact-new-byte Unicode parity, traversal/DAC and full-chain acceptance remain controller gates. The controller reported the preceding `c2cb1c9` full-chain/OS DAC/HMAC/retained-FD/EACCES checks passed; that evidence does not automatically validate this later patch. No native/VPS run, network, push, broad suite, updater installation, model/source/math/schema change or Task 3 edit was performed by this implementer.

The code commit contains only `deploy/update_server.sh` and `tests/test_context_update_hook.py`; this report is committed separately. In particular, `tests/test_context_updater_repair.py`, its RED report, and root evidence/progress WIP are excluded.

## Exact file hashes

- Updater: `24a5366692abeda8c4bcab1157fbed8806b97a72822b0db992545bb62e3de6a5`.
- Hook tests: `cec4a95c8211319ded36b41608791e715789bd176c2ad8a00e090d29ddf631e7`.
- Unchanged backup helper: `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`.
- Unchanged staging helper: `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
