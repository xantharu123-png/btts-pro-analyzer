# Task 7: equivalent Tennis owner and completed-stamp refinement

## Scope and status

Base: `65cd304930a422d0bd43dd0549ca0131a28b24f7`, branch `codex/context-capacity-recovery-20260910`.
Immutable differential oracle: `89923867a00904253f75a4a6ace5c793e8e988b8`.
Changed product files only: `context_sources/tennis_status.py`, `context_runtime_history_cache.py`.
Tests: new `tests/test_tennis_check_equivalence.py`, extended `tests/test_context_runtime_receipt_witness.py`.
No native execution, full repository suite, VPS, publication, push, API/schema/math/data/policy/budget edits performed by this implementer.
Native actual-current capacity remains FAIL pending controller's exact candidate measurement; a local test or G3-only pass is not acceptance.

## RED / GREEN evidence

All commands ran in `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910` with the quality Python.
The first two tests were written and executed before product edits. Spies delegate to real normalization/encoding; SQL counts use a real SQLite trace callback. No source-text or timing assertion substitutes for behavior.

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_tennis_check_equivalence.py --basetemp=.pytest_tmp/task7-red-counts
```

RED: exit 1, **2 failed in 2.24s**. Same accepted row returned byte-unchanged, but `(normalizations, identical-content encodings)` was `(2, 5)` rather than `(1, 3)`; each schema queried 2 rather than 1 times at a completed witness boundary.

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_tennis_check_equivalence.py tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task7-green-initial
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_tennis_check_equivalence.py --basetemp=.pytest_tmp/task7-matrix-1
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_tennis_check_equivalence.py tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task7-green-expanded
```

GREEN: respectively **95 passed in 20.71s**, **78 passed in 2.07s**, **202 passed in 27.16s**, all exit 0. Final derivation counts are **1 normalization / 3 identical-content encodings**, and **1 fresh main + 1 fresh temp query** per completed boundary (two boundaries still surround each candidate row). Standalone expected-envelope normalization remains separately asserted. Independent cold owning seal and cold fallback counts remain tested; two older public-validator spies were retargeted to the actual cold owner, not weakened to a mock result.

Final witness refinement: the query-mutation test now consumes `rows[0]`, an actual sealed byte-equal hit, rather than a differing ordinal. Re-ran the complete new-module/witness pair after this test-only strengthening:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_tennis_check_equivalence.py tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task7-green-final-witness
```

Result: **202 passed in 27.60s**, exit 0. No product source changed during either focused run.

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_tennis_check_equivalence.py tests/test_context_runtime_receipt_witness.py tests/test_context_runtime_capacity.py tests/test_context_runtime_shared_history.py tests/test_context_runtime_tennis_live.py tests/test_tennis_status_v3.py tests/test_context_tennis_capture.py tests/test_tennis_native_status_codes.py tests/test_tennis_context_features.py tests/test_tennis_v3_model_transport.py tests/test_context_runtime_transport.py tests/test_context_transport.py tests/test_context_transport_bytes.py tests/test_tennis_live_integrity.py tests/test_context_runtime_semantics.py tests/test_context_runtime_backup.py --basetemp=.pytest_tmp/task7-green-focused
```

Focused result: **887 passed, 12 skipped in 511.56s (8:31)**, exit 0. This is the named 16-module focused suite, not the full repository suite. The separate final-witness run above verifies the subsequent test-only sealed-hit strengthening.

