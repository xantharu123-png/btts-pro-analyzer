# Root independent reader-fix rereview — 9 September 2026

Accepted narrowly: `40113925e165c378fdff6cb202ac80bc0df0f5fb`, based on
`7201302`, independently read in its frozen `kontext-reader-fix-20260909` WT.
Root read the full final owner report, entire 57-line shared reader change,
closed physical-schema diff and both permanent test files before execution.

Both unchanged original F1/F2 finding cases and the two unchanged qualified
WAL controls were rerun, together with 10 new Root-only probes and all 61
permanent reader cases: **74 passed, 1 genuine Windows symlink skip, 7.48s**.
The first combined invocation collected conflicting same-named test helpers
from two worktrees and ran zero tests. Preimporting the exact target helpers
resolved the harness collision; no original probe or production code changed.

Root additions check frozen source hashes, real special-character database
paths, query-only/trusted-schema/read transaction, denied data/schema writes,
native close despite rollback failure, missing-store noncreation and late
hardlink aliases of all three companions. No new findings.

JUnit in fix WT: `.pytest_tmp/root-reader-rereview-20260909-02.xml`, SHA256
`8fc6c96c0cee75446d945a4c348a0cbddcc493401c9a3f80fb3a3cee19d7c439`.
Root probe in root WT:
`.pytest_tmp/reader-root-rereview-20260909/test_root_reader_checks.py`, SHA256
`fa3afb1d72f178ef8c47a9d72f377521af59b025b9e8e4db0518560ba2ae800d`.
Frozen consumer/dataset source hashes remain
`b49824992a65505f4ef9fd39d2c32fe5d79fee9fbcc153d45116c88a1892decd` and
`a63ea094fe38635af3f5175597afc3b4b167e162f3a8af0e8f0540af80c99fde`.

This accepts the observed physical trust and schema correction. Trusted live
WAL metadata remains permitted; same-trusted-user replacement races are not
claimed impossible. No source truth, numerical empirical approval or production
activation follows from this result. Merged into Root as `ef1aea8` with exact
source hashes preserved; Root integration run is recorded separately.
