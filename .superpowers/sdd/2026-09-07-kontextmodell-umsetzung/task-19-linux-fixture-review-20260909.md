# Independent D4 Linux-fixture correction review

Date: 9 September 2026. Reviewer: `/root/b3_shared_snapshots_20260909`.
Disposition: **PASS for these two fixture-only corrections. No finding.**
This review is separate from the completed freeze/open-registry review and
does not broaden either packet into empirical, deployment or activation approval.

## Exact reviewed bytes

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Parent: `dfcc6d357c536e4390322c1267bc26957663ddbd`.

| File | SHA-256 |
| --- | --- |
| `tests/test_context_runtime_backup.py` | `71dc37951bed4e6fc576e842829f7b0af08b692243bd6c353423237c9cddef62` |
| `tests/test_tennis_state_codec.py` | `e422a1cc4dba16706c98d149a3fe1b72bf226b2d2299ffbfe27b2ed777d7d246` |
| Unchanged `context_runtime.py` | `c470d35fd60e413c8371aa22baa9097dedc2385a5eee5644ca56e0930b6c10c2` |
| Unchanged pinned stage helper | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |

All four hashes matched at entry and after the combined run. Reviewed the exact
two-file diff against the parent, complete changed test bodies and their
surrounding setup/assertions, the unchanged runtime owner/mode guards, and the
complete controller Linux report. Protected source and helper also match the
parent Git bytes exactly, not merely a normalized text comparison.

## Findings and proof

Only three test bodies differ:

1. The real WAL-stage/archive/restore test explicitly creates the two new
   restore directories with 0700 and the new database with
   `O_WRONLY | O_CREAT | O_EXCL`, mode 0600. The expected archive member remains
   explicit, with no extractall, overwrite or archive-directed destination.
2. All three intentionally empty SQLite companion fixtures are changed to
   mode 0600 before verification. They therefore reach the intended sealed-stage
   rejection instead of failing earlier on permissive POSIX fixture permissions.
3. The valid legacy-pickle fixture gets mode 0600 before the real trusted loader.
   Its missing-field migration/default/hash checks remain unchanged.

These modes remain private under ordinary umask 0002. The product verifier is
not relaxed to accommodate an overly permissive fixture. The deliberately
world-writable negative test, actual symlink/hardlink checks, other test bodies,
exception messages, assertions and decorators are unchanged.

Eight independent added checks support that reading:

- Two whole-module AST comparisons prove that only the three declared test
  bodies change; every assertion, pytest raise/fail/skip call, decorator and
  function signature remains exactly the same. All other top-level nodes are
  AST-identical to the parent.
- One source check verifies raw pinned source/helper hashes and their exact
  Git bytes, plus unchanged runtime-path and legacy-loader source text.
- Five real fixture executions observe the actual 0700 directory arguments,
  exclusive 0600 creation, three companion chmod calls and valid legacy chmod.
  They still execute their real existing verifier/loader and full assertions.
  These Windows call observations are not misrepresented as POSIX enforcement.

## Own local executions and reviewer correction

Designated quality Python, `-B -m pytest -q -p no:cacheprovider`, fresh basetemp
for every run:

| Run | Result | Basetemp |
| --- | --- | --- |
| Both full changed test files | 142 passed, 3 skipped, 9.11 s | `.pytest_tmp/d4-linux-fixture-independent-windows-01` |
| First independent probes | 1 failed, 7 passed, 1.22 s | `.pytest_tmp/d4-linux-fixture-independent-probes-01` |
| Corrected independent probes | 8 passed, 1.40 s | `.pytest_tmp/d4-linux-fixture-independent-probes-02` |
| Combined exact packet | **150 passed, 3 skipped, 8.82 s** | `.pytest_tmp/d4-linux-fixture-independent-combined-01` |

The single initial reviewer failure was not a product or fixture defect: my
probe compared existing CRLF `runtime_paths.py` checkout bytes with its LF Git
blob. The clean Git diff confirmed the file was unchanged. The probe now
normalizes CRLF only for the two unpinned pre-existing Windows checkout files.
Raw exact equality and full SHA checks for the pinned source/helper remain
strict. No product/test file was reformatted or modified. The three skips are
the two unavailable Windows symlink privileges and the unchanged POSIX-mode test.

New independent probe:
`.pytest_tmp/d4-linux-fixture-independent-20260909/test_fixture_diff_independent.py`.
Final SHA-256:
`b0479f1a08e158ce1b7774a3c3bfe17674a879a7b59f81792a13afb589ba4698`.

## Linux evidence and honest boundary

The controller's complete report was read:
`docs/audits/2026-09-09-d4-linux-restore.md`, SHA-256
`60981f554ba072093df0169cef1b821f21ab56a9dfcbd8e389d73d073b29771b`.
It records the unchanged dfcc6d archive, separate private non-root Linux QA
copies, ordinary umask 0002, original 5 failed/429 passed and corrected
434 passed/0 skipped over the same eight full files. The documented changed
hashes and unchanged source/helper hashes match this independently inspected
packet. These are controller-provided Linux execution results, not an additional
SSH or Linux run performed by this reviewer.

This fixture review does not close source-resolved D2 evaluation, the complete
D3 input envelope, production backup/deployment integration or real empirical
injury/load acceptance. The earlier bounded D4 source review remains unchanged.
No source edit, commit, push, SSH, API/provider request, production read/write,
VPS command, protected-helper mutation, activation or financial action occurred.
Only isolated independent probes/report and their test data were created.
