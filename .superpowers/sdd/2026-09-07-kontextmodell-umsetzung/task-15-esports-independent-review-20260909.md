# Independent C4 review — 9 September 2026

## Disposition

**Changes required: two P2 correctness findings, eight independently red
regressions. Do not merge this frozen C4 packet as accepted.** The controller
has acknowledged both findings and will assign narrow owning fixes followed
by an independent re-review. No reviewer source fix has been made.

Reviewed worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c4-esports-20260909`.
Frozen HEAD `26e891096ecee78ac962b5090a8294deefd7d395`, parent
`bd2a5c4d4af580baa44ea238b28ded84b5c68140`.
The nine target files retain the hashes below and Git remained clean before,
during and after the independent tests. Only this ignored review directory
was added. No provider, external API, VPS, SSH, push, live database, production
worker, source normalization, privileged helper or money change was made.

## Finding C4-R1 — stale terminal series survives a newer started revision

Priority P2. Owning location: `context_models/esports.py:148-166`, in the
whole-event identity/status selection following `_selected`.

The cross-fact identity deliberately removes `event.status`, and the later
invalidation branch recognizes cancellation/conflict/identity changes but not
a **completed -> started** transition. Consequently a newer native parent
series revision received through a map can say the series is still running,
while the older series completion remains selected for performed load and
exact recovery. This is not the valid forward started -> completed case.

Actual independent reproduction uses the closed normalizer, append-only B1
SQLite and `observations_as_of`, not a hand-built FeatureVector:

1. A completed native series for team 7 (and independently team 8) ends at
   09:00 UTC; its result is received at 09:01.
2. At 11:00, the same native event, same participants/scope/schedule revision,
   reports `event.status=started` alongside a completed native map ending at
   10:00. This newer whole event status withdraws the old terminal claim.
3. At the 12:00 cutoff for the target beginning at 18:00, the frozen code still
   returns `observed_series_count_1d_<side>=1`, state `available`, and
   `observed_recovery_exact_hours_<side>=9.0`, state `available`.

The old whole-series completion can no longer justify those values. Keep a
typed missing/conflicting value until a consistent later terminal series
revision exists; do not invent a completion time or discard actual completed
map evidence from a legitimate forward progression. A later source correction
must remain outside an earlier cutoff.

Four immutable red cases:
`test_independent_c4.py:59` (count, both teams) and
`test_independent_c4.py:73` (exact rest, both teams).
The opposite forward progression, cutoff -1/0/+1 microsecond controls,
participant/schedule/season corrections, and known map/series separation
already pass independently.

## Finding C4-R2 — signed feature check accepts nonzero tampering around zero

Priority P2. Owning location: `context_models/esports.py:601-604` in
`_prepare_effect`; the producer at lines 449-461 computes the actual signed
participation difference directly.

The consumer checks the signed value against its source components using
`math.isclose(..., abs_tol=1e-12)`. The producer and consumer use the same
two operands and arithmetic; this is an integrity equality, not a noisy
statistical assertion. A different FeatureVector value within that tolerance
therefore passes even though its unchanged measured components prove zero.

Actual B1-native synthetic fixture: player 702 has current participation 1,
reference participation 1, exact signed difference 0. Changing only the signed
value to `9e-13`, `-9e-13` or the next representable positive value above 0
is accepted. Source refs and both components are unchanged.

For a deliberately large but finite, schema-valid **synthetic mechanical**
coefficient `1e12`, `9e-13` becomes a 0.9 logit change. The comparison goes
from `p_a=0.7996764800884426` to `0.9075661822383244` and is accepted through B3
as an experimental comparison. Without D2 approval B3 **correctly retains the
original used parameters/markets**. This is not evidence of a live paid-tip
change, a provider capture, an actually fitted huge coefficient, or empirical
activation. The failure is acceptance of a contradictory signed feature even
before any release decision.

Require exact equality to the same actually computed component difference;
do not widen numeric tolerances or change source features to make the probe
pass. Preserve the genuine exact-zero byte-preservation control.

Four immutable red cases:
`test_independent_c4.py:87` (three perturbations) and
`test_independent_c4.py:100` (B3 integration/magnitude).

## Independent evidence

Interpreter used:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Every pytest invocation used `-B -m pytest -q -p no:cacheprovider` and its own
`--basetemp`; no cached result was used as this review's evidence.

| Run | Result | Time | Evidence |
| --- | --- | --- | --- |
| Initial new probes | 10 failed, 28 passed | 17.65 s | `run-01.xml` |
| Final frozen independent packet | **8 failed, 59 passed** | 39.14 s | `run-02.xml` |
| C4 + B1/B2/B3/A1 + legacy Shadow focused regression | **722 passed, 4 skipped** | 32.49 s | `focus-01.xml` |
| Entire unchanged owning suite | **4154 passed, 18 skipped, 97 subtests passed** | 237.33 s | `full-01.xml` |

The initial two extra failures were **review-harness expectations**, not new
product findings: the reviewer first asserted a withdrawn/cancelled series
must become measured zero with exact older recovery. The owning conservative
unknown result is correct. Only those two assertions in the review test were
corrected to unknown, explicitly accepted by the controller; no source, gate
or eight real red repro assertions were changed. `run-01.xml` is retained.
All 67 final independent cases are collected explicitly; the normal suite
does not collect this ignored `.pytest_tmp` review directory.

The 18 full-suite skips were inspected in the actual JUnit XML: Windows
symlink creation lacks privileges and POSIX owner/mode/umask enforcement is
not the Windows ACL implementation. No skipped C4 numeric/native-series
case is disguised as a pass. Linux/production permission QA is separate.

The explicit final repro command, from the target worktree:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider .pytest_tmp/c4-independent-20260909/test_independent_c4.py .pytest_tmp/c4-independent-20260909/test_additional_c4.py --basetemp=.pytest_tmp/c4-independent-20260909/rereview-new
```

