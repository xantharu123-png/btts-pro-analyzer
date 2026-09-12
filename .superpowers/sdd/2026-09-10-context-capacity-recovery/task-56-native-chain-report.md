# Task56 — native small-chain import and custody preflight

Status: **READ-ONLY PREFLIGHT COMPLETE; NATIVE CHAIN NOT YET EXECUTABLE.**
This is a bounded map for the next Task54 small integration only. It is not a
Task51 review, a native run, B runtime-closure authority, approval C completion,
or release evidence. Task51's current imports/API are treated as WIP input and
are not graded here.

## Smallest real route

The next native measurement must execute one fixed ATP case and one fixed WTA
case through the same actual owner chain required by Task54. Import discovery is
only preparation for that execution.

1. Before any writer, create one immutable `WorkspaceBudget` plan containing the
   exact corpus main/journal/two-bank-ledger, old-parts main/journal, history
   main/journal, features main/journal, and new-consumer main/journal slots plus
   directory metadata and the actual source `ExternalInput`. `WorkspaceBudget`
   retains all closed/failed/retried allocations and has no release/reset API
   (`context_storage_v2/workspace_budget.py:111-118`); external input identity and
   the active-input ceiling are bound at construction
   (`context_storage_v2/workspace_budget.py:156-180`).
2. Produce a small real legacy baseline with the existing `configure`/`run_batch`
   fixture route. Those helpers call the actual state/artifact owner, controlled
   provider reception, capture owner, live worker, prediction, Original/snapshot
   persistence, and Shadow store (`tests/test_tennis_live_worker.py:50-95`). Make
   a byte-identical, separate old oracle. The two ordinary normalized receptions
   plus the one genuine scheduled live reception are the three and only three
   new receipt inputs. This disposable setup/oracle phase may write its separate
   legacy context and Shadow stores; it is not the profiled C one-writer phase.
   Close every legacy/Shadow writer before starting the measured C path. If this
   setup runs inside the same native job, predeclare its context/oracle/Shadow
   files and retained retries as additional fixed slots and charge its disk,
   CPU, wall, RSS and output to that whole job; it cannot become unmeasured
   prehistory merely because the C phase starts later.
3. Call `build_receipt_corpus` with those three actual
   `(normalized_record, observed_at)` pairs. The owner commits and closes its
   writer before opening its own verification reader
   (`context_storage_v2/receipt_corpus.py:545-580`), and the returned dataclass is
   observed data rather than Source permission
   (`context_storage_v2/receipt_corpus.py:57-73`).
4. Open a **new file-backed, profiled `mode=ro` `TrackedConnection`**, configure
   it, begin and hold its transaction. Recompute `inventory_raw` and exact full
   typed membership against the oracle. Construct `VerifiedArtifactMapping`,
   build the actual `digest -> created_at` mapping, and call
   `context_runtime._verify_artifact_types`; that owner lazily loads tour-state
   and D2 semantics (`context_runtime.py:316-361`). Pass only its returned
   `semantics["protected_receipts"]` to `VerifiedReceiptMapping`, then call
   `validate_all`, whose completion is owned by the mapping itself
   (`context_runtime_inventory.py:61-70`, `context_runtime_inventory.py:113-125`).
   Keep this exact connection/transaction alive: both mappings are invalid after
   transaction-generation/end changes (`context_runtime_inventory.py:22-33`).
5. With the held source, create schemas in the separate fresh old-parts writer,
   call `adapt_source_snapshots`, validate exact coverage, commit and close it.
   The adapter requires both connections live, does not commit, and re-reads the
   complete source/output before returning (`context_storage_v2/snapshot_source.py:524-578`).
   Reopen the completed parts output read-only and check all old snapshot
   coverage. Never append new-consumer products to this source-coverage store.
