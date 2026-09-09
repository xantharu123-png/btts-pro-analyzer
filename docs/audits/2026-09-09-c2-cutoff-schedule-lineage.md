# C2 exact-end and schedule-lineage corrections — 9 September 2026

Controller follow-up to `0d6accca7d3273d125ae080b3a1254ee506dea57`.
This is unreleased internal source/CPU mechanics on synthetic fixtures. It does
not establish a working player feed, empirical improvement or D3 integration.

## Independent second review and preserved negative evidence

The unchanged second report `rereview-c2.md` has SHA256
`31dc3a793fa8a7ea9756f878bd958ce794d9bda9e66236bc8d12dcd31691ec5c`.
It closed the three original findings with 250 passing tests, then found:

- F4/P1: dropping a completion exactly at the decision cutoff from the rest
  timeline substituted an older game and overstated exact recovery. A separate
  45-case run had 43 passed and 2 failed.
- F5/P1: simultaneous participant and schedule revision through the generic
  exact-schedule B1 reader lost the former participant's uncertainty. Its
  separate two-case diagnostic failed twice. This was an owning integration
  error, not a defect in the generic reader's explicit exact-revision contract.

Those were three separate runs, not a single combined 297-case execution.
All original review reports and probes retain their original bytes. In
particular, the two F5 probes using the wrong generic reader deliberately
remain negative integration evidence. They are not relabelled as passing.

## Corrections

1. Include an actual completion `<= cutoff` in the exact-rest timeline. Every
   performed-load window still uses `< cutoff`; an end at the upper boundary
   does not enter a 1/3/7-day total. End and receipt must both be causal.
2. Add the owning `basketball_observations_as_of(path, event_key, *, cutoff,
   schedule_revision)` reader. It verifies real persisted B1 receipt/content
   identities, retains all causal appearance revisions across schedules, and
   restricts current rotation/availability to the exact requested revision.
   C2 still owns latest-value selection and complete/partial correction handling;
   old participant proof does not restore obsolete minutes.
3. Validate scope and aware cutoff before opening a database. Corrupt stored
   clocks/content/index fields raise integrity errors rather than turning into
   missing data. Other legitimate source schemas are not interpreted as this
   internal basketball transport. No generic B1 selector change or data migration.

The permanent file grows from 32 to 56 cases: both orientations and input
orders, exact-end/receipt microsecond boundaries, complete/partial corrections,
actual SQLite schedule-plus-participant lineage, current rotation/future
revision selection, invalid scope before file creation, and three real database
corruptions. All eight corrected schedule-lineage cases exercise actual fitted
B2/C2 and B3: without approval the used parameters/markets remain exactly base.

## Controller evidence

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`,
`-B -m pytest -q -p no:cacheprovider`, unique isolated basetemps.

- `c2-controller-cutoff-lineage-red-01`: **10 failed / 4 passed / 32 deselected**,
  8.21 s: two exact-end failures and eight absent-owning-reader failures.
- `c2-controller-cutoff-lineage-green-01`: **14 passed / 32 deselected**, 16.72 s.
- `c2-controller-all-corrections-green-01`: **319 passed**, 113.43 s. Exact
  inventory: original 166 C2 + permanent 56 + original independent 52 + second
  independent 45. The two unchanged wrong-reader diagnostics are not included.
- `c2-controller-final-full-20260909-01`: **3795 passed / 15 expected
  Windows/POSIX skips / 97 subtests**, 129.05 s.
- Diff whitespace check passed. No Cricket, price/ranking, account/ticket,
  generic B1, D1/D2, production history or VPS change.

Independent final re-review of these frozen bytes is requested and remains
required before Root merge. D3 must call the owning reader; tests of the pure
adapter alone do not establish that the live worker does so.

## Frozen bytes (SHA256)

```text
6d93c2b77ce5f0085cb1861edcc9524d3064b84faa772b501bf8481fedfb7228 context_models/team_sports.py
b68f39bb176e4f09ad49327859e088524bcf68960e3b29bd5b66f5347eeef039 context_sources/basketball.py
930cf704978437021b58ec73d1a31a0757c73e9d2c928833ec873f40503137b8 tests/test_basketball_revision_recovery.py
f6d90d61f143754591efae950ffe93e2655a3476e59fd7dcf40dbed1193a88cd tests/test_basketball_context.py
8680ccfcf7282feeb64b5a54d9f4a6e156f937906b74c3083e1d620b79b98cba .pytest_tmp/c2-independent-20260909/test_c2_rereview.py
b1328ac79ee457e7fd101d378bfd36122a9fb46421c0a50eb70410d07e4da429 .pytest_tmp/c2-independent-20260909/test_c2_schedule_lineage_rereview.py
```