Use a new basetemp on re-review; keep both frozen test files unchanged.

### Independently green properties and boundaries

- Real SQLite normalizer -> receipt persistence -> selected B1 -> actual B2
  fit on four separate synthetic cases -> A1 effect put/load -> B3
  compute-once snapshot. The independently recomputed logit result matches,
  but used base and both used markets stay original without D2. Repeated
  reads compute once, and real SQLite `integrity_check` returns `ok`.
- A true shared native head-to-head appears in both 20-series windows but
  contributes **39 unique series**, 40 reference receipts including the target,
  and exactly 20 measured participation weights of 1/20 per team. No extra
  Elo-pass or repeated-window participation weighting is created.
- Repeated native receipts count one performed series. Complete native
  participant correction removes the former participant's old positive load;
  an incomplete correction instead leaves an explicit conflict/unknown.
- Native whole-event schedule, season and participant changes in a later
  observed lineup invalidate the old series evidence. Full Event/Base binding,
  original source body/index mismatch with recomputed public hashes, and B3
  nested Event/FV/Base/effect substitution are rejected.
- Unknown terminal end is used only as a strict receipt upper bound. Actual
  SQLite tests cover every 1/3/7-day window at -1/0/+1 microsecond, retaining
  exclusion proof refs. A series ending exactly at cutoff is excluded from
  the half-open performed window. No career-history-complete claim appears.
- Missing lineup remains missing; patch unknown is not a numeric winner
  advantage; map minutes and medical fatigue stay unknown. Unreviewed patch,
  medical or map aggregation feature names are rejected by the winner head.
- Handicap starting score, forfeit, wrong BO and boolean BO are rejected by
  the native rules boundary. Exact zero effects retain original parameter and
  market bytes. Old Shadow/15K release flags cannot serve as context approval.
- The exact previous committed `multi_sport_recommendations.py` was read with
  `git show 26e8910^:...` and executed **in memory** as a distinct module. Seven
  independent pre-match/live/finished BO1/3/5/7 E-Sport states and three Cricket
  default inputs match current output canonical bytes exactly. No target file
  or line endings were changed; the owning frozen Cricket prematch test also
  passes in the actual full suite.

## Reviewed scope and honest data limits

