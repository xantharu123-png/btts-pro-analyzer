# Independent D2 CPU scorer / registry review — 2026-09-09

Reviewer: `/root/b6_tennis_load_20260909`, independent of the implementation.
Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Controller-provided base: `1574044519b1c6c92a6b52c982af7562ffda9496`.
No Git command was used; file bytes were independently hashed before and after
review. All four supplied implementation/test hashes and the owning audit hash
match the frozen package exactly.

## Disposition

**No actionable finding in this bounded four-file CPU package. Review passed
for this implementation boundary only.**

Independent focus: **413 passed** in 10.64 s, including **95 new independent
cases**. Independent complete repository suite: **3954 passed, 18 skipped,
97 subtests passed** in 92.54 s. No implementation change was needed or made.
The 95 new cases live outside the normal repository test discovery; they are
additional to, not included in, the 3954 default-suite test count.

This is not an approval of a real context model, a completed D2 evaluator,
source-authentication pipeline, live worker integration, or deployment. The
package's explicit `empirical_approval_verified=False` boundary is correct and
was tested. C2 sources were not touched; their independent review/fix belongs
to another worktree/controller task.

## Read scope

Read completely: approved specification; task-17 brief; current context-contract
and validation-contract decisions including the new owning-distribution-scorer
section; owning audit `docs/audits/2026-09-09-d2-verteilungsvergleich.md`; all four
frozen files. Traced the original `score_matrix`, complete strict tennis simulator,
native outcome normalizers/validator, selected B1 receipt/hash validation, full
frozen-hypothesis/opening registry, paired-event/coverage helper and original
HAC/BH formulas. Checked existing calibration diagnostics and thresholds without
modifying their arithmetic or policy.

Source inspection confirmed that free loss rows are intentionally accepted only
by a pure statistics assembly helper, not represented as source/fit/replay truth.
Its caller must supply independently reconstructed outcomes and comparisons at
the later owning evaluator boundary. Public content hashes alone are not source
authentication; the package and its audit do not claim otherwise.

## Independent adversarial and mathematical checks

`test_d2_independent.py` is the frozen review probe. Repository fixtures are used
only to construct typed inputs. The principal math oracles are independent:

- Eight football parameter/outcome pairs use an 80-digit Decimal log of an exact
  integer factorial, not the implementation's `lgamma` expression. Cases include
  rates at 8, the smallest positive float, 26/25 goals, and 1000/901 goals. Exact
  score tails are not silently folded into matrix cell25 or epsilon-clipped.
- Fifty tennis final-set-score cases use a separate rational `Fraction` game-
  state recursion with the declared hold-based tiebreak law and combinatorial
  final-set-count probability. Bo3/Bo5, both winners, every legal losing-set
  count and five hold pairs are covered. Two pairs have genuinely different
  serve/return chances, testing first-serve alternation rather than only IID
  game probabilities.
- The final-set-count policy intentionally marginalizes game paths. Two 6:0
  sets and two legal 7:6 sets give the same declared 2:0 loss despite different
  native game/hold/trial observations. This is not falsely labelled an ordered
  point/game-path log density.
- Smallest-positive Bernoulli probabilities and values immediately below one
  retain representable positive `log`/`log1p` losses. Exact zero is distinct from
  absent data and from assigning zero probability to the observed winner.
- Whole-match product underflow still yields a finite log-space loss when the
  per-set mass is representable. If the unchanged simulator has zero observed
  set mass, scoring raises `DistributionScoringError` instead of substituting
  a floor, zero effect or an excluded favorable cohort.
- One retained API-Football source envelope and one retained ESPN tennis
  envelope were normalized by the actual owning source normalizer, appended to
  a real isolated B1 SQLite store, selected as actual receipts, then scored.
  Their new local ingestion clocks were retained. The bases are explicitly
  synthetic, and these two mechanical paths are not historical predecision
  training or held-out empirical events. No provider request occurred.
- Reusing an existing valid receipt after schedule, competition, format,
  participant orientation or native-event mutation is rejected. Receipt/content
  hashes, effective clock, evidence class, source schema, completion and kind
  mutations do not become computed losses.
- Chronological HAC was recomputed manually from one average Brier advantage
  per canonical event. Shuffled source row order leaves the full result exactly
  unchanged. Two winner markets do not double the 210-event sampling unit.
- Independent BH adjustment includes six registered hypotheses, including
  explicit `fit_failed`, `unsupported`, `insufficient_data` and baseline-control
  entries with p=1. Failed variants do not silently disappear from multiplicity.
- Duplicate targets, null distribution losses, bad outcome types, wrong blocks,
  conflicting original densities and wrong outcome contracts are rejected even
  when another ready variant has already made that event ineligible. Validation
  precedes shared-cohort intersection.
- Real zero losses retain 210 events and zero numerical values; missing losses
  empty the ready cohort with null metrics, exclusions and failures, never a
  relabelled unsupported status or fabricated zero result.
- Exact half-open block starts/boundaries/end and equivalent UTC-offset loss
  clocks were tested. The final endpoint cannot borrow the previous block.
- A paired worsening of exactly +1 beside absolute losses `10**100` is preserved
  globally and per block and fails the distribution requirement. Absolute float
  display rounding cannot hide the degradation.

