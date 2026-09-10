# Task 1: fresh-input capacity diagnosis (2026-09-10)

## Scope and status

Read-only source/harness investigation against HEAD `b39789d54adf8c5c836a50782e276d3810349979`, retaining the Task 1 `c4e20e0` reader. No product, test, helper, installer, index, Git commit, or VPS changes were made by this investigation. This report is the only authored file. The systematic-debugging skill was used to distinguish observed facts from hypotheses before any implementation proposal.

The controller reports that the fresh complete 88-database backup and actual restore/HMAC checks passed, but the exact fresh-input D4 CLI did **not** complete: input 114929664 bytes; CPU 300.067 s; wall 300.163 s; exit -9; peak RSS 362972 KiB; no report; input unchanged. This is a genuine open acceptance gate, not superseded by historical measurements. CPU approximately equals wall and memory remains well below 1 GiB: repeated CPU work is a stronger initial hypothesis than memory exhaustion, but only the phase trace can identify its distribution.

Final diagnostic status: the bounded native trace below now confirms repeated cold construction and LRU eviction through the eighth original. It stopped before completing original verification, with no snapshot feature call reached. The initial hypothesis sections are retained as the pre-trace reasoning, not as claims that all ten requests were measured. The shared-basis recommendation remains subject to the pending user decision; there is no implementation authorization or successful fresh D4 acceptance.

## Confirmed workload difference

Controller-observed fresh inventory: 12 artifacts (10 live tennis originals, 2 tour states), 10 snapshots, 48307 receipts and 2 manifests. Receipt kinds: availability 748, base_fixture 110, confirmed_lineup 351, event_status 26098, workload 21000. All ten originals use ATP and the same state reference; there are five cutoff groups, two originals each. The artifact traversal order is 12:07, 16:37, 19:07, 14:07, 10:00, 12:07, 14:07, 19:07, 10:00, 16:37 UTC (full controller timestamps retained in its diagnostic evidence).

The previous real input had 47497 receipts, 6 artifacts and 4 snapshots. Thus only 810 additional receipts accompany six additional original checks and six additional snapshot consumers. The growth is not merely about database bytes.

`live-capacity-evidence-20260910.md` records exact c4 old-current acceptance at 192.065 CPU / 192.209 wall seconds, 348524 KiB, 104202240 input bytes. Its largest synthetic generation passed at 298.435 CPU / 298.846 wall, 354128 KiB, 188791 receipts. These remain valid evidence for those inputs only.

The ignored `build_synthetic_capacity_generation.py` deliberately retains the original six artifacts/four snapshots while adding receipts with clocks shifted by generation days. It exercises full physical validation growth, but does not exercise five causal cutoff pools and ten replay consumers. It therefore cannot stand in for this fresh workload.

## Source-grounded repeated work

1. `context_runtime.py::_verify_connection` completes physical receipt validation before original and snapshot replay. `VerifiedReceiptMapping.validate_all` checks every physical content and receipt, including future/unreferenced material, before granting cutoff traversal. This must remain intact.
2. `context_runtime_tennis.py::verify_live_originals` processes every original in artifact mapping order. `_verify_live_original` resolves/decodes its tour state and validates its own publication and prediction even if another original has the same state. It requests history per original.
3. `EncodedHistoryCache` has the unchanged 64 MiB aggregate encoded-byte budget. Each distinct `(cutoff, tour)` is a separate fully encoded history. A covering hit selects the nearest completed later cutoff, decodes its prefix, and `_replay_history` subsequently stores that prefix as another complete entry. Such a store can evict the covering source or a different later pool.
4. The historical two entries were each 28432021 bytes. If fresh entries remain near that size, only two fit. Five groups in the observed nonchronological order can repeatedly discard later pools and require another cold scan. Exact cache `misses` are **not** cold rebuild counts: a miss can be satisfied by covering reuse.
5. A cold scan runs the unchanged owning receipt decoder and per-row tennis selector over eligible rows. No new participant/tour/source pruning may bypass their validation. The selector validates eligible selected receipt material before its tour filter.
6. Every snapshot calls the unchanged owning `tennis_features_v3`; its `_history` validates every selected receipt before participant/event pruning. Encoded cache hits avoid cold selection, not those ten full owning model validations. Reusing one state or one cutoff is not proof of identical event-specific feature results.

