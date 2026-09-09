# Independent D4 live Tennis review — 9 September 2026

Disposition: **PASS for this bounded packet; no qualified findings.**

Reviewer: `/root/worker_failures_20260909`, independent of the Root author.
The reviewed checkout remained clean at
`5d5bab6650df67bba653249e02f4c7a4e4691cdb`, compared with
`22a1f37e5c33b4885f99238f6034caed1fb42dbe`.
Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-tennis-d4-20260909`.

This is not a full-repository, native-source-completeness, empirical betting,
Linux/DAC, production consumer, updater policy, push or VPS release acceptance.
The reviewer changed no source, owning test, pinned helper, Git ref or production
data. Only ignored independent probes, their temporary stores, JUnit outputs
and this report were created. No provider/VPS requests or full-suite run.

## Read scope and frozen identities

Read the full owning audit, all five source/test changes and the actual producer,
tour-state decoder/load path, live-origin contracts, native status selector,
v3 feature builder, D4 artifact/receipt/snapshot transaction and pure transport
projection. The complete diff contains six files: five code/test files plus the
audit, 548 insertions and four deletions. Relevant approved D3/D4, B6/B7 and
context/validation decisions remain the contract; this review creates no new
native alias or empirical permission.

All six raw SHA256 identities were checked at the start and again after the
independent executions; every value stayed identical:

```text
context_runtime.py
  974917709b8e292b9621c6bef17112794a0724c4885f04f97052bde3799eab3e
context_runtime_tennis.py
  a43bce930e10763bc97d24af639057ee2a674c704782629d1eed796e9fd22340
context_sources/tennis_status.py
  696302d12822151105d2e2067d22d216d0071f47446799e462744271910b62a4
context_transport.py
  a47d980a4e528ef12917db39e47d025c4670070737901f6e8c9688dfe84a1a9e
tests/test_context_runtime_tennis_live.py
  ed40f9b9a2887e85a871b4835285e4a4613cf12a5f4cbddf18c077d2f48b54a7
docs/audits/2026-09-09-d4-tennis-live-replay.md
  222bce666edd52519d09f1c0e276f01e9ca076c92351f5081d2cf4592f7ea35b
