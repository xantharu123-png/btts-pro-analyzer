# Root: real unprivileged Linux regression of the trusted context hook

9 September 2026. The controller reran the identical 13-file Linux matrix on
an isolated source copy as uid1000 (not root and not the production app user).
No production code, source request, dependency install, service, timer, model,
ticket or account was changed.

## Original RED preserved

Frozen base archive `context-hook-linux-a224d13.tar` (101335040 bytes), SHA256
`e76488f9a34ca8544667411151bac6e69ab275ccad4d6079c47a2051cf83492f`.
Original private source:
`/tmp/betboy-context-qa.9xr68INa/hook-a224d13-20260909`.
JUnit `.pytest_tmp/hook-linux-unprivileged-01.xml`, SHA256
`f820d5e996f47dd00cd4fdf8d279ce55470824a6abdb5afcb622c618ad2df004`.
Observed: **14 failed / 771 passed / 0 skips, 52.65 seconds, exit1**.

All fourteen actual XML failures were inspected. With the deliberate ordinary
Linux umask0002, positive test companions/sentinels were0664 and the positive
app fixture parent0775. The existing trust check correctly rejected these
before the specific intended hardlink/identity or Unicode-config assertion.
This is a test setup defect, not permission to weaken production protection.
The original source, archive, tests and RED XML remain untouched.

## Accepted exact fixture correction

Independent owner `2346846e0362b152ba6c4f8a17620559c9a67df3` changed only six
positive regular-file `chmod(0o600)` calls and one positive directory-loop
`mkdir(mode=0o700)` call. Root read the entire owning audit and exact diff.
No assertion, skip, umask, parameterization or production code was changed.
Owner's identical Windows before/after focus:271passed/1expected-symlink-skip,
26.27/25.96seconds respectively; those are not Linux DAC evidence.

Patch archive contains exactly the two test files and their `tests/` directory:
`context-linux-fixtures-2346846.tar`,71680bytes, SHA256
`b5af4e6d4083c794b7af349c40e7d592d4b10f7eb3f14e5cf8a5d0c40726f9b4`.

## Actual green Linux run

New private source, preserving the earlier source:
`/tmp/betboy-context-qa.9xr68INa/hook-fixtures-2346846-20260909`.
The stdlib harness verified uid1000, canonical private root0700, regular
single-link owner-matching archives and exact hashes. It rejected links,
devices, traversal, duplicate names and unexpected patch members. Only the
two positive fixture files were replaced in the newly extracted copy.
All existing source-file hashes were checked before/after the complete run.

Existing isolated QA venv, Python3.12.3; no install into app venv. Exact command
used `-B -m pytest -q -rs -p no:cacheprovider --tb=short`, a fresh basetemp/JUnit
and **umask0002**, not a process-wide restrictive workaround.

Unchanged matrix: `test_context_update_hook`, `test_context_runtime_tennis_live`,
`test_context_reader_trust`, `test_context_runtime_backup`, `test_model_artifacts`,
`test_context_snapshots`, `test_backup_stage`, `test_backup_stage_archive`,
`test_backup_stage_e2e`, `test_tennis_state_codec`, `test_tennis_tour_state`,
`test_tennis_live_worker`, `test_tennis_live_publication_clock` (all `tests/*.py`).

Result: **785 passed, zero failures/errors/skips, 55.61seconds, native exit0**.
Five existing SQLite placeholder deprecation warnings concern Python3.14's
future sequence/named-placeholder behavior; current Python3.12 completed.
They were not hidden or counted as failures fixed by this fixture packet.

Remote JUnit `.pytest_tmp/hook-linux-unprivileged-fixtures-02.xml`, SHA256
`7c77e9d5069e4a503b3774832f90d6e0a9421ba155904ff9cd860fb2850b175e`.
Copied read-only to Root's same `.pytest_tmp` filename; exact SHA verified.
Harness and archives remain local ignored `output/context-evaluation/` evidence.

## Unchanged source pins and limits

```text
74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f deploy/update_server.sh
1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026 scripts/stage_runtime_databases.py
cf711ac8438eef369500014298ad6c7c14ae2c5c0ae3b6ada526d9299b70e501 tests/test_context_update_hook.py
89e2b95d23f74fff5fd7c79d38c4f46451dbaa0a7545de4fad6ad6bf1cf8ea85 tests/test_context_reader_trust.py
```

Root accepted the fixture commit via merge `bb297bbd34ca80eb83129e87cf1559cc44ae20df`.
This is a real Linux test run, but **not** a real root/app separation test or
the installed trusted updater A-to-B transition. Those release proofs remain
separate, as do consumer/sport integration, whole-suite and browser acceptance.
No empirical context effect, main push or VPS functional deployment is claimed.
