# Independent D2 source-evaluator review — 9 September 2026

Reviewer: `/root/worker_failures_20260909`; controller: `/root`.

## Frozen target and scope

Target is the clean worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-d2-evaluator-20260909`,
commit `84c101ba810ceea40851beb3c9fb823cc629fb4b`, based on `70d6ce1`.
The packet adds exactly ten files (1,934 inserted lines), without changing
existing tracked source. The reviewer read all ten complete files, not just
the owning audit or test summaries.

Authoritative instructions read in full: the approved context-model design;
Task 17 brief; Task 17 evaluation controller rulings; context-contract and
validation-contract decisions; Task 16 preflight; original corpus inventory.
The controller clarified that these checked-in decisions and the packet's
explicit outcome/opening addendum are final, and no additional untracked D2
preflight or new user approval is required.

Review is limited to the actual A1/B1 dataset, whole-inventory opening,
source/base/feature/five-alpha replay, paired report and narrowly scoped
approval mechanism. The inherited pure statistical and training contracts were
traced where this packet consumes them. This is not a review of the separately
owned D3 worker wiring, transport, UI, or any production run.

No source, existing tests, Git state, provider, network, production database,
VPS, production active model slot or deployment was changed. Only this ignored review
directory, independent probes and isolated temporary test databases were
created. Deliberate SQL corruptions below affect only those temporary copies.

## Conclusion

**Bounded PASS for this exact technical packet; no reproduced actionable
source finding.** The reviewer independently ran the unchanged 70 owning
tests and 15 additional adversarial integration tests: **85 passed**, no skips
in those two successful runs. All ten target hashes and clean HEAD were
rechecked after completion. This is not empirical model approval, whole-Task-17
completion, activation or production release.

## Actual code path checked

- `dataset.py:165`, `_headers`, checks the complete experiment/config/family
  partition, actual A1 insertion clocks, frozen Event/decision/global native
  identity, all training/final case inventories, and the entire candidate fit
  inventory before resolving any B1 body. Training cannot borrow another
  final event under a different case or receipt hash.
- `dataset.py:120`, `_physical_receipt_preflight`, hashes actual opaque BLOB
  bytes and checks receipt indexes using only the five fixed outer JSON
  metadata fields plus outer key names. It does not invoke Python B1/outcome
  decoding or project result labels. This is deliberately not a claim that
  SQLite does not parse JSON bytes.
- `dataset.py:326` and `:377` resolve actual B1 receipt pools, enforce receipt,
  case, recipe, replay and fit timing, reject omitted already-known native
  revisions, and reconstruct D1 features/bases and all five train/tune fits.
  Exact full canonical FitResult equality includes unused alpha candidates,
  scores, coefficients, scale and status, not only the chosen artifact hash.
- `dataset.py:293`, `outcome_revisions`, validates owning native result
  receipts within the frozen source/schema/scope. Original train/tune claims
  use their own phase boundary; final claims use the original report clock.
  A receipt later than that boundary is skipped before its body decoder.
  An in-scope conflicting eligible result is not silently relabelled or
  selected away. Older differing results do not displace a later frozen one.
- `evaluator.py:204` commits the entire opening in a separate transaction
  before any final payload is resolved. The subsequent `BEGIN IMMEDIATE`
  rechecks source state and computes/report-writes atomically. A later semantic
  failure rolls back that report, not the original opening.
- `evaluator.py:82` derives targets and original/context distribution losses
  from the actual resolved case and exact candidate. Per-event target rows
  are retained together. `:61` keeps all frozen hypotheses in the multiplicity
  registry and sets failed-ready inferential p to 1 before a fresh whole BH
  pass. It does not make a caller's free loss table an authority.
- `evaluator.py:173` and `activation.py:46` replay actual historical evidence
  on the supplied connection and compare the full report and policy-produced
  approval. A stored `passed` flag, rehashed report, or valid-looking approval
  envelope alone cannot certify a fit.
- `activation.py:87` validates the real active approval claim before any
  inapplicable-scope fallback. Event/decision, family/base/feature versions,
  population, exact coverage, tested markets, source-bound feature reference,
  publication/evaluation clocks and exact effect identity remain closed.
  Historical source replay is separate from per-card CPU projection. Current
  worker features still require their owning verified input pipeline.
- The CLI is explicit-path, bounded, offline research. It does not accept
  free result/loss/force inputs, create a missing input database, use a default
  production path or publish active slots.

## Independent evidence, beyond the owning tests

The probes use owning normalizers, actual temporary A1/B1 SQLite storage,
source-qualified D1 mechanics, real reconstruction and all-five-alpha fitting.
Their match/receipt values remain explicitly synthetic. No provider fetch or
native Tennis alias was fabricated.

| Independent attack | Required observable result |
| --- | --- |
| Two distinct family configs, omission in either first or second group | Entire partition rejected before either body decoder, with no opening. |
| Complete two-config ready/control dataset | One durable whole-event opening exists before every final decoder; both configs score all 3 events/9 markets; control probabilities equal the original base and p=1. |
| Rehashed nested duplicate goal key or Boolean goal in a final receipt | Fixed outer-header check does not read labels; owning body/semantic validation rejects after opening; two attempts retain exactly one opening and zero reports. |
| SQLite statement trace during physical preflight | Actual `json_extract` statements use fixed outer metadata, not `$.payload` or `$.result`; Python body decoders are forbidden spies. |
| Unchosen candidate created after the fit, but before freeze | Rejects actual dependency timing despite unchanged valid content hash. |
| Identity map, recipe or replay created after its case, but before freeze | Rejects actual dependency timing, with no final outcome decode or opening. |
| Replay inserted before its claimed reconstruction | Rejects the separate actual A1 clock, not merely a payload hash. |
| Valid-looking approval with correct event-inventory hash for the real 3-event report | Replays all seven actual own outcomes and real five-alpha FitResult before policy rejection; read-only memory connection denies insert/update/delete, full SQL dump and change count remain identical. |
| Added train/tune correction within the original phase during historical verification | Old report rejected without any write; original opening remains. |
| Semantically invalid final outcome received after the original evaluation clock | Original report remains exactly reproducible and the future body is never decoded. |

Initial independent probe run: **12 passed, 3 failed in 155.83s**. These three
were reviewer harness mistakes, not product findings: one spy targeted a
function imported locally by `_prepare` instead of its owning `training`
module; two exception-message regexes omitted the correctly raised phrase
`original train/tune phase`. Only the spy binding and the shared exception
assertion were corrected; target source and owning tests were unchanged. Initial probe SHA
was `023bdc2bfbc9fde1c33d880ef3c8642c54cac153f3e7d1b95007573e563d35a6`;
its original JUnit failure evidence remains `attacks-01.xml`.

## Commands and results

Interpreter for both reviewer runs:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.

Own rerun of the complete, unchanged packet's 70 tests:

```text
-B -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/d2-independent-owning-01 --junitxml=.pytest_tmp/d2-independent-20260909/owning.xml tests/test_context_dataset.py tests/test_context_evaluator.py tests/test_context_activation.py tests/test_context_evaluator_cli.py
```

Result: **70 passed in 443.32s**; no skips. This is independent execution,
not the producer's 70-test count. The producer's 4,093-test full run was read
as prior integration evidence only and is **not** presented as the reviewer's
own full-suite execution.

Final independent probe rerun:

```text
-B -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/d2-independent-attacks-02 --junitxml=.pytest_tmp/d2-independent-20260909/attacks-02.xml .pytest_tmp/d2-independent-20260909/test_d2_independent.py
```

Result: **15 passed in 166.09s**. All target source/owning-test bytes remained
unchanged through both reviewer runs. The first three reviewer harness failures
and their correction are retained transparently above and in `attacks-01.xml`.

## Exact frozen identities

SHA256 identities checked before and during review, with final recheck required
below. All ten target hashes match the producer's frozen packet.

| Target file | SHA256 |
| --- | --- |
| `context_models/dataset.py` | `3b87304d86684bb0cae8e72b9cae6fe7f3fc5610e770b84b3a0568bb2b3e59e7` |
| `context_models/evaluator.py` | `b9fbb815f2cbccbb14055a23fa3da97d32dbec198053fca98fbb805a3607baa1` |
| `context_models/activation.py` | `887090c03a7107eb16946dd214a5ae7235b4e6cc3ea714a462c5c0e2f1ffd0c3` |
| `scripts/evaluate_context_models.py` | `ec46ccda1557e2e19744f8ed83ab5db2b87e6dd7344a699e8d063ee86683c120` |
| `tests/context_dataset_helpers.py` | `b26c961d81fc572814679ce9abc70583a00b1dcd8bb61c8193fd0a8f9b13a817` |
| `tests/test_context_dataset.py` | `e21a07a69e7554850fe8de8691cb3054181447ccd4c962155476b9a1d3fd9261` |
| `tests/test_context_evaluator.py` | `7289488c502abcfe246e75a768acca885e4a86ab5ad7e3097956009ce27cf38a` |
| `tests/test_context_activation.py` | `90f309c2c9df8785398ed71cb77007bc9387ffb854a62d5829fe9e3681860106` |
| `tests/test_context_evaluator_cli.py` | `dba1f8a94eac1bd4999711649d3a0d457cbce374b8cdb2ee490bb2ebac72b39e` |
| `docs/audits/2026-09-09-d2-source-evaluator.md` | `c9b85ad45b47889659355d64a42e6bf7ac6e8b136756e23294bdb2829118719f` |

Reviewer evidence:

| File under this review directory | SHA256 |
| --- | --- |
| `test_d2_independent.py` (corrected, final probe source) | `d50d281d187bd19528b48713940e1657dfb01d8f3db1cc3210c38f9e27e6d3d6` |
| `owning.xml` | `8910ec3113101b752e16a7864058c4ede75a5083a95467e17d4f93c4de85d9d0` |
| `attacks-01.xml` (original harness failures retained) | `1157358b993840f04ae8c7ba562220ef2a90c114faa4e02d99bd3667dc31dd3a` |
| `attacks-02.xml` (final 15-pass rerun) | `9e4b26dd0b60c00b7f189d53d789a34984cba07ad54ec59f6f83e2bba086b911` |

## Boundaries retained, not silently promoted

1. No source-resolved **successful** >=200-event approval is demonstrated.
   The real temporary storage path uses only seven synthetic native-shaped
   cases and three final events, so no approval is expected. Separate 210-row
   helper tests and stand-in active-scope tests prove mechanics only.
2. Native Tennis state-key replay remains explicitly unavailable. Basketball,
   hockey and E-Sport D1/D2 corpus support is not supplied by this packet. Their
   upcoming adapters cannot inherit this football result by matching strings.
3. High-load, injury-present, missing-context, confirmed/uncertain lineup and
   exact/bounded-recovery detail cohorts still need their own preregistered
   grouping/threshold/source contract. Existing family/coverage/block metrics
   do not complete every original Task 17 reporting bullet.
4. The strict source-byte pin means an implementation change needs an explicit
   reviewed upgrade or original implementation replay. A Git text identity
   alone does not establish cross-platform loaded-byte/BLAS reproducibility.
5. Hash/index/clock validation proves consistency of the supplied local
   stored history, not provider truth, independently authenticated ingestion
   time, or that nobody viewed external final results. Complete code/storage
   control lies outside this consistency mechanism's evidence claim.
6. Current worker inputs, D4 readonly snapshot verification, real provider
   availability, actual active-manifest publication, Linux behavior, UI/browser
   rendering, real-money bookkeeping, old tickets, VPS and deployment remain
   separate untested boundaries here. This review does not activate an effect,
   alter a quote, prohibit a market, change Cricket or rewrite any historical
   selection/settlement.

The independent review can approve this bounded technical packet for controller
integration only. It cannot label Task 17, the complete context model rollout,
the application's betting quality or a production release complete.

Final freeze check: `git status --short` empty and HEAD still exactly
`84c101ba810ceea40851beb3c9fb823cc629fb4b`. All ten source/test/audit hashes
above were identical after the final independent test process exited. No
provider, VPS, commit, push or production publication was performed.
