# Task10 native measurement harness delta review

Date: 2026-09-11. Bounded read-only review of ignored measurement supervisor,
not product/full-branch review or native acceptance. No script/product/test/
index edits, SSH, application imports, execution, native job or subagents by
reviewer. Only this report is authored.

## Preliminary verdict

**APPROVED delta design; execution HOLD until exact corrected revision repin.**
No blocking delta finding. The current
`TASK10_CORRECTED_COMMIT_PENDING` intentionally fails closed: it cannot satisfy
both the40-lowercase-hex revision check and equality to that nonhex string.
This is not an executable accepted candidate yet. Controller must provide the
corrected commit and final helper SHA for a narrow repin review before use.

Reviewed complete `.pytest_tmp/measure_task10_profiles.py`, SHA256
`53445988e88c5d50016bd5eb682fc94e18f92dcb79227b44318c81bdb6858034`,
independently verified, and complete predecessor
`.pytest_tmp/measure_task9_profiles.py` plus their complete no-index diff.
Also read current `task-10-native-evidence.md`; G3 completion/hash/count evidence
was supplied separately in the controller dispatch while that document still
said G3 was running. No remote state was independently inspected here.

## Only changed behavior

1. The former1c65ada revision assertion is replaced by the explicit pending
   marker; the final corrected Task10 commit is not guessed or accepted early.
2. Three new independently generated/sealed synthetic profile pins are added;
   all prior actual/historical profile pins remain available unchanged.
3. The previously reviewed producer-supervisor cleanup pattern is adopted:
   selector/output/failure initialization before Popen; progress printing,
   selector setup and reads within immediate postspawn `try`; unconditional
   owned-session-group SIGKILL in `finally`, even after leader exit, tolerating
   `ProcessLookupError`; bounded direct-child reap and handle closure.
   This fixes the old setup-exception/descendant-lifetime gaps without changing
   measurement success criteria.

No profiler, model monkeypatch, source rewrite, alternate verifier entry point,
history pruning, budget increase or acceptance shortcut appears in this delta.

## New synthetic pins checked against supplied evidence

Common directory:
`/var/lib/betboy-task10-growth-0cguwnz6/generation-N/context.db`.

| Profile | SHA256 | Receipts / artifacts / snapshots |
| --- | --- | --- |
| G1 |04e7db378a84fb90fb115db4aed6508ae295d0b99adb9f5626eba03a1f43b94b|99775 /33 /31|
| G2 |3bc7f87c46afa4656eacd1db3193d03196ccfe312d4efe6e1d5cc77316f73f8a|99776 /34 /32|
| G3 |96a43af314e03b5d9ba29a45b9f80b4b9ef7f0d3ab6222dd938cee007bf8efd1|99777 /35 /33|

G1/G2 match the controller ledger; G3 matches the explicit controller completion
message. Exact hashes bind the complete newly sealed inputs whose generator
proved31/32/33distinct query keys and preserved all baseline rows. The D4
measurement wrapper independently rechecks physical table counts; it does not
itself rederive original-query-key counts. No construction PASS is treated as
a D4 measurement PASS or arbitrary future-growth proof.

## Unchanged execution and acceptance contract

- Supervisor requires actual UID997. It imports only stdlib, reads only named
  root-sealed inputs, and launches the real application CLI as UID997; no app
  import as root is introduced.
- Exact command remains `/opt/betboy/venv/bin/python -I -B` followed by
  `<source>/scripts/verify_context_runtime.py --database <dataset> --sealed-file`.
  No source/model/cold validator is patched and no output is fabricated.
- Source root follows the existing private `/var/lib/betboy-capacity-code-*`
  stage shape. Source/dataset ancestors must be root-owned, nonwritable and
  symlink-free. Input must be root0440, regular, one-link and exact pinned SHA.
- Independent stdlib SQLite reads remain `mode=ro&immutable=1`, query-only;
  header must be SQLite DELETE mode and no WAL/SHM/journal may exist. Required
  tables/counts, optional rollback handling and prelaunch identity check remain.
- Fixed child AS2GiB/CPU300, fresh session group, stdin/devnull, clean environment
  with all four numerical thread settings1, merged stdout/stderr1MiB cap and
  outer600second wall stop are unchanged.
- Complete output is parsed as a single JSON document only for child exit0/2.
  The unchanged acceptance predicate requires **measured wall<300, CPU<300,
  peak RSS<1GiB**, no supervisory failure, unchanged input SHA/full identity,
  no companions, exact independent counts, `status=incomplete`,
  `verification_level=transport_only`, empirical approval exactlyFalse and the
  two exact D1/D3 limitation strings in their established order.
- Child/output/resource/invalid-JSON failures cannot become an accepted report.
  Postrun input hash/identity and companion checks remain mandatory. The emitted
  complete report remains diagnostic evidence, not a model-quality approval.

## Existing external responsibilities, not new guarantees

Exact source revision is an argument/pin plus externally verified immutable
archive/stage evidence; this wrapper does not independently hash the complete
source tree or read Git. Final corrected source-stage verification is still
required before labeling a run with that revision. Never point the new revision
argument at the old1c65ada stage merely because the directory shape passes.

As in the predecessor, supervisor pre/post hashing/count checks lie outside
the child measurement interval and child resource limits. Preserve bounded
controller invocation and assertion-enabled normal Python; no `-O` or
`PYTHONOPTIMIZE`. The cleanup timeout fails closed if kernel I/O prevents a
bounded reap; it is not a promise of recovery from an externally killed
supervisor or uninterruptible kernel I/O.

Local nonexecuting AST parse passed (no application imports) and confirmed the
pending marker cannot match the required revision regex. No timing test,
generator invocation or native acceptance was performed by this reviewer.

Controller owns final repin/staging and serial exact-current-first execution,
then G1/G2/G3 and retained required historical cases, DAC/races, final tests/
reviews and release/backup gates. Current actual-input failure remains in force
until the corrected exact candidate produces fresh complete native acceptance.

## Final revision repin: native harness APPROVED

Independently verified final helper SHA256:
`85a781d2d9fab30ab06a0abe993eed629c1ec3e1a2415b1dddfc274efe9afe8d`.
The sole change is replacing the pending revision assertion with exact
`72421d3bdbec4ab15a3d2953cb153e867e7e340a`. Reversing that exact assertion
replacement in memory reproduces the initially reviewed helper SHA256
`53445988e88c5d50016bd5eb682fc94e18f92dcb79227b44318c81bdb6858034`, proving
no other intervening byte change. Read-only `git cat-file -t` confirms the
named object is a commit; it does not substitute for its separate code review.

The pending-revision harness HOLD is cleared. This exact harness is approved
for the described unchanged-boundary measurements once the controller has
completed the separately required candidate approval and immutable source
staging. Controller-supplied candidate archive SHA256
`45a5bfbae0ab11e248e555ef4f6d5b9b23b5c5eda965351f95a09b76f8183dd1`
still requires its GitPAX/safe-content/hash-transfer/root-seal checks; those
were not performed by this reviewer. Separate P2 product rereview was ongoing
at this repin and no native execution/success is claimed here.

No helper/product/index edit or execution by reviewer. All construction versus
D4 versus empirical/release distinctions above remain in force.
