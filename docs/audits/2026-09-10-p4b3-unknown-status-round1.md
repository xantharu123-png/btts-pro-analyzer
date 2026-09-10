# P4b3(a) Round 1: unknown status preserves the unchanged legacy baseline

2026-09-10. Based on `2aecc108067832c1825967e76bb52ddf5215cb4f` in
`codex/kontext-p4b3-baseline-20260910`. This is the controller-authorized narrow
correction of the independent review, not package (b), a new context effect,
or deployment. Exactly two source files, two test files and this audit change.
No full suite, provider call, SSH/VPS, push, money/store, generic B1/D4, source
adapter, model formula, UI or Cricket change was made in this round.

The whole original review, including its **R2 WITHDRAWN** addendum, was read
before changes. Its original two-case probe and XML remain unchanged. The
original implementation audit is also unchanged; this report supersedes its
incorrect implicit unknown-status withdrawal behavior. Review/TDD verification
was performed in the already approved worktree; no additional agent was spawned.

## Disposition and behavior

**R1 fixed for the bounded shared legacy worker.** One native `unknown` state
is not evidence against an otherwise valid legacy prediction. Acquisition,
six-hour reuse and failed-refresh fallback now keep that same base visible in
both normal and Risk catalogs. Missing native receipts likewise do not create
a new qualification gate. No original prediction, source-observation time,
model/history cutoff, probability, identifier or persisted view is retimed.

This does not ignore known contrary evidence:

- The latest native identity cohort must still have complete, consistent
  participants and schedule. Known original/native participant, schedule,
  season or format contradictions reject the old view. Missing raw legacy IDs
  alone are not newly interpreted as proof against the base.
- Native alias ambiguity and simultaneous whole-revision conflicts retain the
  existing rejection behavior. Equal-time `scheduled` and `unknown` are a
  conflict, not one merely missing status. Actual B1 source validation and
  causal receipt selection are unchanged.
- The lifecycle decision uses the newest **determined** status cohort from the
  full relevant causal lineage. A later `unknown` or merely `not_completed`
  cannot erase a proven cancellation/start/completion. Equal-time adverse and
  scheduled claims stay adverse; only a strictly later known scheduled revision
  clears the earlier adverse status. The actual kickoff check still prevents
  calculation or display once the event has started by the decision clock.
- Both catalogs consume the same current selection; this introduces no second
  fetch, target fit, prediction, source clock or model publication.

**R2 is withdrawn, not repaired by adding a new gate.** `failed_batch` is
unchanged. Previously validated same-day partial views can survive further
source failures. Two new positive cases each perform three actual failed
refreshes and verify identical old view/prediction/observation/cutoff bytes,
`partial`/`source_failed` attempt metadata, immediate retry and no extra target
calculation. The old review witness still asserts the unauthorized completed-
only policy and therefore remains RED; it is not an outstanding defect and is
not renamed, edited, xfailed or reported green.

**Minor closed in the existing publication contract.** After full owning row
validation and before the current-time projection, every stored BB/NHL batch's
`sources[sport].candidate_count` must be an actual integer, not bool or float,
and equal its published owning model-row count, including zero. The unchanged
reviewer's single-row-omission witness now fails closed. Legitimate lifecycle
withdrawal with a historical batch entry and zero current rows remains valid.
This detects omission with unchanged publication metadata. It is **not** a
reconstruction of every historic filter decision or an authenticity proof
against coherently rewriting both the JSON rows and the count. No schema,
database, artifact, refit or generic RiskStore change was introduced.

## Preserved open boundaries

The four unchanged original real-worker visibility/clock acceptances pass.
The two unchanged original B3-reference acceptances still fail because the
shared legacy snapshot has `context_ref=None`. Two missing references are not
a verified common B3 reference. Package (b), native historical replacement,
deduplicated original/history transport, its owning D3/D4 replay and genuine
empirical context activation remain separate work.

The normal BB/NHL boundary remains explicitly RESEARCH/null uncertainty: no
zero haircut, invented conservative probability/minimum odds, price gate or
money candidate. `CompletedHistoryStore` remains the existing baseline, not
backdated native B1 proof. Synthetic native-shaped responses and real local
SQLite/model/worker execution do not prove real feed availability, browser UX,
profitability, full-suite integration or production readiness.

## RED / GREEN evidence

All filenames below are under the owning ignored `.pytest_tmp`. No earlier
XML was overwritten. Exit-1 outcomes are retained as such.

