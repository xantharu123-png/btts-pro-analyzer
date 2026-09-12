# Task 16: approved C implementation, controller evidence (in progress)

12 September 2026. This records development, not C/B/native/release acceptance.
The latest explicit `ja` approves C specification08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba.
B498e63c5 and existing controlled commit/push/deployment authority remain valid.

## New bounded ownership

- Root: contracts.py, inventory.py, test_context_storage_inventory.py,
  test_context_storage_integration.py, execution plan/handoff/index.
- c_refs: refs.py and own tests/report; subsequently snapshots.py and separate
  task17 report. Root and c_tennis independently review C2.
- c_history: history.py and own tests/report; independent inventory/Tennis review.
- c_tennis: tennis.py and own tests/report; independent refs review.
- No old model/source/runtime/feature/worker/odds code is changed in this cohort.
  New storage modules have no production caller yet. No implicit new CLI mode.

## Root implementation and actual local checks

Complete raw inventory is strict about the actual SQLite INTEGER/TEXT/BLOB/NULL
storage class and preserves raw string/blob bytes (including embedded NUL and
UTF-8/UTF-16). It scans all closed-schema tables and complete logical keysets,
including future, other-tour and unreferenced rows, and includes absent-vs-empty
schema identity. Different physical rowids are deliberately not logical keys.
Large values use incremental read-only blob access; small values use a bounded
inline path. An identity is historical evidence, never a reusable proof/view.

Inventory now has42 passing tests, including a fixed-class Limits validator
instead of an instance-overridable callback. Earlier41-test evidence remains
historical, not the count of the final test file.
Earlier root combined integration through a real source owner, one shared
max-cutoff spool, three earlier-cutoff feature comparisons and transaction-end
rejection: `4 passed in4.80s`, actual full old canonical bytes/digests equal.
The first integration invocation executed no tests because pytest's default
Windows Temp tree was inaccessible. A new never-existing workspace basetemp
was used; no existing temp tree or ACL was changed/deleted.

Runtime: bundled Python3.12 with project .venv site-packages explicitly supplied,
pytest9.1.1, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. The copied .venv launcher itself is
not portable. Local SQLite3.53.1 is not the VPS SQLite3.45.1 acceptance result.
No package installation, global environment/config mutation or memory update.

## Review findings retained, not hidden by green counts

1. c_history found the old schema owner's unbounded foreign_key_check.fetchall
   on corrupt input. Root added first-error-only preflight, with10,000 actual
   bad references proving the old collector is not called. Closed/reviewed.
2. Root found C3 periodic footprint measurements alone could overallocate.
   C3 writer now sets and verifies max_page_count before schema creation;
   actual8KiB SQLITE_FULL regression returns no partial view. Closed in50C3tests.
3. Root found C2 iterator main/temp DDL changes could yield another cached ref
   before a block-end check. Owner added per-yield schema generation binding.
4. Root reproduced C3 TEMP-view shadowing: query_only OFF -> CREATE TEMP VIEW
   history AS SELECT * FROM main.history WHERE0 -> query_only ON hides all
   rows without total_changes/main-file changes. The added genuine regression
   failed (`1 failed,4 deselected in1.15s`); corrected, actual main/temp schema,
   journal, database-list and resource identities bound; independent rereview green.
5. c_history separately reproduced Tennis output writer schema/journal changes
   without a changed row counter. Read-only reopen plus full reader-state
   binding and TEMP/schema regressions are complete, including additional
   attach/temp-journal/resource cases. Independent final202-test run green.
6. c_tennis found C2 post-first-yield resource PRAGMAs/forged frozen limits were
   not rebound. Exact resource+limits lifetime binding, fixed-class validator,
   genuine immediate-next tests and independent rereview now complete.
7. Independent C2b reviewer reproduced SQL length(TEXT) stopping at NUL:
   20MiB trailing metadata was fetched into Python before later digest rejection.
   Root now binds complete octet lengths using actual SQLite encoding width.
   Original43 direct/UTF8/UTF16 probes pass unchanged; Python peaks9,092/7,078B
   instead of20MiB. Local allocator evidence, not native RSS or C6 acceptance.
8. Independent C1 copy review proved O_EXCL-close-SQLite-reopen could overwrite
   a pre-existing replaced destination before rejection. Root removed every
   writable SQLite reopen: fixed exclusive output FD, binary bounded raw copy,
   fd/path binding and fsync, required original source SHA, exact copy SHA and
   independent complete raw inventories. Actual Windows handle refuses the
   attempted target replacements; Linux replacement behavior still unmeasured.