An additional measurable cost is lifetime checking: covering lookup performs two `_check` calls per examined row, each reading both schema versions; storing the result checks again and canonical-serializes every row. Completed `values_at_or_before` checks its validation stamp before decode, after decode and after consumer resumption (two schema PRAGMAs each). These are concrete profiling surfaces, **not** permission to remove transaction/schema invalidation guards.

## Initial hypothesis and falsifiable prediction (before the completed trace)

Hypothesis: consumer/cutoff growth combines repeated cold history construction after LRU pressure with additional mandatory owning snapshot work. This explains why the smaller fresh DB can fail where much larger fixed-consumer synthetic input passed.

Under the explicit **unmeasured assumption that exactly two fresh entries fit**, the ten-original order predicts five cold constructions, four covering reuses and one exact hit: cold 12:07; cold 16:37; cold 19:07; covering 14:07; covering 10:00; covering 12:07; exact 14:07; cold 19:07; covering 10:00; cold 16:37. This excludes the subsequent ten snapshot requests and is not a claim that the failed CLI reached every original. A fresh entry-size/cache trace must confirm or falsify it.

If no evictions or no additional cold constructions occur, this specific LRU explanation is falsified. If physical validation time increases disproportionately to the receipt growth, inspect actual serialized payload sizes and owning-decoder cost before attributing the increase to consumers. If original replay remains bounded but snapshot time grows, the repeated owning model-validation phase is the stronger cause. Nested cumulative profile times must not be summed.

## Minimal bounded diagnostic surface

The controller ran an observational phase/cache trace as the application UID, with source/input unchanged. Useful records are phase start/end CPU and wall; history request cutoff/tour and consumer phase; actual `_cold_replay_history` calls; cache before/after hits, covering_hits, stores, evictions, bypasses and entry_bytes; and number of selected rows. Do not log receipt bodies, participants or credentials. Keep existing hard ceilings; an intentionally bounded diagnostic may finish without a D4 report and is not acceptance.

Existing ignored harnesses provide reusable observation points: `observe_capacity_cache_api.py`, `profile_first_context_history.py`, `profile_capacity_physical_receipts.py`, and `inspect_capacity_replay_groups.py`. Their old hardcoded DB identities/count assertions must not be silently accepted for this fresh input: a controller adaptation must bind the actual fresh SHA/size, exact source revision and confirmed 12 artifacts / 2 manifests / 48307 receipts / 10 snapshots, independently inventorying the content and rollback counts rather than inferring them. The cache observer should return the real cache instance and preserve all wrapped return values/exceptions. Profiling windows, not replacement validators, can separate canonical encoding, owning decode/selection, model `_history`, and schema-check overhead.

## Preserved boundaries

No budget increase, receipt/history truncation, skip of unreferenced/future physical rows, semantic fallback, model memoization, artifact reordering, or change to source/model/history/ticket behavior is authorized by this diagnosis. Stage helper `1441158...`, A0/P4b3 and installed helper pins remain unchanged. Any later explicitly approved implementation requires independent semantic/security review plus fresh exact CLI acceptance on the actual sealed input; diagnostic timings and the old synthetic pass are not substitutes.

## First native trace and architectural assessment

The controller subsequently reported the first bounded native trace on unchanged b397 source, application UID 997: complete physical `_verify_observations` took 29.238 CPU seconds; first 12:07 history was cold, 62.619 CPU seconds (64.385 including history-store composition); its canonical entry was exactly 28432021 bytes, one store. At elapsed 101.899 seconds, the next 16:37 request started another cold construction. Thus the first fresh pool has the historical size, physical validation is not the initial dominant expansion, and increasing-cutoff originals really do force repeated cold work. The remaining trace is still needed to establish the actual later eviction/rebuild sequence; these initial results alone do not prove all five predicted cold constructions.

At the controller's request, the following is an architectural recommendation, not implementation authorization. A single reviewable work unit is preferable to another isolated LRU tweak:

