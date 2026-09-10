### Spec Compliance

- ✅ The reviewed implementation conforms to Task 4's scoped representation and trust requirements. Review range: `46380d598e02a5e1d78bb84cad50e4193ac6dcab..fc7f0c78ecdfacf8b93349da970e2ac8ff4f8003` (final product revision `52189a6`). Complete proof gates the owning publication planning pass; maximum cutoffs are per tour, and the original consumer loop retains artifact order (`context_runtime_tennis.py:154`, `context_runtime_tennis.py:161`, `context_runtime_tennis.py:191`).
- ✅ Original distribution, supported code, state clock, native target and predictor checks remain individual checks, not model-result reuse (`context_runtime_tennis.py:113`, `context_runtime_tennis.py:115`, `context_runtime_tennis.py:129`, `context_runtime_tennis.py:134`, `context_runtime_tennis.py:144`). The package changes no owning predictor/feature/selector, inventory, updater or protected helper file.
- ⚠️ Task 4 as an accepted capacity recovery is NOT complete. The implementer's report explicitly records the exact 7b6 Linux run failing at CPU300 with no report and unchanged sealed input; 52189a6 addresses optional-preparation memory bounds, not a measured capacity pass (`.superpowers/sdd/2026-09-10-context-capacity-recovery/task-4-report.md:35`). Exact final-source actual-input and receipt-plus-consumer growth acceptance, then the final immutable repository suite, remain controller gates (`task-4-report.md:36`). Unit passes cannot discharge them.
- ⚠️ Full runtime report/exit-schema and all cross-task protected-byte identities cannot be independently established from this scoped diff. The diff contains no changes to those owners; the controller must retain its source-pin, exact-report and final-source evidence. The report parity test compares the real verifier with cold consumer replay, but is not native release acceptance.

### Strengths

- Shared-basis behavior is small and localized: planned earlier prefixes return immediately without being retained as duplicate encoded entries, and cold fallback cannot store non-maximum prefixes (`context_runtime_tennis.py:99`, `context_runtime_history_cache.py:137`). Descriptors retain the cache reference rather than decoded histories or encoded entry references (`context_runtime_tennis.py:52`).
- Optional preparation has an independent canonical size limit and catches only `_HistoryBasisOverflow`; it rechecks trust before fallback. Per-consumer admission remains on the complete requested history, and owning selector exceptions propagate (`context_runtime_tennis.py:78`, `context_runtime_tennis.py:176`, `context_runtime_tennis.py:182`).
- The completed proof is pinned in addition to existing identity, transaction, write and schema checks. Post-encoding validation closes the final oversized-row bypass; covering materialization checks both sides of decoding and the empty/final result (`context_runtime_history_cache.py:57`, `context_runtime_history_cache.py:115`, `context_runtime_history_cache.py:126`, `context_runtime_history_cache.py:151`).
- Boundary tests use actual publications, receipt decoding/selectors and owning replay with observational spies. They address the real interleaved ten-consumer workload, canonical parity/isolation, opposite-tour malformed receipts, global eviction/reference release, optional overflow and mutation. Final focused evidence is explicitly distinguished from the earlier pre-final 586-test run (`task-4-report.md:27`, `task-4-report.md:29`).

### Issues

#### Critical (Must Fix)

- None found in the reviewed product-code scope.

#### Important (Should Fix)

- Acceptance blocker, not a newly identified code defect: the exact native capacity gate remains failed/unproven on the final product revision (`task-4-report.md:35-36`). Do not mark Task 4 complete, merge on a capacity-success claim, deploy, or waive the unchanged limits based on this code review or local tests. The controller needs successful final-source actual-input/growth evidence under the specified gates, or must explicitly retain the failed release status.

#### Minor (Nice to Have)

- None identified that warrants a scoped follow-up.

### Assessment

**Task quality:** Approved for the scoped implementation; overall Task 4 completion and release acceptance remain held.

**Reasoning:** The change removes duplicate retained cutoff pools without introducing a decoded/result cache or bypassing consumer-specific owning replay. No actionable correctness or maintainability defect was found; the failed native gate is still a separate, binding outcome requirement.

### Checks and Review Limits

