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

