# Context capacity recovery implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore full D4 verification and the normal controlled update path for the existing, growing context database without discarding history or weakening semantic checks.

**Architecture:** Keep the existing small-image reader and add an explicitly selected, strictly root-sealed file reader for larger backup inputs. Validate the complete inventory but retain decoded values only while needed; replay tennis originals and snapshots serially. The user approved a one-time, updater-only atomic replacement with backup, independent review and rollback; application deployment remains a separate normal updater invocation.

**Tech Stack:** Python 3.12, SQLite, POSIX DAC, Bash, systemd, existing pytest harnesses; no new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-07-kontextmodell-design.md`, especially D4 and Task 20; exact recovery rationale in `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-20-context-size-recovery-preflight-20260910.md`. The controller also read the independently authored recovery implementation preflight in the original controller worktree. This is a repair of the accepted implementation, not new product design.

## Global Constraints

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

Linux verification child: fixed single-thread numerical-library environment; candidate address-space limit 2 GiB, CPU limit 300 seconds, wall limit 600 seconds, stdout/stderr aggregate bound 1 MiB. Before release measure actual current data, at least three representative growth generations and a valid >64-MiB fixture; peak RSS should remain below 1 GiB and runtime below 300 seconds for the chosen supported profile. A resource failure must be typed and must occur in the before-downtime preflight, preserving the running application. A fresh after-quiesce backup is still checked before payload replacement. If a complete individual replay cannot fit, fail with a resource error; never truncate causal history or silently use a partial model. The preflight is not a permanent unbounded-retention promise.

## Task 1: Bounded complete D4 reader and serial tennis replay

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

## Initial evidence

- Fresh LF repair worktree clean at base `82ca31d4340ed2dabd2a9812eb6bcadfbd757a5a`.
- Focused baseline: **332 passed, 3 skipped in 45.69s**, exit 0. JUnit `.pytest_tmp/capacity-baseline-01.xml`. These are pre-repair tests, not new large-input proof.
- User's current `ja` explicitly approves the updater-only transition; no second approval is needed for the same scoped action. Resource/review failures remain real release blockers.