```

The owning audit and original author REDs are unchanged. The report below does
not count author-reported runs as reviewer evidence.

## Independently established behavior

1. **Actual original A1/B1 binding.** Every known live original is checked even
   without a snapshot consumer. Missing/wrong-kind/wrong-tour/late tour state,
   a different valid predecision calibrator retaining the old probabilities,
   and changed original numerical inputs fail after public identities are
   rebuilt. Existing author cases additionally exercise raw/calibrated numbers,
   native receipt/time, competition revision, code identity and full event.
   The real owning predictor is replayed offline on the decoded referenced
   immutable state; no model refit is introduced.
2. **Current native revision and exact cutoff.** New cancelled, postponed,
   started, incomplete participant, scheduled-time, swapped participant and
   unsupported terminal-code revisions fail when received before or exactly at
   the original cutoff. The same revisions received later do not retroactively
   alter that original. Same-clock identical ingestion is idempotent; a genuine
   conflicting whole revision is rejected.
3. **Entire causal history, not just the supplied reference list.** With actual
   received bilateral previous matches in SQLite, omitting a newer predecision
   cancellation/start/incomplete-pair history record cannot preserve an old
   minimum recovery delta. If the worker receives that cancellation before it
   calculates, recovery stays unknown. A genuine new complete terminal revision
   restores only its own receipt-bounded recovery. In both cases the exact end
   and exact recovery remain unknown; the unchanged baseline stays in use.
   Later-than-decision history does not rewrite the earlier feature vector.
4. **Physical integrity before availability.** Modified receipt event, source,
   subject, kind, clock or schedule index fields fail. Removing either one
   actual bilateral workload receipt or its content fails. These are not
   silently reported as missing context or converted to zero.
5. **Public rehash is not semantic authority.** The qualified reader probes
   rebuild the input key, feature-reference digest, result base hash and payload
   digest directly. Changing one live version/kind marker, an integer schema to
   Boolean, or a coherent winner distribution by one ULP still reaches and
   fails the actual pure card projection. The raw arithmetic is not approved
   merely because all public hash layers are consistent. This is independent
   of HMAC; it is not a claim to detect an arbitrarily replaced, internally
   consistent entire world without an external trust anchor.
6. **Offline replay versus pure card reading.** Spies forbid SQLite access,
   model-source file reads, prediction, fitting/calculation, B1 path reopening
   and provider requests in the respective pure projection boundary. Both
   market orientations retain the exact unrounded original probabilities and
   their same immutable reference; payload bytes are not mutated. D4 source
   selection consumes its already decoded image, not a new live B1 connection.
7. **Actual mixed D2/live store.** An unopened real local D2 experiment (synthetic
   football mechanics, actual A1/B1/D1 dataset) was copied with SQLite backup,
   then the actual Tennis worker published an original and B3 snapshot into that
   same store. The final outcome decoder was guarded. D4 replayed the Tennis
   original without decoding the unopened final labels or feeding them to the
   Tennis selector. Corrupting a protected final BLOB failed its byte/index
   boundary before Tennis replay, without opening the outcome body. This is a
   full-store integration test, not an isolated tuple/flag mock.
8. **Legacy boundaries.** The independent 375-case run includes old Tennis v2
   winner/serve and all five consumer families, C3/C4 transports, exact transport
   bytes, actual legacy predictor parity, native v3 capture/status and existing
   D4 backup/restore/integrity. The packet does not change those model sources
   or the existing Cricket/15K/price/ranking behavior. It does not qualify a new
   effect, native historical state-name resolver or real court model.

The producer records an actually used predecision state; this review does not
invent a requirement to replace a legitimately loaded state with the newest
manifest at a later clock. The referenced state's actual bytes, tour and clocks
and its exact prediction remain binding. Likewise, recorded native-to-state
identity remains explicitly `unresolved`; replaying the recorded name inputs
is not evidence for a new historical alias resolver.

## Reviewer execution ledger

All runs used the quality Python runtime, `-B -m pytest -q -p no:cacheprovider`,
distinct temporary directories and JUnit reports. Times below are actual
independent pytest results. Runs overlap; do not sum them as unique coverage.

| JUnit under `.pytest_tmp/` | Actual result | SHA256 |
| --- | --- | --- |
| `tennis-d4-independent-owning-01.xml` | 37 passed, 6.47 s | `3e9b1d0f7db5eafdb66c25740d4f1e14b629326df83d5d31031468ead22eea3e` |
| `tennis-d4-independent-probes-01.xml` | 1 reviewer collection error, 0.72 s | `b10884102b2baa56e19bff3815107cc48d030b05eaa80ae15c5fcded1ed3f942` |
| `tennis-d4-independent-probes-02.xml` | 50 passed; five reviewer construction failures, 9.75 s | `6112d6faa1872fbc460ce9fcce144ca4a416e0778ca4bb2823569abb2ae0b57d` |
| `tennis-d4-independent-qualified-03.xml` | 57 passed; eight explicitly replaced original cases deselected, 9.92 s | `9a3a72f12a03fff8eb3806df58cd69b8c537aedf6003e17670df3f047461ba18` |
| `tennis-d4-independent-regression-04.xml` | 375 passed; three Windows/POSIX skips, 37.52 s | `094d26c3b885e22d3e3f358e008ef8e651b1ced5d7f822e4de9860084f89d318` |
| `tennis-d4-independent-mixed-05.xml` | 2 passed; no skips/deselections, 52.53 s | `3e90b7a65bf50d458a9dcde4612947241d593dc98af7f58c8b3516dd2aa0e212` |

The first collection command omitted the tests fixture import path. No source
change was needed: explicit `-o 'pythonpath=. tests'` fixes that harness command.
The initial 55-case independent source remains byte-for-byte intact. Its five
failures were **not product findings**:

- One restoration control compared an independently written decimal expression
  as bit-exact to the existing timestamp arithmetic (one rounding bit differs).
  The qualified control tests the minute-scale expected value with `1e-14`
  absolute tolerance; it does not loosen any model/feature binding validator.
- Two removal setups queried `kind='performed_match'`, but the actual B1 kind is
  `workload`; `performed_match` is the source fact, not that table index value.
- Two invalid-origin card probes called a validating reference-hash constructor
  before the actual projection, so the owning validator rejected setup early.
  The qualified witnesses construct the public digest directly, reach the real
  projection and still reject. There is no weakened final assertion.

`test_qualified_tennis_d4.py` supplies all eight parameterized cases from those
three functions plus two new actual-state/calibrator negatives. The final
combined command deselects the original three functions (eight cases) rather
than editing their source or hiding their first results. The remaining original
47 tests plus the qualified ten tests give the stated 57 passes.

The three regression skips are exactly two actual symlink cases for missing
Windows privilege (`WinError 1314`) and one POSIX world-writable-mode check.
No claim of a Linux filesystem/permission proof is made.

## Frozen independent probe identities

All paths below are relative to this report's directory. No original failure
file or assertion was overwritten:

```text
test_independent_tennis_d4.py
  d890430f0d775dd0f4218750f8003a91eaae5938ac2319e1fcce6c1154596eeb
