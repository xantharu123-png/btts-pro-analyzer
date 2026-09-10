# Independent Review — P5b-A0 final FootballOriginal callback

Date: 10 September 2026  
Reviewer scope: frozen `ecff029f3c8b0601495547b60ba3941c41cf38ac` against parent `887cb4713d996d2f6efc8b70fbb4cc71e867f13d`  
Owning worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-p5b-a0-20260910`  
Reviewed packet: `review-p5ba0-887cb47-ecff029.diff`, SHA256 `d6b56ed5b5b7db42bdcd8adcf75634fbadd2682481be085a34d00a06bcf74a34`

## Verdicts

- **Spec compliance: PASS for the bounded P5b-A0 prerequisite.** The frozen packet implements the approved opt-in final-original seam and does not claim or implement default production capture, B3 publication, context effects or deployment.
- **Code quality: PASS.** No Critical, Important or Minor source/contract defect was found in the six-file packet.
- **Integration recommendation: ACCEPT A0 only.** This verdict is not approval of complete P5b/B3, safe bets, model adequacy, provider readiness or deployment.

## Findings

### Critical

None.

### Important

None.

### Minor

None.

## Direct review evidence

### Frozen scope and ancestry

Read-only Git inspection resolves `HEAD` to exactly `ecff029f3c8b0601495547b60ba3941c41cf38ac` and its first parent to exactly `887cb4713d996d2f6efc8b70fbb4cc71e867f13d`. The worktree was clean apart from ignored test output. The commit changes exactly these six files:

1. `alternative_markets_tab_extended.py`
2. `challenge_15k.py`
3. `wettfinder_automation.py`
4. `tests/test_football_final_original_a0.py`
5. `tests/test_football_original_parity.py`
6. `docs/audits/2026-09-10-p5b-a0-final-football-original.md`

`git diff --check` reported no whitespace errors. The five source/test hashes match the owning audit. The audit itself matches the controller-supplied SHA256 `f4f189eb6b2e5fbb9dfde706cba16a38675c60784b0bc4c93782df8a9f8505a0`.

### Production contract

The complete diff contains exactly 14 additive production lines across the three authorized functions.

- `scan_daily_challenge`, `_default_football_scan` and `_run_market_scan_worker` each receive a default-`None`, keyword-only `original_capture` parameter. The existing `*` in the scanner and the newly placed `*` in both wrappers preserve every prior positional call.
- Each function rejects a non-`None`, non-callable value before its own provider construction, source access or model invocation. This gives scanner callers and both wrapper callers the same fail-early contract.
- Each wrapper conditionally adds the keyword only when a callable was actually supplied. The scanner does the same at the one assignment `fixture_candidates = build_fixture_candidates(...)`. Consequently omission and explicit `None` retain the old lower-level call signature; they do not activate the P5a provenance/capture clocks.
- The scanner forwards only at the actual final candidate build. The unchanged UEFA feasibility/fallback/probe paths receive no callback. There is no added fit, prediction, calibration evaluation, history lookup or HTTP GET.
- Callback exceptions are not swallowed. The direct scanner/automatic paths propagate them, and the existing manual `scan_jobs` boundary can report `error` without a result or completed audit.
- No production import, return field, DTO/schema, JSON projection, price/money rule, 15K default, model signature or global/default recorder changed.

These conclusions do not rely on the prose audit alone: the production diff establishes the placement and default behavior, while exact whole-module AST comparisons bind every other statement in all three modules to the frozen parent.

### Actual-final/original and regression witnesses

The new permanent test file exercises the real scanner and both real wrapper paths with synthetic HTTP/history/clocks. Its primary domestic/UEFA cases compare complete canonical worker results with parent functions compiled from the exact `887cb47` blobs. The assertions inspect the callback's actual `FootballOriginal`, rather than recreating it from rounded cards, and cover:

- one capture/provenance/capture-clock operation for the final calculation, including the existing four UEFA goal-model invocations but no capture on feasibility/probe calls;
- exact parent HTTP/history/manual-quote invocation lists and complete worker dictionaries;
- all 90 final calibrated probability triplets, the corresponding unrounded raw triplets, count-model values and calibration recipes;
- the existing source-receipt versus capture-clock ordering and immutable detached projection behavior;
- no-model, duplicate-fixture and incomplete-source cases;
- omission/explicit-`None`, falsy callable, invalid callback, throwing callback, 15K default, manual job error and automatic/manual JSON non-leakage paths.

The preserved JUnit files independently confirm the reported run totals, not the semantic truth of every assertion:

- `p5b-a0-red-03.xml`: 47 tests, 43 failures, 0 errors/skips.
- `p5b-a0-first-green-04.xml`: 48 tests, 4 failures, 0 errors/skips.
- `p5b-a0-green-05.xml`: 85 tests, 0 failures/errors/skips.
- `p5b-a0-focus-06.xml`: 590 JUnit cases, 0 failures/errors/skips, consistent with 558 pytest passes plus 32 subtests.
- `p5b-a0-original-preflight-07.xml`: 12 tests, 2 failures and 10 passes, preserving the two intentionally open original witnesses.

I did not rerun the author's 558-case focus selection or the intentional RED witnesses. Their behavioral weight comes from the reviewed test bodies plus the preserved JUnit results and hashes; HTTP, cached histories, clocks and fit adequacy remain synthetic/test-controlled.

### Exact AST accommodation

The four-line change to `test_football_original_parity.py` imports the new exact-removal helper, identifies only `scan_daily_challenge`, removes the authorized additions, and still executes the original complete module-to-parent/closure assertion.

`strip_exact_a0_additions` is appropriately fail-closed for this exception:

- it requires the exact last keyword-only name and `None` default;
- it requires the exact early callable guard immediately after the optional docstring;
- it requires exactly one conditional `**original_capture` spread;
- that spread must call the expected named callee and be the value of the expected named final assignment;
- it removes only that parameter/default, guard and spread, after which the entire module AST must equal the exact parent AST.

The nine mutation cases independently cover all three modules and reject an unrelated statement, altered guard and relocated/renamed forwarding assignment. No whole function, unknown node or parent assertion is skipped.

### Ordinary Root pytest import check

The new tests mix direct `test_*` imports with `tests.test_*` imports, so I ran only the concrete import/collection risk with the repository's quality Python, from the owning repository root, with no author `pythonpath` override and unique ignored basetemps:

```text
python -B -m pytest -q -p no:cacheprovider tests/test_football_final_original_a0.py::test_callback_is_keyword_only
3 passed in 2.59s

