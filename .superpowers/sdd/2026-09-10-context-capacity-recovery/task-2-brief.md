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

