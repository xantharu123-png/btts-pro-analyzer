# Context capacity recovery implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore full D4 verification and the normal controlled update path for the existing, growing context database without discarding history or weakening semantic checks.

**Architecture:** Keep the existing small-image reader and add an explicitly selected, strictly root-sealed file reader for larger backup inputs. Validate the complete inventory but retain decoded values only while needed; replay tennis originals and snapshots serially. The user approved a one-time, updater-only atomic replacement with backup, independent review and rollback; application deployment remains a separate normal updater invocation.

**Tech Stack:** Python 3.12, SQLite, POSIX DAC, Bash, systemd, existing pytest harnesses; no new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-07-kontextmodell-design.md`, especially D4 and Task 20; exact recovery rationale in `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-20-context-size-recovery-preflight-20260910.md`. The controller also read the independently authored recovery implementation preflight in the original controller worktree. This is a repair of the accepted implementation, not new product design.

## Task10 approved internal checking-dispatch continuation

The latest exact1c65ada30-snapshot input failed CPU300 despite complete local
and scoped code acceptance. Root's measured first-feature profile attributes
nearly all feature-pass cost to unchanged witness/type/SQLite checks. Under
the existing equivalent-checking repair authority, only the two narrowly
specified allocation/dispatch seams are reopened; no acceptance predicate,
model/feature/source output, history or resource cap may change.

Executable brief and RED/validation requirements:
`.superpowers/sdd/2026-09-10-context-capacity-recovery/task-10-brief.md`.
Analysis: `fresh30-capacity-analysis.md` in the same SDD directory.

- [x] Task10.1: deterministic real dispatch/allocation RED plus independent
  exact-type and actual SQLite lifecycle/override/cleanup boundaries.
- [x] Task10.2: same-order recursive loop/fixed leaf tuple and exact-owner
  short-lived local tracked cursor, retaining canonical comparison and every
  fresh proof/cookie boundary; original subclass route preserved.
- [x] Task10.3: focused regression, exact two-product/new-test/report commit,
  independent immutable-delta review; no author push or native/fullsuite.
- [ ] Task10.4: current-first exact native acceptance, meaningful larger
  consumer controls, final tests/review/backup/current-data and separate release
  actions. Prior complete fullsuite7292/30/97 is evidence at1c65ada only.

Task10 corrected code72421d3 and scoped P2 rereview are complete. Actual
30snapshot input passed288.095CPU/288.261wall/485440KiBRSS with full unchanged
report/input. Stronger31-query G1 FAILED at299.975CPU/300.165wall/
485792KiBRSS, child-9 and no report; input unchanged. Stronger32/33 controls
are constructed/sealed but not D4-run. Task10.4 remains open: no final724
fullsuite, main promotion, updater exchange or app deployment. Exact
reports/pins are in SDD`task-10-native-evidence.md`.

The completed bounded G1 diagnostic attributes only1.360743CPU to its one
overflow original. Rolling batches therefore cannot remove a G1 traversal.
Learned non-owning prefixes could reduce repeated covering work, but would
change those later consumers from per-row checks to the existing exact-hit
edge contract. This is a new proof-contract decision, not an unchanged-
frequency Task10 refinement. `task-11-growth-analysis.md` is a read-only
proposal; no Task11 implementation is approved and no same-frequency
material fix is demonstrated. Keep source/limits/models frozen pending a
concrete boundary decision; do not silently lower checks or label G1 passed.

Rolling query batches and replacing the canonical-byte witness are excluded
from Task10. A microbenchmark or an older26snapshot PASS cannot authorize
release. Preserve earlier task/evidence history below.

## Global Constraints

- **User-approved amendment, 11 September 2026:** the latest explicit approval permits narrowly repairing the Tennis and D2 checking routines after Task4's measured growth failure, then committing/pushing and controlled VPS deployment. This supersedes the earlier owner-file freeze only for these equivalent checking changes. It does not permit changed model mathematics, data/history deletion, weaker validations, higher resource caps, rewritten archived evidence or compatibility hash whitelists. Tasks5/6 document the new work; old Task4 constraints/evidence remain historical. The normal exact updater route remains required.
- Cricket stays unchanged. Odds remain price information; no changes to ranking, forecasts or model mathematics.
- Preserve all database rows, predictions, tickets, ledger, settlements, keys, markers, source schemas and archived evidence.
- Do not change owning predictor, feature, dataset, evaluator or training implementation hashes, or whitelist new hashes for old reports.
- Full D4 validation remains mandatory, including unreferenced and inactive data, manifest chains, source lineage, exact snapshot receipt binding and unopened-final protection.
- The original root worktree's stage helper is protected: SHA256 `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`. Do not edit it anywhere in this repair.
- Installed updater expected SHA256: `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`; root:root 0755, one link. Actual initial production source is `2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
- Never import app/venv Python code as root. Root may only stage trusted exact bytes and perform reviewed standard-library transport/permission operations. Full model verification runs as the app user against an app-unwritable private backup copy.
- Updater-only repair has exactly one permanent executable target, `/usr/local/sbin/betboy-update`. It does not update the app or touch configuration, units, databases, helper pins or timer policy.
- Work only in `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`, branch `codex/context-capacity-recovery-20260910`. Base `82ca31d4340ed2dabd2a9812eb6bcadfbd757a5a`. Frozen A0 and P4b3 work is excluded.
- One implementation writer at a time, fresh independent review per task. Use `apply_patch`, exact staging paths and `git -c core.autocrlf=false`; never add-all/reset/clean. Controller owns push and VPS actions.
- Resource values below are candidate admission ceilings, not release claims. Final promotion requires measured Linux full-replay evidence; shrink an excessive profile, never silently raise it to pass a failing measurement.

## Capacity and evidence contract

The actual VPS has 4,005,441,536 bytes RAM and 2 GiB swap. Its context database grew from 100,671,488 to 104,202,240 bytes; do not reuse old row counts for a newer snapshot.

Keep `MAX_CONTEXT_IMAGE_BYTES = 64 * 1024 * 1024` for the old untrusted-path in-memory input. New sealed-file input has an explicit candidate maximum of `1024 * 1024 * 1024` bytes and at most `256 * 1024 * 1024` canonical bytes for one materialized tennis replay history. Existing valid <=64-MiB databases must not be rejected by this new history budget. Use no decoded-object cache initially (zero retained cache bytes): SQLite lookups stream one canonical row at a time. A1 state and one complete history may exist for the current replay; no whole-inventory decoded tuple or retained histories per cutoff.

**Measured Task1 refinement (controller approved, 10 September):** the zero-cache cold path exceeds the real-copy runtime profile because eight original/snapshot consumers repeat selection for two actual causal keys. Permit one verification-local **immutable encoded-history** LRU cache with a candidate64-MiB aggregate canonical-byte budget, including pending entries. This is not a decoded-object cache or a new proof shortcut: misses execute the entire unchanged owning receipt/selection path; hits deserialize fresh dictionaries and a real tuple from exactly its completed output. Bind cache lifetime to the exact receipt inventory, tracked transaction generation and unchanged `total_changes`; invalidate permanently on mutation/end/restart. Publish no partial history. Evict or bypass on cache pressure; a cache size alone must never reject an otherwise valid input. Recheck the separate history admission budget on hits and misses. Store canonical bytes per selected row to avoid a second giant serialization buffer. Numeric/typed feature replay, source hashes, full physical validation and protected-final handling remain unchanged. Record actual cache sizes/misses and cold/hit parity; do not assume both real histories fit. Defer indexed cutoff filtering or a second trusted receipt decoder unless subsequent measured evidence needs a separate refinement.

**Second measured refinement (controller approved after the largest growth failure):** exact4fad098 on the387739648-byte/188791-receipt synthetic generation ended at300.040CPU seconds, childreturncode-9, with no report; peak312792KiB and input unchanged. The cache alone is insufficient for this profile. Permit a validation-owned completed-inventory capability in `VerifiedReceiptMapping`: move the existing complete content/receipt/orphan checks into `validate_all()` without dropping/reordering owning checks, and grant its internal completion stamp only after success. Pin exact mapping/generation/total_changes/main+temp schema; invalidate permanently on mutation or failed/interrupted validation, including started iterators. A new `values_at_or_before(cutoff)` falls back to the unchanged full `.values()` path when never validated. After successful full validation only, scan receipt identity/clock metadata and decode eligible ordinary rows through existing `__getitem__`; later receipts have already been physically validated and were already excluded by the unchanged owning selector. Preserve every protected-final row as opaque regardless of cutoff, avoiding a new assumption about its clock proof. Keep inclusive canonical-clock comparison, both-tour eligible typed validation, all native revisions, exact tuples/refs/math and cache/history budgets. No event/tour/source pruning, new index/schema, caller-supplied trusted flag, generic decoded cache, reduced physical validation or source/model edits. This refinement must pass malformed future/unrelated, interrupted/orphan validation, boundary/timezone, protected-final, ordinary/DDL/transaction and live-iterator RED regressions plus fresh native capacity measurements.

