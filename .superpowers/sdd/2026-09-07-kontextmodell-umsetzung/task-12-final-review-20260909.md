# Independent C1 rereview — 9 September 2026

Reviewer: `/root/b6_tennis_load_20260909`, the original C1 reviewer.
Decision: **APPROVED for integration of the bounded CPU-only C1 correction**.
All three original findings are resolved. No new implementation finding in this
rereview. This is not source, empirical, activation, deployment, or complete C1
product acceptance.

Frozen commit: `f14f75e92d3acea3b91bc2c8f0e6fa1bdf345f06`.
Parent: `87b27458538b03b0631d1159c806bd30d26803be`.
Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c1-wetter-20260909`.
The entire correction diff, current audit, full producer, new permanent tests,
and applicable B1 selection/usable-reference code were read independently.
The existing B5 feature-version/orientation boundary and the reviewed B6/B7
unknown-end interval rules were compared; no contract transfer was assumed.

## Original findings, unchanged reproductions

1. **Fresh weather sources no longer receive implicit global latest-receipt
   priority.** Latest revisions are selected per source before testing metadata,
   scope and interval applicability. Actual B1 selection evaluates those current
   sources jointly. A differing still-fresh forecast remains conflicting;
   input ordering and duplication cannot choose it. Expiry does not revive an
   older same-source interval. A simultaneous incomplete alternative from the
   same fresh source remains a conflict, not a reason to drop that alternative.
2. **A partial newest native football revision no longer disappears.** Every
   known old/new participant is conflicting until a later complete coherent
   joint revision resolves that native fixture. Older counterparts are not
   borrowed. A different older fixture cannot certify exact recovery while the
   incomplete new fixture could change it. Unrelated teams remain unaffected.
3. **Terminal receipt upper bounds are now used narrowly.** An unknown end is
   excluded from an N-day window only when its terminal receipt is strictly
   earlier than the inclusive window start. Exact latest observed recovery is
   allowed only when the latest known end is at least every unknown end's
   receipt upper bound. Bounds at the exact window boundary stay ambiguous.
   Distinct bounded/partial timing coverage and the actual exclusion receipts
   are retained. Empty histories and unknown durations are not zero/full data.

The earlier 37-case independent file was executed unchanged and its SHA256
checked before and after execution. All 37 pass on the correction; the original
report recorded 8 failing and 29 passing on the parent. The shipped C1 suite now
contains 163 cases, all passing independently here.

## Additional independent probes

`test_c1_final_independent.py` contains **29 new cases** using synthetic closed
source transports through actual B1 SQLite TEMP storage and receipt selection:

- Three source histories, six input permutations, repeated receipts, competing
  latest fresh revisions, and a third source exactly expired.
- A latest source revision with missing issue time, missing interval, unknown
  roof, or expired interval. The old version cannot be revived; another source
  qualifies only under the existing B1 applicability/freshness semantics.
- Full Event changes in latest same-source receipts (schedule revision,
  kickoff, participant), with an independently current other source.
- Receipt at cutoff plus one microsecond remains unavailable at the earlier
  decision. Cross-source conflict heals at the exact expiry only with the new
  decision/base revision; an old base cutoff is rejected.
- Several known actual ends plus both ancient and recent unknown bounds on
  both sides: separate 1/3/7-day sums, completeness, exact recovery, and all
  actual completeness/recovery references. A lone ancient unknown end still
  cannot invent exact recovery or zero performed minutes.
- Side swap with different bounded/partial coverage: side values, states and
  references swap; every available signed delta negates; missing stays missing;
  full Event/base binding changes and original input bytes are unchanged.
- Partial cancellation, scheduled and in-progress corrections remain conflicts
  until the full matching pair arrives. The later repair does not alter an
  earlier cutoff. Two different partial pairs never create one complete match.
- Nonempty available C1 weather/load facts cannot inherit injury-only B5's
  effect artifact. Typed rejection retains the original base/artifact bytes.

The full Event/base reference remains
`football-context-reference-v2` with validated complete base hash, complete Event
hash, and the explicit empty preprocessing list. The C1 coverage names are
versioned C1 identities, not aliases for B7 or injury-only B5 populations. No
numeric fatigue/weather coefficient, calibration, approval or runtime routing
was introduced or accepted by this review.

## Fresh independent runs

Python: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
All commands used `-B -m pytest -q -rs -p no:cacheprovider` and distinct basetemps.

| Run | Result |
| --- | --- |
| `tests/test_football_weather_features.py` plus unchanged original review | 200 passed, 5.65 s; `.pytest_tmp/c1-final-original-permanent-01` |
| New independent 29 cases | 29 passed, 2.03 s; `.pytest_tmp/c1-final-extra-01` |
| Full repository `tests` | 3170 passed, 15 skipped, 97 subtests passed, 72.44 s; `.pytest_tmp/c1-final-full-01` |
| Shipped C1 + original review + new independent review together | 229 passed, 6.97 s; `.pytest_tmp/c1-final-combined-01` |

The separate review cases are not included in the full repository `tests`
count. The 15 skips are Windows/POSIX umask, permission-bit and unavailable
symlink cases in backup, artifact, server-job and tennis-training tests; these
are not Linux or VPS acceptance. No tests were changed to obtain green results.

## Exact bytes and untouched boundaries

| Path | SHA256 |
| --- | --- |
| `context_models/football_load.py` | df594cbd76c37cb88891c65c545f566da54bb3c3e777a4a73d661a7a0e4e9fe3 |
| `tests/test_football_weather_features.py` | ab8a53fc6b06ba83d66f96584c5d2c3354de130fe800bbf7395a3dc56677e513 |
| `docs/audits/2026-09-09-c1-wetter-belastung-mechanik.md` | 3e55ebc5c9ffdc8d16ef4abd4440bbff048a513c0a607a002e4052294287c44d |
| `context_sources/weather.py` (unchanged) | a2a9fdb838a4d4f5f05e39d43dd0dd7f15c8c9f05bdf74c77e4d8fad76ec11a0 |
| `tests/fixtures/context/football/c1-schedule-20260907.json` (unchanged) | dd21398ef1e6e05802b9666cfd0b34ddd051d55e0b9d83a6f66d9b15656b21f3 |
| `.pytest_tmp/c1-b6-independent-review/test_c1_independent_review.py` (unchanged) | 0a390a9b5e3553f54cc35e7c202758d2e0bdaac3223a4ce42b3f954472550fdd |
| New `test_c1_final_independent.py` | 624371216277c95115a514db45dbcf312abf4e9d8c411105d01779472565df0b |

The frozen commit has exactly three changed tracked files relative to its
parent (345 insertions, 34 deletions). `git status --short` was empty before and
after execution. The reviewer only added this report and new tests under the
assigned ignored `.pytest_tmp/c1-final-independent-20260909` directory. No
implementation, shipped test, original review, source fixture, or tracked audit
was modified. No commit, push, external provider query, VPS or productive DB IO.

## Actual data versus synthetic mechanism — remaining boundaries

The existing sanitized real source evidence is **one file with two native
football fixtures**, only one completed. It was actually received on
2026-09-07T14:46:05.939454+00:00 and stays bound to the original source sample
SHA256 `5314091f34eb0927cab41ba0b22fb4cea45eebbb57ceaf181b735859e3c0aab4`.
It does not establish exact ends, match duration, stadium coordinates/roof,
complete domestic/international histories or an earlier receipt time.

There are **zero qualified real weather responses** in this package. Every
positive qualified weather and exact-end scenario in the added probes is
synthetic. The CPU-only weather transport is not a real OpenWeather adapter;
source issue/receipt and valid-window provenance, native stadium resolution,
shared request governor, actual complete schedule feed, causal training,
untouched empirical assessment, D1/D2 and production integration remain open.
No probability-improvement claim, physiological fatigue diagnosis or betting
quality guarantee is supported by these tests.