| File stem | Actual result / meaning |
| --- | --- |
| `p4b3-review-original-before-round1` | 2 failed, 2.64 s: real omission Minor plus the withdrawn R2 expectation. |
| `p4b3-round1-red-01` | 18 failed / 62 passed, 14.52 s: six unknown acquisition/reuse/fallback errors, two later-scheduled restoration errors, ten count/omission errors. |
| `p4b3-round1-green-01` | 80 passed, 12.33 s after the first source correction. |
| `p4b3-round1-boundary-red-01` | 8 failed / 12 passed, 4.89 s: six real simultaneous-status regressions in the first fix, two own harness errors from calling `len()` on an integer request counter. |
| `p4b3-round1-boundary-red-02` | 6 failed / 14 passed, 4.78 s after fixing only those counter assertions. The six genuine source failures remained. |
| `p4b3-round1-focus-01` | **452 passed / 26 subtests**, 29.14 s; 205 owning cases plus 247 existing focused cases. Includes the corrected simultaneous-conflict guard, 76 new cases, exact-parent default math/ID/float controls, retry/clock, null-price, actual thread/process exclusion and Cricket parity. |
| `p4b3-round1-original-acceptance` | **4 passed / 10 deselected**, 4.42 s; original visibility and post-acquisition clock tests unchanged. |
| `p4b3-round1-original-b3-open` | **2 failed / 12 deselected**, 3.93 s; genuine deferred B3 reference boundary unchanged. |
| `p4b3-round1-original-review-after` | **1 passed / 1 failed**, 3.66 s: original omission witness GREEN; original withdrawn completed-only expectation still RED. |

The focused run used the existing quality Python with `-B -m pytest -p
no:cacheprovider -o "pythonpath=. tests"`, a new basetemp and new JUnit path:

```text
tests/test_team_sports_baseline.py tests/test_team_sports_baseline_unknown.py
tests/test_wettfinder_automation.py tests/test_ev_signal_sources.py
tests/test_wettfinder_surface.py tests/test_riskobet_candidates.py
tests/test_riskobet_automation.py tests/test_sports_prematch_original_capture.py
tests/test_completed_sports_history.py
```

Original acceptances were executed directly from the unchanged owning preflight
file using `--rootdir=.` and their existing functional test-name selections.
The independent reviewer probe was run whole, preserving its withdrawn failure.
`git -c core.autocrlf=false diff --check` is clean. Source/test bytes are now
frozen for independent re-review; no additional full suite was started.

## Frozen SHA256

```text
212bff429b3a9266a68b77faad0600182ba6c5d8f6890f7957a5fd3cd9c333bb team_sports_baseline.py
0b3b20d6136273c0e4fbb4066f5a321f69731b83e292fa9accb042ef4a1cc277 ev_signal_sources.py
907b7d0f8365b14db6b46a11df51f42a92e365e5dc0518ce84ee6c0987dce6df tests/test_team_sports_baseline.py
8f45f3bc7960fdda3ee4f9969cdda9a1f6ed42b95fbcb65ebd4df4457b4af935 tests/test_team_sports_baseline_unknown.py
```

Read and preserved source evidence:

```text
a72fa65f22eed60370522040b19caf91fc40311dcda2498d15e4967e6b9e274c docs/audits/2026-09-10-p4b3-shared-baseline.md
666a0f0da3a41c3775fe9ab4c075344e312f3cf2e7afaf14558034d5c3d82929 ../kontextmodell-20260907/.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-18-p4b3a-independent-20260910.md
14945d3a31bd9ccb860ca10ed8aa715a0aed729f8709c1395aeedc277dbe547e .pytest_tmp/p4b3-independent-review-20260910/test_p4b3_contracts.py
853783250150050c6029552a8d59efc0461c33b3c60c437cb8a55425ca6954be ../kontextmodell-20260907/.pytest_tmp/p4b3-worker-preflight-20260910/test_worker_seams.py
87451d71ed02967c2d4977baf95e7f59f3bddf39866e92906eb0746231a4c928 .pytest_tmp/p4b3-original-b3-open-final.xml
```

Round evidence:

```text
d8760e7e157a54db7f16debb9aa8e823a152ef1ab43a23dd2f59e871b7058f8f .pytest_tmp/p4b3-review-original-before-round1.xml
4a46f7dcc006371b55624cf5f537bacc23eefa9c1b4e6f09f9bbe70228bd50e4 .pytest_tmp/p4b3-round1-red-01.xml
5dd1c9a99c62b2b5c0011fa0844f3819dec22366d8305a9bbb4dfcdc46612f7c .pytest_tmp/p4b3-round1-green-01.xml
c8646ce108a81eaea2fa8173c7d064828587a0fbefde888e0cfbe79e255f63a9 .pytest_tmp/p4b3-round1-boundary-red-01.xml
89fa85bf1a12c4e7e294ebbe842c056eeefbd2383ac0eff8f2308fccbe13990f .pytest_tmp/p4b3-round1-boundary-red-02.xml
4fe8b6aa6d859178fe57979a96bcfee2043b01d6af48265deea334051b7c7cee .pytest_tmp/p4b3-round1-focus-01.xml
6e6e503e366030f23677e59f9e158e851113d9555bc38a93daede583c27491d7 .pytest_tmp/p4b3-round1-original-acceptance.xml
6153a237d20ca0fee65b4abb7f396e334e1604e35fc9c3d5a3b9804c68a8004c .pytest_tmp/p4b3-round1-original-b3-open.xml
8737b4a9fa3d9b315ab14b2ce89c0307495d6bb1b7882ab9d1da7cbd1948a4f2 .pytest_tmp/p4b3-round1-original-review-after.xml
```

The focused commit and this audit's hash are reported separately. Root owns
integration, independent re-review and any later broader/runtime release steps.