Linux verification child: fixed single-thread numerical-library environment; candidate address-space limit 2 GiB, CPU limit 300 seconds, wall limit 600 seconds, stdout/stderr aggregate bound 1 MiB. Before release measure actual current data, at least three representative growth generations and a valid >64-MiB fixture; peak RSS should remain below 1 GiB and runtime below 300 seconds for the chosen supported profile. A resource failure must be typed and must occur in the before-downtime preflight, preserving the running application. A fresh after-quiesce backup is still checked before payload replacement. If a complete individual replay cannot fit, fail with a resource error; never truncate causal history or silently use a partial model. The preflight is not a permanent unbounded-retention promise.

**Third measured refinement (controller approved after8249 native failure and phase diagnosis):** largest generation still failed at299.949CPU seconds with no report. The exact current-copy observational run completed242.787s: two cold selections64.406/64.290s, two28,432,021-byte entries, no eviction, sixhits; snapshot owning features remain approximately14s each. Actual Mapping order is later12:07, earlier10:00, later12:07, earlier10:00. The263 intervening rows are all football. An earlier-key-only incremental algorithm would not fix this measured order and is not authorized here. Instead allow the existing verification-local immutable cache to derive an earlier result from the nearest successfully completed **covering later cutoff of the same tour**. The unchanged owning selector is row-local/cutoff-monotone, sorted by(observed_at,digest), and its added evidence fields depend on row clocks only. Thus retain every cached selected row with canonical observed_at<=requested cutoff, in order, decoding individually into fresh objects without constructing a second entire later tuple. Require the existing successfully completed inventory proof plus all current lifetime/schema pins; never-validated means full cold fallback, revoked/failed means rejection. Exact hit remains first. Charge the admission budget only to the complete retained earlier history, not the full covering entry. Encode any new key independently under the unchanged aggregate64-MiB LRU limit; parent eviction must not invalidate or truncate a child. Keep empty-tuple owning argument validation and lifetime checks before/during/after reconstruction, including empty results and interruptions. No interval SQL, source/tour pruning of newly read rows, inventory/owner/source/schema/index/model changes, validator memoization or budget increase. Scope:cache helper,Tennis replay orchestration,capacity tests. RED covers actual later-first order/full-cold parity, both-tour malformed inputs, full physical corruption, exact boundaries/timezones, empty results, budgets, missing/different/evicted/forward-only keys, never-validated fallback, failed validation, write/DDL/transaction/closure races, interrupted encoding, cache pressure/consumer isolation and real unopened finals. Implement only after Task2 hands back the sole-writer slot; independent review and fresh exact native profile remain mandatory.

## Task 1: Bounded complete D4 reader and serial tennis replay

**Fourth measured refinement (controller approved, after4db largest-profile failure):** exact4dblargestCLI still reaches300.342CPU seconds withoutreport. Directgeneration3diagnosis proves one cold selection76.698s and successful4.202scovering reuse, but fullphysicalvalidation costs147.192s. A25CPU-second physical-receipt profile attributes24.638scumulative to23667lookups, including21.734sunchangedownerdecoding and2.256strackedSQLexecution. Permit only traversal optimization in`context_runtime_inventory.py`, with no new decoder semantics, input/resource/cache-setting change, owner/source/hash/schema/index change or predicate before fullphysicalproof. Factor its existing raw-row handling into one shared path used bylookup and streams: ordinary rows call unchanged`context_observations._decode_receipt`; protected rows keep only their opaque outer representation. Preserve malformed/null identity rejection. In`validate_all()`, stream the existing unfiltered LEFTJOIN`_SELECT` once instead of one indexedJOIN perreceipt. Preserve allcontentchecks first, allreceiptchecks, orphancheck afterward, per-rowtransactionchecks, finalstampcomparison and permanentfailure. No decodedretention or fetchall. After successful completedproof only,`values_at_or_before()` streams the same LEFTJOIN withparameterized`WHERE r.observed_at<=?`; canonicalordinaryclocks were alreadyvalidated. Keep an identity-only set of remainingprotectedrefs: discardthose encountered, thenfetchremaining individually regardlessclock; skipgenuinelymissingprotectedrefs as the old wholeinventory did, withlifetimechecks aroundabsence so postproofdeletion cannotbehidden. This avoidsvariable-limit INlists, tempobjects and newindices. Keepnevervalidatedfullvaluesfallback, alleligibleboth-tourtypedvalidation, protectedno-bodyguard, inclusivecanonicalclocks and fail-closedchecks before/during/afterdecoding/yieldresumption/exhaustion, includingemptyresults. RoworderwithinSQLtraversal wasunspecified; preservephaseorder and everyrejection, not a fabricatedfirst-errorordering guarantee. REDcovers oneJOIN/fullownerdecodecounts/phaseorder, futuregrowthwithoutPythonrow/stampgrowthafterproof, exactcutoff/timezone/resultparity, future/unrelated/opposite-tourcorruption, protectedbefore/after/unknownclocks/absentrefs, missingcontent/invalididentity/indices/orphans, write/DDL/transaction/closure/interruption/last-rowfailures, cachelifetime, actualprotectedfinal and authorizedrollbackparity. Existingcache/Tennisorchestration remainunchanged. The expected benefit is bounded dispatch/traversal saving, not removalofmandatorydecoder cost; independentreview and freshexactnativecurrent/growth acceptance remainrequired. ImplementonlyafterTask2's nextcoherentsole-writerhandoff.

**Files:**
- Create: `context_runtime_input.py` (strict sealed-file reader only).
- Create: `context_runtime_inventory.py` (transaction-bound decoded-on-demand mappings).
- Modify: `context_runtime.py` (global validation orchestration and explicit input selection).
- Modify: `context_runtime_tennis.py` (serial replay descriptors instead of retained history tuples).
- Modify: `scripts/verify_context_runtime.py` (explicit sealed-file CLI selection).
- Modify only if needed for the exact lazy Mapping contract: `context_runtime_semantics.py`.
- Test: `tests/test_context_runtime_backup.py`; create `tests/test_context_runtime_capacity.py`.

**Interfaces:**
- Preserve `verify_context_database(path)` and its report schema and the `_verify_connection` return dictionary used by authorized rollback writers.
- Add explicit keyword-only `input_mode="memory"` to `verify_context_database`; the only other allowed value is `"sealed_file"`. Never choose file mode automatically on size, MemoryError or another trust failure. Update `scripts/verify_context_runtime.py` with `--sealed-file` without changing default behavior.
- `context_runtime_input.open_sealed_connection(path, *, max_bytes)` is a context manager yielding one SQLite connection already configured query-only, trusted_schema=OFF and held in a read transaction. No caller-supplied trusted boolean. Root-owned regular file, link count one, 0440 or stricter, app-unwritable root-owned ancestors up to filesystem root, DELETE header, no companions, no symbolic links. Bind pre/post FD/path identity and streamed SHA256. Fail closed on platforms that cannot prove this sealed-file contract; the memory reader remains cross-platform.
- `VerifiedArtifactMapping` and `VerifiedReceiptMapping` implement read-only `collections.abc.Mapping`, bound to the caller's held SQLite transaction. Use the existing owning decoders; membership/iteration must not body-decode protected finals. No cached mutable values. Access after connection closure fails, never returns previously retained values.
- `verify_live_originals` returns small replay descriptors rather than `(base, history)`; `verify_live_snapshot` reconstructs and releases a complete causal history for that descriptor. Original and snapshot mathematical replay and bound receipt lists stay exact.

- [ ] **Step 1: Add RED tests for complete lazy iteration, direct mode selection and no accumulated histories.**

```python
def test_large_input_does_not_implicitly_switch_to_file_mode(tmp_path):
    # Build a valid input with existing fixture helpers; lower only the memory
    # threshold for this unit test, then keep real >64-MiB proof separate.
    with pytest.raises(RuntimeArtifactTrustError):
        verify_context_database(path)

def test_lazy_membership_does_not_decode_unopened_final(monkeypatch):
    # Use the existing protected-final fixture and spy on its owning decoder.
    # Membership and the complete D4 run must preserve the current zero-call
    # invariant; corruption in an unrelated ordinary receipt must still fail.
    assert protected_id in receipts
    assert final_decoder.call_count == 0
```