- Represent a tour's completed, owning-selector-validated history as one immutable canonical encoded basis at the maximum cutoff actually demanded by its validated original metadata. Represent earlier cutoffs as prefix bounds/byte counts over that basis, not separately stored duplicate histories. The existing covering-cache argument supplies the starting semantic proof: owning selected row evidence is cutoff-independent, and the completed basis is sorted by observed_at/digest. This property must remain explicit and tested.
- Plan required cutoffs from validated original publications, after complete physical inventory proof. Do not use raw SQL flags, participant hints, or table membership as substitutes for owning validation. Preserve every original, including unreferenced safe originals, and every snapshot check. Preplanning may move the timing/order of failures; review whether exact failure precedence is contractual, not only whether successful reports match.
- Keep one verification-local owner of counted encoded bytes, bound to the exact receipt inventory and transaction/schema generation. Cutoff descriptors must not retain evicted encoded pools outside budget accounting. Multiple tours remain subject to the same total 64 MiB budget, with complete cold fallback if a basis cannot be retained. No persistent cache, decoded-inventory retention, model-result memoization, or new installed helper is needed.
- Every original/snapshot consumer still materializes its own fresh nested dictionaries/lists as the exact tuple expected by the existing owning interfaces. Check the complete prefix's canonical input size against the unchanged per-history budget; never return a truncated prefix merely to fit. Existing invalidation and mutation boundaries must be preserved around materialization. The unchanged `tennis_features_v3` and `_history` must validate their inputs again for each event-specific snapshot.

This targets redundant cold decoding/selection, duplicate canonical encoding/stores and pressure-induced rebuilding together. It deliberately does not claim to remove the ten mandatory owning feature calls. With physical validation at 29.238 CPU seconds and one cold history at 62.619, about 91.857 CPU seconds are already committed before remaining original/model/materialization work. Older owning feature timings were about 14 seconds each on a different reader/profile; ten such calls would contribute roughly another 140 seconds. That is only a hypothesis-guiding arithmetic estimate, not a fresh total-time prediction or a promised 300-second pass.

The bounded RED/review surface should include five interleaved cutoffs at two-history-equivalent memory pressure; duplicate cutoffs; fresh-consumer mutation isolation; covering versus cold canonical equivalence; equal-time receipts and future boundaries; both tours and total-budget pressure; oversize bypass; complete unreferenced/malformed physical inputs; transaction end/restart, writes and main/temp schema changes; protected opaque receipt behavior; exact public report/limitations; and unchanged owning feature call count for all ten snapshots. It must detect an encoded basis accidentally retained by descriptors after eviction. Resource acceptance remains an exact uninstrumented CLI run on the actual fresh sealed DB, not a mocked speed assertion.

## Completed bounded native trace

The controller's final diagnostic used the application venv as UID 997 against unchanged b397 source and the same sealed input. The first system-Python probe lacked Pandas; that unsuccessful environment probe is not the measured run. In the actual run, observational wrappers preserved the original functions' return values. The CPU-275 diagnostic stop completed with 276.411 CPU / 275.792 wall seconds, peak RSS 360448 KiB, input unchanged and **no complete verification**. This is separate from the uninstrumented CPU-300 D4 failure recorded above.

| Original request | Observed history behavior | CPU seconds |
| --- | --- | ---: |
| 1, 12:07 | Completed cold build; first store | 62.619 cold; 64.385 history composition |
| 2, 16:37 | Completed cold build; second store | 67.941 cold |
| 3, 19:07 | Completed cold build; third store causes first eviction | 68.279 cold |
| 4, 14:07 | Covering reuse plus new store/eviction | 3.538 |
| 5, 10:00 | Covering reuse plus new store/eviction | 3.359 |
| 6, 12:07 | Covering reuse plus new store/eviction | 3.922 |
| 7, 14:07 | Exact cache hit | 0.757 |
| 8, 19:07 | Fourth cold build begun, interrupted by diagnostic stop | 16.740 partial cold |

All three completed cold histories encoded to exactly 28432021 bytes. Final cache state: hits 1, covering_hits 3, misses 7, stores 6, evictions 4, bytes 56864042, peak_bytes 67107824, pending_bytes 0. No store was published for the eighth request because its cold build was interrupted. The exact-miss counter correctly includes the three successful covering reuses.

`verify_live_originals` consumed 239.528 CPU seconds before interruption. **No snapshot feature invocation was reached.** The record therefore confirms the predicted cold/reuse/eviction path through original 8, including rebuilding the already-built 19:07 pool after its eviction. It does not establish completion of that fourth cold build, a fifth cold build, or any of the ten fresh snapshot feature durations. The full future cost of unchanged owning feature checks remains an additional unmeasured acceptance risk, not an observed cause of this diagnostic stop.

The demonstrated cause is redundant original-history construction under the actual cutoff order and fixed cache pressure. The proposed shared immutable basis addresses that demonstrated duplication, but its implementation and resource acceptance remain unapproved/unproven. No code change or limit increase follows from this report update.
