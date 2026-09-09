# Independent narrow Tennis-consumer correction review

Date: 2026-09-09. Reviewer: `/root/b3_shared_snapshots_20260909`.

## Disposition

**PASS for the three specified consumer corrections. No new finding in this bounded review.**

Frozen owning checkout: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-tennis-consumer-fix-20260909`.
HEAD before/after: `5a865e0228360051ea92f95793b45b69936f7367`, tracked clean.
Reviewed base: `3e415db63894ab6d206cf7b87ff0f804aded1ab0`.
The delta is exactly two source files, one 49-case test file and the owning audit; 308 insertions/5 deletions.
No source, tracked test, original diagnostic, original report, Git state, provider, production database or VPS was changed by this reviewer.
Only this new ignored review directory and fresh disposable test outputs were authored.

This is not a whole-model/D4 approval, evidence-source authentication, effect-approval review, empirical-quality demonstration, browser/UX acceptance or deployment verification. A valid consumer link does not establish that the training data or the model itself is correct.

## Sources and original evidence read

Read the complete owning correction audit, complete copied original independent report, both complete current consumer modules and their complete base-to-HEAD diff, complete new permanent regression file, all six unchanged original probe files, the existing shared-consumer regression file, and the relevant actual state-codec, tour-wrapper, A1/B3/dataset-read contracts and fixture producers.

The original report has three distinct findings:

1. F1/P2: a fully public-rehashed ATP original could reference an actual WTA state because the consumer read but discarded the known A1 state header.
2. F2/P2: present false-valued non-text context metadata was interpreted as optional absence and could reach the true legacy RisikoBet path.
3. F3/P3: the generic reader leaked untyped base-shape indexing errors; the exact older Git-parent reader rejected the same temporary database shapes with the declared contract error.

The source corrections match those boundaries. `tennis/context_consumer.py:68` validates the existing closed wrapper/state key inventories, actual integer schema versions and exact tour before either market projection. It uses the already loaded artifact in the held transaction; it does not decode, refit or select a latest state. At line 46 absence is limited to explicit None or empty string; other present inputs must be JSON text and decode to an object. `context_consumers.py:70` validates the base object and checks event/cutoff identity with typed failures before projection.

## Fresh execution

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B`.
Both runs used `-m pytest -p no:cacheprovider -o "pythonpath=. tests .pytest_tmp/consumer-original-review"` and separate fresh basetemps/XML files. No full suite was started.

1. The six byte-identical original probe files, `tests/test_tennis_shared_consumer.py`, and `tests/test_tennis_consumer_binding.py`: **165 passed, 0 failed, 0 errors, 0 skips; 22.16s**.
   Basetemp: `.pytest_tmp/tennis-consumer-independent-original-01`.
   JUnit: `.pytest_tmp/tennis-consumer-independent-original-01.xml`.
   This comprises the unchanged 67 original cases plus the existing/new 98 owning cases. It includes the actual stored Shadow/adapters, exact Git-parent reader control and actual WAL interleaving; none was replaced by a mocked success assertion.
2. New independent `test_independent_boundaries.py`: **46 passed, 0 failed, 0 errors, 0 skips; 5.07s**.
   Basetemp: `.pytest_tmp/tennis-consumer-independent-boundaries-02`.
   JUnit: `.pytest_tmp/tennis-consumer-independent-boundaries-02.xml`.

Total fresh bounded evidence: **211 passed**, from these two non-overlapping case sets.

The retained pre-fix XML `.pytest_tmp/consumer-fix-original-red-01.xml` is byte-identical to the owning audit's hash and still reports 31 failures/36 passes, no errors/skips. This reviewer inspected and preserved that evidence; this review did not reset the source or rerun the old version. The independent current rerun did execute all 67 unchanged originals.

## Independent adversarial/positive controls

The new probes use actual disposable A1/B3/Shadow databases produced by the real worker test harness with synthetic provider responses. Public identity re-pointing reuses the unchanged original witness helper; expected error/projection behavior is asserted independently.