Explicit skip audit:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -rs -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_capacity.py::test_linux_real_dac_and_sqlite_readonly tests/test_context_runtime_capacity.py::test_linux_sealed_reader_rejects_unsealed_inputs tests/test_context_runtime_backup.py::test_real_symlink_path_is_rejected_when_platform_allows_it tests/test_context_runtime_backup.py::test_world_writable_database_rejected_without_modification --basetemp=.pytest_tmp/task7-platform-skips
```

Result: **12 skipped in 1.08s**, exit 0: nine require real Linux DAC fixtures; two lack Windows symlink creation privilege (`WinError 1314`); one is POSIX owner/mode enforcement. These are not claimed as passed native checks.

## Acceptance-equivalence reasoning

1. Every selected cold call still applies actual `normalize_observation(content, observed_at=...)` and canonical equality to the entire actual closed content. Only after this equality does SHA-256 reuse those exact content bytes. Receipt digest, prospective/effective/publication metadata, source/sport/schema and workload owner branches retain their checks and errors.
2. `_validate_tennis_status_payload` is the unchanged native payload/reception validator factored out of the public validator. It accepts no trusted flag and still checks the raw supplied fields, exact types, tour/event/player identifiers, canonical schedule, statuses/flags, issues, paired digests and reception revision.
3. `_record_fields` contains the original pre-normalization construction. Ordinary `_record` and public standalone `validate_tennis_status_record` still normalize it. The selected path constructs its expected envelope from this call's normalized payload and independently checked event identifier/clock, then compares full canonical bytes, never digest-only identity. These fields equal `_record`: event/subject are exact validated native strings; tournament/tour produce valid fixed-code competition text; format/kind/source/schema are closed strings; revisions are computed hex digests; publication/expiry are null; valid_from is canonical; complete is the literal boolean false; and the payload already passed the same complete JSON/type/finite normalization. No accepted field can undergo a further normalization change. Public standalone validation retains its original handling of metadata it does not own.
4. Completed-proof fusion calls the authoritative fresh `receipts._check_validation()` before trusting its stamp, compares the exact mapping and stamp against the cache's original generation/changes/main/temp tuple, rechecks live total_changes after the queries, then rechecks the tracked transaction. Missing/never-completed stamps retain the old full cache check/cold behavior. Failures clear entries, seals, bytes and pending bytes immediately. Inventory-owner failures permanently revoke that owner through its unchanged implementation.
5. Witness canonical-byte equality, plain-JSON eligibility, ContextVar ownership, serial checks, all entry/per-row-before/per-row-after/exit boundaries, byte/metadata budgets, `_store` independent full cold-own-validation and covering-history checks are untouched. No normalized rows/bytes are retained across calls; no model-result cache exists.

## Differential oracle and regression coverage

Development-only Git oracle; committed tests do not depend on Git/history or embed a copied validator. The following command compared **20 native producer cases, 89 candidate rows, 169 owner outcomes**, all exact canonical output/error-class equal:

```powershell
$task7Oracle = @'
import copy, subprocess, sys, types
sys.path.insert(0, 'tests')
import test_tennis_check_equivalence as cases
import context_sources.tennis_status as current
from model_artifacts import canonical_bytes
baseline = subprocess.check_output(['git','rev-parse','8992386'], text=True).strip()
legacy = types.ModuleType('task7_immutable_status')
source = subprocess.check_output(['git','show',baseline+':context_sources/tennis_status.py'], text=True)
exec(compile(source, baseline+':context_sources/tennis_status.py', 'exec'), legacy.__dict__)
def outcome(fn, row):
    try:
        result = fn(copy.deepcopy(row))
        return ('accepted', canonical_bytes(result))
    except Exception as exc:
        return ('rejected', type(exc).__module__, type(exc).__name__)
rows = list(cases.invalid_rows())
for i, (changes, kwargs, want) in enumerate(cases.NATIVE_CASES):
    native = cases.competition(**changes)
    old = legacy.normalize_tennis_status(kwargs.get('tour','ATP'), kwargs.get('tournament','189-2026'), native, grouping_slug=kwargs.get('slug','mens-singles'), observed_at=cases.records.__kwdefaults__['clock'])
    new = cases.records(native, **kwargs)
    assert canonical_bytes(old) == canonical_bytes(new), i
    for j, content in enumerate(new): rows.append((f'native-{i}-{j}', cases.selected(content)))
for field, value in [('evidence_class','archive'),('effective_at','2026-09-09T10:00:00.000000Z'),('publication_resolution',{}),('digest','0'*64),('content_digest','0'*64),('evidence_class',cases.StrAlias('prospective')),('observed_at','2026-09-09T11:00Z'),('observed_at','2026-09-09T12:00:00.000000Z'),('observed_at','bad-clock'),('observed_at',cases.StrAlias('2026-09-09T11:00:00.000000Z')),('observed_at',True)]:
    row = cases.selected(cases.records()[0]); row[field] = value; rows.append((field+repr(value),row))
checks = 0
for label,row in rows:
    names = ['_validate_selected_tennis_receipt_cold']
    if row['source_schema'] == current.STATUS_SCHEMA: names.append('validate_tennis_status_record')
    for name in names:
        old, new = outcome(getattr(legacy,name),row), outcome(getattr(current,name),row)
        assert old == new, (label,name,old,new)
        checks += 1
