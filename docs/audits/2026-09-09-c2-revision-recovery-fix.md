# C2 revision and recovery corrections — 9 September 2026

Controller fixes on original C2 `8cffd12da3c4db530e76fcd94aea3eb58e1c533a`.
The prior owning audit's hashes describe that original packet, not this fix.
This packet remains internal CPU/source mechanics, not a real basketball feed
or an empirically approved context model. All test receipts/fixtures are synthetic.

## Reproduced independent findings

Original independent report SHA256
`5b2af671ff6523a70c1d51aa8c442b04592d67803f070a21edfb2b742454c738`:

- F1/P1: a latest incomplete native participant correction lost the former
  team's ambiguous recent participation. An older game then falsely supplied
  exact rest and complete recent load, including through actual B1 SQLite/B2/B3.
- F2/P2: two case-distinct EuroLeague event IDs were merged by legacy casefold
  before the native-reference check. Checking only the selected receipt could
  wrongly certify the legacy projection as native identity.
- F3/P2: an old conflict blocked all current team workload, even when all
  actual terminal receipt bounds proved it irrelevant to each recent window.

The original 52 independent probes were preserved unmodified. Controller run
`c2-controller-original-red-02`: **8 failed / 44 passed**, 12.61 s. A new
permanent 22-case regression run `c2-controller-permanent-red-01` independently
reproduced **10 failed / 12 passed**, 5.71 s. No tolerance/acceptance was relaxed.

## Owning corrections and actual source-store boundary

1. Preserve full native participant lineage at the source identity seam:
   `subject_id = event_key + ':participants:' + digest({home_id, away_id})`.
   B1 selects latest per subject. Previously its actual SQLite query discarded
   the old participants before C2 could preserve them; direct tuple-only tests
   missed this. C2 still selects latest by whole event/kind, so old minutes do
   not revive. Same-participant revisions still supersede each other normally.
   A complete correction removes the former participant; an incomplete one
   keeps recent participation unknown instead of manufacturing exact recovery.
   This is an unreleased internal C2 v1 identity correction, no stored live-data
   migration and no generic B1 selector change. The original repository's exact
   subject assertion was changed to the exact new identity, not removed; the
   52 independent review files retain their original bytes.
2. Inspect all causal raw spellings of every contributing native event before
   latest-casefold receipt narrowing. A genuine same-native-ID repeat remains
   usable; a future spelling is not evidence available at an earlier cutoff.
   Unknown native mapping removes only the new reference, not the original
   available baseline or its unchanged legacy formula/output.
3. Retain conflicts as native proof records plus an actual upper-end bound only
   when every latest receipt is usable. Evaluate that bound per 1/3/7-day window
   and separately for latest exact rest. Only strict earlier bounds can prove
   irrelevance; equality or +1 microsecond remains unknown. Keep the bound and
   identity receipt refs with available derived features. No old conflict may
   repair the historical/current rotation actually needed by the roster feature.

The first correction run with source subject still event-only produced
**2 failed / 238 passed** (`c2-controller-revision-green-01`, 37.51 s); both
failures were the real SQLite effect path. The source-identity fix above closed
those failures: **240 passed** (`...green-02`, 36.37 s). This intermediate result
is recorded rather than presenting direct tuple coverage as end-to-end proof.

## Permanent controls and final controller checks

`tests/test_basketball_revision_recovery.py` now contains 32 permanent cases:
partial home/away and input-order permutations; each 1/3/7-day boundary at
-1/equal/+1 microsecond; separate rest bounds; old required rotation conflict;
real B1-to-B3 nonapplication of false exact recovery; causal vs future native
case collisions; actual SQLite participant revisions in both orders with both
partial and complete corrections; unchanged-participant latest vs future value
selection exactly once. Same-ID updates still work; corrected-away old minutes
stay absent. The original baseline and missing-approval behavior stay unchanged.

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`
with `-B -m pytest -q -p no:cacheprovider` and new isolated basetemps.

- `c2-controller-revision-green-03`: original 166 C2 tests, 32 new permanent
  cases and 52 original independent probes: **250 passed**, 50.61 s.
- `c2-controller-revision-full-20260909-01`: complete owning worktree suite:
  **3771 passed / 15 expected Windows/POSIX skips / 97 subtests**, 117.63 s.
- Changed files pass `git diff --check`; no D1/D2, generic B1, sports default,
  Cricket, price/ranking, historical forecast, ticket/ledger or VPS change.

Final independent re-review of these corrected bytes remains required before
Root merge. The successful controller suite alone is not independent acceptance.

## Frozen code and unchanged review probes (SHA256)

```text
9613030dce16c193e0eec8c215c68a33992bdb10532606692d08e8bef7d64505 context_models/team_sports.py
7e75bdfee94b68616665be7a27d23bba15566cda962082521c2e82c4b197a696 context_sources/basketball.py
f6d90d61f143754591efae950ffe93e2655a3476e59fd7dcf40dbed1193a88cd tests/test_basketball_context.py
c400d38941b8ee31831ff38e28ab22148d71b7fe29259699e0650feb7f142b20 tests/test_basketball_revision_recovery.py
4d21d7b3930dd64f4f965e05e6e776bf6fe1382576a528afd800db807ef9563d .pytest_tmp/c2-independent-20260909/test_c2_independent.py
1d1f0e054e523a29816bf9c602f63e24982e5cf2a6970707d217097efe920b94 .pytest_tmp/c2-independent-20260909/test_c2_receipts_and_effects.py
f2bf5075611553425b4d65ecfa52c9bc3592c7804f52ab1bf1b021ec62be27c3 .pytest_tmp/c2-independent-20260909/test_c2_conflict_negative_controls.py
```
