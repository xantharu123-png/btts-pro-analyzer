# Integrated B2 release execution notes

Frozen QA target `286601b9a3290d8459bb7f77932fb6a20bc15a47` in a fresh detached
LF worktree `kontext-release-b2-20260910`. Source is exactly integrated
`74d714a712ba3abc207ff0c717e7f27927624ba5`; the next commit corrects/adds only
audit and handoff documents. Root feature branch was pushed to286601b.
P4b3(a) remains outside this target. Main/VPS last verified2ba3931.

## Local preflight and qualified test-launch error

Actual fresh Git status empty. Actual file SHA256 before the full run:

- UI9447488dd3874946e46087ad33fed8525372226099386644a5e8d85650c2a88b
- runtime710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c
- protected helper1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026
- updater74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f
- bootstrapeb2cec227d710156f960ba78a620c5bdfe4bd97cd95ba2deb33a3c120fd5dec6

First full attempt used nested `--basetemp` before ensuring its `.pytest_tmp`
parent existed. Many fixture-setup E results appeared. Root interrupted only
that owned test process; it did not produce a completed JUnit file or a valid
suite count. It is not a passed run, nor are all unreported E causes inferred.

Immediate `-x --tb=short` diagnostic, unchanged source, reproduced the first
error at `tests/test_api_budget.py::test_priority_reserves_protect_recommendation_and_critical_calls`:
`pathlib.mkdir -> FileNotFoundError [WinError3]` for the nested diagnostic
basetemp. Four tests passed and one errored. Its JUnit output created the
previously missing parent during final reporting; at the explicit subsequent
directory check the parent therefore already existed. Root ensured it using
`New-Item -Force`, without deleting old files or changing application code.
The exact failed test then passed unchanged,1/0 in0.28s.

- diagnostic01 XML SHAc74de14d97eed6ac861f441b82b871aa894f045ca44ea0f3c266eab4bf91fc55
- diagnostic02 XML SHAa4d7b8dc12026ed2b91772b3076c24446861c1c0a6664c7c53436a3484d109ab

Second full attempt, new basetemp and XML suffix02, started with the verified
parent in place. It is still running as of09:30UTC/11:30CEST; no final count
or success is claimed yet. Use the existing quality Python with `-B -m pytest
-q -rs -p no:cacheprovider`; do not normalize protected/inherited files.

## Fresh read-only VPS checks

- All15 explicit BetBoy units are loaded from exact `/etc/systemd/system/`
  filenames, no DropInPaths. App and seven timers active, app/timers enabled.
  Six batch services inactive/success; existing Tennis service failed, exit1.
- Installed existing trusted backup verifier read the latest preupdate archive
  `/var/backups/betboy-update/betboy-preupdate-20260909T075815Z-a0fc89cdef1c.zip`:
  exit0,87 databases verified. No restore, new archive or key disclosure.
- This archive predates the intended deployment. The trusted updater must
  create/verify a fresh backup after stopping all database writers for each
  actual deployment step. No A/Main/B mutation is authorized merely by the
  current partial local test output; full release verification remains open.

## Completed integrated run, 10 September 2026, 09:49 UTC

The second full attempt completed with exit0: **6552 passed,20 skipped,
97 subtests passed in1279.19s**. JUnit has6669 cases,0failures,0errors,
20skips,time1279.054; its start timestamp is2026-09-10T11:27:11.132420+02:00.
XML `.pytest_tmp/context-release-b2-full-20260910-02.xml` SHA256:
`9dd05fc2e22879c8d8367bb83e5cb6e92183e8621aba91f0f99201a545610237`.
The20skips are the platform's unavailable symlink privilege and POSIX
umask/permission tests, not application failures. Their complete names/reasons
remain in the XML. Separate actual Linux/DAC evidence is in the owning reports;
this Windows result does not itself execute those platform checks.

Fresh LF QA tracked status is empty. UI, runtime resolver, protected stage
helper, updater and bootstrap raw hashes still exactly equal the five values
recorded before the run above. No application or test edit was made to repair
the qualified first launch. `286601b -> 887cb47` changes only this execution
note and the independent final deployment-delta report. Final publication may
add only handoff/evidence documents before freezing the release hash; verify
that complete diff explicitly rather than claiming a new full-suite execution.

Remote main remains2ba3931, feature887cb47. Fresh VPS read remains2ba3931 with
clean tracked tree, active app, inactive batch writers except the known failed
Tennis unit. Installed old updater is root:root0755,nlink1,SHAa07ad24c92f207c9d1124acee37fb4b0e443dae39876dad6c1948b55bb725cbb.
Root accepts the independently reviewed technical partial release, original
ordered A-then-B route, and separately verified manual-price UI. No empirical
injury/load effect or unfinished P4b3/P5b is added to that acceptance. Actual
installation, fresh backups and postdeployment observation are next, not yet
claimed by this completed local test record.