6. Build `History` from the live validated receipt mapping. Its writer is
   committed/closed before it opens and returns a held RO `HistoryView`
   (`context_storage_v2/history.py:717-746`); the source mapping/connection and
   exact source file are rechecked for its lifetime
   (`context_storage_v2/history.py:264-323`). Call current Task51
   `prepare_tennis_consumer`; it uses the live History/Source, performs the real
   prediction once, writes/closes the feature writer, and returns a live prepared
   object holding the RO feature stream (`context_storage_v2/tennis_consumer.py:279-389`).
7. Open a **separate** fresh new-consumer writer and retain its caller-owned
   transaction. Call `put_tennis_consumer`; its returned value is only a
   candidate, not permission to accept or commit. Publication rejects aliasing
   with source/history/features and owns one savepoint but never the caller's
   commit (`context_storage_v2/tennis_consumer.py:560-610`). While that output
   transaction is still live and uncommitted, complete every comparison and
   caller-required cleanup: close the real prepared/feature owner, then History,
   the held Source and any remaining readers/cursors. Only after all final checks
   and closes succeed may the caller accept the candidate and commit/close the
   new-consumer writer. The final consumer contract explicitly requires
   `prepared.close()` before acceptance/commit because a returned result cannot
   certify later cleanup (`context_storage_v2/tennis_consumer.py:561-567`;
   `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-51-report.md:61-75`).
   Any comparison or cleanup error must propagate inside the writer scope so the
   caller rolls back/abandons the consumer transaction and publishes no success;
   the failed consumer file and all earlier private corpus/parts/history/feature
   artifacts remain retained for diagnosis (`context_storage_v2/sqlite_profile.py:400-423`).
   After successful commit, reconcile the whole workspace with no writer live,
   then reopen old-parts and new-consumer outputs RO and repeat the exact
   byte/membership/hash comparisons.

Exactly one writable main is live at a time **during the profiled C phase**.
Disposable legacy fixture/oracle setup (including its separate Shadow output) is
a prior, separately identified phase whose writers must all be closed at the C
boundary; if it shares the native job, its complete cost and slots remain in the
same whole-job accounting. The source, History, and feature RO owners overlap
only for the scopes required above, and the new-consumer transaction remains
uncommitted across their required final checks/cleanup. No detached dataclass,
`ReceiptCorpusResult`, `RawInventory`, public hash, caller boolean, or parts
descriptor can resurrect or replace these live owners.

## Exact source-declared import/data closure

This map was obtained by static inspection only; no project package was imported
and no probe was rerun. It distinguishes source-declared local closure from the
still-unmeasured Linux package/ELF closure.

### Actual chain entry clusters

- **Legacy fixture/oracle:** `tests/test_tennis_live_worker.py` eagerly imports
  `scripts/tennis_daily.py`, `tennis/shadow.py`, `tennis/elo.py`,
  `tennis/model_state.py`, `tennis/serve_model.py`, `tennis/state_codec.py`,
  `model_artifacts.py` and `pytest` (`tests/test_tennis_live_worker.py:2-16`).
  `configure` lazily imports `context_sources/tennis_capture.py`,
  `runtime_paths.py`, `tennis/live_context.py`, and `tennis/tour_state.py`; its
  provider call is replaced by the controlled response at the actual
  `requests.get` seam (`tests/test_tennis_live_worker.py:50-79`). `run_batch`
  lazily imports the capture/live-worker owners and invokes the actual Daily
  fetch/scan/finish route (`tests/test_tennis_live_worker.py:82-95`).
- **Corpus/custody:** `context_storage_v2/receipt_corpus.py` ->
  `contracts.py`, `copying.py`, `inventory.py`, `receipt_append.py`,
  `sqlite_profile.py`, plus `context_models/contracts.py`,
  `context_runtime_transaction.py`; `inventory.py` also imports
  `context_runtime.py` and `model_artifacts.py`
  (`context_storage_v2/receipt_corpus.py:22-45`,
  `context_storage_v2/inventory.py:9-18`).