Add concrete tests using existing seeded/receipt fixtures for orphan content, corrupted unreferenced receipt, cache mutation, invalid-after-close, multiple original cutoffs, complete historical native revisions, exact snapshot receipt references and history budget. Existing cap/header/WAL/path-race tests remain passing in memory mode. Linux tests must prove DAC, read-only writes, hardlinks, ancestor replacement and sidecar rejection; mark only genuinely unavailable Linux DAC checks as skipped on Windows.

- [ ] **Step 2: Run focused RED tests with the quality venv and record the exact expected failures.**

```powershell
& C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -B -m pytest tests/test_context_runtime_capacity.py -q -p no:cacheprovider --basetemp=.pytest_tmp/capacity-red
```

- [ ] **Step 3: Implement explicit sealed transport and transaction-bound lazy validation.**

```python
if input_mode == "memory":
    reader = _open_database(path)
elif input_mode == "sealed_file":
    reader = open_sealed_connection(path, max_bytes=1024 * 1024 * 1024)
else:
    raise RuntimeArtifactTrustError("unsupported context input mode")
```

The sealed reader validates every component with no-follow stat/open checks and holds FD identity and full SHA across SQLite's separate read-only path open. Root ownership of the private path is essential: chmod on an app-owned file does not seal it. It starts its own read transaction, so the orchestrator must not issue a nested BEGIN. Validate all physical contents and receipts before returning success, using an equivalent SQL antijoin for orphan detection. Keep opaque finals hash/outer-only. Do not alter schema, report versions, D2 hash rules, predictor code or rollback writer permissions. The `tennis_status` and `tennis_v3` tuple contracts remain unchanged: construct one exact full tuple at a time, not a fake lazy tuple or player-only history.

- [ ] **Step 4: Run focused capacity, runtime, semantic, rollback and tennis regression tests once, then self-review.**

```powershell
& C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -B -m pytest tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py -q -p no:cacheprovider --basetemp=.pytest_tmp/capacity-green
```

Discover exact adjacent test filenames with `rg --files tests` and include only those covering the named unchanged contracts. The controller performs one final whole-suite run after integration.

- [ ] **Step 5: Commit exact Task 1 files and write RED/GREEN evidence; obtain independent spec/quality review.**

```powershell
git -c core.autocrlf=false add -- context_runtime.py context_runtime_tennis.py context_runtime_input.py context_runtime_inventory.py scripts/verify_context_runtime.py tests/test_context_runtime_backup.py tests/test_context_runtime_capacity.py
git -c core.autocrlf=false commit -m "fix: bound context verification memory without dropping history"
```

## Task 2: Streaming updater stage and before-downtime capacity validation

**Files:** Modify `deploy/update_server.sh`; test `tests/test_context_update_hook.py`.

**Interfaces:** Task 1's CLI `scripts/verify_context_runtime.py --sealed-file` and unchanged JSON report. Root extractor streams the chosen ZIP member to a root-owned private stage, verifies uncompressed length, ZIP CRC, SHA, SQLite DELETE header, then seals before app-user verification. No full `read()` of the member. Candidate sealed input limit is the same 1-GiB contract; existing trusted helper pins stay unchanged.

**Binding integration clarification after source preflight:** Read `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-2-integration-preflight.md` completely. Preserve Git/rollback `STAGE_DIR` under `/var/tmp`, but create a separate exact private context tree under `/var/lib/betboy-context-update.XXXXXXXX` with independent `online` and `quiesced` hooks/seals. Check real mount-specific combined disk requirements. Cleanup, if used, is restricted to the exact newly created, identity-checked private path; preserve failed-recovery evidence.

Use distinct `PREFLIGHT_BACKUP` and `FRESH_BACKUP` variables and work/archive paths; the online archive is not the later recovery checkpoint. Factor only the existing standard-library archive-production logic to accept the explicit phase/path/source head. Normal scheduled archives without MANIFEST are not accepted as updater archives. Before/after online capture preserve the exact DB path inventory and safe file/principal identities, but allow ordinary same-file SQLite content/size/time changes. The online finish binds the sealed snapshot, not a false assertion that the live DB stopped changing. The quiesced finish retains its existing strict live-signature/no-writer proof. No unconditional reuse of the existing strict finish in online mode.

No key or marker is created/changed in online preflight. Preserve explicit in-progress resume and the existing distinction between comparison predecessor and actual backup HEAD. For the genuinely old **keyless AND proven contextless legacy** case only (the same independently validated `not_present_legacy` condition, no present context database), retain the original post-quiesce first-migration backup route: there is no context payload to capacity-replay online. This is not a missing-data fallback for a context-aware predecessor or a present database; missing authentication in those cases fails before downtime. Tests must cover both sides of that boundary. Never fabricate a key, marker, context absence or completed migration.

Keep `scripts/backup_runtime_databases.py` byte-identical. Its embedded-manifest verifier still materializes one member; bound every complete-backup verifier child, including the inline verifier, and measure its actual peak instead of claiming the entire pipeline is constant-memory. An updater-owned standard-library launcher sets the fixed AS/CPU limits then `execve`s only the fixed verified helper or the fixed target D4 command at the appropriate uid; no free command/argument/env override. Root never imports the app/venv. The existing twelve allowed limitation strings and exact report/exit-code validation remain unchanged; resource errors never become allowed limitations.

- [ ] **Step 1: Add failing extraction/preflight tests.**

```python
def test_context_stage_streams_large_member_without_unbounded_read():
    # Instrument the existing hook harness ZIP stream: reject read(-1).
    # A valid >64-MiB sealed member must reach the target verifier.
    assert hook_report["status"] == "verified"

def test_capacity_failure_precedes_service_stop():
    # Existing command recorder must contain no stop/restart/payload write
    # when the new complete preflight returns resource exhaustion.
    assert not any(command_stops_services(c) for c in recorded_commands)
```

- [ ] **Step 2: Run the named RED tests and implement streaming and resource-bounded app-user child execution.**

```python
while chunk := member.read(1024 * 1024):
    total += len(chunk)
    if total > max_image:
        raise RuntimeError("context backup exceeds sealed input budget")
    digest.update(chunk)
    destination.write(chunk)
```

Use held/root-validated file descriptors and fsync, not the shorthand destination handling above. Verify full fresh online backup and target D4 before stopping services, then repeat against the post-quiesce fresh backup before payload replacement. A before-downtime backup is extra evidence, not a substitute for the existing recovery checkpoint. Fixed numerical thread environment, address-space/CPU/wall/output bounds and typed errors; no arbitrary shell environment override. Keep old-complete-state failure recovery rules and no mutation before capacity acceptance.

- [ ] **Step 3: Run hook regressions, negative failure-order tests and installer syntax check.**

```powershell
& C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -B -m pytest tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/capacity-hook
& 'C:\Program Files\Git\bin\bash.exe' -n deploy/update_server.sh
```

- [ ] **Step 4: Commit exact two files and obtain independent review, including normal rollback call sites.**

## Task 3: Exact updater-only repair installer and release proof

**Files:** Create `deploy/repair_context_updater.sh` and `tests/test_context_updater_repair.py`; update `deploy/README.md` with the one-time recovery contract and execution evidence only after it exists.

**Interfaces:** Installer arguments are exactly `EXPECTED_TARGET_COMMIT EXPECTED_NEW_UPDATER_SHA256`; both are fixed in the controller's reviewed release evidence before execution. Remote is hardcoded trusted HTTPS repository, never an argument. The existing old-updater SHA is fixed in the installer. Installer uses `/run/betboy-deploy/deploy.lock` and only installs `/usr/local/sbin/betboy-update`.

- [ ] **Step 1: Add failing filesystem transaction tests for exact old/new/third SHA, lock contention, download failure, bad blob, failed backup/restore/replay, fsync/replace interruption and repeated recovery.**

```python
def test_unexpected_existing_updater_is_preserved():
    before = updater.read_bytes()
    result = run_repair_fixture(old_sha="unexpected")
    assert result.returncode != 0
    assert updater.read_bytes() == before

def test_failure_after_own_replace_restores_exact_old_bytes():
    before = updater.read_bytes()
    result = run_repair_fixture(failpoint="after_replace")
    assert result.returncode != 0
    assert updater.read_bytes() == before
    assert updater.stat().st_nlink == 1
```

- [ ] **Step 2: Implement narrow repair transaction.**

```python
# Reviewed root-only byte operations; no import from the staged application.
os.fsync(new_fd)
os.replace(private_new_path, installed_updater_path)
os.fsync(parent_fd)
# Revalidate exact new digest and root:root0755/nlink1. On our own failed
# replacement restore the independently copied/fsynced old bytes atomically.
```

