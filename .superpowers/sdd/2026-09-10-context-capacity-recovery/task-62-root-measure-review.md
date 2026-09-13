# Task62 fixed-root measurement review

Spec/scope: COMPLIANT. Instrument quality: APPROVED for the one fixed read-only measurement.
Critical findings: none. Important findings: none.

Both instruments were read completely. Verified entry SHA256
`93272441757aa51c547a18a671c26e64e67c7a88c7d01a3d8cbfb5b6f3d593d6`
and runner SHA256
`1a1c4ebd44f7b4124564a72443ae0f2853b5600ee5710efa107399aa79cd70f7`.
No instrument, test, Git command or SSH/native action was executed. Only this
report was written; local Python was used solely to read verified archive bytes.

## Checked coupling and bounds

- The runner holds and pins the template and archive before replacing the one
  exact placeholder. The entry independently verifies archive size/hash, commit
  comment, closed member set and every member hash before executing code.
  Nothing is extracted to disk. The test member is validated but never executed.
- Execution uses the two reviewed stdlib catalogue namespaces only. The old
  namespace is explicitly injected; neither pytest nor product/dependency code
  is imported. The only invoked operation is `retained_root` on the literal
  `/tmp/betboy-context-qa.9xr68INa` path. No admission, worker, complete retained
  union, live database operation or control-file write is introduced.
- The response-shape check used catalogue bytes directly from archive SHA
  `817d2ed8a7f529881537d6007c136b829267c6452182cbc923c91a465ce04e6d`,
  with member SHA `a17c62e6fec58735974f74be59e16dfd2d7ac9061da58239eac35a4f3a202185`.
  The current working catalogue had already advanced and was not treated as the
  pinned execution source. No review of that newer implementation was performed.
- Pinned catalogue lines268-356 dispatch to the Linux walker, open children
  read-only/no-follow, hash all regular-file bytes and inert link targets, and
  validate named/held epochs and directory membership. Line356 returns only
  path, identity, membership digest and five counts/totals, not the full member
  list. Consequently the two successful JSON messages remain small and do not
  disclose file content. Exceptions do not become successful completion records.
- Limits are CPU60, AS2GiB, regular-file output size0 and core0 before catalogue
  execution. The controller requires actual root UID/GID, isolated/no-site/
  non-optimized Python, disabled bytecode and the exact clean environment.
  There is no controller-created child. Its alarm300 is supplemented by external
  timeout300 TERM with five-second KILL escalation, starting before Python.
  File-size0 is defense in depth, not a general filesystem write sandbox; the
  reviewed invoked path supplies the read-only behavior. Filesystem read-atime
  effects are not a promise of zero kernel metadata changes.
- The runner creates only fresh local observation logs, waits for both streams,
  flushes them, retains hashes and propagates actual SSH exit. External GNU time
  remains outside timeout. A signal/timeout must remain a nonzero terminal
  outcome; neither a begin record nor even an end record substitutes for exit
  and stderr verification. No retry or successful-cleanup inference is added.

## Interpretation and remaining gates

The scan timing starts immediately before the begin message, so it includes
that small serialization/output cost. `parent_whole_cpu_ns` is a pre-final-output
sample, not an exact final CPU total; use the external terminal time result for
whole-process accounting. Successful completion establishes one full observation
of this exact root only. It supplies neither an old-code timing baseline nor an
isolated speedup ratio, complete retained-union timing, full preparation fit,
admission authority or full-C/B/release completion.

Root's supplied DryRun payload153789/SHA
`e7ff249139bf70c5e743444c620d7862be68b5c813d5b32329a07e49346e08a9`
and exit0 are preparation evidence, not native measurement evidence regenerated
here. Actual root contents, finished measurement, resource usage, signal/exit
status and post-exit process state remain to be observed. Preserve partial logs
and STOP evidence on failure; no automatic rerun or cost refund follows.

T2 generic SSH log caps remain explicitly deferred, neither reopened nor cleared.
