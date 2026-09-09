# Shared Tennis consumer: bounded independent-review corrections

9 September 2026; isolated worktree `kontext-tennis-consumer-fix-20260909`,
base `3e415db63894ab6d206cf7b87ff0f804aded1ab0`.

## Original findings remain preserved

The independent report was read in full. Its frozen original location is
`.worktrees/kontext-tennis-consumer-20260909/.pytest_tmp/tennis-consumer-independent-20260909/REPORT.md`
relative to the primary checkout; SHA256
`08724efbb75169e304eb09d1bf32b332842ae3a2c5794769cb413be5065a4c94`.
Disposition there: exactly two P2 findings and one P3 regression. No alteration
of that report, its six original probes, the original worktree or its Git HEAD.

All seven artifacts were copied byte-identically into this worktree's
`.pytest_tmp/consumer-original-review`, checking each source hash before/after
and each destination hash. The six unchanged probes reproduced **31 failures
and 36 passing controls, 10.52 s** on the original source before this fix.
They were rerun unchanged after the fix, without deselecting or weakening a case.

## Exact repair

- Retain the already-read A1 `tennis-tour-state` artifact. Check its known
  wrapper shape, the state codec's closed key inventory, integer version 1 on
  both layers, and exact state tour against the bound Event/Shadow tour.
  This is a header/identity check, not Elo/Serve decoding, fitting, prediction,
  native historical name resolution, D4 replay, or latest-manifest inference.
  Nested training/model values remain the producer and D4's responsibility.
- Only absent/None/empty-text context and valid legacy JSON objects can mean
  optional legacy context. Present nontext values (including False, zero and
  empty containers) raise typed integrity errors before any database access.
  No probability or price value is being filtered by this metadata rule.
- The held generic reader checks the base's object shape and uses explicit
  event/cutoff presence comparisons before projection. Malformed physical
  snapshots retain `ContextContractError` rather than leaking a raw TypeError
  or KeyError. The full owning projection validator is unchanged.

The only production edits are in `tennis/context_consumer.py` and
`context_consumers.py`. Normal/Risk adapters, their selection/price/rank/set
semantics, source/worker code, original rows, all ledgers, Cricket, transport
schemas, model values and empirical approvals are unchanged.

## Permanent regression and observed runs

New `tests/test_tennis_consumer_binding.py`: **49 cases**. They retain the real
stored Shadow revision reader and all three actual adapters for foreign-tour
and same-tour witnesses. Disposable SQL stores only: the existing revision
immutability trigger is restored byte-identically after the public-rehash
witness. Synthetic model-gate fixtures are not evidence of real calibration.
Additional cases cover exact header shapes/types, malformed metadata, explicit
legacy controls and typed generic failures. Reader spies prohibit model decode,
prediction, publication and provider access. Source databases stay byte-identical
during each consumer assertion.

All runs use the existing quality Python, `-B -m pytest -q -p no:cacheprovider`,
unique basetemps/JUnit and an explicitly existing `.pytest_tmp` parent.

| Run | Observed result | JUnit SHA256 |
| --- | --- | --- |
| `consumer-fix-original-red-01` | Original independent probes: 31 RED / 36 GREEN, 10.52 s | `dc45360d53203ad5fb5d5cfacc25aa17992cec5ed8e38594a0cb453e188551e3` |
| `consumer-fix-rereview-green-02` | All 67 unchanged probes + 49 old owning + 49 new permanent: 165 passed, 22.66 s | `a91707ee5e8fb1d51169f8308c8645036d5fa1454f05547f21676d1b4cc67b23` |
| `consumer-fix-broad-green-03` | 680 passed, 1 existing Windows symlink skip, 26 subtests passed, 32.05 s | `814d9a329fac2c7a27d966d5ffbda5f00060f39b63b4e9f1d5c9104e8c47de06` |

JUnit files are `.pytest_tmp/<run>.xml`. The two passing commands explicitly
returned native exit code 0; the original RED command returned 1. The wider
focus is the independent report's same 15-file suite plus the new permanent
binding file. It is not a full repository test, browser acceptance or Linux run.
The original 31 failures overlap the new permanent cases; do not add the counts
as distinct product bugs or unique coverage.

## Frozen raw source hashes

```text
0566911f00924902d6f10a76947d62d08425bda5e83b9444b32378e45a0cabc2 context_consumers.py
bb07da8c63102712bae093fe225109e52d7ee24f7b1936416afc5e5c8d308e89 tennis/context_consumer.py
ece91dc0288e633695f4176c5c1cd6ffd44f98d48b698634982e7ca3b0b8cb26 tests/test_tennis_consumer_binding.py
```

Original probes, both generations of RED/GREEN XML and all prior WIP remain
preserved. The narrow fixes are ready for independent recheck. No full suite,
main push, provider call, production database change or VPS deployment is claimed.