- ATP to WTA and WTA to ATP substitutions, with same-tour controls: both conflicting states fail before either A/B projection. Controls project exactly `winner_a`, `winner_b`, retain the same original/base probabilities and do not decode or predict.
- Fully rehashed known-header missing/extra keys, wrong schema type/value, trailing-whitespace tour and Cyrillic-lookalike tour: all fail before projection. There is no lowercase/visual alias normalization.
- A newly published real latest manifest/state does not change an already stored original consumer result. Both tours continue reading the exact original hash; latest-manifest lookup, tour-state loading, model decoding and prediction are expressly forbidden during the read.
- Actual state-artifact insertion time at decision minus 1 microsecond and equality is readable; plus 1 microsecond is rejected, for both tours. This tests the actual A1 clock, not a caller's reader-now value.
- Additional false-valued non-text metadata (including float zero), whitespace-only text, JSON scalars/arrays, present null sidecar and escaped duplicate JSON key are rejected without opening or creating a database. Valid whitespace-surrounded JSON legacy objects and unrelated old metadata remain optional absence and likewise perform no database IO.
- Missing base, string base, missing/list/numeric cutoff, missing/null/list event are physically rehashed and stored. Each throws the declared contract error before generic projection and does not alter the database bytes.

The unchanged original controls additionally exercise real normal/strict/RisikoBet Shadow adapters, actual SQLite artifact storage types, known schema mutation, exact original-publication/append ordering, a real WAL writer commit between A/B projections, and post-transaction trust failure preventing result escape. The existing owning controls cover unrounded probability/reference equality, old no-link adapter bytes and set markets, quote invariance and same held transaction.

No arbitrary nested model corruption was promoted to a new consumer requirement: training-cutoff coverage, Elo/Serve decoding, source identity and replay remain the explicitly separate producer/D4 boundary. No gate, ranking, price or source-budget policy was tested as changed or declared newly approved.

## Frozen source/evidence hashes

All source/owning test/audit and copied original hashes below were checked before and after execution. Hex SHA-256:

| Path relative to checkout | SHA-256 |
| --- | --- |
| `context_consumers.py` | `0566911f00924902d6f10a76947d62d08425bda5e83b9444b32378e45a0cabc2` |
| `tennis/context_consumer.py` | `bb07da8c63102712bae093fe225109e52d7ee24f7b1936416afc5e5c8d308e89` |
| `tests/test_tennis_consumer_binding.py` | `ece91dc0288e633695f4176c5c1cd6ffd44f98d48b698634982e7ca3b0b8cb26` |
| `docs/audits/2026-09-09-tennis-consumer-binding-fix.md` | `5bd0b56c3a4f95f361a736b2b9763bfc1cc8c7eec64577eb4ab2f013e69b2043` |
| `.pytest_tmp/consumer-original-review/REPORT.md` | `08724efbb75169e304eb09d1bf32b332842ae3a2c5794769cb413be5065a4c94` |
| `.pytest_tmp/consumer-original-review/test_state_identity_candidate.py` | `e562fb3c5ff9da21ac647e83309b8c4da49a9d0eb36aee64713589d615397973` |
| `.pytest_tmp/consumer-original-review/test_state_identity_qualified.py` | `42adda1949e28f5362bb4e99ce456cad9991da7f6d542d962698562dba5e164f` |
| `.pytest_tmp/consumer-original-review/test_falsey_context_candidate.py` | `8802ee37349b5d10cab037253e0a81e0867b6e0beb36fbccd261a2dec6c073bd` |
| `.pytest_tmp/consumer-original-review/test_consumer_controls.py` | `e8f4dc17e8e787c3e408fbb165590267a5800be256298f7c14d83e4a7ee24b4b` |
| `.pytest_tmp/consumer-original-review/test_generic_shape_candidate.py` | `c779fec0bd725f2210ec162c23df02ab727c3ef4f7da064ceccad72a0a1c4bbb` |
| `.pytest_tmp/consumer-original-review/test_generic_shape_legacy_control.py` | `fe0a17223aec7d65a16b90b374c873d739fd01b895419def844413d2a2a21c25` |
| `.pytest_tmp/consumer-fix-original-red-01.xml` | `dc45360d53203ad5fb5d5cfacc25aa17992cec5ed8e38594a0cb453e188551e3` |
| `.pytest_tmp/tennis-consumer-rereview-20260909/test_independent_boundaries.py` | `9b293723cd92294b98c3669bced7922ead631407f0629d0771d581d165c3910c` |
| `.pytest_tmp/tennis-consumer-independent-original-01.xml` | `798f4f1b0e58b97ccfbd6e7712182ba42a90e7772eb757849369083123af0b38` |
| `.pytest_tmp/tennis-consumer-independent-boundaries-02.xml` | `4d017c9a7fa76ca116b80eb6c7a40fd7993cafc66d58566de57736f2fa5e4d92` |

This report's own hash is transmitted separately after writing; no self-referential hash is claimed.