Read completely: approved context spec; Task15 brief; C4 controller rulings;
context-contract and validation-contract decisions; basketball/hockey/esports
source-readiness; the full C4 preflight and audit; all nine changed/new files;
unchanged `esports_elo.py`; relevant current B1 factor-selection and B2 offset
code. This is independent source/CPU correctness review, not design approval.

Preflight location:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/.pytest_tmp/c4-preflight-20260909/PREFLIGHT.md`,
SHA256 `ad94e352cac1a46a0b8238efaa8b1666158daa184e1d79171c1feff54955afa7`.

**Real PandaScore context captures used by this review: 0.** New provider
requests: 0. Every new source payload here is expressly synthetic internal
transport persisted through the real local SQLite implementation. The actual
B2 fit is software-mechanism evidence on synthetic labels, not source-qualified
D1/D2 validation or a measured roster/fatigue effect. Native provider adapter,
real captured roster/patch/veto/map-time history, native owning D1 assembly,
distribution scorer/cohorts and D2 approval, and D3 live wiring remain outside
this packet. No qualified 200-event population or production release is
claimed. Cricket is unchanged and outside the new context scope.

The equal-series reference is mathematically a measured participation
baseline, **not an analytic causal decomposition of Elo weights**. The original
base retains the actual post-IID-roundtrip output before card rounding. No new
map winner/handicap or live certainty is derived from a series-winner head.

## Frozen SHA256 inventory

| Target file | SHA256 |
| --- | --- |
| context_sources/esports.py | 9e7600ffcb3de561af220ef1950ad2bda95505957952fc7c93ffdbf5343e58c0 |
| context_models/esports.py | 728043d2bad26533010d04c1a681fde63c723b4bbf931138f3ffab50f5ddf49e |
| context_models/contracts.py | e538ddd05128504996a7bb25892e30e6d75b979397cb54343854910bd226be33 |
| context_snapshots.py | 746f0b2d265088fb82caf3bc884b269896bd275489a06c9f9b01dba0b89d35ee |
| multi_sport_recommendations.py | 80c545cf82a577bd4d1540bbd2619a12171662781373161d6db4c80ba38615c5 |
| tests/test_esports_context.py | 9995c77e8b2d68eff410b6361d2ed8258622da84052119f8e5475323bcebe331 |
| tests/test_esports_context_model.py | 5c4911a2de028ba69346b27caa9f36513de82e6b0dcc00a6125a7d7dbf1faac9 |
| tests/test_esports_context_revisions.py | d46d550486ad617d0cdb4d04a6f264925ce7036534b9ea80af32684819757997 |
| docs/audits/2026-09-09-c4-esports.md | a06859f7101d4f603b80bc97d943516f96ff6eccbb28bc0c7adce176c110f9b5 |

Actual C4 `esports_elo.py` SHA256:
`bd431e06926a319a68d5803749771595bbf72bb8561d39da2b8ee841d2af7140`;
unchanged Git blob `ca390bc51976a5ce598c9a2a952568cd25439ca2`.
The controller separately reported different raw root checkout bytes because
of line endings. No source normalization or portable raw-recipe identity is
asserted: equal Git blobs alone do not satisfy the raw loaded-code binding.

| Independent artifact | SHA256 |
| --- | --- |
| test_independent_c4.py | 1504b746aa9e19eaf44a485cf0ad391414adacfd091559a1e90cba164371bd2b |
| test_additional_c4.py | 777cd1c2aabcf54777ee4df9b4395a68076d19738a2dc428e96e699bd9f0df5e |
| run-01.xml | 201253192101b08b5d8d7d1a54b21e59db5d07b36405458710da4d2bfe888c21 |
| run-02.xml | 0957aea9eb45b8777c5f4fa0f01729fd36788665c005397ba36e01206c72eb14 |
| focus-01.xml | 8a53c86f6facacad7794852e8f638c35a72f2f9ec7358940955c435086e28544 |
| full-01.xml | b9dc7af6346d2afe239a22ebc61a1f5c87399299b6549caf314f0141118d1197 |
