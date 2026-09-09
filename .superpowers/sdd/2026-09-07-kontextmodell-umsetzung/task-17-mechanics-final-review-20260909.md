# D2 mechanics final rereview — 9 September 2026

Disposition: **PASS for the bounded mechanics packet**. The original large-loss
F1 and the subsequently reproduced nonzero-underflow edge are resolved.
No open finding remains in this reviewed scope. This is not experiment-registry,
source, statistical model approval, real evaluation or runtime activation.

Exact final files:

- `context_models/validation.py` SHA-256
  `ed4e8dd075e0a259b70d3ed8b83307f8eb79699777cb11cab79cee35303144b1`.
- `tests/test_context_paired_metrics.py` SHA-256
  `d96678e9a133c1e494c3ec24d74eaba51afaffe7a94f40abe2860d78cfc12262`.
- The other five original reviewed files retain the hashes in `review-d2.md`.
- Original 91-case independent probe SHA remains
  `1ad5609ced098151afe9421d28c0613b07b530f3d0a529e363ef7b86cfa0eeed`.
- Additional 16-case extreme/mixed-numeric probe SHA remains
  `82988c3cfc959c8cf64eb53e01efc49f72d77563d6b44786549bb1a14c0d1f89`.

The first rereview and its precise two underflow REDs remain separately recorded
in `rereview-d2.md` (SHA
`12fa9488149a8a43cbd38e3bb82a5ffb8d83b99a30a565a9cd1f7e582b778764`). Root fixed
that edge while the historical first rereview report was being written; the
updated hashes were explicitly detected, then read and retested independently.
No test file used for independent reproduction was changed between RED/GREEN.

The final narrow follow-up introduces `_representable_fraction`: retain the
exact rational result, convert once, reject nonfinite overflow and nonzero
underflow with a typed contract error. `_finite_mean` now uses the same safe
rational accumulation before its one display rounding, avoiding pre-sum
subnormal loss. Actual event-paired differences are still computed independently
of displayed absolute means. Exact cancellation remains zero, including huge
positive/negative per-event differences whose mean is representable. A truly
representable minimum subnormal remains legal. Mixed integer/float arithmetic
keeps its exact numerical meaning.

The legacy engine HAC/BH extraction and calibration formulas remain byte- or
AST-verified unchanged as documented in the original review. This correction
does not change acceptance thresholds, zero-loss semantics, identity/chronology,
paired cohort selection or old 15K arithmetic. The fractional mean applies only
to the new D2 report arithmetic; no new empirical authority is inferred.

Fresh combined run: **246 passed in 2.56 seconds** with the designated Python,
`-B -m pytest -q -p no:cacheprovider`, fresh
`.pytest_tmp/d2-independent-rereview-final-01`:

- all 131 original shipped D2 tests;
- all 91 unchanged original independent cases;
- all 16 unchanged additional extreme/mixed-numeric cases;
- eight new permanent regression cases from the two controller fixes.

No full-suite rerun was performed during the separately active registry TDD,
as requested. The previous full-worktree result and its isolated missing-module
registry failures remain in `review-d2.md`, not converted into a green release
claim. No reviewed source edit, commit, push, provider call, VPS write or model
activation was performed by this reviewer.
