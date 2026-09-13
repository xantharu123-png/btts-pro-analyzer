# Task61 fix round1 scoped independent review

## Spec Compliance

**Spec verdict: compliant for the scoped fixes I1-I4 and T1.** All five findings are ADDRESSED. No new Critical or Important breakage was identified within these fixes. Native execution and the broader Task61/full-C/release gates are not approved by this verdict.

**Review identity:** BASE `fec316ff05545fff89217399cfbf872f19ee6c7f`, candidate HEAD `1632072216b33d85b0343c1f389f762356b62d0a`.

- Actual report SHA256: `6c3a05f7b99b78c8d22cd8ae492fc5c4883157157a7b936d1b0d0ffa9a8961c4`.
- Actual fix-package SHA256: `a467a1d208632b55e1e301a278d2d2481f3160b0c58badca94a5fdc30bb68ec4`.
- Both match the dispatch. The complete updated author report was read. Review inspected the package's scoped parent/catalogue/worker/test/transport hunks; intervening controller documents/evidence were deliberately not broadly re-reviewed. The first tool output truncated catalogue/worker hunks, so only those omitted sections were retrieved separately. No changed source file was reopened outside the diff. A reference-only diff index supplied current line numbers.

## Findings disposition

### I1 — ADDRESSED: actual active-input allocation and metadata

- `tests/native_context_receipt_diagnostic_catalogue.py:168-180` holds the declared file set and bounded unique ancestor-directory union. `:183-222` compares held/native path epochs, measures actual allocation through the existing `_allocation` function, rejects physical file-slot overruns, measures directory metadata, enforces the actual input/new-job union against4GiB, and compares later observations with the original sample. It does not replace actual occupancy with declared caps.
- `tests/native_context_receipt_diagnostic.py:383-384` invokes the real binding/sampler before admission; `:397` rechecks immediately after admission and before writes; `:409` rechecks during the existing parent recheck. The measured observation is retained in `plan.json` and its digest in the final report.
- `tests/test_native_context_receipt_diagnostic.py:655-668` drives actual main and rejects file physical-allocation and directory-metadata overruns before the real admission call site, with no write/launch event. `:738-769` verifies physical drift within a slot, file and directory epoch drift, measured union and the combined4GiB bound. Physical block injection is correctly portable test evidence, not a Linux measurement claim.
- The stricter full ancestor epochs and repeated held reads can fail closed under unrelated namespace changes or resource pressure. That is not a false successful admission; actual native practicality remains to be measured under the unchanged parent60CPU bound.

### I2 — ADDRESSED: worker phase exact slots and whole reserve

- `tests/native_context_receipt_diagnostic_worker.py:53-80` adds `WorkerAllocation`: it derives only exact attempt-relative slots, uses the actual exact-slot scanner, bounds checks, records measured logical/allocated metadata, and enforces `free >= 8GiB + complete_job_reservation - observed_child_allocated`. Root-only/registry bytes receive no occupancy credit, so their full reservation remains outstanding conservatively.
- `:101-137` integrates checks into actual phase begin/end and includes checker costs in the inclusive phase interval while retaining separate checker timings. The normal worker constructs this checker at `:332`. Append checkpoints do not call it; the real owner/generator and existing fixed limits remain unchanged.
- `tests/native_context_receipt_diagnostic.py:283-310` requires closed, non-null before/after allocation observations for successful phase summaries, validates their bounds and reserve formula, and bounds checker times by inclusive phase times.
- `tests/test_native_context_receipt_diagnostic.py:146-190` extends the existing real1024-owner positive path with the real checker and verifies two checks per completed phase, not per receipt, plus visible timing/reserve observations. `:689-734` injects reserve loss above the old4GiB threshold, an unknown file, and physical over-allocation at the real copy-return boundary; failed outputs/progress remain retained and nonterminal.
- The new checks preserve the existing outer cleanup attempts when a check fails. Successful evidence remains fail-closed: a failed checker emits failure rather than a successful phase return. Repeated hashing of the growing corpus can materially increase actual native CPU/wall cost; those costs are now measured inside the original limits, not waived or represented as a capacity pass.

### I3 — ADDRESSED: exactly4GiB backup/rollback reserve

- `tests/native_context_receipt_diagnostic_catalogue.py:329-330` requires an exact integer equal to4GiB in the retained-control validator. Parent `tests/native_context_receipt_diagnostic.py:218-225` and worker `tests/native_context_receipt_diagnostic_worker.py:59-61` independently enforce the same exact constant.
- `tests/test_native_context_receipt_diagnostic.py:671-685` reconstructs retained hashes, allocation and plan digest for0,4GiB-1 and4GiB+1; validation still rejects. This implements Root's final **EXACT4GiB** ruling, not a weaker minimum or merely internally consistent caller-selected reserve. The separate free4GiB requirement remains intact.