- **Actual Source/D2:** `context_runtime.py` ->
  `context_models/contracts.py`, `context_observations.py`,
  `context_snapshots.py`, `context_runtime_transaction.py`,
  `model_artifacts.py`, `runtime_paths.py` (`context_runtime.py:9-34`). The
  actual `_verify_artifact_types` call then lazily imports
  `tennis/tour_state.py`, `context_runtime_semantics.py`, and for an Original
  `context_models/tennis_live.py` (`context_runtime.py:316-361`).
  `verify_d2_artifacts` in turn always imports `context_models/activation.py`,
  `evaluator.py`, `replay.py`, `training.py`, and `training_cases.py` before its
  data-dependent dispatch (`context_runtime_semantics.py:264-291`). Their eager
  local closure includes `context_models/dataset.py`, `experiments.py`,
  `training_contracts.py`, `distribution_losses.py`, `evaluation.py`,
  `validation.py`, `offset.py`, and `model_loss_statistics.py`.
- **Parts:** `context_storage_v2/snapshot_source.py` -> `inventory.py`,
  `refs.py`, `snapshots.py`, `contracts.py`, `model_artifacts.py`; snapshot bytes
  add `ref_chunks.py`, `context_snapshots.py`, and `context_transport.py`
  (`context_storage_v2/snapshot_source.py:12-27`,
  `context_storage_v2/snapshots.py:17-28`).
- **History/features/new consumer:** `history.py` -> `context_observations.py`,
  `context_models/contracts.py`, `context_runtime_inventory.py`,
  `context_runtime_transaction.py`, `context_sources/tennis.py`,
  `context_sources/tennis_status.py`, `model_artifacts.py`, `contracts.py`, and
  `sqlite_profile.py` (`context_storage_v2/history.py:14-35`). `tennis.py` adds
  `context_models/tennis.py`, `context_models/tennis_v3.py` and lazily
  `refs.py`/`HistoryView` in the live feature route
  (`context_storage_v2/tennis.py:26-49`, `context_storage_v2/tennis.py:643-665`).
  Current `tennis_consumer.py` imports the preceding owners plus
  `context_models/dataset.py`, `offset.py`, `tennis_live.py`,
  `context_snapshots.py`, `context_transport.py`, `tennis/predict.py`,
  `tennis/live_context.py`, `tennis/state_codec.py`, and
  `tennis/tour_state.py` (`context_storage_v2/tennis_consumer.py:25-49`).

### Numerical/network package roots and lazy edges

The fixed source-declared non-stdlib package roots for the current route are
**NumPy, SciPy, pandas, requests**, and **pytest only if the new native driver
imports the existing test helper/test module**. This is already wider than the
old numerical diagnostic:

- current consumer imports `ContextModelError` from `context_models/offset.py`,
  which eagerly imports NumPy and `scipy.optimize`/`scipy.special`
  (`context_models/offset.py:8-13`);
- consumer imports `tennis.predict` and `tennis.tour_state`
  (`context_storage_v2/tennis_consumer.py:40-43`); `predict.py` eagerly imports
  `backtest`, `data_loader`, `model_state`, `simulator`, and `workload`
  (`tennis/predict.py:29-40`);
- `tour_state.py` and `model_state.py` eagerly import pandas, backtest and
  data-loader owners (`tennis/tour_state.py:9-20`,
  `tennis/model_state.py:32-46`), while `data_loader.py` eagerly imports pandas
  and requests (`tennis/data_loader.py:24-39`);
- prediction calls `ModelState.calibrate_match`, whose method-level import of
  `_sigmoid/_logit` is at `tennis/model_state.py:74`, and calls workload code;
  `native_workload_records` has a method-level import of
  `context_sources.tennis` (`tennis/workload.py:17-27`);
- selection always enters `_Inventory.select`, which lazily imports
  `context_models/tennis_effect.py` (`tennis/live_context.py:89-103`); that file
  eagerly imports NumPy (`context_models/tennis_effect.py:14-35`).

