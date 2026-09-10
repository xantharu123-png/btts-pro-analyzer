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