Before replacement require fresh full backup with all then-current DBs, key and complete marker, an actual isolated restore, full new-target D4 replay of context data and measured resource acceptance. Pin exact old file/metadata, production SHA/complete marker and exact fetched new Git blob. Validate trusted root-owned stage/parent/source and fixed Git/TLS configuration. Keep a durable root-private journal and old copy; only exact old/new states are resumable, unknown external replacement is not overwritten. No sourcing the installed updater; reuse narrowly audited algorithm by implementation, not execute its main. No automatic app deployment inside the repair.

- [ ] **Step 3: Run local filesystem/syntax regressions and independent full patch review before any VPS mutation.**

```powershell
& C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -B -m pytest tests/test_context_updater_repair.py -q -p no:cacheprovider --basetemp=.pytest_tmp/updater-repair
& 'C:\Program Files\Git\bin\bash.exe' -n deploy/repair_context_updater.sh
```

- [ ] **Step 4: Controller runs exact-LF full suite and Linux role/race/resource/restore tests against fresh real backup and multiple growth fixtures.**

Record commit, archive SHA, context SHA/size/row counts, four artifact and two snapshot replay counts (or fresh actual counts), RSS, CPU/wall time, readonly evidence and supported profile. No synthetic fixture represents real injury-model validation. If evidence is insufficient, keep production untouched and record the concrete failure.

- [ ] **Step 5: Commit/push reviewed exact release; execute only user-approved updater replacement; verify installed SHA. Separately execute the ordinary new updater for the exact release and verify application SHA, services, timers and both health endpoints.**

```text
trusted updater-only repair -> exact installed SHA check
ordinary /usr/local/sbin/betboy-update <exact reviewed 40-hex release>
server HEAD + complete marker + app/Caddy/timers + internal/public health
```

- [ ] **Step 6: Save durable handoff distinguishing repair completion from the still-open five-sport context/model work; commit/push evidence. Never claim all twenty tasks done because this release succeeds.**

## Task 4: Shared validated Tennis history basis (approved continuation)

**Approval:** The user explicitly answered `ja` to replacing duplicated per-cutoff histories with a jointly fully verified Tennis history basis and separate historical time views, without reducing data, checks or resource limits. This reopens only the Task 1 history representation after the fresh b397 capacity failure; Tasks 2/3 and the owning models are not implementation scope.

**Requirements and evidence:** Read `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-1-fresh-profile-diagnosis-20260910.md`. Actual sealed input has 48307 receipts, 10 originals/snapshots at 5 cutoffs; old growth fixtures held consumers fixed at 4. Three complete cold histories took 62–68 CPU seconds each and each occupied 28432021 encoded bytes; the fourth cold rebuild began after eviction. The exact b397 CLI failed at CPU300, before snapshot feature replay. A successful optimization must remove that duplication, not just rearrange the existing LRU keys.

**Files:** Modify `context_runtime_history_cache.py`, `context_runtime_tennis.py`; add focused tests in `tests/test_context_runtime_capacity.py` and/or `tests/test_context_runtime_tennis_live.py`. A small purpose-specific new test module is permitted. No owning selector/predictor/feature/training/evaluator/source/schema changes. Do not change `context_runtime_inventory.py` or its validated-inventory contract for this task. Controller alone owns deployment scripts, native transport, push and VPS actions.

**Binding design:**

- After complete physical inventory validation, discover needed maximum cutoffs by tour from owning-validated original publications. All originals, including unreferenced safe originals, still receive the unchanged original model and native-input check; every snapshot still receives its exact full owning `tennis_features_v3` and mathematical replay. A planning pass may move failure precedence, but cannot admit a formerly invalid input. Preserve replay order of individual consumers.
- Build one completed, owning-selector-validated immutable canonical encoded basis at the required maximum cutoff per tour. Earlier requests materialize exact inclusive prefixes; do not store each prefix as another full encoded entry. Original and snapshot descriptors retain only bounded metadata/references to the verification-local cache, never a decoded history or a reference keeping evicted bytes alive outside accounting.
- Bind basis lifetime to the exact `VerifiedReceiptMapping`, completed proof, tracked transaction generation, unchanged `total_changes`, main/temp schema and open connection. A never-validated inventory uses the entire existing cold path. Revoked/failed proof, closed connection, writes, DDL and transaction end/restart must still fail closed, including empty results and started iterators.
- Aggregate canonical-byte budget remains 64 MiB INCLUDING pending entries and every retained encoded basis. Multiple tours share this one budget. No decoded-object cache, persistent cache, model-result memoization or validated flag supplied by callers. Oversized basis/eviction must fall back to a complete cold history, not reject smaller valid prefixes, truncate history or silently raise limits. The default small memory-reader contract remains compatible.
- Every consumer receives fresh nested dict/list objects in a real complete tuple, exact owning order `(observed_at, digest)` and evidence fields. Recheck the unchanged per-history canonical admission budget (256 MiB in sealed mode) against the complete requested prefix. Preserve owning typed API checks, all eligible opposite-tour receipt validation, unopened D2 finals and full future/unreferenced physical validation. Maximum-cutoff preparation must not swallow malformed metadata or selector errors as cache misses.
- Keep report/exit schema, limitation strings, mathematical results and source hashes identical. Do not introduce empirical approval or imply this release completes the five-sport context-model work. Cricket, quote independence, historical receipts, snapshots, tickets, ledger, keys, markers, installer/updater bytes and protected stage helper `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` remain unchanged.
- Linux acceptance is exact uninstrumented CLI at UID997 on a root-sealed copy, AS2GiB/CPU300/wall600/output1MiB, measured CPU/wall <300s and RSS <1GiB. Existing admission limits are not performance promises. No cap increases, no deletion/retention workaround, no skipping event-specific feature calls.

- [x] **Step 1: RED regression.** Reproduce five interleaved cutoff groups (the real order is 12:07,16:37,19:07,14:07,10:00,12:07,14:07,19:07,10:00,16:37) under two-full-history-equivalent cache pressure using real selectors/fixtures. Assert canonical full-cold parity, a single completed basis per fitting tour rather than repeated cold construction, fresh consumer isolation, and no duplicate retained prefix bytes. Name the broken behavior and record the expected failing output before product edits.
- [x] **Step 2: Implement the shared basis and validated planning.** Keep complete consumer-specific validation and all invalidation/size/fallback semantics above. No unrelated cleanup. Record any failure-order change explicitly.
- [x] **Step 3: Boundary tests.** Include duplicate/equal-time/timezone/future cutoffs; two tours and global pressure; no hidden references after eviction; oversize bypass with valid smaller prefix; never/failed/interrupted inventory validation; mutation/DDL/transaction restart/closure during materialization and after last/empty row; malformed future/unrelated/opposite-tour rows; actual unopened-final fixture; orphan original; exact reports and all ten original/snapshot owning calls. Use controlled real dependencies with spies only at observational boundaries, not replacement validation.
- [x] **Step 4: Focused regression and self-review.** Quality Python is `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`; run capacity, live Tennis, runtime backup/transport/semantics, authorized rollback and affected context contracts. Full repository suite is controller-owned once on final immutable source. Preserve existing outputs; use a unique `.pytest_tmp` path.
- [x] **Step 5: Commit exact Task 4 files and write RED/GREEN report.** Report at `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-4-report.md`, including commands, counts, TDD failures, limitations and review concerns. No push or VPS access by implementer, no subagents. One implementation/index writer only; use `apply_patch` and exact staging with `git -c core.autocrlf=false`.
- [ ] **Step 6: Independent task review, fresh native actual-input/growth acceptance and final suite.** Controller verifies code diff/source pins, executes independent review and the exact CLI. Growth testing must increase replay consumers/cutoffs as well as receipt volume. A failed real profile holds release even when tests pass. Existing updater-only repair then separate ordinary exact app deployment remain later gated steps, not effects of this task.

**Task4 outcome, 11 September 2026:** Scoped code reviewed and final full suite6926passed/30skipped/97subtests. Current actual input passes285.388wall seconds, but G1receipt-plus-consumer growth failsCPU300 with no report; G2/G3 unmeasured. Native unit output also identifies a pre-existing D2SQL binding compatibility finding. Step6/release remains HOLD; no source-owner edit, cap increase, data pruning, updater exchange or deployment is authorized by these test results. See`task-4-native-evidence.md` and`task-4-review.md` in the SDD directory.

## Task 5: D2 SQLite parameter compatibility without opening labels

**Approval and scope:** The user explicitly approved the Tennis/D2 checking repair and subsequent commit/push/deploy. The native Task4 warning-as-error reproduction in `task-4-native-evidence.md` identifies `context_models/dataset.py::_physical_receipt_preflight`: repeated numbered/named `?1` parameters are currently passed a tuple. Repair this exact query, not D2 semantics or evaluator identities.