The exact transitive Python-package files, extension modules, and ELF/shared
libraries on the native host are **not established by these source edges** and
must be sealed/inventoried there. In particular, copying only the four old
NumPy/SciPy directories cannot establish pandas/requests (or their own runtime
dependencies), Python-extension, loader, or system-library closure. No Windows
package inventory is evidence for that Linux closure.

### Runtime file lookups a top-level import scan misses

- Both the old live owner and current consumer hash/read the six exact
  `CODE_PATHS`: `tennis/predict.py`, `tennis/model_state.py`, `tennis/elo.py`,
  `tennis/serve_model.py`, `tennis/simulator.py`, `tennis/data_loader.py`
  (`context_models/tennis_live.py:19-20`,
  `tennis/live_context.py:250-266`,
  `context_storage_v2/tennis_consumer.py:101-113`). These files must exist under
  the same sealed project-root layout for preparation and publication rechecks.
- The intended small route opens only its controlled context/source DB, separate
  Shadow oracle DB, and the fixed workspace files: `legacy-copy.sqlite`, its
  `-journal`, `receipt-additions.bin`, `snapshot-parts.sqlite` and `-journal`,
  `history.sqlite` and `-journal`, `features.sqlite` and `-journal`, and
  `consumers.sqlite` and `-journal`. Corpus owns the first three fixed names
  (`context_storage_v2/receipt_corpus.py:199-256`); History and Features own
  their fixed names (`context_storage_v2/history.py:599-627`,
  `context_storage_v2/tennis.py:643-697`).
- `tennis/model_state.load_state` can lazily select/read the trusted runtime or
  packaged pickle (`tennis/model_state.py:229-275`), and data-loader functions
  can seed/read/download training CSV/XLSX/leader-source files
  (`tennis/data_loader.py:150-190`, `tennis/data_loader.py:356-456`,
  `tennis/data_loader.py:529-580`, `tennis/data_loader.py:731-755`). Those paths
  are **not invoked** by the required database-backed state fixture
  (`load_tour_state(..., allow_legacy=False)` follows the artifact slot at
  `tennis/tour_state.py:190-205`). A native worker must preserve that routing and
  fail closed if an unplanned training file, pickle fallback, or network call is
  attempted; merely having imported requests/pandas is not evidence of such I/O.

## Existing native machinery: reusable vs missing

### Reusable unchanged

- `context_preparation_process_guard.install_single_process_guard`: identity is
  dropped before product imports, then AS/CPU/FSIZE/NPROC/CORE and seccomp state
  are installed/read back (`context_preparation_process_guard.py:481-515`).
- `context_preparation_supervisor.run_single_process`: fixed script argv, one
  held workspace/cwd, fork/runpy after UID/GID drop, pidfd/wait4 custody, CPU,
  wall, output and RSS measurement remain suitable interfaces
  (`context_preparation_supervisor.py:257-296`,
  `context_preparation_supervisor.py:330-345`).
- `context_preparation_budget.PreparationBudget` remains the durable CPU-charge
  mechanism, and `context_storage_v2.workspace_budget.WorkspaceBudget` remains
  the fixed disk/input accounting owner. Neither is a native quota or B proof.

### Cannot be reused as the chain catalogue/worker

- The sealer explicitly admits only a five-file archive: three helpers plus the
  probe and worker, and caps archive members accordingly
  (`tests/native_preparation_seal.py:1-8`,
  `tests/native_preparation_seal.py:90-116`). It walks only
  `numpy`, `numpy.libs`, `scipy`, `scipy.libs`
  (`tests/native_preparation_seal.py:22-37`,
  `tests/native_preparation_seal.py:119-151`). Its 512 MiB copy and 64 MiB
  output reservations are diagnostic constants, not Task54 slots
  (`tests/native_preparation_seal.py:22-30`).
