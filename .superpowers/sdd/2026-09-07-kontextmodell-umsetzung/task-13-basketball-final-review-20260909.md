# C2 final independent re-review — 2026-09-09

Disposition: **PASS for the bounded F4/F5 source/CPU correction.** No new
actionable finding against the frozen three-file implementation. This is not a
real player-feed, empirical, D3-worker, user-interface or production approval.

## Exact reviewed state

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c2-basketball-20260909`.
Review began on `0d6accca7d3273d125ae080b3a1254ee506dea57` plus exactly the three
controller WIP files. Controller committed those identical bytes during review
as `23aa21c6cd41aad159439821941f5fb2d0d6a449`, adding only the separately read
cutoff/schedule-lineage audit. Final tracked worktree is clean. All pinned
source/test hashes were verified at entry and after the final execution.

Read the full three-file implementation/test delta, owning basketball source,
relevant complete B1 storage/selection implementation, C2 selection/feature/
effect interfaces, and the complete new owner audit. Generic B1, B2, B3,
original Ridge/Cricket code and contracts were not modified by this correction.
This reviewer changed only independent files under its existing `.pytest_tmp`
QA directory; no Git, provider, production, monetary or VPS mutation.

## Independent execution

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`,
`-B -m pytest -q -p no:cacheprovider`; every basetemp new.

1. `c2-final-original-20260909-01`: **319 passed, 118.94 s**. Original C2 166,
   current permanent revision tests 56, original independent 52 and unchanged
   second independent 45. This closes original F1/F2/F3 and actual-end F4.
2. `c2-final-owning-20260909-02`: **44 passed, 35.54 s**, newly written
   independent tests in `test_c2_owning_final.py`.
3. `c2-final-wrong-reader-20260909-01`: **2 failed, 4.19 s, exit 1**. The
   original F5 tests deliberately continue to use generic exact-schedule B1.
   Both retain the false 36-hour-rest result and remain negative integration
   evidence, unchanged and NOT counted as green or silently rewritten.

Thus 363 positive tests passed in TWO separate runs, not a combined 363 run.
The 2 wrong-path diagnostics remain separately red. No fresh independent full
suite was required by this bounded follow-up. Controller's full result in the
hash-verified audit is **3795 passed / 15 expected platform skips / 97 subtests,
129.05 s**; it is explicitly controller evidence, not this reviewer's execution.

Own-probe harness note: first run `c2-final-owning-20260909-01` was 43 passed /
1 failed, 44.15 s. The new synchronous writer-during-reader probe initially
assumed WAL while SQLite actually used DELETE mode; the writer correctly
blocked on the held read transaction. Only that own setup was changed to
explicitly set and assert `PRAGMA journal_mode=WAL` in its private test database.
No source was changed and no concurrency assertion was removed. The final
probe performs a real successful append during row decoding, verifies the
first query retains its old transaction snapshot, then verifies the next query
sees both authentic receipts. It uses no sleep/race-probability assertion.

## What the 44 new tests establish

- 12 actual source -> B1 SQLite -> owning-reader cases: native participant
  leaves and returns through THREE schedule revisions, both orientations,
  complete/incomplete latest revision and three insertion permutations. All
  three causal receipts survive; calculated features equal the exact direct
  source replay byte-for-byte. Only latest revision values contribute.
- Those 12 cases also fit real B2 identity-margin heads and call C2/B3. Complete
  comparisons stay experimental; incomplete ones are not applied. Used base
  parameter and market bytes never change; approval is null and certified
  market list empty.
- Six incomplete schedule-correction receipt boundaries at cutoff -1/equal/+1
  microsecond, both sides. Future receipts cannot erase or certify a prior fact;
  causal incomplete correction cannot restore old minutes or exact recovery.
- Four equal-time, different-schedule participant conflicts with both insertion
  orders remain conflicting, rather than being sorted, averaged or discarded.
- Six current rotation/availability checks: a newer unknown, expired or not-yet-
  effective row cannot be healed by an older healthy other-schedule collection.
