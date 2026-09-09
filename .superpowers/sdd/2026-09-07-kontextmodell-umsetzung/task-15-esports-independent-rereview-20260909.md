# C4 first fix — independent re-review, 9 September 2026

**Original C4-R1/R2 probes pass; one adjacent cancellation-retention defect
remains. Changes required before C4 acceptance.** This finding is a concrete
extension of the same R1 lifecycle, not a reinterpretation of the earlier
cancelled=unknown positive control.

Target: clean worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c4-esports-20260909`,
commit `79763a179b3efdd67c9f6d8ae6bd1c0d2032e3a2` on `26e8910`.
The full new correction audit, complete four-file diff, all 35 new permanent
cases and the relevant whole-event/status selector were read. No target source,
test, prior review/probe, Git state, API/provider, production or VPS mutation
was made. Only the new ignored review directory and test-run outputs were added.

## Confirmed progress

The exact original 67 independent cases remain byte-identical and now all pass.
Together with the 131 previous C4 tests and 35 new permanent regressions, the
independent run produced **233 passed in 84.42 seconds**, no skips.

This confirms the original completed->started issue and signed-difference
tolerance issue are fixed. The source's explicit owning status-subject-v2 keeps
actual intermediate status receipts instead of rewriting historical receipts;
old unversioned identities are rejected rather than silently migrated. New
terminal-series ends are checked against actual known completed map ends.
Normal forward status progression and true zero effects stay intact.

The prior reviewer probe hashes remain:

- `test_independent_c4.py`:
  `1504b746aa9e19eaf44a485cf0ad391414adacfd091559a1e90cba164371bd2b`.
- `test_additional_c4.py`:
  `777cd1c2aabcf54777ee4df9b4395a68076d19738a2dc428e96e699bd9f0df5e`.

The actual new 233-test JUnit artifact is
`.pytest_tmp/c4-independent-20260909/fix-01.xml`, SHA256
`dce1b5b109f4fcfcdae3e1079248a5972c447154c1c9f2ed9051baa6b4c90120`.
The owner's 4189/18/97 full run is prior evidence, not a new reviewer full run.

## C4-R1b — a cancelled parent can still revive an old series end

Priority P2. Owning location: `context_models/esports.py:162-171`.

`withdrawn` recognizes cancellation only if it is the newest event status.
The new retained-history `terminal_retracted` clause examines **started only**.
Consequently a true later `cancelled` parent event received through a map or
observed-lineup fact is retained by Subject-v2, but ceases to invalidate an
older series completion when another map/lineup later says `completed`.
That other fact is still not a fresh series result/actual series end.

Actual normalizer -> B1 SQLite -> causal selection reproduction:

1. The original native series ends 09:00, result received 09:01.
2. At 10:00, a map or observed lineup explicitly carries that same native
   parent event as `cancelled`; all cancelled result/lineup fields are correctly
   empty under the closed source schema.
3. At 11:00, the same non-series fact reports a completed parent again. Its
   own map ends at 08:00 (or it contains an observed lineup), so this is not
   the already-fixed series-end-before-map-end inconsistency.
4. At cutoff 12:00 for target start 18:00, the code reinstates the old
   `observed_series_count_1d_<side>=1` and exact recovery `9.0`, even though no
   new terminal series receipt has been supplied after the cancellation.

Both historical statuses are present in the actual returned B1 observations.
This is not a lost/caller-forged receipt or a source clock guess. All four new
negative cases fail: map and observed-lineup cancellation, independently for
each target participant. Failure location:
`test_c4_lifecycle_edges.py:43` (four parameterized cases).

A narrow correction should retain the actual cancellation as a terminal
retraction until the same owning terminal fact is freshly and consistently
reported, just as for started retractions. Source-v2 already retains these
cancelled receipts; no new B1 shape or historical migration appears necessary.
Do not turn a cancellation into a measured zero or infer a new end from
unrelated map/lineup metadata.

## New positive controls and evidence

The additional file produced **4 failed, 6 passed in 10.86 seconds**, no skips.
No assertion was changed after the first execution.

Six independently green controls prove:

- An actual newer terminal series receipt after either cancellation path can
  establish its own consistent end 11:15 and correct recovery 6.75 hours.
- Cancellation directly on the series fact remains unknown even after a later
  unrelated completed map; this existing conservative behavior is correct.
- Known actual map/series end comparison is exact at -1/0/+1 microsecond:
  series end before the map is conflicting, equal/later ends are accepted,
  and the actual map remains separately countable.

Frozen file: `test_c4_lifecycle_edges.py`, SHA256
`1ce6f4d68509267720bf5445964d2a61ccea272ef7d0c9b8bffab585c5b7fb72`.
JUnit `run-01.xml`, SHA256
`247e80d78c1ff515fa1ddfa09265329ac704427454949082f5ae8d587fe6c1e0`.

Run against the C4 worktree using a new temp path:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider .pytest_tmp/c4-final-independent-20260909/test_c4_lifecycle_edges.py --basetemp=.pytest_tmp/c4-final-independent-20260909/rereview-new
```

## Unchanged frozen target bytes and limits

| Target | SHA256 |
| --- | --- |
| context_sources/esports.py | 6719a39df1578e59e5c20197b6f2f6057253eee0fc4063bc1048b4de84beb567 |
| context_models/esports.py | c09cc9661eae812caba205119ae21184ecce0ae6150a890cd83d6ec6957d052c |
| tests/test_esports_context_corrections.py | 57b1270062de31224551bb90eff148104834b32a76a2676e1d86a4364da1cc74 |
| docs/audits/2026-09-09-c4-esports-korrekturen.md | e61204a8105608076a34146275b06cbc1eff21f1f4f70f89dbedcfa75949a7ef |

These hashes and clean Git state were checked after the new negative run.
The old independent first review and both original probe files remain unchanged.
All additional transport payloads are synthetic; real PandaScore captures and
new provider calls remain zero. This is not measured fatigue, actual native
D1/D2 population, empirical activation, complete C4 integration or production
acceptance. Cricket, old Elo/default outputs, raw source line endings, money and
server state remain outside the change and review scope.