- The guarded worker has only six fixed diagnostic modes. Its positive mode
  appends only the dependency directory, imports NumPy/SciPy/SQLite, solves a
  2x2 system, and creates one `probe.sqlite3` using `journal_mode=MEMORY`
  (`tests/native_preparation_worker.py:17-18`,
  `tests/native_preparation_worker.py:81-114`,
  `tests/native_preparation_worker.py:204-246`). It imports no Corpus, Source,
  D2, parts, History, feature, consumer, fixture, or WorkspaceBudget owner.
- The probe hard-codes a six-case/60-CPU-second/64-MiB artifact diagnostic
  (`tests/native_preparation_probe.py:35-58`) and truthfully labels itself as no
  Corpus/B authority with only minimal MEMORY-journal SQLite scope
  (`tests/native_preparation_probe.py:542-546`).

Therefore the missing seam is a **new, separately reviewed fixed native chain
catalogue plus a dedicated chain worker/coordinator contract**. It must seal the
actual finalized Task54 driver, all route-live local code, Python/package/native
dependencies and six code-hash files; admit the exact external input and fixed
multi-slot workspace; then call the existing supervisor once per fixed ATP/WTA
case. This is an orchestration/harness seam, not permission to add a fake Source,
mapping, dataclass, descriptor, validator result, or product writer. Final worker
hashes/catalogue bytes cannot be fixed before Task51 and Task54 driver bytes are
final.

## Native measurement checklist for that later worker

- Child `cpu_seconds=300`; hard/read-back AS **2 GiB**; observed and terminal
  RSS strictly **<1 GiB**; combined stdout/stderr retained/observed output
  **<=1 MiB**. The reusable supervisor constants are
  `context_preparation_supervisor.py:40-46`; per-file FSIZE remains an explicit
  caller value and does not replace aggregate workspace accounting.
- Before any write, fixed aggregate new-work **plus all retained retry slots <=8
  GiB**; full simultaneously active inputs **<=4 GiB**; selected History **<=1
  GiB per tour**; encoded reference/processing chunks **<=16 MiB**. Do not add a
  per-value SQL 16/64 MiB cap. When legacy fixture/oracle setup is inside the
  native job, its context/Shadow files, failed attempts and compute time are part
  of these same fixed whole-job reservations and measurements, even though its
  writer topology precedes and is distinct from the profiled C one-writer phase.
- Reserve every main **and** DELETE journal at its own page-aligned ceiling, the
  corpus two-bank ledger, all directories, old-parts, History, Features and
  new-consumer attempts. Sample actual logical and allocated sizes, identities,
  unchanged source hash, slot occupancy, and free space at each quiescent
  boundary. Actual free space must retain **4 GiB plus every unspent reserved
  byte** (`context_storage_v2/workspace_budget.py:221-289`).
- Record one-writer-at-a-time transitions, every live RO owner, terminal exit,
  stop reason, child/parent CPU, boot-clock wall, peak/terminal RSS, output hash,
  full workspace inventory, and all reopen comparisons. Specifically record that
  the new-consumer transaction remained uncommitted through final comparisons
  and `prepared.close()`/History/Source cleanup; inject/observe a real late-close
  failure that rolls it back, emits no accepted result, and retains artifacts.
  Unknown/custody failure remains charged and unpublished.
- Global preparation **1800 CPU seconds / 3600 wall seconds is still not
  established**. The old small probe reserves only 60 CPU seconds and 120 wall
  seconds (`tests/native_preparation_probe.py:48-58`,
  `tests/native_preparation_probe.py:134-153`); starting a fresh per-run
  stopwatch cannot omit earlier preparation/catalogue/admission cost.

Remaining gates: finalize and independently approve Task51; implement/review the
Task54 small integration and the new fixed native catalogue/worker; execute and
retain ATP/WTA native evidence. Full three growth profiles, complete native
runtime closure/reopening, all-cost owner, B, restore and release remain later.
