# Full-suite native-chain regression diagnosis

Status: QA-only correction implemented following Root's explicit ruling;
focused and final scoped GREEN complete. Source/test edits are frozen for
Root's independent review and final whole-suite run. Starting HEAD is
`0b529cf53307382c8f6708dded419bdf4eeb66ca`.

## Diagnostic and test plan (recorded before code changes)

1. Compare each pinned owner against raw worktree, LF/CRLF representations,
   pre-batch Git blobs and current Git blobs; do not change admission pins.
2. Derive reservation independently from the actual closed file slots.
3. Reproduce the five failures at HEAD and in an isolated source-only archive
   of pre-batch `f3c2b6083b8bcf78014a26302beb3afd97b8aaf9`.
4. Await Root's remainder result and ruling. If authorized, separate current
   portable integration from historical native-contract fixtures, preserving
   native raw-byte rejection and every fixed resource/identity guard.
5. Run focused RED/GREEN and relevant native-chain tests, not the full suite.

## Exact cause

All four pinned owner files are unchanged between pre-batch and HEAD. Their
worktree bytes equal those Git blobs exactly (LF, zero CRLF pairs). The three
helper files match their frozen pins. Only Task54 differs from its native pin:

| Owner | Worktree / HEAD / pre-batch SHA256 | Frozen pin |
| --- | --- | --- |
| context_preparation_process_guard.py | 62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4 | same |
| context_preparation_budget.py | fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478 | same |
| context_preparation_supervisor.py | c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8 | same |
| tests/test_context_storage_corpus_consumer.py | c6a78cf2e5e06b26d2730b88ffc8482d97aff72d5dd67e59bb3b76aa029c8473 | 5a59f75d0a3093238031159a813ce81b6c633c63105cab0338ed376a7bac7649 |

Task54's CRLF representation hashes to
`9f1241df5690c321eea78bcb58cf4b21c2d0b6df6490b2c24e53ee242c51e05a`;
neither representation matches the frozen historical pin. This is not a
Windows/path/SQLite allocation issue and not caused by the current five-commit
repair batch.

Earlier commit `f3a0ebc6d63e96833c1b837cd87cf287b50c85cf` added two exact 4096-byte
coordination-file reservations and their regression test to Task54. It did not
update the historically frozen native catalogue/parent. The original pinned
Task54 belongs to `cac8db725b4c9ffac6bbcb4f81817d90da2823c9`.

The independent slot sum is:

- Setup: four main/journal pairs at 4 MiB each, 1 MiB directory metadata, plus
  two fixed 4096-byte lock slots: `8*4194304 + 1048576 + 2*4096 = 34611200`.
- Whole job: five main/journal pairs at 4 MiB each, 1 MiB ledger, 1 MiB metadata:
  `10*4194304 + 1048576 + 1048576 = 44040192`.
- Union: `34611200 + 44040192 = 78651392`, exactly 8192 above old 78643200.

WorkspaceBudget sums the predeclared ceilings; path names and observed SQLite
sizes do not enter this ceiling. External-source allocation affects its
separate active-input ceiling, not workspace/union reservation.

The native parent also hard-rejects anything but the old owner, setup34603008,
whole44040192 and union78643200. The native attempt catalogue omits the new
lock filenames. Thus repinning Task54 alone or changing the test's expected
number would not repair the native contract and is prohibited here.

## RED evidence

Environment: existing Python3.12 venv, `PYTHONDONTWRITEBYTECODE=1`,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Common invocation:

```text
C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe -B -m pytest -q -W error::DeprecationWarning -p no:cacheprovider tests/test_native_context_chain.py -k "actual_fixed_driver or manifest_requires_exact or timezone_launcher" --basetemp=<fresh-root> --tb=short
```

- Current HEAD, basetemp `output/playwright/native-chain-red-20260918-01`:
  **5 failed, 55 deselected, 7.10s**, exit1, same five exact reported failures.
- Detached pre-batch source archive: `git archive f3c2b6083b8bcf78014a26302beb3afd97b8aaf9 --format=tar --output=output/playwright/ncbaseline-20260918-01.tar -- '*.py'`;
  extracted into `output/playwright/ncbaseline-20260918-01` without moving HEAD.
  Same invocation from that directory with basetemp
  `../ncbaseline-red-20260918-01`: **5 failed, 55 deselected, 6.23s**, exit1.
  All five failures exactly match current HEAD (including +8192).