- Read the supplied skill, reviewer contract, Task 4 brief/report, prerequisite fresh-profile diagnosis and supplied diff package. The tool truncated the first diff rendering; only its omitted product/test-fixture span was subsequently retrieved.
- Changed-file context completion: the diff cuts `_lookup`/`_lookup_covering` and `_verify_live_original` mid-function. Read only `context_runtime_history_cache.py:89-134` to inspect exact/prefix last-row and empty-result invalidation, and `context_runtime_tennis.py:107-151` to inspect preservation of the original native/predictor checks.
- One focused unchanged-file check for the concrete risk that a revoked/interrupted physical proof could still enable prepared reuse: inspected `context_runtime_inventory.py:79-156`. `validate_all` publishes proof only after complete physical checks and clears it on any interruption/failure; traversal checks proof around yields and on exhaustion.
- No Git commands, broad repository crawl, test rerun, subagent, index/branch mutation or external operation. No focused repro was necessary: the diff and supplied final focused evidence answered the concrete code questions. This report is the only written file.

### Follow-up Review — 2026-09-11

- **Historical record:** The preceding review and its approval of the scoped implementation are retained. Its then-open actual-input gate assessment is superseded only by the new controller evidence below; the known failed 7b6 run remains historical evidence, not the current final-source result.
- **Spec verdict:** Task 4's scoped code verdict remains approved. Overall completion/release remains held pending growth acceptance and the other final gates; a current actual-input pass does not constitute growth acceptance.
- **New controller-supplied actual-input evidence:** Exact final `fc7` uninstrumented CLI passed at 285.297 CPU seconds / 285.388 wall seconds / 321584 KiB peak RSS, with expected counts `12/48307/10/2/0`, the same transport-only limitations and unchanged sealed input. The controller also reports seven actual file/ancestor/mode/companion races rejected, three application write denials and eight unsafe classes passing. These runs were not repeated by this reviewer.
- **New controller-supplied native QA evidence:** Ordinary QA UID1000, exact immutable `fc7`: **199 passed, 10 skipped, 14196 DeprecationWarnings, 171.42 seconds, exit 0**. This is a successful test exit with significant warning noise, **not a pristine PASS**. The controller's focused warning-as-error run failed at the identified query after 29 passing tests. The ten skips comprise one non-Linux check and nine root-fixture-based tests not configured for ordinary UID1000; separate actual UID997 DAC checks are distinct evidence, not execution of those skipped tests.

#### Important — Pre-existing SQLite Binding Compatibility Finding (Outside Task 4)

- `context_models/dataset.py:169-174`: `_physical_receipt_preflight` repeats the numbered placeholder `?1` in six outer-header JSON projections but supplies the sequence `(opaque,)`. The controller's native warning identifies this as a named-parameter/sequence mismatch and explicitly warns that Python 3.14 raises. The source inspection confirms that exact query and parameter shape. The reported trigger is `tests/test_context_runtime_capacity.py::test_lazy_membership_does_not_decode_unopened_final`, via the execute wrapper at `context_runtime_transaction.py:16`; the wrapper is the emission site, not the offending SQL owner.
- **Impact and classification:** A real forward-compatibility defect and present warning-as-error failure, not a harmless clean-test annotation. A runtime enforcing the announced binding rule will reject this D2 physical preflight path for otherwise valid inputs. It does not establish invalid-input acceptance or a current warning-only runtime failure. This query is unchanged in the reviewed `46380d5..fc7` package; therefore it is **not an introduced Task 4 code regression** and does not invalidate the scoped shared-history implementation verdict. It remains an Important owner-level compatibility finding for explicit disposition before any compatibility/clean-validation claim.
- **Scope boundary and proposed repair:** D2 owning source is outside Task 4 authorization. Do not silently patch it, suppress the warning or relax warning-as-error checks. A separately authorized focused repair can use one named placeholder such as `:opaque` throughout these same projections with a matching dictionary parameter, retaining the exact bytes, hash checks, closed outer-header checks and prohibition on outcome/body decoding. That repair would require its own review and targeted unopened-final/physical-preflight validation on the relevant Python runtime; this report does not implement or authorize it.

#### Follow-up Assessment and Checks

- **Task quality:** Approved for the scoped Task 4 implementation; release hold remains. The warning is an independently tracked, pre-existing compatibility finding rather than a reason to disguise the new native QA output as clean.
- **Bounded source check:** Inspected only the reported unchanged `_physical_receipt_preflight` function, `context_models/dataset.py:149-191`, for the named binding-compatibility risk. No broad suite, focused repro, Git command, product edit, warning suppression, VPS action or subagent was used. Only this review report was appended.
