# P5a original capture — independent Root review

2026-09-10 CEST / 2026-09-09 UTC. Source frozen at
`8691022e70603311d0c2d93f003884b5b559dee5`, worktree
`.worktrees/kontext-football-original-20260909`. No source modification.

## Disposition: one P3 correction required

`football_original.calibration_recipe` checks that `MarketCalibration.samples`
is an exact integer but does not apply the representability check already used
for calibration points. An otherwise usable owning curve with samples
`10**5000` or `-(10**5000)` still calculates exactly as before: the count is
not used by its `__call__`. The new optional observation, however, feeds this
integer into JSON and raises Python's 4300-digit conversion error. The optional
capture then aborts a valid baseline. Both the direct owning curve and the
owning conservative wrapper reproduce it.

The small fix must mark only the unsupported recipe, preserve all original
model outputs and invoke the callback once. No clamping samples, changing
Python's integer limit, changing a curve, suppressing callback errors or
claiming new native evidence. This is an adversarial metadata edge, not evidence
that ordinary football probabilities are numerically wrong.

## Actual independent run

Owning 57 tests plus 18 new Root cases: **4 failed, 71 passed**, 5.48 seconds,
exit 1. The four negatives are the two signs in both owning containers.
All tests and original XML remain unchanged in the original worktree:

- `.pytest_tmp/p5a-independent-20260910/test_independent_capture.py`
  SHA256 `3fe95f459ba99779dc8be3496eca4e41a861732b91f869099d3421b9e8a4e7c4`.
- `.pytest_tmp/p5a-independent-root-01.xml`
  SHA256 `52c9aba8668b8e82fea456bcdbdc8eec62c17918f377d3ad18e53a7b044da969`.

Green controls include samples zero, negative one, representable `10**300`,
null, boolean, string and object without changing any original probability;
missing count families; ignored and duplicated raw positions in separate
league/team pools; the actual clock after all three curve calls; opaque
callables whose attributes cannot be inspected; price-free byte invariance.
The last probe's name mentions IO, but it measures price invariance only and
is not being reported as an actual IO interception test.

The actual Python code frames were profiled, not numerical outputs mocked:
one fixture model, three score matrices, two count models, six count matrices
and exactly three owning curve calls per configured calibrated market. Counts
and full original outputs are unchanged with the optional capture enabled.

The entire owning audit, new module and both new test files, both complete
production diffs and relevant actual model/provenance implementations were
read. The owning audit's SHA256 is
`677fea13acd6486dfe1cdcdf3c17868400fea2b126acb8789911f554d64b1bf8`.
Its separately reported 368 tests and 32 subtests are not added to Root's
independent count and are not a repository full-suite result.

## Frozen source identities

```text
football_original.py e5ccaf7d66a7b6138d602f7539f40f01f77095f73c1531d77d9bc69c04d5f2d9
challenge_engine.py 9e3b35cc9c0aba5f611d334336beaccfd4e885b280d9173dd98dcd7c6740922e
challenge_15k.py 289b3a2a2b4676666cf7c87f95af8c77260d0d4e812735f46854d6b2e5ec3c73
tests/test_football_original_capture.py 6909fe55fcca1888f9b7d5c8c5bc5ed5b1f12bc452b56399bca7d8be805f2546
tests/test_football_original_parity.py 1a91b75dd96527c7e03506b65bd9d3104a462279ad3f45ed56907288f26da962
```

The correction is assigned in another worktree on this exact frozen commit.
Original RED evidence is not overwritten. Actual final scanner publication,
B1/B3 linkage, shared consumer and empirical effects remain separate work.
