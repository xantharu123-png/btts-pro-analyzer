# Actual Tennis producer: original Root review, 9 September 2026

Decision: **REQUEST CHANGES**, one P2 finding, reproduced through two actual
publication entry points. This is the original negative result on frozen source
`32ac1d8ac739a51f84654c2c41fc27017c95cedd`, not an acceptance of its successor.
Audit-only `bdf123c173f3b882fe7c0075bda10a7b669c8270` leaves these sources unchanged.

## Actual finding: publication can be timestamped after its consuming append

The actual live worker publishes its immutable original A1 artifact at 12:30,
then accepts a Shadow append timestamp of 12:00:02 for the 12:00 decision.
The original's time is checked against the decision, but not against the actual
final consuming append. Both an explicit earlier append clock through the real
batch and a backward final clock through `scripts.tennis_daily.main()` succeed.
The latter prints one stored prediction and returns success. Neither raises the
expected `ContextContractError`. These are temporary real A1/B1/B3/Shadow writes
with synthetic clocks; no production access or market-price modification.

The original must retain its genuine decision time and native receipt time,
but a later-created reference target cannot truthfully have been available at
an earlier claimed publication/append time. Use the actual stored A1 `created_at`
on idempotent publication, not the requested new value. Reject backward clocks;
do not silently shift a timestamp or weaken the before-start check.

Approved narrow correction: an internal optional
`context_original_published_at` accompanies only the new original/context pair,
strictly validated before Shadow-file creation and again against the genuine
existing transaction append clock. No new database schema, serialized field,
legacy ID, price rule, source request, fitted coefficient or old-row rewrite.
Legacy absent-context calls retain their original clock path.

## Immutable independent evidence

Root witness directory:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/.pytest_tmp/tennis-live-root-review-20260909`.

- `test_root_publication_clock_findings.py`: SHA256
  `25399d669f97c0833484c712acb0afccd4cf40cfab09e54ecc41619ceedb938b`.
- Two cases: `test_explicit_shadow_append_must_not_precede_actual_original_publication`
  and `test_real_main_rejects_backward_append_clock_after_original_publication`.
- Both **failed**, `DID NOT RAISE ContextContractError`, no skips/deselections.
- Owning worktree `.pytest_tmp/root-live-clock-red-20260909-01.xml`: SHA256
  `01ef19cde6ef5c8725156fdaed5ab960428d80aaa9bd7ef1e28ea50b92687e46`.

The original witness and result must remain unchanged. Rerun their exact bytes
on a corrected successor before acceptance; add valid-clock positive controls
separately, including actual stored-time reuse and the final transaction clock.

## Initial Root probe preparation retained, not relabelled

First combined run: **166 passed, one reviewer harness error**. The state mutation
used nonexistent `state.platt_a`, rather than the genuine `state.cal_a`. This is
not a product finding. Also, its positive later-publication case accidentally
kept the helper's earlier explicit append clock. That permissive expectation
exposed the real finding above and is not a valid acceptance requirement after
the fix. A new qualified positive must use decision < publication <= append.
Neither initial test nor first result was overwritten to claim green evidence.

- Original `test_root_tennis_producer.py`: SHA256
  `329f39fc449f8f8a8ca114855a81c8b7a8e1ca0530ce6bcbc8ed4d7f87b17dba`.
- Initial owning worktree `.pytest_tmp/root-live-producer-review-20260909-01.xml`:
  `b1b8af7e1f74fb5098ea4cb6dea4df7665ec41017dfb175c5914594a9d86f695`.

Other bounded independent controls exercised unchanged actual model state,
shadow row association, idempotence with once-only B3 calculation, restored
context-manager scope, publication failure without dangling Shadow rows, and
exact reviewed code hashes. No empirical or source-coverage approval follows.

## Owning full-suite evidence is a pre-fix stage only

Owner completed **5,249 passed, 19 skipped, 97 subtests**, 1,067.06 seconds,
exit zero, on frozen 32ac sources. `.pytest_tmp/tennis-live-full-01.xml` SHA256
`11bec44ddc00a4e4e03bdc4ce1cba6eea05bdb29d7eceba950798685a1371d3f`.
This does not negate the independent missing-clock case and is not the final
integrated suite. No main push, server update, live context integration,
new bookmaker tip, empirical effect or cricket work is claimed here.