test_qualified_tennis_d4.py
  ae9c794fbbbc818636a7d2a2cfecadb23d0ee2978f7b2fa9be448cccf1b72092
test_mixed_unopened_tennis_d4.py
  b248102379275efa5252982addc68896e5e888783914d8ab5c98deb0baefd9f2
```

Reproduce the qualified witness set from the reviewed worktree:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -o 'pythonpath=. tests .pytest_tmp/tennis-d4-independent-20260909' --basetemp=.pytest_tmp/REVIEW_NEW_UNIQUE .pytest_tmp/tennis-d4-independent-20260909/test_independent_tennis_d4.py .pytest_tmp/tennis-d4-independent-20260909/test_qualified_tennis_d4.py -k 'not test_real_predecision_cancellation_is_unknown_until_own_new_terminal_revision and not test_missing_one_actual_bilateral_history_member_is_rejected and not test_public_rehashed_card_metadata_does_not_bypass_exact_original'
```

Run the mixed-store file separately with `-o 'pythonpath=. tests'` and a fresh
basetemp. The original first source may be run unchanged to reproduce the five
documented reviewer setup failures. Do not relabel them as source regressions.

Actual local legacy raw hashes, not a cross-platform recipe claim:

```text
tennis/predict.py bd1c2c8f7666e3de5f32d754eac09967edde566c1d7b48c298635f2b3d989ecc
tennis/model_state.py 3512c7aa047d11f809402fe434fcaae6ebf0542e961174348d2e6972198d7134
tennis/elo.py 689c50cdd9cbb5489ff66fbcc10814683c18ebcc79c97b648ceea4db738083c6
tennis/serve_model.py dd76339957cc806e5bea14584c47c9467b242966bd531a6c03adf3b067e803aa
tennis/simulator.py 6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f
tennis/data_loader.py 521bb2525a8a874b64f4afe55c49e18c075bdc04348e38b1632c95af6aec4620
tests/fixtures/tennis_predict_legacy_da0ae34.py f92d9451d3e7c0612832101ab1d6298cb99baeeaaa4f2d7c89cb8e9fe0526c7c
```

## Remaining boundaries, not waived

The accepted packet is the mechanical offline replay and pure identity binding
shown above. Its named D1/D3 limitations remain present and empirical approval
stays false. Upstream completeness, native historical player/state identity,
real physiological effects, court qualification and prospective training data
remain separate. Context-store verification is not a full Shadow/15K money-
ledger join, nor an external authenticity guarantee after a wholly consistent
replacement of all evidence. Code compatibility is limited to the supported
raw/LF/CRLF variants of the six recorded source files, not arbitrary source,
dependency or interpreter changes. Future model code requires an explicit
compatible replay contract. Browser, actual shared consumer integration,
production Linux restore/permissions, whole integrated suite and VPS deployment
are not established by this local review.