Both archive and temporary results remain retained. No cleanup, network,
publication, deployment, native execution or budget reset was performed.

## Approved minimal correction

Root lifted the temporary source freeze after the remainder finished:
2913 passed, 48 skipped, 2 failed in206.59s on unchanged0b529cf. Root explicitly
approved QA-only separation, not native requalification. Read the generated
`docs/superpowers/plans/2026-09-18-native-qa-portability.md` and
`.superpowers/sdd/2026-09-18-native-qa-portability/task-1-brief.md` before edits.

Native catalogue/parent/worker, all three helpers, Task54 and product owners
remain byte-for-byte unchanged. Historical manifest/archive positive cases
use an exact hash-checked fixture of original cac8db7 Task54. Current portable
driver integration independently asserts its actual lock-inclusive reservation
and real rollback. It verifies frozen parent rejection first for the actual
current owner and then for current reservation even if falsely relabelled with
the old owner. Positive frozen parser coverage is a separate, explicitly
synthetic historical protocol fixture; all six existing rejection mutations
remain and run against an otherwise accepted fixture for both ATP and WTA.

Manifest tests exercise native/Windows/POSIX path representations and reject
current Task54, each helper's byte tampering, and CRLF raw bytes. Launcher cases
build actual archives/manifests with recomputed consistent hashes and reject
current/tampered/CRLF Task54 at the unchanged owner gate. The historical positive
still executes only the actual bootstrap/catalogue and rejects timezone aliases.
The historical Task54 fixture is data only and never imported/executed.

Current native harness qualification would remain blocked until separately
authorized coherent review of Task54, pins, slots and parent constants. Local
fixture repair is not that approval and does not establish release readiness.

## Additional two failures and corrected baseline evidence

The shared receipt-diagnostic fixture also read current source bytes while
claiming a historical frozen owner. `context_storage_v2/inventory.py` is the
only mismatch among all13 receipt PINS/HELPERS:

- Current worktree, HEAD and pre-batch exact LF SHA:
  `05e4054dc764001ef6ecf1ab631bacadd109ca89b94b30c5deb60a1ce704e295`.
- Current CRLF SHA:
  `71604dad702da88b7642d8bf8ae64528d7e28232367095581245bc103bdb3f76`.
- Frozen SHA and exact c5912a7 Git blob (13268 bytes):
  `7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b`.
- Earlier `bf2268125b98d2708be3abe0449d6e774f778700` added two table declarations:
  context_snapshot_references and context_snapshot_reference_blocks. No code in
  that owner changed during the current five-commit repair batch.

The shared v1/v2 fixture now uses that exact historical inventory blob, with
new current-owner/tampered/CRLF rejections after recomputing the complete
allocation/admission identity. No production inventory behavior/pin changed.

Important correction to the first detached experiment above: Windows Git
archive inherited core.autocrlf and rewrote export line endings. Its first five
failures are not sufficient exact-source baseline proof; the additional two
initially failed earlier at old-catalogue raw-byte validation. Both misleading
experiments remain retained, not silently deleted or presented as final proof.
Repeated the source-only archive with explicit `-c core.autocrlf=false` into
`output/playwright/ncbaseline-lf-20260918-01.tar`, extracted into same-name folder.
Verified Task54, inventory and old-catalogue hashes match pre-batch Git blobs.

Final exact pre-batch RED command, from that isolated LF directory:

```text
C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe -B -m pytest -q -W error::DeprecationWarning -p no:cacheprovider tests/test_native_context_chain.py tests/test_native_context_qa_coordinator.py tests/test_native_context_receipt_diagnostic.py -k "actual_fixed_driver or manifest_requires_exact or timezone_launcher or v2_manifest_accounts_external_controls or closed_manifest_recomputes" --basetemp=../ncbaseline-lf-red-20260918-01 --tb=short
```

Result: **7 failed, 130 deselected in6.52s**, exit1. Exact same seven failures,
not earlier mask failures; original HEAD never moved.

## Owned files and fixture provenance

- `.gitattributes`: exact LF rules for only the two new historical fixtures.
- `tests/fixtures/native_context_chain_task54_cac8db7.py`: byte-for-byte copy of
  cac8db725b4c9ffac6bbcb4f81817d90da2823c9 Task54; 27577 bytes, SHA5a59f75d above.
