# Independent B6/B7 correction rereview

9 September 2026; reviewed commit bf75820636e4944d05fc28c6067ab58282de806b.
Read full source diff from 96988c93eb6a8173fdfbc4402e2cbbc38c05f081, all new
permanent tests, full final audit amendment and the Controller's explicit
bounding/coverage/zero-value ruling. Source files were not modified. No network,
provider call, production data, empirical or runtime action.

## Disposition

**Scoped review approval: both original findings are closed; no new finding
in this correction rereview.** This is not an empirical or production release.
The separately repaired shared B2 integer-fit guard still needs Root's combined
integration; it is not counted as a new issue here. Training inventory, D1/D2,
actual serve successes/trials and runtime delivery remain separately open.

## Exact reviewed bytes, unchanged after all review tests

- context_models/tennis.py: 313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab
- context_models/tennis_effect.py: 41c5bb4f10fef2cdef73795bf25dfbaa00e65529dda09b4a8e6fb9ecffa7ecb9
- tennis/simulator.py: 6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f
- tests/test_tennis_context_features.py: 9f9874ee40a67754154f4b1ba4ff7db067d27c40cd254302a0f180dbb51dcfce
- tests/test_tennis_context_model.py: bd8836f68c3951c9b66cf06b4d2a48328797bab02f9d1a7758d4aaa03a356473
- tests/fixtures/tennis_simulator_legacy_dd6fd38.py: c0f6a751b09c59c3bb547d13703eb854094c0b6b5527f2bc27358086b3da3734

Worktree stayed Git-clean at the final freeze check. Original reproduction
package is unchanged: test_independent_b7_review.py, SHA256
4163e4470cca8460e93f0438e0f0bd1433a0489ada30e83d9f715b3115d566ab.
New independent boundary package: test_independent_b7_rereview.py, SHA256
d73a5317b5b175074d743ad5c337e4313920372c7602d6708ab7608f803ded81.

## Independent executions

- b7-worker-rereview-original-01: **266 passed**, 4.42 s. Includes the untouched
  original 18-case attack package, all B6/B7 tests, strict simulation and exact
  legacy fixture parity. The original four failures now pass without rewriting
  their expectations or normalizing away the last-bit discrepancy.
- b7-worker-rereview-attacks-01: **18 further independent cases passed**, 1.51 s.
- The owning implementation audit's 2950/15/97 full-suite result was read, not
  presented as a newly executed full-suite run in this rereview. The earlier
  review independently ran all 2931 existing tests on the original target.

## Additional adversarial checks

- Each 1/3/7-day lower boundary, one microsecond before/on/after: only strict
  `terminal_upper_bound < window_left` permits exclusion. The equality case
  remains unknown because the window includes its lower edge.
- The old exclusion receipt remains a completeness/rest witness but never
  becomes numeric in-window sets or an invented actual end. Complete career
  flags remain zero; null recent minutes remain null even when sets are known.
- Latest actual end must dominate EVERY unknown upper bound. A second upper
  bound one microsecond later removes exact recovery; equality remains safe.
- One entirely bounded side cannot hide a recent, potentially relevant unknown
  end on the other side. That case remains receipt-bound/partial and cannot
  consume a complete-load coefficient.
- A real Normalizer/B1/B6 partial-exact case can consume only its supported
  exact-rest dimension. Its uncertain workload remains unusable. Changing its
  fitted coverage to all-known is rejected; no silent all-known transfer.
- A numerically unchanged but nonzero tiny residual retains original market
  bytes, as do true zero features/coefficients. Returned dictionaries are detached.
- Winner and serve B3 base/comparison/used values preserve exact originals at
  zero effect while remaining experimental, with no certified markets.

The new bounded-irrelevant and partial-exact coverage cases preserve the
distinction between proving exclusion/latest-end dominance and knowing every
old actual timestamp. They grant no training approval and do not loosen the
handling of genuinely relevant unknown end times.