**Files:** Modify `context_models/dataset.py`; add a focused regression in `tests/test_context_dataset.py` (or one small purpose-specific test module if the existing fixture is unsuitable). Report in `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-5-report.md`. No other production file, source-hash allowlist, schema or deploy change.

**Interfaces and invariants:** `_physical_receipt_preflight(connection)` still returns `None` on a valid closed opaque outer header and rejects malformed bytes, hashes, clocks, identities and incomplete tables. Preserve the exact six outer projections, all outer keys, BLOB bytes and bound value. Never Python-decode a protected outcome body or project a label. The evaluator's normal `implementation_hashes()` naturally changes for the changed dataset source; do not relabel old reports or make their source hashes pass. The real production inventory currently has only original/state artifacts, not an old evaluated D2 report; final native D4 must confirm compatibility of the actual immutable input.

- [ ] **Step 1: RED.** Add a real preflight regression with warnings promoted to errors on a SQLite runtime that exhibits the bug. On a runtime which no longer emits the warning, add a narrow parameter-boundary check that calls the real SQLite connection and enforces named-parameter mapping use; this tests our emitted binding contract, not SQL source text. Keep an actual valid opaque receipt and assert the successful preflight plus no body decoder calls; retain separate invalid-byte/index tests. Record the exact baseline failure. The old final native QA tree also supplies a previously reproduced real warning-as-error failure.
- [ ] **Step 2: Minimal fix.** Replace the six repeated `?1` references with `:opaque` and bind `{"opaque": opaque}`. Keep the separate existing anonymous `?`/tuple query unchanged. No broad SQL rewrite, suppression or fallback.
- [ ] **Step 3: GREEN and boundaries.** Run `tests/test_context_dataset.py`, `tests/test_context_runtime_semantics.py`, `tests/test_context_runtime_capacity.py` and D2 evaluator tests discovered with `rg --files tests`. Use quality Python `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest ... -q -p no:cacheprovider -W error::DeprecationWarning` with a fresh `.pytest_tmp/task5-*` base. Confirm unopened-final rejection behavior and old/mismatched report hashes remain fail-closed. The controller owns native Linux and the full final suite; do not repeat the full repository suite here.
- [ ] **Step 4: Exact commit and report.** Read your own diff, write RED/GREEN commands/results, changed files and concerns to the report, stage only assigned files with `git -c core.autocrlf=false`, commit. No push, VPS or subagents. One implementation/index writer; do not stage controller-owned plan/ledger/handoff changes.
- [ ] **Step 5: Independent scoped review.** Controller supplies the immutable task diff, checks spec and quality findings, and repeats the native warning-as-error reproduction on the new exact source before release.

## Task 6: Equivalent Tennis receipt checks against the sealed shared basis

**Approval:** The 11 September user amendment explicitly allows this checking-only repair and later tested publication/deployment. Read `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-6-design-analysis.md` completely: the recommended option C is the binding implementation design, with the concrete constraints below. It is not authorization for different model outputs or reduced evidence.

**Measured reason:** The exact old fc7 G1 diagnostic on 95406 receipts/11 snapshots built one 56865423-byte ATP basis, no eviction/bypass. Full physical validation cost41.045CPU seconds; cold selection91.672; all11 original replays114.188 inclusive selection. Each completed old-cutoff snapshot's unchanged feature call cost9.140–10.133CPU seconds. The diagnostic deliberately stopped during feature10 at275CPU (overall276.824CPU/275.898wall,472448KiBRSS); it is not an acceptance pass. The new checking proof must remove repeated row-local semantic derivation, not event-specific mathematics.

**Files:** Modify only `context_runtime_history_cache.py`, `context_runtime_tennis.py`, `context_sources/tennis_status.py`; add `tests/test_context_runtime_receipt_witness.py` and modify existing capacity/shared/status tests only where they exercise this new contract. Report `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-6-report.md`. Keep `context_models/tennis_v3.py` and `context_models/tennis.py` byte-identical, along with predictor/state CODE_PATHS, inventory/transaction/input modules, dataset/evaluator/training code, schemas, deploy scripts and helper pins.

**Interfaces:** Public `validate_selected_tennis_receipt(row)` and `tennis_features_v3(event, observations, base, *, cutoff)` signatures stay unchanged. Factor the exact existing selected-row validator body into `_validate_selected_tennis_receipt_cold(row)` and retain it as unconditional fallback. Add private `EncodedHistoryCache._selected_receipt_scope(receipts, *, cutoff, tour)` context manager and a private exact-type `_SelectedReceiptScope` witness. Only the existing full feature call in `verify_live_snapshot` enters the scope; no changed tuple, skipped feature call or alternative feature implementation.

**Binding implementation details:**

- The existing physical inventory completion stamp is not selected-Tennis validation. `_store` must cold-own-validate every retained canonical row before atomically publishing its seal/entry serial. Check the original row's exact plain JSON type tree before encoding, so invalid tuple/subclass inputs cannot be laundered through JSON. For a nonplain row, cold-validate the original: preserve its rejection; if the old owner accepts that edge case, preserve acceptance but do not seal that entry for accelerated use. For plain rows, cold-validate the single decoded encoded representation. No caller supplies a validated flag, proof serial, arbitrary trusted callback or manufactured seal.
- A private ContextVar may communicate only the exact active witness implementation. Unrelated objects/callbacks in it confer no authority and must not have arbitrary methods invoked. Scope creation, per-row matching and exit check the exact inventory/proof/transaction/main+temp schema and connection lifetime. Active revocation is a hard failure. Reset the ContextVar token and deactivate the witness in `finally`; nested fresh scopes restore their predecessor, copied inactive contexts cannot retain acceleration, and an old witness is never reactivated.
- Witness retains only cache/inventory references, key, entry serial, ordinal and bounded active metadata. No encoded-entry alias, decoded row/history, hash index or generator retaining bytes. Retrieve at most one encoded row temporarily for comparison; recheck entry presence/serial and lifetime afterward. Eviction/replacement removes the seal with bytes; a stale witness falls back to full cold validation, never silently authorizes an old or new entry. Replacing the same key must keep byte accounting exact.
- Each hit requires exact built-in JSON types recursively (dict with exact str keys, list, str/int/float/bool/None), then full current-row canonical bytes equal to the owner-sealed row at the cursor ordinal. Digest/Python equality is insufficient. Every field participates. Ineligible types, encoding failure, valid changed/reordered/duplicate rows, absent entry or no completed proof use unchanged cold validation. Do not turn optimization misses into new input rejection; invalid ordinary rows must still fail. Scope ordering mismatch may reduce hits but cannot grant trust. Cold sealing bypasses the scoped wrapper unconditionally.
- Aggregate retained plus pending canonical cache bytes remain64MiB, including both tours; metadata stays bounded by the existing32-entry bound. No second cache or retained prefix bytes. Complete per-consumer history admission stays256MiB in sealed mode; memory reader compatibility stays unchanged. Cache pressure/oversize uses complete cold paths, no cap increase/truncation. A failed/interrupted/final-row-mutated seal publishes no partial proof and clears pending accounting.
- Preserve full future/unreferenced physical checks, eligible opposite-tour typed checks, unopened D2 final protection, native revisions, source refs, all original/native/predictor and per-snapshot feature/transport replays. The original six CODE_PATHS and legacy model/evaluation math files remain byte-identical; no historical hash allowlist or empirical approval. Source checker's changed bytes are recorded honestly.

- [ ] **Step 1: RED repeated-work and provenance tests.** In the existing real `five_groups`/`encoded_history_fixture` setup, count unchanged owner validation during repeated full snapshot feature calls: one fitting basis seal may run once, subsequent equal current rows must use equivalent checking rather than repeat the cold validator. Before product edits, observe the expected failure. Add direct `_store` poisoning with source-invalid and type-alias data, plus a final-row interrupt, before implementing the seal.
- [ ] **Step 2: Implement owner seal, bounded scope and narrow integration.** Preserve the existing cold body verbatim apart from its function name. Use the context-manager pattern around the existing call, not a trusted-argument API:

```python
with descriptor.history_cache._selected_receipt_scope(descriptor.receipts,
        cutoff=decision, tour=original['reference_weights']['event']['tour']):
    features = tennis_features_v3(payload['event'], history, original, cutoff=decision)
```

Use an ordinary null context when no cache exists. Keep following feature equality and transport replay unchanged.