- `tests/fixtures/native_context_inventory_c5912a7.py`: byte-for-byte
  `c5912a7cb8ae095b7e7f63a0b3ce6ae2aaf9052a` Git
  inventory source; 13268 bytes, SHA7e099cd9 above.
- `tests/native_context_chain_fixtures.py`: test-only static mapping and raw
  digest verification, no runtime Git lookup, imports or normalization.
- `tests/test_native_context_chain.py`: actual current driver/reservation and
  rejection, separate synthetic historical parser, historical archive fixture.
- `tests/test_native_context_receipt_diagnostic.py`: shared historical inventory
  manifest data plus adversarial v1 rejection.
- `tests/test_native_context_qa_coordinator.py`: adversarial v2 rejection.
- This report only; Root's plans, ledgers and handoff edits are not mine.

Both fixture files were created using apply_patch from Git blob output and then
verified by direct byte equality against fresh `git show` output, not merely by
a reported digest. Native apply_patch fallback was needed for existing-file
updates because Windows sandbox initialization failed with deny-read ACL error.

## Verification

Focused GREEN (same environment as RED):

```text
C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe -B -m pytest -q -W error::DeprecationWarning -p no:cacheprovider tests/test_native_context_chain.py tests/test_native_context_qa_coordinator.py tests/test_native_context_receipt_diagnostic.py -k "actual_fixed_driver or manifest_requires_exact or timezone_launcher or v2_manifest_accounts_external_controls or closed_manifest_recomputes or nonhistorical_inventory or synthetic_historical" --basetemp=output/playwright/native-chain-green-20260918-01 --tb=short
```

**18 passed, 130 deselected in7.52s**, exit0.

Final complete edited files plus directly related native contracts:

```text
C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe -B -m pytest -q -W error::DeprecationWarning -p no:cacheprovider tests/test_native_context_chain.py tests/test_native_context_timezones.py tests/test_native_context_qa_coordinator.py tests/test_native_context_receipt_diagnostic.py tests/test_native_context_receipt_retained_walk.py tests/test_native_context_qa_retained_v2.py tests/test_native_context_qa_budget.py tests/test_native_context_diagnostic_admission.py tests/test_native_context_active_descriptors.py tests/test_context_storage_corpus_consumer.py --basetemp=output/playwright/native-chain-final-20260918-01 --junitxml=output/playwright/native-chain-final-20260918-01.xml --tb=short --durations=5
```

Full stdout/stderr retained in `output/playwright/native-chain-final-20260918-01.log`.
Result: **337 passed, 54 skipped, 2 warnings in107.66s**, exit0. The warnings
are the existing Task54 `record_property` versus pytest's default xunit2 XML
format, not deprecation/production warnings. The54 skips are explicit native
platform/preparation gates, not new skips introduced here. This includes the
three end-of-file chain cases not reached by the initial full-suite maxfail
cutoff. No full repository test was run by this implementer.

To preserve compatible Task54 XML and verify warning-free reporting, reran
only its six tests with the same environment and
`-o junit_family=xunit1 tests/test_context_storage_corpus_consumer.py
--basetemp=output/playwright/native-chain-task54-20260918-02
--junitxml=output/playwright/native-chain-task54-20260918-02.xml --tb=short`:
**6 passed in8.31s**, exit0, no warnings. No source changed between runs.

Fresh byte-equality check against starting0b529cf passed for native chain
parent/catalogue/worker, receipt parent/catalogue/worker, QA coordinator/budget,
Task54, product inventory, and all three preparation helpers. All fixed bounds,
native/source guards, acceptance pins and financial/model/source behavior stay
unchanged. `git -c core.autocrlf=false diff --check` passed. Unrelated dirty
handoff files and untracked artifacts are preserved, not staged with this work.

## Handoff and remaining gates

Self-review found no production/source guard change. Historical fixtures are
verbatim checked Git blobs, not fabricated matching metadata; raw tampering and
CRLF inputs still fail real unchanged validators. Current ATP/WTA/rollback
execution is proven separately and explicitly rejected by the frozen parent.
No historical fixture is imported as current executable source. No checksum
repinning, resource relaxation, parser bypass, dependency/network action,
database edit, scientific/financial change, push or deployment occurred.

Owned change list above is the exact local commit scope; all other WIP remains
Root/user owned. Root owns independent review, final whole-suite qualification,
integration and any subsequent publication. Current native chain and receipt
diagnostic still reject the newer Task54/inventory owners: coherent native
requalification remains open and cannot be inferred from these portable passes.
