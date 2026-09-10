# Task 2 exact-component rollback fix

Date: 2026-09-10. Base `a435c653d1d1db1bf9e584e6af0d5f67c166ec20`; code commit `6ba2c68acf474d24648a816eac7586fb41929349`.

The independently confirmed rollback discrepancy is fixed with one production-line change: `snapshot_backup_source_metadata` now excludes only exact named components, not every name beginning with `.pytest_tmp`. Thus the allowed `runtime_state/.pytest_tmp-keep/history.db` and its parents are recorded before source permissions change. Exact `.pytest_tmp` remains excluded. Producer, shared enumeration, context relative-path policy and unchanged helper exclusions were checked: they use exact component membership, not this broader prefix rule. No other production behavior or helper was changed.

TDD evidence:

- `.pytest_tmp/task2-prefix-red-01.xml`: 1 expected failure, 339 deselected, 0.44s. The actual snapshot routine returned an empty metadata list instead of records for the actual SQLite fixture and its three parent directories.
- `.pytest_tmp/task2-prefix-green-01.xml`: 1 passed, 339 deselected, 0.35s. The test checks exact path/kind/uid/gid/mode records, applies real fixture chmod changes, observes actual verify rejection, invokes actual metadata restore and verify, and checks restored metadata plus unchanged DB bytes. Only unavailable Unix chown and directory-fsync edges are simulated on Windows; chmod/lstat and SQLite/filesystem bytes are real, and Linux uses real chown/fsync too.
- Full focused run: `python -B -m pytest tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/task2-prefix-green-02 --tb=short --junitxml=.pytest_tmp/task2-prefix-green-02.xml` using the existing quality venv: **340 passed in 48.90s**, exit 0. Bash syntax and exact-file diff checks also returned 0 immediately before commit.

Updater SHA-256: `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.
Test SHA-256: `71070d2ba5285d8aa044bd30b671fe887c5e3edb153fe4fab527221b2bb1b129`.
Unchanged helper pins: backup `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`, stage `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

Review reception, TDD and fresh verification governed this narrowly authorized fix. Only updater/tests and this separate report are committed. Task 3, root reports, model/source/schema/math and installed/VPS state remain untouched. No network, push or broad suite. Native exact-new-byte confirmation and independent acceptance remain controller gates; the preceding Unicode/native-chain passes do not substitute for this patch's acceptance. Writer control is relinquished after the report commit, with no further edits/tests until another grant.
