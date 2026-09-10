# Independent Round-1 Re-Review — P4b3(a)

Date: 10 September 2026  
Frozen revision: `6c8984d62ea66a683c3eb9e668f605e2bdc8e140`  
Reviewed parent: `2aecc108067832c1825967e76bb52ddf5215cb4f`  
Owning worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-p4b3-baseline-20260910`

## Spec Compliance

- **FAIL / HOLD for Round 1.** Direct `unknown` acquisition/reuse/fallback is corrected, a later `unknown` no longer erases an earlier adverse lifecycle state, valid partial views survive failed refreshes without retiming their model bytes, and the publication-count Minor is closed as authorized.
- One Important R1 defect remains: lifecycle and identity are validated from different revisions. A schedule-conflicting `scheduled` revision can clear a proven cancellation when a still later `unknown` revision supplies the old identity. That is not the required genuine later scheduled correction.
- The original review's completed-only R2 remains **WITHDRAWN**. It is not revived by this review.
- The two real B3 `context_ref` REDs and package (b) remain deliberately open and are not counted as Round-1 defects.

## Strengths

- The change is narrowly scoped: two production files, two test files and the owning audit. Read-only Git confirms exact parentage, a clean tracked worktree, and a clean `diff --check`.
- `_current_native_event` now treats absent native evidence and one coherent unknown status as non-adverse, while retaining rejection for alias/current-revision conflicts, incomplete or divergent current identity/schedule, and equal-time lifecycle conflicts.
- The latest-determinate-status rule correctly makes later `unknown`/`not_completed` unable by themselves to erase an earlier cancellation/start/completion; only a strictly later known scheduled timestamp can change that lifecycle result.
- Existing event-start comparison in `current_batch` remains unchanged, so a nominally scheduled event still cannot appear after its stored kickoff at the decision clock.
- `ev_signal_sources.py:1197-1201` validates each owning BB/NHL source `candidate_count` before current-time projection, requires `type(value) is int` (therefore rejects bool and floats), and compares it to exactly the published model rows from that sport's baseline source. It neither equates the count to historical batch entries nor claims protection against coherent row-and-count rewriting.
- The Round-1 production diff does not touch model calculation, shared normal/Risk batch routing, source acquisition, mutex/retry machinery, probability/uncertainty/odds/money fields, Cricket, D4 or the raw staging helper. `scripts/stage_runtime_databases.py` remains SHA256 `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

## Issues

### Critical (Must Fix)

None.

### Important (Should Fix)

1. **A contradictory scheduled revision can be spliced with a later unknown revision to resurrect an old baseline.**

   At `team_sports_baseline.py:190-210`, identity/schedule/issues are checked only on the newest overall cohort (`current`). At `team_sports_baseline.py:213-219`, lifecycle is then selected independently from the newest *determinate* cohort and accepted solely because every status in that cohort is `scheduled`. The scheduled cohort itself is not required to pass the original/native identity, schedule, season and format checks used above.

   This permits the following causal lineage:

   1. valid original baseline for event A at kickoff S;
   2. matching native cancellation;
   3. strictly later native `scheduled` receipt for the same alias/event ID but a conflicting kickoff S2;
   4. still later native `unknown` receipt matching the original identity and kickoff S.

   The current cohort in step 4 passes the identity checks. The independently selected determinate cohort is step 3 and has status `scheduled`, so the function returns true even though that scheduled correction contradicts the old forecast's schedule. Normal and Risk both republish the old view.

   The isolated real-worker counterprobe at `.pytest_tmp/p4b3-round1-independent-20260910/test_round1_contract.py` constructs exactly this sequence through the existing ESPN/NHL normalization and SQLite receipt path. Both cases fail the required `(0, 0)` visibility assertion:

   ```text
   basketball: observed normal/Risk = (1, 1), expected (0, 0)
   ice_hockey: observed normal/Risk = (1, 1), expected (0, 0)
   2 failed in 3.80s
   ```

   This is a source/contract defect, not merely a missing harness assertion: the contract requires strict identity/schedule handling and only a genuine later scheduled revision may clear proven cancellation/start evidence. The restoring determinate cohort must itself be complete, internally consistent and compatible with the original event; a later unknown cohort must not lend it identity/schedule validity from another revision. The same rule should cover participant, season and format contradictions, not only the demonstrated kickoff mismatch.

### Minor (Nice to Have)

None. The original reverse-publication-completeness Minor is closed within its explicitly narrowed owning-count contract.

## Evidence Review

The complete original independent review, including its R2 WITHDRAWN addendum, and the complete Round-1 owning audit were read first. The audit hash matches the supplied SHA256 `8557cdcae188d6d94269ea79193c5b821c7c8d668e9e75067ea9ffa72fda95a4`. The four frozen source/test hashes also match the audit.

Read-only Git inspection confirms:

- `HEAD` is exactly `6c8984d62ea66a683c3eb9e668f605e2bdc8e140` and `HEAD^` is exactly `2aecc108067832c1825967e76bb52ddf5215cb4f`;
- changed production files are only `team_sports_baseline.py` and `ev_signal_sources.py`;
- the remaining changes are the owning audit, updates to `tests/test_team_sports_baseline.py`, and new `tests/test_team_sports_baseline_unknown.py`;
- no tracked local changes or whitespace errors were present.

The preserved JUnit XML supports the stated run totals, although author claims and XML totals are not by themselves semantic proof:

- `p4b3-round1-focus-01.xml`: 478 JUnit cases, 0 failures/errors/skips, consistent with 452 pytest passes plus 26 subtests;
- `p4b3-round1-original-acceptance.xml`: 4 tests, all green;
- `p4b3-round1-original-b3-open.xml`: the two genuine B3 tests remain red;
- `p4b3-round1-original-review-after.xml`: the omission witness is green and the withdrawn completed-only expectation remains red;
- `p4b3-round1-boundary-red-02.xml`: the six genuine simultaneous-status regressions were retained red before the final correction.

The new author tests have good coverage of direct unknown acquisition/reuse/failed-fallback, later unknown after adverse status, current unknown identity defects, strict timestamp ordering for a matching scheduled restoration, simultaneous conflicts, repeated partial fallback, strict owning counts and zero-row lifecycle withdrawal. They do not cover a conflicting determinate scheduled cohort followed by a later clean unknown cohort, which is the gap demonstrated above.

## Harness and Review Boundaries

- I ran only the two-case counterprobe described above with the repository quality Python, synthetic native-shaped inputs, the existing real normalization/SQLite/worker path, a unique basetemp and a separate JUnit file. I did not rerun the author's 452-case selection, original acceptances or historical REDs.
- No production source, author test, Git index/branch, provider, browser/UI, VPS, deployment, full suite, A0 or D4 artifact was modified.
- Synthetic source data and local worker execution do not prove live-feed availability, empirical model quality, profitability or safe bets.
- The count fix proves inconsistency only when the owning JSON count and published rows disagree. Coherently rewriting both remains outside its stated contract.
- Valid same-day partial views remaining visible through repeated failed refreshes is an authorized availability rule, not the withdrawn R2 defect; their original prediction/source observation/model cutoff bytes remain the relevant freshness boundary.
- Real B3 reference publication, the historical correction pipeline, injury/load effects, D4 replay and empirical approval remain package-(b)/later work.

## Assessment

**Task quality:** Needs one further R1 fix.

The direct unknown-status correction and Minor count closure are otherwise precise and well tested, with no observed gate, clock, odds or model-computation regression. Merge trust remains blocked because the current implementation can compose lifecycle permission from a contradictory scheduled revision with identity from a different later unknown revision, allowing a previously cancelled event to reappear in both consumers.