- Seven valid B1-hash but invalid owning-source claims reject: source,
  competition, kind, completeness, invented publication, status and future
  terminal-result clock. Hash identity is not provider truth.
- Four actual missing-content corruptions are detected before future-receipt or
  other-schema filtering; valid unknown schema and future import stay unused.
- Authentic repeated fetches retain distinct receipt identities and one content
  identity, correct UTC chronology and actual receipt-based effective time.
  No archive/publication claim is manufactured.
- Two case-sensitive Euroleague native event lookups preserve exact IDs rather
  than collapsing differently cased IDs. The actual WAL snapshot probe above
  confirms coherent local reads under a concurrent append.

## Explicit remaining caller boundary

`basketball_observations_as_of` is the owning historical pool API, not a generic
B1 replacement. D3 must collect the relevant native history with this API and
pass the full causal appearance lineage to C2; current rotation/availability
must retain the exact requested current schedule. A filtered generic-reader
pool does not certify historical lineage. The still-red original F5 diagnostic
is the permanent evidence of that misuse. No live D3 caller is demonstrated by
this CPU package; its real worker integration and end-to-end tests remain open.

The source schema is still an explicitly internal, synthetically exercised
transport, not a working ESPN/Euroleague roster feed. No learned improvement,
D1/D2 acceptance, source readiness, live activation, money or Cricket change
is inferred from this PASS.

## SHA256 manifest

```text
6d93c2b77ce5f0085cb1861edcc9524d3064b84faa772b501bf8481fedfb7228 context_models/team_sports.py
b68f39bb176e4f09ad49327859e088524bcf68960e3b29bd5b66f5347eeef039 context_sources/basketball.py
930cf704978437021b58ec73d1a31a0757c73e9d2c928833ec873f40503137b8 tests/test_basketball_revision_recovery.py
f6d90d61f143754591efae950ffe93e2655a3476e59fd7dcf40dbed1193a88cd tests/test_basketball_context.py
9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226 context_observations.py
6caa81aa7ac7f188cfef689b688cc0deb452515b8ba8f7fad2f8e5b2f27d6dac context_snapshots.py
763b105a712418c8963b6f620ecea75eb8b42fec54b3775f9587c6e235737b9d context_models/contracts.py
fc1253fbeb0888870715c21238d4da78de2c0cbe19fee910da67ebfd35b756d7 sports_prematch.py
ce3321cdbd0d96569c7133d0192230ec66954b49a9fc00a6ec831839baca2ebe docs/audits/2026-09-09-c2-cutoff-schedule-lineage.md
4d21d7b3930dd64f4f965e05e6e776bf6fe1382576a528afd800db807ef9563d .pytest_tmp/c2-independent-20260909/test_c2_independent.py
1d1f0e054e523a29816bf9c602f63e24982e5cf2a6970707d217097efe920b94 .pytest_tmp/c2-independent-20260909/test_c2_receipts_and_effects.py
f2bf5075611553425b4d65ecfa52c9bc3592c7804f52ab1bf1b021ec62be27c3 .pytest_tmp/c2-independent-20260909/test_c2_conflict_negative_controls.py
8680ccfcf7282feeb64b5a54d9f4a6e156f937906b74c3083e1d620b79b98cba .pytest_tmp/c2-independent-20260909/test_c2_rereview.py
b1328ac79ee457e7fd101d378bfd36122a9fb46421c0a50eb70410d07e4da429 .pytest_tmp/c2-independent-20260909/test_c2_schedule_lineage_rereview.py
496a146d9f2a7a404af0944f14d8ff010f7881c599d71bbdef238feba5124c4d .pytest_tmp/c2-independent-20260909/test_c2_owning_final.py
5b2af671ff6523a70c1d51aa8c442b04592d67803f070a21edfb2b742454c738 .pytest_tmp/c2-independent-20260909/review-c2.md
31dc3a793fa8a7ea9756f878bd958ce794d9bda9e66236bc8d12dcd31691ec5c .pytest_tmp/c2-independent-20260909/rereview-c2.md
```