print('IMMUTABLE', baseline, 'native producer cases', len(cases.NATIVE_CASES), 'rows', len(rows), 'owner comparisons', checks, 'all exact outcome/error-class/canonical-output equal')
'@
$task7Oracle | & 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -
```

Native matrix includes scheduled/in-progress/final/cancelled variants, malformed status, retired/walkover/combined, missing/duplicate participants, missing schedule/tournament/grouping and opposite tour. Malformed matrix includes tuple/dict/list/string/integer/float subclasses, boolean-vs-integer flags (Python bool cannot be subclassed), nonfinite values and signed zero, missing/extra/aliased keys and nested objects, mismatched native identifiers/source/schema/sport/format/clock, invalid publication/prospective fields, revisions and paired digests. Finite altered content gets newly computed B1 content/receipt hashes. Existing witness matrix additionally preserves rejection/cold fallback around aliases, workloads, future/unrelated/opposite-tour rows, eviction/replacement and stale/foreign contexts.

Additional development command: **13 existing full status-feature scenarios / 104 feature comparisons byte-equal**, including paired, legacy, mixed, unavailable, conflicting, player/schedule revisions and target statuses. Current witness/cold behavior is compared with immutable899 cold validation, while mathematical feature code remains unchanged:

```powershell
$task7FeatureOracle = @'
import subprocess, sys, types, tempfile
from pathlib import Path
import pytest
sys.path.insert(0, 'tests')
import test_context_runtime_receipt_witness as witness
import context_models.tennis_v3 as model
from model_artifacts import canonical_bytes
baseline = '89923867a00904253f75a4a6ace5c793e8e988b8'
legacy = types.ModuleType('task7_immutable_status')
exec(compile(subprocess.check_output(['git','show',baseline+':context_sources/tennis_status.py'], text=True), baseline, 'exec'), legacy.__dict__)
real_features, comparisons = witness.tennis_features_v3, []
def compared(*args, **kwargs):
    current = real_features(*args, **kwargs)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(model, 'validate_selected_tennis_receipt', legacy._validate_selected_tennis_receipt_cold)
        original = real_features(*args, **kwargs)
    assert canonical_bytes(original) == canonical_bytes(current)
    comparisons.append(1)
    return current
witness.tennis_features_v3 = compared
cases = witness.test_complete_status_feature_parity.pytestmark[0].args[1]
with tempfile.TemporaryDirectory(prefix='task7-oracle-', dir='.pytest_tmp') as folder:
    for case, mode in cases:
        target = Path(folder)/case; target.mkdir()
        with pytest.MonkeyPatch.context() as patch:
            witness.test_complete_status_feature_parity(target, patch, case, mode)
print('IMMUTABLE FEATURE', baseline, 'cases',len(cases),'full feature comparisons',len(comparisons),'canonical equality all passed')
'@
$task7FeatureOracle | & 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -
```

## Lifetime ordering and concerns

Fresh remaining main/temp query tests mutate writes, main/temp DDL, transaction restart and closure in both before-row and after-row boundaries; existing tests mutate entry, comparison, final exit and empty exit. A separate one-boundary test requires late writes/restarts to be caught by post-query live changes/transaction checks. Failed owner proof cleanup is immediate and permanent owner revocation persists even after DDL reversal. Existing tests retain interrupted/failed proofs, wrong mappings, stale/evicted/replaced scopes, pressure, full original and feature/transport replay, and unopened protected receipts.

Failure-message precedence may now be the authoritative owner's error/permanent revocation rather than the former cache-first generic error; rejection remains an exception, never a cache miss. This also clears unusable cache state immediately when owner validation raises (the original owner call sat outside cache cleanup).

Sequential schema reads do **not** claim atomic exclusion of mutations after the final relevant read. A demonstrably pre-existing edge was measured against both implementations: create a main table immediately after the final temp-schema execute (after the last main-schema read); that individual check cannot distinguish it, and the next boundary rejects it. No boundary was removed to hide this, and no transaction/schema implementation was altered. Exact development command and result:

```powershell
$task7EdgeOracle = @'
import subprocess, sys, types, tempfile
from pathlib import Path
import pytest
sys.path.insert(0, 'tests')
import test_context_runtime_receipt_witness as witness
import context_runtime_history_cache as current
from runtime_paths import RuntimeArtifactTrustError
baseline = '89923867a00904253f75a4a6ace5c793e8e988b8'
legacy = types.ModuleType('task7_immutable_cache')
exec(compile(subprocess.check_output(['git','show',baseline+':context_runtime_history_cache.py'], text=True), baseline, 'exec'), legacy.__dict__)
with tempfile.TemporaryDirectory(prefix='task7-edge-', dir='.pytest_tmp') as folder:
    for label, cache_type, final_query in [('899',legacy.EncodedHistoryCache,2),('candidate',current.EncodedHistoryCache,1)]:
        target=Path(folder)/label; target.mkdir()
        with pytest.MonkeyPatch.context() as patch:
            fixture = witness.encoded_history_fixture.__wrapped__(target,patch)
            data = next(fixture)
            try:
                conn, receipts, cutoff, rows, _ = witness.prepared(data)
                cache = cache_type(receipts); cache._store(receipts,rows,cutoff=cutoff,tour='ATP')
                execute, seen = conn.execute, []
                def changed(sql,*args,**kwargs):
                    cursor=execute(sql,*args,**kwargs)
                    if sql == 'PRAGMA temp.schema_version':
                        seen.append(1)
                        if len(seen)==final_query: execute('CREATE TABLE after_last_main_read (id INTEGER)')
                    return cursor
                patch.setattr(conn,'execute',changed)
                cache._check_selected_proof(receipts)
                with pytest.raises(RuntimeArtifactTrustError): cache._check_selected_proof(receipts)
                print(label,'main DDL after final temp execute: indistinguishable in same check; next boundary rejects')
            finally:
                fixture.close()
