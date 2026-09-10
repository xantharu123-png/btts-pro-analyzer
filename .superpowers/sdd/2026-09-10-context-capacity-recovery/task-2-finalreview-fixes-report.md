# Task 2 final-review inventory fixes - acceptance pending

Date: 2026-09-10. Base: `0fbd75730d66a701f1812652588c3269f7edf283`. Exact code commit: `c2cb1c98ee66fbda792ed2c339eff8aa8ceb0c87`.

The controller authorized only the updater, its hook tests and this report. Review reception, test-driven development and fresh verification skills were applied. This handoff does not grant deployment or independent acceptance. Writer control returns to the controller after the report commit; no subsequent edits/tests without another grant.

## Fixes and scope audit

- The complete producer's initial and final `os.walk` inventories now have an explicit raising `onerror` callback. An unreadable subtree is an immediate traversal failure, never evidence of absence or a completed receipt.
- The other two completeness proofs using `os.walk` now also reject traversal errors: trusted payload extra/missing-file verification and rollback source-metadata inventory. The staged-output chmod walk and application cache purge walk were inspected but are operations, not complete-inventory assertions; this patch does not broaden their behavior.
- Producer discovery and context archive inventory validation now use `Path.suffix.casefold()`, matching the unchanged staging helper's existing `.db`/`.sqlite`/`.sqlite3` contract. Original path spelling is retained in manifests and ZIP members.
- Initial apparent-byte counting and both later metadata/DAC discovery lists now use case-insensitive GNU find suffix matching, including WAL/SHM/journal companions. Their former `-xdev` restriction, and the associated source symlink scan's restriction, are removed to match the producer/staging helper's cross-filesystem discovery scope. Existing exclusions are otherwise retained; conservative byte counting still includes more paths than the producer's excluded-tree set.
- The later source preparation and DAC loops no longer consume unchecked find process substitutions. Each first writes a distinct exclusive root-private NUL-delimited inventory under the existing stage, checks the find status, and only then processes its paths. Partial/failed inventories do not authorize source metadata changes or DAC acceptance.
- No helper bytes, model/source/schema/mathematics, report limitations, archive authentication format, Task 1 code, installed updater, production database or VPS state were changed by this implementer.

## RED evidence

- `.pytest_tmp/task2-finalreview-red-02.xml`: **5 failures**, 313 deselected, 0.85s. Injected real `os.scandir` EACCES for an existing SQLite-containing subtree. With both producer passes denied, the old producer emitted a completed receipt for an incomplete ZIP. Single initial/final denial was only detected later as inventory inequality, not an explicit traversal stop (the initial pass had already performed capture). The old payload verifier accepted a hidden unmanifested Python file; the old rollback metadata inventory published an incomplete manifest. Only Unix metadata/directory-fsync boundaries are simulated on Windows. One earlier fixture fd-mode error was corrected and is not RED evidence.
- `.pytest_tmp/task2-finalreview-red-03.xml`: **11 failures**, 318 deselected, 2.26s. Real producer ZIPs omitted `Historical.DB`, `Live.sQLite` and `Third.SQLITE3` while retaining ordinary `state.db`. Context inventory rejected these otherwise valid DB suffixes. Actual byte counting returned 1 KiB instead of the fixture's 7 KiB. Both actual metadata/DAC loops omitted mixed-case database and companion paths, and both accepted find exit 9 without rejecting.
- `.pytest_tmp/task2-finalreview-red-04.xml`: **3 failures**, 329 deselected, 2.48s. Explicit filesystem-device boundary simulation makes real GNU find prune a real subtree only when the caller asks for `-xdev`; actual byte-count and metadata/DAC command paths all omitted its DB. This is query-scope evidence, not a real mounted-filesystem test. The fixture's escape warning was removed before GREEN.

The controller separately reported an actual native uid-997 EACCES reproduction on the old `bdd5731` updater: valid synthetic producer/copy/inline restore/pinned-helper HMAC controls passed, but an unreadable root-owned subtree's actual hidden DB was omitted and the complete chain still accepted. That is controller evidence, not a native run performed by this implementer. These new bytes still require its native rerun.

## Fresh GREEN verification

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/task2-finalreview-green-03 --tb=short --junitxml=.pytest_tmp/task2-finalreview-green-03.xml
```

Result: **332 passed in 57.01s**, exit 0. Bash syntax check and `git -c core.autocrlf=false diff --check -- deploy/update_server.sh tests/test_context_update_hook.py` both returned 0 immediately before the exact code commit.

The new tests execute the real inline producer, payload and metadata logic, real SQLite/ZIP bytes and the actual shell inventory consumers. No test creates a privileged mount, changes protected helper ownership, or root-runs application imports. Existing 313 tests remain green.

## Remaining gates

Independent review of this exact patch; controller native current-source EACCES, mixed-case/full-chain HMAC/restore and actual DAC/resource/cross-mount checks; Task 1 native capacity/performance and repository-wide acceptance. No broad suite, network, push, installation or deployment was performed here. Earlier Task 2 follow-up/native limitations remain applicable where this report does not supersede them.

## Exact file hashes

- Updater: `1ef6bee0a75cd0005c5ee245ce83d3d65b6739da29689cfb59fbef100532a068`.
- Hook tests: `d52fe775deb93d3bfa1e6eddf06247550bfbbb0beca16e1acd81ce5141e5a3ca`.
- Unchanged backup helper: `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`.
- Unchanged staging helper: `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

The code commit contains exactly the two authorized source/test files; the following report commit contains only this file. Other agents' report/diff artifacts remain unstaged and preserved.
