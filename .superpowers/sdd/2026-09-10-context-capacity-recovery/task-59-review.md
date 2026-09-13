# Task59 independent review — candidate7bb292e

Reviewer /root/c_growth_profile_review,sol/high; BASE32c7edd1c5d4b178ac80cdead8848be63b2fa91d,
HEAD7bb292ee5d11cca36836e289f4a50ed8c9fffa5c.
Package task-59-review-32c7edd-7bb292e.diff,42869bytes.

## Spec Compliance

- Issues found: the supplied tour seed cannot carry and preserve all explicit
  prediction inputs. tests/context_growth_profile.py:221-247 reads only surface
  from the caller's fixture and substitutes best_of=3,indoor=None;
  :317-340 declares no precise input type containing those values. This
  misunderstands task-59-brief.md:28-32. The real consumer requires explicit
  surface,best_of,indoor arguments at context_storage_v2/tennis_consumer.py:284-306.
- Remaining reviewed contract implemented: lazy bounded generation/immutable
  descriptors at tests/context_growth_profile.py:56-178; exact tour/key/clock
  scheduling :127-163,250-314; real normalization :194-203,221-238; target-only
  labels :106-125. Cricket/odds/ranking/forecast math/product/storage/existing
  tests untouched by this three-file diff.
- Cannot verify from data-only task: sealed baseline, old-row collision freedom,
  stored preservation, model-state/Source/D2 authority, complete corpus/native
  capacity/observed590553/199/199/114. Correctly excluded by report:201-215;
  Root confirms these are still separate uncompleted integration gates.
- Diff rendering truncated mid-hunk; reviewer inspected the two changed
  code/test files under the cut-hunk exception. No suite rerun.

## Strengths and evidence

- Schedule vs on-demand real normalization separated without490000-row
  retention (module:143-203); frozen canonical fixture bytes/detached copies
  (module:260-314).
- All three complete cheap schedules independently counted, with IDs,
  consumer membership, cutoff grouping and actual burst ties/backward edges
  (tests:84-182).
- Representative/all consumer records use actual physical decoder/source
  validator (tests:64-81,185-203; unchanged context_observations.py:80-99).
- Retained child/outer0/0,29pass,empty stderr/no timeout (report:144-176).

## Important finding I1 — required before integration

tests/context_growth_profile.py:221-247,317-340: the seed contract omits
caller-supplied best_of and indoor, then silently invents3 andNone. Consequently
the generator cannot represent or preserve an indoor fixture or best-of-five
prediction input, despite the brief requiring explicit prediction inputs.
Tests cement the substitution by supplying no such inputs at
tests/test_context_growth_profile.py:34-50 and asserting the constants at:150-152.
Define a precise tour-seed input shape carrying the native competition plus
surface,best_of,indoor; validate/freeze it and copy those values unchanged into
every descriptor, with tests for non-default ATP and WTA values.

No Critical or separate Minor findings. Spec NOT compliant; task quality
NEEDS FIXES. Otherwise strong bounded scheduling/normalization/isolation;
the hardcoded inputs make later consumer integration semantically unreliable.

## Scoped fix-round1 review — final6ce7702

Same reviewer /root/c_growth_profile_review,sol/high; FIX_BASE
7bb292ee5d11cca36836e289f4a50ed8c9fffa5c; HEAD
6ce770235341e1979c8e86eba49534e846b04ab7. Immutable package
task-59-fix1-review.diff,28262bytes, read once; no Git commands or suite rerun.

Finding I1 — ADDRESSED. tests/context_growth_profile.py:1-20,39-52,216-272
defines the exact closed five-field seed mapping, validates explicit surface,
best_of and indoor, derives grouping from tour and preserves supplied scalars
instead of defaulting them. tests/test_context_growth_profile.py:31-69,146-163
exercises non-default ATP/WTA inputs; :210-238,274-338 verifies mutation
isolation, explicitNone, missing/unknown fields and invalid values.

New Breakage — None. The fixed mapping matches the Root ruling; surface=None
and indoor=None remain representable while invalid inputs fail before iteration.
The real consumer transports them explicitly at
context_storage_v2/tennis_consumer.py:284-286,348-351; the model accepts optional
surface/indoor and best_of3/5 at tennis/predict.py:113-165.

Out-of-Scope observations — None.

Evidence checks: report:285-310 records child/outer0/0,42passed, empty stderr,
no timeout; :312-317 records corrected tested hashes. Root independently parsed
XML42/0failures/0errors/0skips,time9.734 and matched all reported final hashes.

Fix round verdict: ALL FINDINGS ADDRESSED; NO NEW CRITICAL/IMPORTANT BREAKAGE.
With the preceding complete review, final Task59 spec is compliant and task
quality approved. The explicit full-native/Source/D2/global/B/release exclusions
above remain open future gates, not silently converted to a pass.
