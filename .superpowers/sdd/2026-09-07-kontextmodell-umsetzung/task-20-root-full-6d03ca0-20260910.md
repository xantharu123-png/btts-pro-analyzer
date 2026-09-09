# Root immutable integrated full suite — 6d03ca0

Completed 2026-09-10 CEST, 2026-09-09 UTC. Independent clean worktree
`.worktrees/kontext-integrated-qa2-20260909` remained at
`6d03ca00c487295a9a336e5917c314762e8ec637` for the whole run.

**6168 passed, 20 skipped, 97 subtests passed**, 1206.62 seconds, exit 0.
JUnit records 6285 cases including the subtests, zero failures/errors,
20 skips and 1206.529 seconds. Do not count subtests twice.

Command, using the existing quality interpreter:

```text
python -B -m pytest -q -rs -p no:cacheprovider
  --basetemp=.pytest_tmp/context-integrated-qa2-full-20260909-01
  --junitxml=.pytest_tmp/context-integrated-qa2-full-20260909-01.xml
```

XML SHA256:
`07cf9cd6ef66142a13f00b90c523ee7d3481c28da44f1ec828d477e65a230f6c`.

All 20 skips were individually read: unavailable Windows symlink privileges
or POSIX mode/owner/umask semantics. No selected product behavior was skipped
for a missing network credential. Separately, the actual Linux 785-case
fixture matrix and actual root/betboy DAC run are recorded in their own
reports; they must not be relabeled as a complete Linux 6168-case run.

This includes accepted Tennis producer/consumer, model/domain/reader fixes,
P4a/F1 originals, P4b1 native capture and trusted-hook/fixture fixes. It does
not include later frozen P4b2, P5a or P6a packages. No server deployment,
rendered-browser acceptance or real learned-effect/source readiness follows
from this full-suite result alone.