python -B -m pytest -q -p no:cacheprovider tests/test_football_original_parity.py::test_whole_challenge_module_has_only_the_authorized_closure_type_replacement
1 passed in 2.50s
```

This closes the named ordinary Root-pytest import concern for both the new module and the older parity module's new `tests.*` import. It is not a wider test-suite claim.

## Evidence and acceptance boundaries

- No browser, live provider, network, VPS, deployment, source mutation, index/branch mutation or full-suite run was performed.
- The author suite uses synthetic provider responses and pre-existing cached histories/artifacts; it proves deterministic plumbing and parity, not current upstream availability, empirical calibration fitness or profitable/safe bets.
- The callback is an in-process observation seam. It creates no durable ownership, schema, publication or restore behavior.
- The two original default-capture/B3 REDs are correctly still RED and are not A0 regressions.

## Remaining concrete gaps outside A0

All of the following remain open and must not be inferred from this PASS:

- default production capture has no receiving owner, and once-only B3 publication/read behavior is absent;
- a durable calibrated-live original with exact native event/source binding, distinct original/context clocks and D4 read/restore is absent;
- native cancellation/first-half withdrawal handling, historical roster exposure, exact load/fatigue timing, trained player effects and real injury/load application are absent;
- empirical 200-event/fit approval and live-provider evidence are absent;
- no release, VPS or end-to-end production acceptance was performed.

## Assessment

The implementation is unusually narrow and auditable: conditional keyword forwarding preserves the old call graph by default, and the exact AST checks make the claimed 14-line production scope independently testable. The tests distinguish actual parent output, real in-process originals and JSON boundaries carefully. Within the authorized prerequisite, the task quality is **ready to integrate**; broader P5b/B3 remains explicitly not done.
