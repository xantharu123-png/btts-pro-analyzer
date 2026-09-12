# Task57 independent task review

## Spec Compliance

- **Issues found.** The small diagnostic's original-input allocated-byte/metadata accounting is missing (I1), and the explicitly requested no-pre-reservation-child regression is missing (I2). Neither finding asks for a native filesystem quota, the deferred protected whole-C/B cost registry, or broader runtime closure.
- Reviewed BASE `ca663ec16d9df53b5e90efd3fafdb324be4a1362` to HEAD `85294fdf9f94ee55dd66984ddfdc7f741badc6e9`. The supplied complete diff is 103104 bytes, SHA256 `928faf2dd63824273e6edbbfb05ac23550a0a2c23434afa3ff091205d752f99c`. Its complete contents were reviewed once in four consecutive bounded chunks through EOF; a subsequent metadata-only extraction located review line references. No changed source file was separately reread.
- The six diff entries match the stated scope plus Root's brief amendment: the brief bootstrap ruling, implementer report, three new harness modules, and focused tests. No product, existing guard/supervisor/budget, Task54 acceptance owner, deployment, or daily-job change appears in this diff.
- **Cannot verify from this diff:** the eventual immutable-commit archive/catalogue/stdin pins, actual native package inventory, Linux admission/import/guard execution, kernel resource/custody observations, and external terminal closeout. These are expressly later Root gates, not missing evidence falsely counted as current acceptance. The parent correctly emits `native_pass: False` pending external terminal observation (`tests/native_context_chain.py:401-419`).
- **Cannot verify from this task:** full590553-receipt/199-Original/199-snapshot/114-key growth profiles, transitive runtime closure, protected all-cost owner, global1800CPU/3600wall, B, restore, whole suite, main/VPS deployment, release, and Task54-M1's direct new-Original-created_at assertion. The report explicitly retains them, and this review does not certify them.

## Strengths

- The guarded adapter invokes the actual fixed Task54 callable with actual `pytest.MonkeyPatch.context()` ownership, in ATP then WTA order, and ATP runs the actual retained late-cleanup rollback test. The observation wrapper first calls the real quiescence owner, propagates failures, and returns its real result (`tests/native_context_chain_worker.py:63-97`; `tests/native_context_chain.py:191-202`). The focused integration test executes these real callables and cold-reopens the retained rollback store (`tests/test_native_context_chain.py:141-188`).
- Assertions are required before the acceptance imports, and the native entry checks identity, capabilities, single-task/seccomp state, and exact limits before inserting product/dependency paths (`tests/native_context_chain_worker.py:33-52`, `tests/native_context_chain_worker.py:100-145`). The unchanged supervisor itself performs descriptor cleanup, identity drop, guard installation, SIGSTOP/readback, and only then worker execution (`context_preparation_supervisor.py:257-294`).
- Bootstrap execution is fixed to held embedded sources, with the catalogue and helpers pinned and the exact reconstructed stdin digest checked against Root's reviewed digest. There is no installed-path fallback (`tests/native_context_chain.py:83-111`, `tests/native_context_chain.py:274-289`; `tests/native_context_chain_catalogue.py:277-302`).
- The budget plan retains one300CPU-s charge with parent90 plus child90/90, exact fixed attempt slots, no refund/retry, and an external-exit acceptance boundary (`tests/native_context_chain_catalogue.py:146-187`; `tests/native_context_chain.py:318-323`, `tests/native_context_chain.py:399-419`). Both copying and child orchestration contain admission checks (`tests/native_context_chain.py:126-142`, `tests/native_context_chain.py:204-224`).
- An actual unreaped-child exception disables the wall alarm before fallible custody reporting, preserves the same PID/pidfd, and cannot proceed to WTA or success. Report failure cannot bypass the stop/reap loop (`tests/native_context_chain.py:204-251`). This exception is correctly described as operator-custody-required, not a completed600s diagnostic.
- Failed bounded copies and native output records are retained rather than cleaned or reused, and both sealed trees plus prior ATP output content are rechecked (`tests/native_context_chain_catalogue.py:304-326`; `tests/native_context_chain.py:359-391`).

## Issues

### Critical (Must Fix)

- None found within the reviewed task scope.

### Important (Should Fix)

#### I1 — Original active inputs have no allocated-byte/metadata admission or boundary observation

- **Evidence:** `tests/native_context_chain_catalogue.py:167-180` calculates the active-input ceiling from logical archive/code/dependency lengths; `tests/native_context_chain_catalogue.py:251-262` returns only logical size and SHA256 for an input; `tests/native_context_chain_catalogue.py:329-368` traverses original dependency directories but does not return their allocation/metadata totals. The native parent rechecks the original input hashes/identities at `tests/native_context_chain.py:359-370`, then applies `workspace_sample` only to the new job at `tests/native_context_chain.py:375-380`.
- **Problem:** the original archive, original manifest, dependency files, and relevant source-directory metadata remain active while their copies exist, but their observed physical allocation is never incorporated into the active-input admission or sampled total. A preallocated original can have `st_blocks * 512` materially above its logical length without failing these logical-size/hash checks. Unchanged identities establish continuity, not that the initial allocation fitted the cap. The128MiB slack reservation is not a measurement of those originals.
- **Why it matters:** the brief requires active inputs, including indexes/blocks/manifests, to remain within4GiB and requires logical AND allocated observations at real boundaries. Root explicitly confirmed during review that this includes the held original archive/dependency inputs and their metadata/manifest. Therefore this is a missing small-diagnostic admission/accounting requirement, not merely the intentionally deferred native-quota or whole-C/B closure proof.
- **Fix:** predeclare and observe the original input file/directory logical and allocated costs, bind those observations to the held input identities, include the original manifest and relevant metadata in the simultaneous active-input calculation, and recheck the actual allocated totals at the same pre/post-worker boundaries. Reject an original-input allocation overrun before launching a child. Add a focused regression where original allocated bytes exceed logical bytes/the admitted active ceiling; do not infer that an unmeasured original fits the slack allowance.