The unchanged repository tests additionally cover distinct ATP/WTA cohorts,
partial fixed targets, one-block/199-event failures, exactly calibrated/sparse
markets, 1.99% improvement, invalid policy/registry inputs, continuous density
transport in the generic helper, immutable opening history and no storage/approval
writes from this CPU comparison. These tests were rerun, not accepted from an
earlier reported count.

## One corrected review-fixture expectation, not a product finding

The first independent run was 72 passed / 1 failed. The failed assertion expected
zero A set mass for `hold_a=5e-324, hold_b=nextafter(1,0)`. Direct inspection of
the unchanged kernel showed **2.4090632328092265e-207** A set mass: the tiny
break-to-tiebreak path remains representable. The scorer correctly returned a
finite log loss. The fixture expectation, not source code, was wrong.

The intended zero-mass case was changed to the reverse orientation and an away
winner, where the existing float kernel yields B set mass zero. The original
positive-tail orientation was retained as its own permanent review test. Later
expansion added serve/return-asymmetric rational-DP cases and the set-count/path
distinction. No test tolerance or source contract was loosened.

This also records an existing strict-simulator numerical limitation: it is the
versioned hold-proxy/IID-set kernel, not an arbitrary-precision point engine.
The D2 scorer neither changes it nor hides its unrepresentable observed masses.

## Actual commands/results

Interpreter for every run:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`
with `-B -m pytest -q -p no:cacheprovider`; every basetemp was new and isolated.

| Run | Scope | Result |
| --- | --- | --- |
| `d2-independent-attack-01` | First independent probe draft | 72 passed / 1 wrong review expectation; 2.99 s |
| `d2-independent-focus-02` | Corrected 74 independent cases + repository D2/registry/outcome/statistics files | 392 passed; 8.88 s |
| `d2-independent-focus-03` | Final 95 independent cases + same repository focus | **413 passed; 10.64 s** |
| `d2-independent-full-01` | Entire normally discovered suite | **3954 passed / 18 skipped / 97 subtests; 92.54 s** |
| `d2-independent-skip-audit-01` | Files containing platform skips, name-selected cases, `-rs` | 5 passed / 15 skipped / 223 deselected; 1.41 s |
| `d2-independent-skip-audit-02` | Remaining three exact skipped node IDs, `-rs` | 3 skipped; 0.76 s |

All 18 skips were independently accounted for: 13 unavailable real symlink
creation checks (Windows privilege/WinError1314) and five POSIX-only owner/mode/
umask checks. None is a skipped D2 scorer or registry test. Hardlink-related
selected checks ran successfully; no Linux/POSIX acceptance is claimed here.

Focus files: the independent probe, `tests/test_context_distribution_losses.py`,
`tests/test_context_registered_metrics.py`, `tests/test_context_paired_metrics.py`,
`tests/test_context_validation.py`, `tests/test_context_outcomes.py`,
`tests/test_context_experiments.py`, `tests/test_model_loss_statistics.py`.

## Exact freeze

```text
8aa0bcc530d81103b7b9c6823574504e3c591f5654b9a599e0518458c9fe7f0a  .pytest_tmp/d2-independent-review-20260909/test_d2_independent.py
d70ccbf430bf553f77579010a7c76de8d2317c6b12ec32b36a4c93e9f885f950  context_models/distribution_losses.py
20e602e6256e7806928b83f8bc7292dccf72e8a829f8d462bf5ad57373f725a0  context_models/evaluation.py
e9d2f288eada2cf43e8340a5631bef48dbef204cb3627214b2d245d08f99f44b  tests/test_context_distribution_losses.py
155496751f7e946287d79545974b64e8c07a84400b1fc8cda539f40ec89ed4cd  tests/test_context_registered_metrics.py
3a6b0936a1d8d994ad5c273739497d157af3b6cabf1c8b2a34bef89463ed5b93  docs/audits/2026-09-09-d2-verteilungsvergleich.md
ed4e8dd075e0a259b70d3ed8b83307f8eb79699777cb11cab79cee35303144b1  context_models/validation.py
c4d79ee8be2cff2181a25d0c157bab44b1d3eae8161ca5ae3972557f56683a7b  model_loss_statistics.py
080bcf30cf48b14dafdb045611414cf9d82ce975d93ea951022fb99c3bd17ce1  context_models/experiments.py
dd204c3863dcd6712531213c05aeeb3a9551f6b0f8ec9a160e1375182958e033  context_observations.py
e61943527fd764d1017f3c78ae09cd5d1d8bc67db44e19961517bc4b329e6786  context_sources/outcomes.py
6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f  tennis/simulator.py
915a49325754ace657227c8195c914a18cd2d5fba83482c8f526d7fb03f75fa5  challenge_engine.py
```

## Explicit remaining boundary

Still pending: owning source-resolved `evaluate_experiment`, exact D1 case/fit/
artifact resolution, prediction/outcome/loss reconstruction, native alias and
complete failure provenance, local test opening before label use, full report
persistence, scoped `approved_effect` resolver/CLI, real unseen qualified corpora,
and D3/D4 runtime connections. A ready numerical failure must remain an explicit
failure at that later evaluator; it must not be translated into a favorable
missing-data row. These helpers cannot themselves verify that upstream claim.

No genuine serve hold/trial source, real ≥200-event/three-block acceptance, fresh
empirical effect, release publication or server activation follows from the tests.
No source, money/ledger/15K, Cricket, stage helper, UI or production file was
modified; only this independent review report/probe and isolated test artifacts
were written. No push, Git operation, SSH, provider request or API call occurred.
