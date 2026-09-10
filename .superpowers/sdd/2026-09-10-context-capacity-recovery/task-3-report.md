# Task 3 implementation: review checkpoint, not deployment approval

10 September 2026. Base `9e97f2bda1bedbd7e61aeeddfc9b25b6a9992b40` on
`codex/context-capacity-recovery-20260910`. The earlier RED slice is committed
as `a435c653`. This implementer changed only the installer, its test file,
`deploy/README.md` and this report. Controller/reviewer progress and other WIP
were preserved and excluded from staging. No VPS, push, application deployment,
service operation or installed-helper change was performed.

## Implemented boundary

- Exact public arguments: reviewed 40-lowercase-hex target commit and
  64-lowercase-hex new updater SHA256. No path/remote/command/test override.
- Root-owned private installer invocation, the existing deploy lock, sanitized
  Git access to the hardcoded HTTPS repository, exact fetched main tip and
  exact updater blob, plus Bash syntax validation. Installed old updater SHA,
  source HEAD and complete marker must match the accepted production contract.
- The installed marker helper remains pinned. Production key, marker, config,
  application principal and old updater byte/inode metadata are recorded and
  rechecked across the online preflight and immediately before installation.
- The full fresh online backup uses the unchanged Task2 producer, independent
  root-owned copy, inline isolated SQLite restore and pinned helper's actual
  isolated restore/Challenge HMAC verification. No scheduled archive is
  relabeled, and no key/marker/permission/legacy fallback is created.
- Target payload/manifests and context transport use the existing audited
  source, configuration, receipt and sealed-file checks. D4 runs only as the
  actual `betboy` user. Existing limitation/report semantics remain unchanged.
- A new fixed stdlib-only root measurement supervisor launches only the
  existing fixed betboy D4 child. It records Linux wait4 descendant rusage,
  elapsed wall time and full bounded report bytes. The measured record binds
  target commit, new updater digest, sealed DB digest and exact report digest.
  Peak RSS must be strictly below 1 GiB; CPU and wall strictly below 300 seconds.
  Existing child AS2GiB/CPU300/output1MiB/hard-wall600 plus10-second grace stay
  fixed. This supervisor is not a general command runner.
- Accepted archive/stage/report/production/restore/inline/measurement hashes
  are persisted and copied into the durable transaction journal. The complete
  report and sealed snapshot/source bindings are rechecked before acceptance.
- Old executable bytes are independently copied/fsynced root-private. New
  bytes are prepared beside the installed target, intent is durably journaled,
  then exact identity is rechecked, replacement is atomic and parent-fsynced.
- Operational failures restore only the recognized own replacement. A new
  process recovers solely from strict disk journal/old-copy evidence. Unknown
  hashes, foreign same-hash inodes, malformed journals or a different release
  request are not overwritten. Completed matching requests are idempotent.
- The repair state directory's parent entry is fsynced even when the directory
  already existed; the rollback temporary entry is parent-fsynced before its
  exchange. No cleanup deletes preserved failed-recovery evidence.

Only `/usr/local/sbin/betboy-update` is the permanent executable installation
target. Backups and root-private repair records are intentionally retained.
The existing application's checkout, data, helper pins, units, keys, marker,
timer policy and running state are never changed by this installer.

## Reviewed reuse decision

Controller explicitly approved mechanical implementation-time duplication,
not runtime extraction/sourcing. Seventeen needed functions are byte-identical
to the independently accepted `6ba2c68` updater source, SHA256
`4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`:

`acquire_deploy_lock`, `as_betboy`, `root_git`, `git_betboy`, `trusted_file`,
`target_payload_file`, `verify_root_owned_file`, `parse_marker_state`,
`create_trusted_manifests`, `context_hook_data`, `context_hook_command`,
`verification_launcher_source`, `configure_context_phase`,
`prepare_verification_launcher`, `verify_backup_archive`,
`capture_root_verifier`, `produce_update_backup`.

An exact-source parity test guards this deliberate duplication. No updater
main, app deployment, backup-service migration, unit installation or unrelated
rollback function was copied. The unused ordinary D4 orchestration function
was removed from the copied set once the measured repair-specific path existed.

## RED and fresh local verification

Initial RED: 35 explicit missing-installer failures, documented in the earlier
RED slice. Added measurement RED: **14 failures**, missing fixed measurement
function, before implementation. Added state-directory parent-entry RED:
**1 failure**, observing missing parent fsync for an existing state directory,
then fixed without changing byte/inode/identity contracts.

Final command:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_updater_repair.py tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/updater-repair-integrated-02 --junitxml=.pytest_tmp/updater-repair-integrated-02.xml --tb=short
```

Result: **409 passed, 1 skipped in 58.42s**, exit0. This comprises 69 Task3
passes, one Windows-only real-flock skip, and the unchanged 340 Task2 tests.
All embedded Python programs compile; actual Bash `-n` succeeds; scoped diff
whitespace validation succeeds. Installer raw LF SHA256:
`8476a5a9a4956245ddb4026f5aff9bb1c8db980859d34fc129a28d453bf415f7`.

Tests exercise real filesystem bytes/inodes/links, restart namespaces,
replacement and fsync failures (including every fsync in the successful path),
same-hash foreign inodes, corrupt recovery files, missing/wrong evidence,
request parsing, actual Bash main/gate ordering and exact fetch commit/blob
failures. Linux flock uses a real contending lock; only its separate root-DAC
precheck is simulated. Windows lacks flock and explicitly skips that case.

Unit principal/mode emulation is now transparent on both Windows and non-root
Linux, with only Windows directory-fsync and fd-ctime limitations separately
emulated. No test/app import runs as root. These tests do not relabel mocked
principals as actual Linux DAC or power-loss durability evidence.

## Open independent review and native gates

This is a review checkpoint, NOT production or release approval. The new
measurement supervisor and installer-specific full transaction still require
independent review and native role/process/rusage/crash testing. Local boundary
and composition tests are not a fresh real backup/restore/HMAC/D4 run.

Controller's newly attempted real producer correctly refused twelve existing
0775 source directories. The separate read-only investigation established an
additional effective backup-service writer through its supplementary group;
there is no safe permission-check relaxation. Task2 source remains unchanged.
Any narrowly approved 0775-to0755 controller preparation is outside this
installer and requires its own metadata backup/recovery and fresh full backup
rerun. No such preparation is claimed or performed here.

Fresh real backup/restore/HMAC, measured target D4, native Task3 resource and
transaction proof, independent release review and explicit controller rollout
remain open. The user already approved the updater-only replacement, but that
authorization is not substituted for these safety/evidence gates. The ordinary
application deployment remains a separate subsequent command.

Process used: TDD and verification-before-completion inside the controller's
subagent-driven plan. The controller owns independent review and deployment.