'@
$task7EdgeOracle | & 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -
```

Result: exit 0; both printed `indistinguishable in same check; next boundary rejects`.

## Exact raw SHA-256 identity audit

Checked by `hashlib.sha256(subprocess.check_output(['git','show','65cd304:'+name]))` versus `hashlib.sha256(Path(name).read_bytes())`; unchanged entries were also byte-compared, not merely assumed from git status.

| File | Base / candidate SHA-256 |
| --- | --- |
| context_sources/tennis_status.py | `8fc6018f827874d429495c9717496e9cbdaad837c64865113c866948ae5e56ab` -> `348c48489abcadad8c10939ee6f76ac5ffe19d5c2684385a283d534944a669a2` |
| context_runtime_history_cache.py | `260eb2f2ed1808ddc3307a9047d555a4ea9e2145c7e4b4fe1424c4e4658ecd6f` -> `9836a5048744ee8eee2fec2fe94f5dc9019081a567e3697c05a8926a27512413` |
| context_runtime_inventory.py | unchanged `a4f0f9a2833c5b5cc8eacc2a562cc2d2104a4aafcffe44dd0c7e7851b8ced707` |
| context_runtime_transaction.py | unchanged `ecec258d9b67964da29b9da91859c5d80ed24100765b04e14db5269b8d4e8e5b` |
| context_runtime_tennis.py | unchanged `b3f09a86f11bdb7c76101d3ed881568a424e3a54e17b04761a375363d8d8d2f6` |
| context_models/tennis_v3.py | unchanged `ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c` |
| context_models/tennis.py (v2) | unchanged `313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab` |
| context_models/tennis_live.py (CODE_PATHS declaration) | unchanged `5498d79266bf5b5a9e9ddc97610a2318f6abe292c164e8a0bf57b0adfcf09ed0` |
| context_models/tennis_effect.py | unchanged `ab556ac6bc5258332ab3e7b7faf5406d960f426541a7afef3974b4baf8fcb675` |
| context_models/contracts.py | unchanged `7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8` |
| tennis/predict.py | unchanged `bd1c2c8f7666e3de5f32d754eac09967edde566c1d7b48c298635f2b3d989ecc` |
| tennis/model_state.py | unchanged `3512c7aa047d11f809402fe434fcaae6ebf0542e961174348d2e6972198d7134` |
| tennis/elo.py | unchanged `689c50cdd9cbb5489ff66fbcc10814683c18ebcc79c97b648ceea4db738083c6` |
| tennis/serve_model.py | unchanged `dd76339957cc806e5bea14584c47c9467b242966bd531a6c03adf3b067e803aa` |
| tennis/simulator.py | unchanged `6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f` |
| tennis/data_loader.py | unchanged `521bb2525a8a874b64f4afe55c49e18c075bdc04348e38b1632c95af6aec4620` |

## Self-review / handoff

No correctness issue found in bounded self-review. The product diff only factors the original record/payload code, reuses canonical content in the same cold invocation, and fuses completed selected-proof stamps with immediate failure cleanup. No cache witness matcher, sealing loop, budget, inventory/transaction owner or mathematical/predictor file changed. No historical source allowlist or acceptance shortcut was added.
Independent task-scoped review, actual-current/G1/G2/G3 exact uninstrumented native checks, whole-branch review/full suite, backup/restore/HMAC/updater-only transition and ordinary exact deployment remain controller-owned separate gates.
Stage only the four assigned product/test paths and this exact report with `git -c core.autocrlf=false`; force-add only this ignored report. Controller progress/native-evidence edits remain unstaged and untouched. This report belongs to the implementation commit; index is checked empty after commit.