9. The same reviewer proved a checkpointed WAL header without companions can
   create source side files on first schema read. C1 now checks raw01/01 header
   before _HeldRead/schema/page queries. Original source remains untouched.

These are new unpublished implementation findings. Reports retain the genuine
RED runs as well as exact corrected code hashes and independent follow-up runs.
Earlier passing targeted runs do not certify later changed bytes.

## C1/C2b source integration, 12 September continuation

copying.py is a new standalone-sealed-image adapter, not a live SQLite backup
API. It requires expected_source_sha256 supplied by the sealed input owner.
Complete source/copy bytes are identical; every old key/type/value is separately
inventoried on both held readers. Unknown old data is neither decoded away nor
deleted. Failures retain charged private partial files and return no receipt.

snapshot_source.py reads actual held source BLOBs in bounded chunks and extracts
only the known canonical top-level observation_refs array. Its remaining header
is limited to1MiB/the block budget, decoded by the existing owner. All real raw
row frames match the fresh complete C1 inventory; a separate coverage ledger
binds every source key, raw digest, size, adapted status and parts identity.
Unknown/oversized non-reference objects explicitly remain raw-source dependencies,
not standalone v2/model-approved results. Missing/extra/same-count foreign output
and malformed recognized inputs fail the whole new batch. No old owner changed.

Actual completed local runs (unique workspace directories and persisted JUnit):
- Initial combined new/adjacent509tests:111.89s, before the final NUL/FD fixes;
  .pytest_tmp/task16-all-frozen-03.xml. Not final-byte release evidence.
- Final C1 + C2 + C2b207tests:24.00s; .pytest_tmp/task18-copy-05.xml.
- Independent C1 + inventory + own FD probes75passed/1Windows-source-swap-skip,
  9.04s; reviewer retains original failed old-reopen/WAL probes unchanged.
- Source adapter83tests plus complete related315-test regression:35.81s.
- Root source -> exact raw copy -> parts -> close/reopen -> both real-source
  coverage and every known payload reconstruction, plus existing inventory /
  Tennis integration:6passed6.30s; .pytest_tmp/task19-integration-01.xml.

Root's complete `pytest tests` run is currently in progress with durable JUnit
destination .pytest_tmp/task19-full-suite-01.xml. Do not claim a full-suite pass
from these partial counters. Sourceadapter independent final review is complete:
23 actual independent cases pass on f080d605, including real SQLITE_FULL,
forged coverage/foreign keysets and complete4MiB raw-only hashing.
The runtime bytes are frozen while the full project suite executes.

The first combined launch named a nonexistent legacy test file and ran no tests.
The next tool session became unavailable after the user continued the turn; no
completion was assumed. Its full replacement with durable JUnit produced the
recorded509-pass result. This is local development/testing, not a reset of any
started native C preparation job; no such job has been started.

Fresh GitHub read verifies repairbranchb2e811a and main2dd1116. No new commit/push
or deployment at this checkpoint. Git output is not a server deployment claim.

## Fresh read-only VPS check

SSH uid1000; main/app revision2dd1116b68f3d94e9c24338c6c9dff9b01799221.
Correct unit betboy-app.service and Caddy active+enabled; internal8501 health
returnsok. The first exploratory service query used non-owning betboy.service;
its inactive result is not an app-outage observation. Corrected owning-unit
query confirms app operation. Seven timers listed. A later exact owning-state
check confirmed Wettfinder started09:07:28CEST and completed09:13:57 withResult=success;
its timer isactive/waiting withnext09:37CEST. The earlier dash coincidedwiththat
execution and was not used alone to claim either timerhealth or a schedulingbug.
Separate betboy-tennis.service remains failed; no restart/clear/repair performed.
Filesystem available14,828,679,168B; original isolated baseline remains270,233,600B.
No runtime database was downloaded, no new backup/worker/data preparation job
started, no new key/user/service installed, and no C/app/updater deployment.
The existing backup and seal must be freshly hashed/checked again before reuse.

## Still required

Finish and independently review all new components, exact local combined tests,
lossless snapshot storage/copy and whole input/workspace owner, complete actual
growth corpus with unchanged owner outputs, CPU/RSS/AS/disk evidence, then B
inventory/proofs/lifecycle/bootstrap, whole-suite/restore/release acceptance.
Global4GiB inputs and8GiB new workspace cannot be inferred from per-file checks.
No whole capacity proof, empirical model approval or completed rollout claim.
Concrete next-owner sequence, without a renewed approval question or silently
widened resource values: docs/superpowers/plans/2026-09-12-kontextspeicher-gesamtintegration.md.