- [ ] **Step 3: RED/GREEN boundaries.** Implement the detailed design report's concrete cases: strict nested type aliases/subclasses and dictionary keys, bool/number/nonfinite values, changed body with old hashes and rehashed source-invalid body; valid changed/reordered/duplicate rows cold-fallback; every row including future/unrelated/opposite-tour; complete feature/report parity for paired/legacy/mixed/unavailable/conflicting/revised/target statuses and cutoffs; real unopened finals; caller mutation/fresh tuples; invalid/never/interrupted proof, DDL/write/transaction restart/closure, mutation during/after last comparison, empty/nested/exception/copied scopes; both tours/eviction/reinsert/no byte retention/zero and oversized cache. Assert real accepted/rejected behavior and exact complete output, not source text or mocks. Observe each newly needed behavioral test fail before its change.
- [ ] **Step 4: Focused regression and self-review.** Quality Python runs new witness, `test_context_runtime_capacity.py`, `test_context_runtime_shared_history.py`, `test_context_runtime_tennis_live.py`, `test_context_runtime_semantics.py`, `test_tennis_status_v3.py`, `test_tennis_context_features.py`, `test_tennis_v3_model_transport.py`, and affected live-worker/integrity contracts using `-B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning` and a unique `.pytest_tmp/task6-*` base. Controller alone runs the final full repository suite and native profiles after code review.
- [ ] **Step 5: Exact commit and report.** Write commands, named RED failures, GREEN counts, scope/lifetime/memory reasoning, changed source hashes, unchanged model hashes and concerns to task-6-report.md. Stage only assigned files (`git -c core.autocrlf=false`, force-add only the exact assigned ignored report if needed), commit and return index ownership. No subagents, push or VPS actions.
- [ ] **Step 6: Independent review and release proofs.** Controller obtains task-scoped spec/quality review, then exact uninstrumented current/G1/G2/G3 native CLI acceptance with receipt AND consumer growth, fresh whole-suite and whole-branch review. Keep UID997, AS2GiB/CPU300/wall600/output1MiB, measuredCPU/wall<300 andRSS<1GiB. Fresh full backup/actual restore/HMAC and unchanged-data/source evidence remain required. Only then commit/push the exact release to main, execute the approved updater-only installer and separately ordinary exact app deployment, verify VPS source/services/timers/health, and record remaining model/evidence work honestly.

## Initial evidence

- Fresh LF repair worktree clean at base `82ca31d4340ed2dabd2a9812eb6bcadfbd757a5a`.
- Focused baseline: **332 passed, 3 skipped in 45.69s**, exit 0. JUnit `.pytest_tmp/capacity-baseline-01.xml`. These are pre-repair tests, not new large-input proof.
- User's current `ja` explicitly approves the updater-only transition; no second approval is needed for the same scoped action. Resource/review failures remain real release blockers.

## Task 7: Remove duplicate derivation and stamp queries within equivalent Tennis checks

**Approval and measured reason:** The user's approved Tennis checking repair covers this internal refinement; no further authorization or changed result is inferred. Exact899 failed native CPU300 on the new253333504-byte current input with99521receipts/26snapshots. Its bounded trace shows physical42.950CPU, one cold92.532CPU, one independent seal27.422CPU; all originals end223.805wall. The58390805-byte basis fits64MiB, with no eviction/bypass. Ten completed snapshot feature calls take2.280–2.718CPU each. Repeated queries and normalization are observed duplicate work, but no unmeasured speed estimate is acceptance.

**Files and frozen scope:** Modify only `context_sources/tennis_status.py` and `context_runtime_history_cache.py`; add a small focused check-equivalence test module and extend the existing witness tests where necessary. Report `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-7-report.md`. Do not edit inventory/transaction/input modules, context_runtime_tennis.py, mathematical v3/v2/predictor/CODE_PATHS, dataset/evaluator/training, schema, deploy/updater/installer/helper code, existing data or source hash policies. Controller owns all native work, complete repository suite, integration and publication. No subagents or pushes by the implementer.

**Binding source-owner refinement:**

- Keep actual `normalize_observation(content, observed_at=...)` validation intact inside every cold selected-owner call. Keep the same public APIs, exact closed schema/type/clock/source/prospective/effective/publication/native revision/receipt digest checks and accepted/rejected set. Workload receipts retain their existing owning path.
- Factor native status payload/reception validation from expected-envelope construction, using private helpers which derive their own result and accept no trusted flag. Factor the existing pre-normalization fields of `_record` into `_record_fields`; ordinary `_record` still calls `normalize_observation`, and public standalone `validate_tennis_status_record` still uses that fully normalized expected record.
- Within the selected cold owner only, after actual normalization and canonical content equality succeed, reuse that call's canonical content bytes for its content digest. Run the same native status payload/reception checks and compare an expected envelope built from this call's normalized payload, checked native identifiers and canonical clock to those same content bytes. Its fields must provably equal the existing `_record` result for all accepted inputs, including exact type edges. Do not merely delete expected-envelope validation or assume arbitrary payloads are canonical.
- This is single-call common-subexpression elimination, not a new trusted decoder/validation cache. Do not retain normalized rows or bytes across calls, use identity/digest-only proof, add a model-result cache, or skip the independent full `_store` cold-own-validation. Do not change the canonical-byte witness matcher, plain JSON eligibility, ContextVar ownership, entry serials or budgets.

**Binding completed-stamp refinement:**

- `_check_selected_proof` currently invokes cache `_check` and inventory `_check_validation`, each reading the same main/temp schema. Consolidate duplicate queries only on an already completed exact inventory proof. The existing `receipts._check_validation()` remains the authoritative fresh stamp check, including generation, total_changes and both schemas; compare that proof with the cache's original generation/changes/schema and exact mapping identity. Recheck its tracked transaction after those comparisons.
- Preserve all entry/per-row before/per-row after/exit checks, including empty/final rows, interrupted/failed proofs, closed connection, temp/main DDL, writes, transaction end/restart, wrong mapping, old/stale/evicted scopes and asynchronous mutation around the remaining schema queries. A failed inventory proof remains permanently revoked; cache failure clears bytes, pending entries and seals. Missing/never-completed proof must retain the old full path and cold behavior. No stale stored tuple alone can grant authority.
- Do not remove a lifetime boundary, change inventory/transaction implementations or lower validation strength to save queries. If an ordering edge makes fusion inequivalent, retain the original check on that edge and document it.

**Global invariants:** Complete original/native/predictor and full per-snapshot feature/transport replay, unchanged output schema/limitations/math, all future/unreferenced/opposite-tour checks, protected unopened D2 finals. Aggregate retained plus pending64MiB, metadata32entries, sealed per-history256MiB, input1GiB, nativeUID997/AS2GiB/CPU300/wall600/output1MiB, measuredCPU/wall<300 andRSS<1GiB. No deletion/retention workaround, quote or Cricket change, marker/key rewrite or artificial empirical approval. New source hashes are recorded honestly; no historical allowlist.

- [ ] **Step 1: RED on observable duplicate work.** Using real source fixtures/dependencies and spies that delegate, show that one valid selected status currently normalizes the same closed payload twice and serializes identical content repeatedly. Show that a completed witness boundary queries each schema twice. Assert the proposed one-derivation/one-fresh-stamp contract with exact unchanged output; observe failures before product edits. Do not use elapsed-time thresholds or source-string tests.
- [ ] **Step 2: Implement the two bounded refinements.** Read existing code, preserve error classes and every acceptance/rejection boundary above. No unrelated cleanup. Keep fallback cold semantics for every non-matching witness and all workload cases.
- [ ] **Step 3: Equivalence/lifetime regression.** Compare with immutable899 behavior through real fixtures: all native status variants, paired/missing/conflicting/revised status, workload rows, invalid fields and recomputed hashes, tuple/dict/str/int/float/bool subclasses and aliases, nonfinite/signed zero, missing/extra keys and nested fields, wrong source/schema/tour/format/clock, invalid prospective/publication flags. Assert standalone and selected behavior, not only valid golden outputs. Add mutation during each remaining proof-query boundary and after the final/empty row; retain real DDL/write/restart/closure/revocation/wrong-mapping/eviction tests. No mock may replace owning validation.
- [ ] **Step 4: Focused GREEN and self-review.** Use quality Python `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning` with unique `.pytest_tmp/task7-*`; run new tests plus receipt-witness/capacity/shared/live-Tennis/status-v3/feature/transport and affected integrity tests. The controller owns the one final full repository suite and native executions; do not repeat either here.
- [ ] **Step 5: Exact commit/report.** Report named RED/GREEN evidence, query/derivation count changes, unchanged models, acceptance-equivalence reasoning, commands and concerns. Stage only assigned files and exact ignored report using `git -c core.autocrlf=false`; commit, return an empty index, and report under15lines. Do not stage controller ledger/plan or inherited artifacts.
- [ ] **Step 6: Independent and native acceptance.** Controller requests task-scoped spec/quality review, then measures the exact uninstrumented CLI on actual-current and G1/G2/G3 before any release. A further CPU failure remains a failure, irrespective of local tests or microbenchmarks. Final whole-branch review/full suite/backup/restore/HMAC/updater-only transition/ordinary exact deployment remain separate mandatory gates.