### I4 — ADDRESSED: actual production admission-order regression

- `tests/test_native_context_receipt_diagnostic.py:108-113` now invokes `d.main(argv)`. Its fixture at `:575-651` uses actual temporary control files, held file descriptors and active-input sampling while explicitly substituting native/read-only preflight. The actual Task60 call site rejects; write_new/copy_exact/launch_once are fail-on-reach traps, and the real job remains empty.
- The unused `admitted_run` miniature was removed from `tests/native_context_receipt_diagnostic.py` (deletion hunk beginning at old line168). There is no longer a test passing solely through a separate dead orchestration helper.
- The author correctly reports that this actual-main regression already passed before the fix: it closes a test-coverage gap in existing correct admission order, rather than fabricating a production ordering failure.

### T1 — ADDRESSED: checked held template bytes

- `evidence/task61-native-prefix-run.ps1:8-12` reads the template once into a held byte array, checks its bound/hash and strictly decodes that same array. Placeholder replacement and stdin generation at `:29-33` use the held string; there is no second template content read after validation.
- `tests/test_native_context_receipt_diagnostic.py:772-811` parses and executes the actual acquisition/replacement statements, changes only a temporary template after acquisition, and verifies the held template is used. The test never reaches SSH. Reported mutation RED restores the original reopen seam and fails; the corrected implementation passes.
- Source/template/probe pins were deliberately not automatically refreshed. The runner currently refuses changed QA source hashes as expected. Root must mechanically repin the final approved frozen artifacts and verify the generated stdin before execution. This safety gate is not a remaining T1 defect.

## Strengths

- Fixes remain in the new QA modules and the specifically authorized transport runner; unchanged owners, generator, admission and supervisor/guard code are not modified by the scoped source fixes.
- Actual allocation observations now complement declared reservations, and the worker conservatively accounts for unreadable root-owned controls without lowering any budget.
- Tests target real production orchestration and real owner phase boundaries rather than newly invented stand-ins. Timing tests accept platform clock quantization without relaxing production limits.
- The final result still stays diagnostic-only; no automatic retry/refund, smaller profile or native/full-C success flag is introduced.

## New Critical / Important findings

- **Critical: none identified within this fix scope.**
- **Important: none identified within this fix scope.**
- **Deferred Minor T2:** explicit local transport stdout/stderr caps remain deferred to final review, as directed. The runner still drains unrestricted SSH streams into local files. This fix review neither reclassifies T2 nor treats its deferral as native terminal/custody proof.

## Checks and cannot-verify items

- **No suite repetition:** no tests, native calls, network/server operations, Git commands, installs, cleanup or subagents were run. No additional unchanged-code lookup was necessary; this review relies on the previously checked held-input/scanner/supervisor contracts plus the scoped diff. Only this review report was written.
- **Final evidence inspected, not regenerated:** the updated author report records session58858, actual child/outer exit0, `50 passed, 2 skipped in 97.67s`, outer wall98.078s and empty stderr. XML SHA256 is `a177500a9d45be51616361f96b425caa08828dc9e5f961e039459def69185419`. Root separately reports a fresh match of all five frozen source/script hashes and that XML with52cases,0failures,0errors,2native skips. Earlier failed timing-test runs are explicitly retained and superseded, not hidden. No warning noise is present in the reported final output.
- **Cannot verify native kernel facts:** both native tests remain skipped here. Actual parent60/child240 handoff, capability permission, guard/SIGSTOP/readback, root-only environment, PID/pidfd/reaping and exceptional custody need Root's separately prepared fresh stdlib interpreters and externally retained terminal evidence.
- **Cannot verify actual data/allocation feasibility:** Linux physical blocks/DAC, complete retained namespaces and16-journal replay, actual baseline ID/clock/profile/old-row inventory, live free/outstanding/backup reserve, full native100553+1024 execution, and the CPU/wall cost of new repeated scans remain unmeasured. Portable injected allocations and the real small-owner fixture do not establish those facts.
- **Cannot verify whole-job/release acceptance:** original kernel-start deadline, permanent300CPU accounting and terminal crash acknowledgement require native evidence. Full490000 growth, global1800/3600 proof, C/B, Source/D2, backup/restore, deployment and release remain open. SSH termination or missing result JSON still requires explicit external process/custody checking, never assumed parent-death cleanup or automatic retry.

## Assessment

**Code-quality verdict: Approved for this scoped fix round.**

**Reasoning:** I1-I4 and T1 are implemented on the actual production/test seams, with focused regressions and no newly identified Critical/Important defect inside their changes. This closes these five review findings only; final review, approved-pin preparation, native probes/full-baseline diagnostics and all broader acceptance gates remain separate.
