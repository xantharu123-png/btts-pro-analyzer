# Task62 unit transport I1 fix review

Spec/scope verdict: COMPLIANT for the scoped I1 correction.
Quality verdict: APPROVED for the unit-test instrument; native execution remains unverified.

I1: ADDRESSED. No directly introduced Critical or Important finding.

Reviewed only the changed remote-command line and its two explanatory comments
in `evidence/task62-native-unit-run.ps1:37-39`, plus input hashes. Runner SHA256
`82376c096693bae729289e932d3a4b3f89ca3becd6983d558ab57bbcb97d65fd`
and unchanged entry SHA256
`3f290ec20e4a14c613e3866e0ae9ad92ac0dd70cc77599f66eb001a99f55c00e`
match dispatch.

The fixed command now places `/usr/bin/timeout --signal=TERM --kill-after=5s
210s` outside the isolated Python controller and inside external GNU time.
Thus timeout supervision starts before Python/archive setup and encompasses
the two pytest invocations and output processing. Default non-foreground
process-group supervision is retained. TERM is scheduled at210seconds with
KILL escalation five seconds later; neither `--preserve-status` nor retry is
introduced. Timeout failure remains a nonzero result propagated through the
existing SSH exit handling. This addresses the missing controller wall bound
without relying on an in-process alarm while the controller owns a child.

The clean environment, ordinary-user interpreter invocation and frozen payload
are unchanged. Root reports a fresh read-only UID1000/target/interpreter/GNU9.4
preflight and unchanged225215-byte payload; these are supplied controller
evidence, not checks rerun by this reviewer. Root also reports consulting the
official GNU timeout manual. The reviewer's attempted fetch of that exact
manual URL timed out; it supplies no additional independently retrieved evidence.

No successful timeout signal or SSH exit alone establishes complete process
death. Root's required post-exit process readback remains necessary, especially
after abnormal termination; do not retry or infer cleanup from disconnection.
Native RED/GREEN and actual terminal/artifact observations remain unexecuted
acceptance gates. Real retained-union timing, diagnostic admission, baseline and
C/B/empirical/release claims remain outside this approval. T2 generic transport
log caps stay deferred and are neither revisited nor closed.

No tests, native/VPS command, Git operation, instrument/source edit, broad crawl
or subagent dispatch occurred. Only this fix-review report was written.
