### Spec Compliance

- ❌ Issues found. The approved P4b3(a) split correctly shares one existing BB/NHL prediction revision between normal and Risk consumers and keeps the uncertainty/price boundary null, but it violates two binding lifecycle/fallback rules: an explicit native `unknown` currently withdraws the legacy baseline, and a merely partial predecessor can seed a later failed-refresh fallback.
- ⚠️ Deliberately open and not counted as patch defects: real B3 `context_ref`, the full historical B1 correction pipeline, Injury/Load/D4/empirical approval, durable original/history storage design, and the two unchanged B3 RED witnesses. Live-provider qualification, the separate full suite, browser/device acceptance, deployment, and profitability are also outside this task's evidence.

### Strengths

- `team_sports_baseline.py:99-176,305-382` closes and hashes the persisted view/batch, replays the actual existing projection without another fit, validates every stored entry, deduplicates source identities before prediction, and rejects divergent Risk snapshots/candidates before publication.
- `wettfinder_automation.py:2866,3292-3360,3767` places read/acquire/publish under the shared worker lock, acquires BB/NHL before either consumer, reuses the same current entries for the normal rows and Risk batch, and persists the owning baseline separately from price/money candidates.
- `team_sports_baseline.py:399-410` combines a per-path thread `RLock` with the existing file publication lock. The tests exercise concurrent workers plus a separate nonblocking child-process lock attempt rather than treating sleeps as exclusion evidence.
- `wettfinder_surface.py:248-252,386-397,442-472,606,683-692` preserves the optional-null uncertainty domain: no zero haircut, substitute conservative probability, invented minimum odds, price overlay, manual quote action, or money candidate is created for the baseline contract.
- The retained XML evidence matches the audit without a rerun: `p4b3-final-focus-02.xml` has 402 JUnit cases (376 pytest passes plus 26 subtests), 0 failures/errors/skips; `p4b3-original-acceptance-final.xml` has 4/4 green; `p4b3-original-b3-open-final.xml` retains 2/2 failures. The audit clearly avoids claims of live qualification or safe/profitable bets.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

1. `team_sports_baseline.py:179-185` treats a binding whose native `current_state` is `unknown` exactly like a conflict and returns `False`. Consequently both acquisition and reuse erase the otherwise valid legacy view. The new tests explicitly encode that wrong policy by including `unknown` among the withdrawal cases at `tests/test_team_sports_baseline.py:250-270`. The binding requirement is the opposite: absence/unknown native evidence holds the legacy baseline; only a known cancellation/start, participant contradiction/incompleteness, or simultaneous conflict withdraws it. Split unknown from conflicting/decisive adverse status in `_current_native_event`, and change the acquisition/reuse tests so unknown retains the unchanged legacy projection without refit while the known adverse cases still remove both consumers.

2. `team_sports_baseline.py:385-395` calls `validate_batch(previous, sport)` but never requires or proves that the fallback source was previously `completed`; any valid `partial` batch with entries is copied into the next `source_failed` batch. That contradicts the explicit contract and the audit claim at `docs/audits/2026-09-10-p4b3-shared-baseline.md:79-85` that fallback uses only a previously fully validated same-day batch. The author's fallback test at `tests/test_team_sports_baseline.py:608-632` starts from a completed predecessor and therefore misses this path. The isolated counterexample `.pytest_tmp/p4b3-independent-review-20260910/test_p4b3_contracts.py:23-41` creates a legitimate partial acquisition, makes the next refresh fail, and observes `partial` with retained entries instead of the required failed/empty result. Require completed provenance before copying entries; if repeated failures may reuse an older completed base, represent and validate that provenance explicitly rather than accepting an arbitrary partial predecessor.

#### Minor (Nice to Have)

- `ev_signal_sources.py:878-888,1132-1142` validates every owning batch and enforces visible-row → batch membership, but it does not establish the reverse publication relationship. Removing an otherwise visible baseline row while leaving its hashed batch and source status intact is accepted as a valid document; `.pytest_tmp/p4b3-independent-review-20260910/test_p4b3_contracts.py:8-20` demonstrates the accepted omission. This is availability/integrity hardening rather than an unsafe price path—legitimate lifecycle filtering can also leave stored entries without rows—but the current reader evidence proves one-way consistency, not full two-way catalog completeness. Either validate expected visible-row counts/identities against the persisted publication metadata or qualify that boundary explicitly.

### Harness and Evidence Boundaries

- One isolated two-case counterprobe was run with its own basetemp and JUnit file; both expected fail-closed assertions failed in 3.35 seconds. It did not modify author source/tests or rerun the author's focused/full suites.
- The GET responses are synthetic native-shaped fixtures. The concurrency harness proves the tested thread/process lock boundary, not arbitrary crash recovery or distributed/VPS locking. AST execution of the app loop proves action-path routing, not rendered browser quality.
- The unchanged B3 failures are honest acceptance witnesses for deferred package (b), not regressions introduced by this split. Root's separate full-suite result remains a distinct integration gate.

### Assessment

**Task quality:** Needs fixes

**Reasoning:** The shared baseline architecture, closed snapshots, single-model computation, null price boundary, clocks, and locking are unusually well defended for this narrow split. Merge trust is nevertheless blocked until native `unknown` preserves the legacy basis and fallback can prove that retained entries descend from a completed same-day batch; the reader's reverse-completeness limit should also be fixed or explicitly documented.

### R2 Contract Clarification Addendum

- **No completed-only requirement found.** The controller preflight requires one acquisition/calculation and unchanged prepared references under the existing six-hour refresh/retry policy (`.pytest_tmp/p4b3-worker-preflight-20260910/PREFLIGHT.md:184-193,267-283`). It does not require a fallback predecessor whose batch status is literally `completed`. The task brief likewise requires common failure fallback and preservation of valid basis data when other data are missing.
- `docs/audits/2026-09-10-p4b3-shared-baseline.md:79-85` says “previously fully validated same-day batch.” In this contract, `validate_batch` deliberately validates `completed`, `partial`, and `failed` status shapes and validates every retained entry/view (`team_sports_baseline.py:147-176`). A legitimate `partial` batch can therefore contain completely validated, causally correct same-day views while reporting incomplete source coverage.
- **R2 is WITHDRAWN as a blocking defect.** The counterprobe at `.pytest_tmp/p4b3-independent-review-20260910/test_p4b3_contracts.py:23-41` proves only that those unchanged validated views survive another failed attempt and remain retry-due as `partial`. It does not demonstrate an unvalidated view, a cross-day transfer, changed prediction/model/history/source-observation bytes, or an artificially refreshed model cutoff. Its expected `failed`/empty assertion imposed a stronger completed-only availability policy that the controller/brief did not authorize and that conflicts with the stated rule to keep a valid basis visible when data are missing.
- The original R2 text and witness remain above as historical review evidence; this addendum supersedes their interpretation. R1 remains the sole Important hold. The reverse-completeness Minor remains separately dispositioned and is not promoted by this clarification.