#### I2 — Required no-pre-reservation-child test does not exist

- **Evidence:** `tests/test_native_context_chain.py:342-354` proves that a missing reservation blocks the file writer and copier only. `tests/test_native_context_chain.py:234-245` exercises `run_cases` with an already-failing fake launch, not `orchestrate`'s admission-before-native-launch boundary. None of the supplied tests invokes `orchestrate`, whose relevant ordering is `tests/native_context_chain.py:204-216`.
- **Problem:** the brief specifically requires focused no-pre-reservation-copy/**child** tests. The current code visibly calls `admit()` first, but the requested child-side regression is absent; a subsequent move of that call below native launch would not fail the existing tests.
- **Fix:** add a focused orchestration test with a rejecting admission callback and a supervisor launch spy that must never be called. Assert that no child, second case, retained output, or workspace-opening action occurs. This can be tested portably without native processes, servers, or a guard-suite rerun.

### Minor (Nice to Have)

#### M1 — The retained namespace-replacement fixture is Windows-specific, not portable to Linux

- **Evidence:** `tests/test_native_context_chain.py:314-339` injects a replacement only through `Path.lstat`. The Linux implementation at `tests/native_context_chain_catalogue.py:220-245` checks held bindings with `os.fstat` and `os.stat(..., dir_fd=..., follow_symlinks=False)` instead, so that injected replacement is never observed by the native branch.
- **Effect:** this test will reach the final `pytest.raises` without an exception on Linux even for unchanged correct code. This does not invalidate the reported Windows run or demonstrate a Linux reader defect, but it prevents the same focused test file from serving as a clean Linux protocol check later.
- **Fix:** explicitly scope the CRT/Path.lstat fixture to Windows and provide a corresponding native-branch fixture, or inject through the actual per-platform identity-check seam. Keep a simulated check distinctly labelled from a real Linux rename/race observation.

## Checks and evidence boundaries

- Read the full task-reviewer template, task brief, implementer report, and supplied complete diff. No Git operation, server/network/native execution, dependency operation, suite rerun, cleanup, or subagent was performed. The only checkout write is this independent review report.
- **Named unchanged-interface risk: supervisor compatibility with in-memory stdlib bootstrap and held input FDs.** Checked `context_preparation_supervisor.py:229-294`, `context_preparation_supervisor.py:330-380`: the whitelist permits exactly the installed helper module names, catalogue execution remains unregistered, inherited nonstandard descriptors are closed in the child, and the requested argv/UID/GID/workspace/limits match the actual interface. No incompatibility found in those interfaces.
- **Named unchanged-interface risk: budget filename/status/reservation coupling.** Checked `context_preparation_budget.py:299-305`, `context_preparation_budget.py:445-468`, `context_preparation_budget.py:482-518`, and `context_preparation_budget.py:568-619`: the harness journal digest naming, pending snapshot check,300CPU-s reservation, and stopped/unmeasured retained charge match the real owner. No helper changes or settlement authority were inferred.
- **Named unchanged-interface risk: exact Task54 slot and adapter contract, rather than guessed filenames or substitute Source semantics.** Checked `tests/test_context_storage_corpus_consumer.py:32-34`, `tests/test_context_storage_corpus_consumer.py:257-293`, `tests/test_context_storage_corpus_consumer.py:357-399`, `tests/test_context_storage_corpus_consumer.py:500-574`, and `tests/test_context_storage_corpus_consumer.py:647-678`, plus the fixture configuration/call interface in `tests/test_tennis_live_worker.py:1-101`. The nine main/journal pairs and one ledger per attempt, callable property names, controlled provider/clocks, and actual late-failure callable match. This focused coupling check is not a whole-product re-review or a new Task54-M1 assertion.
- **Named unchanged-interface risk: worker read-only guard readbacks being denied after guard installation.** Checked `context_preparation_process_guard.py:235-257`: the existing policy permits the required read-only prlimit64/prctl forms without allowing limit setters. No guard weakening is requested.
- Final local evidence supplied by Root: `.pytest_tmp/task57-final-owned-11.xml`, independently parsed by Root as26 tests, zero failures/errors/skips,12.054s, SHA256 `27d18ae6671de17200843423567765749bed4e8a5df686f034f3d01b85326559`. I did not rerun or independently reparse that already-verified result. The diff's actual-callable test supports the claimed integration scope; synthetic parser/native counters remain synthetic. Historical RED rows are retained and explicitly distinguished from final GREEN evidence in the report.
- No additional focused runtime probe was needed: I1 follows directly from the data returned/consumed by the accounting code, I2 from the supplied test call sites, and M1 from the two distinct platform branches. A real Linux run remains unauthorized and unperformed.

## Assessment

**Task quality: Needs fixes.**

The fixed execution path, guard custody, conservative charge retention, and honest later-gate reporting are strong. The original-input physical accounting hole must be closed, and the explicitly required child-admission regression added, before this harness can be trusted for its proposed small native diagnostic; no broader C/B or release claim follows from fixing them.
