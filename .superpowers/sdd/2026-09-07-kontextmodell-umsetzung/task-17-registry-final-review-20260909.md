# Independent R1/R2 registry rereview

Date: 9 September 2026. Reviewer: `/root/b3_shared_snapshots_20260909`.
Disposition: **PASS for the bounded freeze/open registry corrections.** Both
original P2 findings are resolved in the reviewed bytes; no additional finding
was reproduced in 51 new independent checks. This is not D1/D2 empirical,
source/case, evaluation, BH-result or activation approval.

## Exact frozen scope

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Starting HEAD: `dfcc6d357c536e4390322c1267bc26957663ddbd`.
Only these two WIP files belong to this rereview:

| File | SHA-256 |
| --- | --- |
| `context_models/experiments.py` | `080bcf30cf48b14dafdb045611414cf9d82ce975d93ea951022fb99c3bd17ce1` |
| `tests/test_context_experiments.py` | `b071f2e5e70f14ca20b2f82a75d47e67da7ff3b3fcdb376ec66449bab8c66202` |

Hashes matched before inspection and after the combined run. Both complete
files, the original review and unchanged reproductions were read. The complete
current validation decisions were reread, including the frozen inventory/opening
section. Actual A1 put/load/connect/first-insertion behavior was inspected;
the changes were checked against the original R1/R2 locations and narrow fixes.
No reviewed-source bytes were edited.

Supporting unchanged A1 `model_artifacts.py` SHA-256:
`6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16`.
Validation decisions SHA-256:
`af080edc12eb2735107b96c59998363728a02c181377c24b7c66893c136d4abd`.

## R1 — resolved

The registry now normalizes actual A1 first-insertion metadata independently
from the public kind/payload digest. It enforces candidate creation in the
closed interval `[training_end, experiment.created_at]`, identity-map creation
no later than freeze, and exact normalized actual/payload creation agreement
for owned experiments and openings. Both load and INSERT OR IGNORE persistence
paths enforce the correspondence. An ignored second insertion cannot repair
an inconsistent first clock or overwrite a consistent original clock.

All five unchanged original clock reproductions pass. Independent additions:

- 12 candidate lower/upper boundary cases: each endpoint and one microsecond
  either side, through both freeze and opening consumers.
- Six identity-map boundary cases: freeze minus/equal/plus one microsecond,
  through both consumers.
- Eight first-insertion cases: experiments/openings, initially valid/invalid,
  earlier/later conflicting second insertion. Actual original rows remain
  byte-for-byte unchanged on repeat and rejection.
- Three normalization cases change all four actual reference/owned timestamps
  to equivalent UTC-12, UTC+05:30 or UTC+14 forms, including date changes.
  Exact freezes/reruns succeed and preserve those original stored bytes.

The contract remains microsecond-normalized aware time, not an external clock
attestation. It does not invent source receipt truth or conflate retrospective
logical cutoffs with physical artifact construction.

## R2 — resolved

`_openings` now iterates the whole A1 artifact digest inventory and verifies
each row's digest, kind/payload byte representation and timestamp type/format
before dispatching on the returned kind. The original changed-kind reproduction
passes. A detectably corrupt row can no longer disappear through an unchecked
SQL kind filter.

Fourteen new corruption cases use an unrelated artifact, not a conveniently
selected opening: BLOB kind, malformed digest, TEXT payload, noncanonical JSON,
naive timestamp, BLOB timestamp and malformed timestamp, each through freeze
and open. All reject without additional or changed rows.

Four valid generic-kind controls remain accepted and byte-identical. Their
payloads deliberately resemble invalid/future opening or case schemas and
contain synthetic label/price fields: the registry checks generic A1 bytes but
does not treat them as an opening, evaluate labels or confer evidence/approval.
This is explicitly structural transport compatibility, not future-kind support
or a verified case. Only the declared v1 opening kind owns reservation semantics.

No protection is claimed against deletion or complete reconstruction of the
database and its public hashes. No extra SQLite table or manifest format was
introduced.

## Concurrency and transaction controls

Two new real races start a generic A1 insertion and registry insertion together
with a Barrier, for experiment and opening. Both possible first-writer orders
are handled: a registry success must have a matching retained actual clock;
if the inconsistent generic insertion wins first, registry consumption must
reject, including the subsequent retry. Exactly one artifact is added. These
races do not claim that the scheduler exercised both orders; the eight explicit
first-insertion cases above independently cover both orders deterministically.

Two further checks attempt a second real SQLite `BEGIN IMMEDIATE` with zero
busy timeout at the registry persistence boundary. It is locked for both
operations, consistent with the inspected transaction covering validation,
inventory dispatch and persistence. Existing unchanged three-opener and
failure-after-real-INSERT rollback/retry cases remain green. No sleep-based
race proof or fake SQLite connection is used.

## Reproducibility

Original reproduction file remains unchanged:
`.pytest_tmp/d2-registry-independent-20260909/test_registry_independent.py`.
SHA-256:
`a180f183bb2178afe3cc20bb86b938d71392e8ed17f4f74e31a3449c1740e734`.

New independent file:
`.pytest_tmp/d2-registry-independent-20260909/test_registry_rereview.py`.
SHA-256:
`ef34a52a8eb6042275b0794d8299d6649547ed44d8450b932aa5856b9a3011e8`.
It passed on its first execution and was unchanged for the combined run.

Each run used designated quality Python with `-B -m pytest -q
-p no:cacheprovider` and a fresh basetemp:

| Run | Result | Basetemp |
| --- | --- | --- |
| 60 permanent + 25 original independent | 85 passed, 2.75 s | `.pytest_tmp/d2-registry-independent-rereview-original-01` |
| New independent boundaries/first insert/integrity/races | 51 passed, 2.09 s | `.pytest_tmp/d2-registry-independent-rereview-new-01` |
| Combined frozen packet | **136 passed, 4.59 s** | `.pytest_tmp/d2-registry-independent-rereview-combined-01` |

No full-worktree run was added while Root performs unrelated Linux/D4 work.
Its separately supplied Linux/Windows fixture results are not included in
these counts or claimed as this registry reviewer's evidence.

Remaining scope: real receipt-resolved identity/cases, full registered paired
evaluation and BH reporting, report/approval provenance and actual empirical
activation. These are neither supplied nor claimed by this mechanics packet.
No commit, push, provider/API call, SSH, VPS, pinned-helper, production-state,
model-activation or financial action occurred. Only isolated QA probes/report
and their temporary databases were created.
