# Independent narrow technical A -> B release review

Date: 2026-09-10. Reviewer: b6_tennis_load_20260909.

## Disposition

**No qualified new finding in the bounded two-step updater/source contract.**
The reviewed technical route is coherent: the existing installed old updater
installs A, then the newly installed updater processes B. This is not evidence
that either step was installed on the real VPS.

**The overall release is still held by Root.** At review close Root reported a
separate real-browser manual-price problem on B: editing the confirmed 1.12
quote to 4.00 leaves the old price decision visible. I did not independently
review or repair that UI in this task. Root explicitly keeps A/main/VPS unchanged
pending disposition of that finding. The positive updater review does not
override this separate hold or certify the whole app.

No SSH, provider/API access, main push, deployment, source mutation, Git commit,
or duplicate full suite was performed by this reviewer. New files are confined
to this ignored review package; generated test data use uniquely named ignored
temporary directories. One initially misplaced, reviewer-created JUnit file
was moved into this package; no pre-existing user file was moved or removed.

## Exact frozen target

- Old installed-code reference: `2ba3931dd8cb35f31d2475ae5797d75b44be268e`.
- A: `655e7a6e430a776b0dcb291daded00399b5b8328`; its sole parent is exactly
  that old reference. Only `deploy/update_server.sh` differs: 559 added/1 removed.
- A LF QA worktree: `kontext-release-bridge-a-qa-20260910`; clean at both checks.
- B: `f2f7611823c8e0b23b102bafba9e880adab87f9f` in
  `kontext-release-b-20260910`.
- A is an actual ancestor of B. B's tree is exactly the tree of Root `19a8f53`:
  `8ecd92df23ad6ad236b3f119b3c1e1eeebd1afb7`.
- B's tracked source/index remained unchanged. It already contained untracked
  `output/playwright/` from Root's work; that directory was not touched.
- A's full Git inventory has 354 files, B's 691. A has no new context modules,
  `model_artifacts.py`, `tennis/tour_state.py`, context CLI or context tests.
  All A app/test files are exactly their old reference bytes.

Both actual LF checkouts match their Git object bytes for the updater and
protected stage helper, without normalizing either file:

| File | SHA256 |
| --- | --- |
| `deploy/update_server.sh` (A and B) | `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f` |
| `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |
| `deploy/bootstrap_server.sh` | `eb2cec227d710156f960ba78a620c5bdfe4bd97cd95ba2deb33a3c120fd5dec6` |
| B `runtime_paths.py` | `710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c` |

## Independently checked route and trust boundary

1. All 15 actual service/timer Git blobs have exactly their old allowlisted
   hashes in old/A/B. Requirements, bootstrap, backup/stage helpers, key helper,
   migration-marker helper and offline-ledger migration helper are unchanged.
   The old protected-runtime-path predicate finds no added/changed protected
   runtime file in either old->A or A->B.
2. The old updater contains 70 shell functions. **69 remain byte-identical**;
   `preflight` receives only the intended command/entry additions. Four hook
   functions are new. The remainder of the main script differs only by the
   intended post-backup context call. A's updater is byte-identical to B's.
3. The old installed entry validates invocation at
   `/usr/local/sbin/betboy-update`, root ownership/modes, fixed HTTPS repository,
   explicit current-main commit, actual source tree and pins. Its existing
   `install_trusted_root_files` installs the reviewed target updater via the
   unchanged atomic installer, **not by executing the new updater during A**.
   It does not import/require a context module or context database for A.
4. Actual old/A/B updater text passes real `bash -n`; no updater was executed.
5. Order matters: ordinarily the requested hash must be the current fetched
   main tip. Therefore publish A, complete its old-entry installation and verify
   the installed new updater, and only then publish B and invoke the new entry.
   Publishing B before installing A would prevent an ordinary A request from
   matching main. The exact in-progress migration-resume exception is unchanged;
   it is not a general ancestry bypass.
6. Once A's new updater is installed, targeting A again fails its new reviewed
   CLI requirement before downtime, because A intentionally contains no CLI.
   This is the explicit two-step boundary, not a reason to relax the guard or
   manually install a root tool from the app checkout.
7. The new preflight checks unchanged dependency requirements, the real target
   import/capability graph as **betboy**, and SQLite deserialize availability
   before downtime. The privileged new inline program imports only stdlib:
   hashlib/json/os/pathlib/re/sqlite3/stat/sys/zipfile. App/venv code is never
   imported as root by the new hook.
8. After quiescence and the existing fully verified fresh backup, the hook binds
   the exact resolver, both full payload inventories, env source and presence.
   Actual full Git A/B inventories were materialized and hashed in private test
   directories. The genuine old code plus absent DB is accepted. A genuine B
   predecessor with missing DB, an orphan WAL, modified/rehashed resolver,
   unmanifested import, false manifest head, external path or duplicate env
   assignment each fails at its expected owning check.
9. The actual legacy `configuration -> stage -> finish` path succeeded against
   those full A/B inventories and a real SQLite-containing test archive. It
   created no context DB or report, changed no archive byte, and opened only
   `MANIFEST.json`: neither the unrelated SQLite member nor the test-only secret
   key member was opened. This is a CPU/content result with explicit Windows
   metadata adapters, not a Linux root/service-account claim.
10. Existing unchanged hook controls independently rerun here cover real
    stage/seal/CLI behavior, scope/identity changes, bounded output, actual Bash
    pipeline exit status and allowed vs unknown limitations. The privileged
    hook permits only the closed structural/transport-continuity contract,
    always `empirical_approval_verified=false`. Unknown artifact capability,
    corruption, timeout or unreviewed report is not turned into success.

Relevant owning source locations in frozen B:
`deploy/update_server.sh`: invocation 525; trusted fetch 560; unchanged complete
manifest producer 632; new inline boundary 1051; configuration 1321; archive
seal 1395; final recheck 1499; unprivileged bounded command 1533; dependency
preflight 1551; post-backup route 1588; atomic root-file installation 2627;
existing recovery 2887; main preflight/order 3195 onward.

## Own executed tests

All commands used the existing quality Python, `-B -m pytest -q
-p no:cacheprovider`, unique basetemps/JUnit paths and checked `$LASTEXITCODE`.
No full suite was duplicated.

| Run | Actual result | Time | Exit |
| --- | --- | --- | --- |
| `run03.xml`, new release controls | 28 passed, 0 skipped | 75.73 s | 0 |
| `hook04.xml`, unchanged hook file plus seven selected existing deploy tests | 246 passed, 0 skipped | 27.22 s | 0 |
| `manifest05.xml`, extra actual old-producer/protected-path controls | 3 passed, 0 skipped | 2.42 s | 0 |

Total: **277 passed, 0 skipped** in three bounded runs; 31 own new controls,
246 existing controls. No fabricated product RED or empirical/model approval.

### Reviewer harness qualifications, preserved rather than rewritten

- First attempt: 17 passed, 1 failed, 10 setup errors, 7.42 s, exit 1. The
  failure incorrectly expected 69 total old functions rather than 69 unchanged
  plus the intentionally extended preflight. The setup path exceeded Windows
  MAX_PATH for actual long tracked names. Shortening only the private basetemp
  removed those setup errors. Original source and JUnit are retained.
- Second attempt: 25 passed, 3 failed, 28.31 s, exit 1. A separate read-only
  diagnosis found a Windows path/descriptor `st_mode` mismatch for exactly the
  three tracked `.bat` files: path 33279, descriptor 33206 (synthetic executable
  bits). The fixture-only Windows signature adapter now ignores only those
  synthetic execute bits and the already documented Windows ctime distinction.
  The source's real Linux metadata/DAC guards remain byte-identical. Negative
  configuration tests were tightened to their exact expected exception reasons,
  so an earlier metadata rejection cannot count as a valid negative control.
- `test_release_ab_independent_prequalification.py` and
  `test_release_ab_independent_before_windows_mode_adapter.py` preserve the
  earlier probes; `run01-harness.xml` and `run02.xml` preserve their outputs.
  Their failed assertions are reviewer-harness issues, not product findings.
- Temp payload manifests in the primary content harness carry the actual full
  file inventories/hashes but use an empty `must_be_absent` list: that member
  is not the new hook's stale-application materialization step. The additional
  actual producer inspection/control separately verifies the unchanged owning
  sorted removal calculation and metadata contract. No actual installation is
  inferred from the content fixture.

## Prior evidence read completely, not represented as this reviewer's runs

The owning README and complete hook audit were read, together with the immutable
Task20 full-suite, actual Linux-fixture, original Linux-DAC design, actual
Linux-DAC report and raw result. Their boundaries are consistent:

- Root full at frozen 6d03: 6,168 passed / 20 Windows skips / 97 subtests;
  1,206.62 s. B's separate full run is Root-owned and not certified here.
- Actual unprivileged Linux fixed-fixture run: 785 passed, no skips, under the
  same ordinary umask; the old 14 failures were positive-fixture permissions.
  No runtime permission or helper pin was relaxed for that run.
- Actual Linux root/betboy DAC: real uid997/gid987 isolation, 12 denied mutation
  operations, real structural/transport CLI cases, broken-reference failure,
  genuine short timeout and bounded-overflow controls. The retained original
  design artifact is not misrepresented as its later execution.
- Root's A LF-only Git-copy run (83 passed/7 Windows skips) was supplied as a
  previous result. My own raw checkout/Git comparisons independently confirm
  the updater/helper bytes. The original CRLF pin failures were not repaired
  by changing or normalizing the protected helper.

Document hashes read at frozen B:

| Document | SHA256 |
| --- | --- |
| `deploy/README.md` | `d9f4a4e7edab436465653f50f4c793ce55552702e001619ae309694e99bea38d` |
| `docs/audits/2026-09-09-d4-trusted-updater-hook.md` | `81114662615349eb03d833a61bf6f6b8db2c656936952d4bd9a704f1ed0d2b94` |
| `task-20-root-full-6d03ca0-20260910.md` | `3e6f76e4ff9fa8ad9cc12ad6dff5c19625de52351a0be1aa26cb51fe325e025a` |
| `task-20-linux-fixture-root-rerun-20260909.md` | `337af725126ac93f289e60bc675d6b80988a257df4528002eff3aa47b330afb9` |
| `task-20-linux-dac-root-run-20260910.md` | `f00ea3527ac040b131a302a01c8c3bd96b0fc9f6c3c0ad79d967e1880e2e2e91` |
| `task-20-linux-dac-original-design-20260909.md` | `551f43ddcc5ca95c730a2a7062dc35fd2a4b39c59129c8b8fc00dc3f00479088` |
| `task-20-linux-dac-raw-result-20260909.json` | `58ee9f2c73bb31847e882b5f225b3764136a8d05895481697d84eba193b7cbf0` |

Task20 documents are under
`.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/`.

## Still required before any claim of deployed release

1. Root's separate browser-price finding must be dispositioned on a separately
   reviewed target. This report does not authorize shipping frozen B as-is.
2. Root must accept its actual release-target full-suite result and resolve the
   exact next target commit after any separate fix. A changed target is not
   silently the exact B reviewed here.
3. Fresh remote main/server/installed-updater/root-unit/environment/runtime
   identity and permission checks remain Root's work; historical 2ba status is
   not a current VPS observation by this reviewer.
4. Actual installed old-entry -> A, verified installed updater digest/owner/mode,
   then new-entry -> final B, verified fresh backup/context result, final Git and
   served application revision, health and all seven timer states remain
   unperformed by this reviewer. Any failure must use the existing stopped/
   disabled recovery boundary, not an ad-hoc root installation.

Missing real empirical data, model approvals or unimplemented future producer
work is not itself a prohibition on the explicitly baseline-preserving safe
technical partial release. Conversely none of this updater evidence certifies
empirical betting quality or completes those separate tasks.

## Frozen reviewer evidence hashes

| File in this package | SHA256 |
| --- | --- |
| `test_release_ab_independent.py` | `944713b751bc191b0b67b3df0caf99f301d2ba1dd87defa21c66218717cc34e4` |
| `test_original_manifest_protection.py` | `a46fd2972c498aac334a2b60eb1b16888fb3594b11b15445b049ebfe8f94446f` |
| `run03.xml` | `44325330d48ef1adaa839343b3a64162cfa4f687cc797c0c388c8c601b957590` |
| `hook04.xml` | `5b3cea973e94f910407446242176f3a440c0744e0dae043f60af7e9eb57b4a1e` |
| `manifest05.xml` | `532814f7d0c6bded22df2d124f248d396d6c2acf48346131f07f758249bff5a8` |
| `test_release_ab_independent_prequalification.py` | `faa44a4bbe1b2a4924f2c873f0c9e9dc7f6ceeb4e2f7011e914faff0e8257e25` |
| `run01-harness.xml` | `b9058be639072f46e30e81a12add209da53f629c2cd77646e8e5e59487d75bca` |
| `test_release_ab_independent_before_windows_mode_adapter.py` | `b09860c5a61d1775d7efda53fc50e2fb00ff5a2069a9363111cff0e7a0280dac` |
| `run02.xml` | `830f000b13cb1e1171c019db2030c6f044869c6e881e8213b64ced5104d2e67d` |

All original probe/report evidence from other tasks, including P4b2-F1, remains
unchanged. This report and these qualified probes are frozen for Root review.
