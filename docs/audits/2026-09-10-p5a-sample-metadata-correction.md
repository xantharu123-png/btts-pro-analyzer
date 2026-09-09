# P5a — finite sample metadata in the original capture

## Scope and reproduced cause

Narrow correction on exact parent `8691022e70603311d0c2d93f003884b5b559dee5`,
isolated branch/worktree `kontext-football-samplefix-20260910`. The original P5a
worktree and independently authored probes stay unchanged. The complete
approved context specification and P5a owning audit were read first.

`MarketCalibration.samples` is not used by its probability calculation.
The new original-capture recipe previously checked only `type(samples) is int`.
Thus `+(10**5000)` and `-(10**5000)` reached recipe JSON and triggered the
Python integer-to-string digit limit, despite a valid, already executed
probability. Both direct owning calibration and its Conservative wrapper were
affected. This is a capture metadata defect, not a model or calibration defect.

The exact independent probe and original Root JUnit were copied byte-for-byte
into the new worktree before any source edit. Original Root evidence was not
rewritten, recolored, or changed to another expectation.

## Exact change

Only `football_original.calibration_recipe` changes. Samples retain the
pre-existing exact-int requirement and are now passed through the same
finite/darstellable `_scalar` boundary already used for curve points. On a
failed numeric representation, the existing `issues` branch returns only
`unsupported-callable`. In a Conservative recipe this marks the affected child
recipe; the unchanged recursive limitation logic records
`calibration-recipe-unavailable`.

No sample is clamped, replaced, recomputed or written back to the curve. No
callback is suppressed. There is no global integer-limit adjustment, catch-all
JSON exception suppression, new model invocation, additional curve call,
metadata qualification flag, or source/empirical approval. The already computed
market probabilities stay bit-identical. Existing unknown callables remain
executable but not certified by this recipe.

Representable owning integers retain their exact integer value, including zero,
negative values and `10**308`. This is a representation check, not a new semantic
claim that a negative sample count is meaningful. The `10**309` boundary has
the same unsupported numeric behavior as existing point scalars. Bool, float,
string, object and null sample metadata remain unsupported, as before.

## Tests and evidence

- Unchanged independent reproduction plus original capture/parity tests:
  **4 failed, 71 passed, exit 1**, 5.38s. Each of the four failures is the actual
  digit-limit `ValueError` after a successfully calculated default probability.
- New permanent suite before correction: **6 failed, 24 passed, exit 1**,
  1.86s. Four direct/wrapper/sign cases reproduce the exception; two numerical
  boundary tests additionally establish parity with the owning point-scalar
  rule. Positive controls preserve exact representable metadata and reject the
  already unsupported types without changing probabilities.
- Final focused result: **416 passed, 0 skipped, 32 subtests passed, exit 0**,
  77.38s. Includes the unchanged independent probe (all four original failures
  now green), all 30 new permanent tests, original capture/real Parent parity,
  base provenance, calibration, xG, market eligibility, core regressions, 15K
  and context replay. No source/test edits occurred during that run.

The permanent end-to-end cases assert one actual callback, unchanged source
`samples` identity, unchanged interpreter digit limit, exact result bytes and
the recipe-only limitation. Default and real Parent parity are exercised by the
unchanged P5a tests, including the real historical Git engine/UEFA factory, not
by a newly written expected formula. No full repository suite was requested or
run. All test commands explicitly captured and returned `$LASTEXITCODE`.

Preserved evidence SHA-256:

```text
Root test_independent_capture.py 3fe95f459ba99779dc8be3496eca4e41a861732b91f869099d3421b9e8a4e7c4
Root original XML              52c9aba8668b8e82fea456bcdbdc8eec62c17918f377d3ad18e53a7b044da969
Own exact-original RED XML     b016f40d9bc3073b05c9c7205867f93738141e3c5f17c5eae6be429edee6a69e
Own permanent RED XML          4ac120923ad277cc2c115b8e1263a4837030edc87b6d22419699009123ac69a2
Own final focused GREEN XML    6f6527cab54012714ecc777b5f87be6c2c99686c745453a1495e8f57483bb6cb
```

## Frozen source boundaries

```text
football_original.py                  138fbe5a6570995e7274741dde84e2d4ea1a9cedb7efbaecb2856d91be88af1d
tests/test_football_original_samples.py 8f1866fb49896e89059813b83dc161898f8200ef10e564ea61ecebc09976831a
```

Unchanged parent files independently rehashed:

```text
challenge_engine.py                    9e3b35cc9c0aba5f611d334336beaccfd4e885b280d9173dd98dcd7c6740922e
challenge_15k.py                       289b3a2a2b4676666cf7c87f95af8c77260d0d4e812735f46854d6b2e5ec3c73
tests/test_football_original_capture.py 6909fe55fcca1888f9b7d5c8c5bc5ed5b1f12bc452b56399bca7d8be805f2546
tests/test_football_original_parity.py  1a91b75dd96527c7e03506b65bd9d3104a462279ad3f45ed56907288f26da962
```

No model, default prediction, quote, ID, history, Cricket, 15K, provider, budget,
consumer or server code was changed. No push, provider call, VPS operation or
deployment. The independent re-review and later integrated release remain the
controller's responsibility. P5a's pending real producer/source/consumer/D4 and
empirical connections are not made complete by this correction.