## Task 8: Owner-complete original-native projections without redundant whole-history materialization

**Binding design:** Read `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-8-design-analysis.md` completely, including the corrected owned-complete fallback sections. It is the precise implementation contract. This is an equivalent internal Tennis checking refinement under the user's existing approval, not a new numerical model or relaxed check. Controller explicitly supersedes the old Task4 complete-tuple representation for original checks only: public original outputs/predicates and every snapshot's complete fresh tuple remain unchanged. The broader approved model spec requires complete evidence and exact calculations, not materialization of unrelated rows for an original's internal latest-native predicate.

**Measured reason:** Exact17cfbbc actual253333504-byte/99521-receipt/26-snapshot input still fails300.063CPU/300.141wall, no report. Its bounded diagnostic shows44.991CPU physical validation,85.677cold,23.607independent seal; all26 originals166.146CPU inclusive. Original history materializations alone cost41.658CPU. Twelve snapshots then complete beforeCPU275 diagnostic stop. Optimizing this materialization is a hypothesis until exact native current/growth passes; no bounds change is allowed.

**Files:** Modify only `context_runtime_history_cache.py` and the original-planning/original-replay portions of `context_runtime_tennis.py`. A small new `context_runtime_original_projection.py` helper is permitted only to keep bounded scalar proof planning/folding/accounting cohesive; no SQL/decoder, app-model import at module load, retained payload, or separate byte/history cache there. Add `tests/test_context_runtime_original_projection.py`; extend existing shared/capacity/witness/live tests only for the new actual contract. Report `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-8-report.md`. Keep `_cold_replay_history`, `verify_live_snapshot`, source validators, inventory/transaction/input modules, v3/v2/math/predictor/CODE_PATHS, dataset/evaluator/training, schemas, deployment scripts/helper pins and data byte-identical. Controller owns full-suite/native/push/deploy; no subagents by implementer.

**Essential implementation boundaries:**

- A cache-private planning owner scans and validates all actual original publications, including orphans and records beyond optional query capacity, and discovers both maximum tour cutoffs. Retain bounded deduplicated `(event_key, cutoff, tour)` queries only. No caller-supplied trusted flag, completion token, selected history or builder callback confers aggregate authority.
- A cache-owned preparation method imports and calls the fixed unchanged full `_cold_replay_history` itself, then executes the existing independent whole-entry owner seal. Only that completed operation may bind a completeness marker and derived query drafts to the exact completed entry serial/current inventory proof. Ordinary/direct `_store` can preserve its existing row-seal behavior, but can mint neither aggregate absence/latest proof nor original full-fallback completeness. Interrupts, replacements and partial work never publish authority.
- During the existing independent seal pass, use its already decoded and cold-owner-validated encoded representation. For each planned query derive whole-prefix canonical byte total, latest matching target clock, multiplicity0/1/2plus and at most one ordinal. Include every target row (status, workload, equal-time competitor); no status filter, new scan/decoder, receipt deduplication or early rejection. The existing native predicate determines rejection in original replay order.
- Plans, provisional drafts, completeness markers and active summaries are cache-owned and charged within the same64MiB retained+pending limit. Aggregate metadata has32slots including entries and queries; reserve2possible tour entries, hence at most30queries. Preserve the existing32entry cap when no queries exist. Long keys/counters/serials must not hide uncharged retained bytes. Prefer dropping optional queries to sacrificing an otherwise fitting basis. Zero capacity, metadata exhaustion and oversized history cause safe full fallback, never data truncation/new rejection. No decoded row or encoded-entry alias survives outside current work/accounting.
- Original lookup validates current lifetime/proof and exact key/serial, enforces the WHOLE prefix admission budget before native absence/ambiguity rejection, and decodes only one fresh candidate for multiplicity1. Absence/ambiguity are completed facts, not misses. Share one unchanged native-predicate implementation between projection and full-history path; preserve subsequent native-event equality, every predictor call and captured-result equality, and preceding publication/base/code/state checks.
- On aggregate miss, full-cache fallback may consume ONLY the particular entry whose current serial has owned-completeness authority. Do not precheck one covering entry and then let a generic lookup reselect an unowned exact-key subset. Pure eviction/replacement discards the attempted materialization and safely cold-falls back; inventory mutation/revocation is a hard error. With no owned entry use `_replay_history(..., cache=None)`. Query-cap-zero owned preparation can still supply a full fresh tuple. Direct-store replacement removes old completeness and aggregates even for byte-identical rows.
- Keep every existing selected-row/physical/opposite-tour/future/unreferenced/unopened-final check, source hash policy, native/predictor/model calculation, report schema and limitation string. Preserve all entry/per-row/final/empty lifecycle checks; no assertion of stronger atomic async-DDL guarantees than existing sequential stamps. Do not route a projection into source/feature functions; `verify_live_snapshot` stays unchanged.
- Resource contracts remain input1GiB, sealed history256MiB, cache64MiB incl all new metadata,32aggregate metadata slots, nativeUID997/AS2GiB/CPU300/wall600/output1MiB, measuredCPU/wall<300/RSS<1GiB. Quote/Cricket/A0/P4b3, all histories/tickets/ledger/keys/markers/protected helpers remain untouched.

- [ ] **Step 1: RED.** Use real existing persisted source/native original fixtures, owning builder and validators. Show repeated originals materialize complete histories despite a fitting fully owned basis; assert proposed original-only bounded candidate decoding while full snapshot tuple/call counts remain exact. Before product edits record expected failure. Add valid-subset/newer-target/equal-time completeness forgery and metadata-budget regressions early; no mocks replacing source validation, elapsed-time or source-string assertions.
- [ ] **Step 2: Implement owned planning/preparation/projection/accounting and original integration.** Follow the complete design above; fixed imports only, complete own builder+independent seal, no authority flag. Keep fallback's actual selected entry bound through reconstruction. Preserve source/model/math/CLI behavior. Stop with concrete concerns if any provenance or admission boundary cannot be met, not an optimistic shortcut.
- [ ] **Step 3: Full behavioral boundaries.** Cover direct _store older/empty/subset poisoning after real inventory validation; same-key direct replacement; unowned exact shadowing of owned covering; zero query capacity owned fallback; caller keys and source-invalid rows. Cover absent/unique/equal-time status+workload/latest nonstatus/revised/cancelled/native identity errors; exact cutoff/timezones/empty/budget edge/large unrelated history/oversized and both-tour pressure. Cover orphan/excess/duplicate queries, all original and full snapshot calls, invalid future/opposite-tour/unopened finals. Cover interruption/mutation/DDL/revocation/restart/closure at cold/seal/publish/lookup/last/empty phases; eviction/replacement must not transfer markers. Prove32slots and64MiB charges including long keys, serial widths, pending work and dropped queries; no hidden aliases/partial proof. Compare canonical report/native error/output behavior with immutable17cfbbc and with optimization disabled/evicted/capacity-bypassed; runtime Git oracle may be development-only, committed tests need meaningful fixture expectations.
- [ ] **Step 4: Focused GREEN/self-review.** Quality Python `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning`; unique `.pytest_tmp/task8-*`. Run new projection, shared/capacity/witness/live-Tennis/status/feature/transport/semantics and affected live integrity tests once before committing. Controller owns final entire repository and all native jobs; do not repeat them here. Report any platform skips honestly.
- [ ] **Step 5: Exact commit/report and return index.** Full report with RED/GREEN commands/results, completeness/admission/lifetime/accounting proof, baseline parity, changed/unchanged hashes and remaining concerns. Stage only assigned product/tests and exact ignored report using `git -c core.autocrlf=false`; commit and return index empty. Root ledger/plan/handoff/native files and inherited outputs are not yours. No push/VPS/subagents; short final status under15lines.
- [ ] **Step 6: Independent review and exact acceptance.** Controller obtains scoped spec/quality review, exact uninstrumented current/G1/G2/G3 native profiles, complete final suite and whole-branch review. Any current-input resource failure still holds release. Fresh complete88DB backup/actual restore/HMAC and exact updater-only transition followed by separate normal exact app deployment remain mandatory; no main/updater/app mutation before those gates.

## Task 9: Fixed physical/Tennis co-traversal with same-invocation B1 checking reuse

**Controller scope amendment,11September2026:** The user already explicitly authorized equivalent Tennis/D2 checking repairs and tested commit/push/deploy. Task8's measured exact current-input failure and the two bounded profiles establish redundant physical/source work. This task narrowly reopens the internal D4 observation/original orchestration, inventory and cache/source-check owners listed below. It does not extend model, input, output, historical data, deployment or resource acceptance. Root has read the complete design and records this as an internal implementation refinement under existing authority, not a new empirical model contract.

**Binding design:** Read `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-9-design-analysis.md` completely. Implement its coordinated traversal PLUS same-invocation B1 reuse, not traversal-only, duplicate-JSON-only or removed-seal substitutes. Physical validation is not source validation. The fixed owner must perform every original generic and source-specific predicate exactly once in the combined frame, then the complete independent source seal remains separate. No accepted runtime prediction is claimed before measurement.

**Measured reason:** Exact07d975f actual253333504B/99521receipt/26snapshot CLI fails300.046CPU/300.135wall. Diagnostic physical45.653CPU, cold87.302, seal26.135; all26projections hit with no full fallback. Late large-history snapshots cost9.148CPU each. The20CPU cold profile attributes10.250cumulative to repeated physical traversal and9.000 to selected cold validation, with generic normalization twice per row. Nested/profiled values are not promised full-input savings.

**Allowed files:** `context_runtime_inventory.py`, observation/original orchestration in `context_runtime.py`, `context_runtime_tennis.py`, `context_runtime_history_cache.py`, and a narrow shared source-tail factoring in `context_sources/tennis_status.py`. A small fixed-owner helper is permitted only if cohesive, with NO separate retained pool. Create `tests/test_context_runtime_coordinated_tennis.py`; extend existing projection/witness/shared/capacity/source/semantics tests only for actual changed contracts. Report `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-9-report.md`. Root owns plan/ledger/handoff/native/review files.

**Frozen:** `context_observations.py` including its real `_decode_receipt`; generic contracts/canonical JSON; `context_runtime_transaction.py`, input module, v3/v2 math/feature/predictor/CODE_PATHS, workload owner, dataset/evaluator/training, schemas, deployment scripts and protected helpers. Do not implement the generic raw-payload-two-serialization micro-optimization. Source hashes change honestly; no old-hash whitelist or report relabel. Cricket, prices/ranking, source data/receipts/snapshots/tickets/ledger/keys/markers, A0/P4b3 remain untouched.

**Fixed owning boundaries:**

- Keep existing public ordinary physical validation/lookup, source selector/selected-cold/standalone validator and normal fallback behavior unchanged. New private inventory entry point owns exact same-connection/generation artifact planning through fixed imports and actual persisted creation timestamps. Arbitrary cutoff/created-at dicts, Mapping subclasses, sinks/callbacks, supplied rows, completion flags or direct cache stores confer no authority.
- One shared complete physical implementation retains all content checks, every unfiltered LEFTJOIN receipt decode, orphan checks and final inventory proof. In the new fixed branch only, unchanged `_decode_receipt(raw)` immediately precedes full source-tail validation in the SAME non-yielding owning frame. No decoded object is exposed between those checks. Do not duplicate the generic decoder or source predicates: share source-tail implementation with the full selected cold owner; arbitrary public rows still run its full generic prefix.
- The residual source checks remain complete: source/sport/schema; full status payload, competition-reception and expected canonical envelope; or kind/format plus unchanged full workload owner. The fresh raw canonical content bytes are already bound by the same physical decoder call. Selected evidence fields are the same owner-generated literals. Canonical equality, not Python numeric/dict equality, preserves signed-zero and type distinctions.
- Plan ALL actual original publications, including orphans/excessqueries, and both tour maxima. Source-check every known Tennis row eligible under the union of maxima BEFORE tour retention. Retain in actual tour basis only within its own maximum. No event/player/latest pruning. All future/unrelated/opposite-tour/unknown-schema physical checks and opaque unopened finals remain exact.
- Explicit controller amendment allows `ORDER BY r.observed_at,r.digest` on the new complete unfiltered receipt traversal to produce exactly the owning basis order. It does not change content-before-receipt-before-orphan phase order; unspecified first malformed receipt order is not a public contract. No persistent schema/index/temp object or new unbounded Python sorting/key pool. Measure actual sort overhead under unchanged limits.
- Source/planning domain errors may cancel optional preparation, freeing all pending/provisional metadata, while physical validation completes. After physical success the EXISTING full cold/planning route must execute and reproduce rejection. Never retain exception/traceback/args as hidden owning state. Physical decode failures are outside the domain-deferral catch. Interrupts, MemoryError/resource faults, SQLite/transaction/schema/revocation/closure and unexpected exceptions propagate fail-closed, not optional misses. No partial other-tour cache survives source failure.
- All pending encoded rows live in the SAME charged64MiB pool. After complete physical/source traversal, independently decode EACH pending encoded row and call the FULL unchanged cold selected validator; fold queries and release work. No full decoded basis or second retained encoding for this seal. All existing per-row/before/after/final/empty/serial/lifetime checks survive.
- Only the fixed completed owning operation may perform the one-time preproof-to-complete transition. It must bind exact original mapping/generation/totalchanges/main+temp schema and fully completed inventory proof plus entryserial. Never relax global cache checks to accept `proof=None`, and never grant completeness from ordinary `validate_all()` or direct`_store`. Already physically validated inventory has no saved source evidence and takes existing postphysical cold route.
- Preserve current cache byte and metadata accounting inclallpending/plans/queries/markers, two tours,32aggregate slots/30optionalqueries. Overflow/eviction/pressure/no originals/cancellation use complete old cold fallback, not rejection or truncated evidence. End owning helper frames/references BEFORE uncharging; no uncharged row/key/iterator/traceback aliases. Reentrant operations cancel optional work, cannot steal pending bytes or adopt replacedserials. Same-key replacement removes authority even for identical bytes.
- Every original still checks actual state/native/capture and runs its actual predictor. Every snapshot receives full fresh tuple, all refs and unchanged feature/transport calls. Whole-prefix256MiB consumer admission precedes original native absence/ambiguity. D4 schema/exit/report/limitations/empiricalfalse are unchanged.
- Fixed budgets: input1GiB, history256MiB, retained+pendingcache64MiB,32slots; nativeUID997/AS2GiB/CPU300/wall600/output1MiB, measuredCPU/wall<300,RSS<1GiB. No new library/dependency, cache of model results or cross-run retained state.

- [ ] **Step1: RED observable duplicate work and provenance.** Real persisted fixtures and real full owning calls; assert one full physical decode per ordinary row in the new route and exact eligible both-tour source/independentseal counts, unchanged full snapshot tuples/predictor/features/transport. Record expected failure before source edits. Prove public/caller-created caches cannot mint completeness, invalid B1/source/opaque controls remain real.
- [ ] **Step2: Implement the fixed shared traversal and same-frame source reuse.** Follow complete design and boundaries above. If the owner transition or source residual equivalence cannot be proved, stop with a concrete concern; do not introduce trust callbacks/flags or weakenvalidation. One implementation writer only.
- [ ] **Step3: Behavioral equivalence/lifetime/accounting matrix.** Complete design's nine test groups: all future/unrelated/opposite-tour/opaque inputs, unequal tour cutoffs/equal clocks, real source-invalid + laterphysicalcorruption, planning/orphan/excess failures, cancellation with actual coldrejection, public arbitrary aliases/signedzero/nonfinite, directvalidsubsetpoisoning, wrong/alreadyvalidatedproof, every boundary mutation/DDL/commit/rollback/restart/closure/final/empty, actual weak/refcount lifetime and pending bytes/longkeys/twotours/reentrancy/markerfit. Compare canonical outcomes and exact callcounts to immutable07d975f using development-only oracle; committed tests use independent expectations, no runtimeGit.
- [ ] **Step4: Focused GREEN/self-review.** QualityPython `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning` with unique `.pytest_tmp/task9-*`. Include new coordinated module, all projection/witness/shared/capacity/live-Tennis/status/equivalence/feature/transport/semantics and affected generic inventory/backup/rollback/D2 unopened-final boundaries. Root alone runs entire final repository suite and native jobs; do not repeat them here.
- [ ] **Step5: Exact commit/report/index handoff.** Report RED/GREENcommands/counts, predicate matrix, complete owner/provenance/error/fallback/lifetime/accounting argument, unchanged hashes, developmentoracle and remaining limitations. Stage only assigned product/tests and force-add exactreport via`git -c core.autocrlf=false`, no add-all/reset/clean. Commit locally and return emptyindex. No push/SSH/VPS/subagents.
- [ ] **Step6: Independent/full/native/release acceptance.** Root scoped review then exact current first, newG1-G3 AND retained historical largest, full repository suite, final wholebranch review, fresh fullbackup/actualrestore/HMAC. Only allpass permits alreadyapproved mainpush, updater-only exchange and separate ordinaryexactappdeployment. Sourcecurrentfailure still holdsrelease regardlesslocaltests; allfive-sport empiricalwork remains separate.
