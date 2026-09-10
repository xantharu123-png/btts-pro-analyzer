# Task2 final review: inventory completeness still HOLD

Exact candidate: `bdd5731b56e19e6da3b2312abf8ef3cbf971beb4`, report `23dac3bd8dc8a12ee1f693cb7e6132496fdf5f04`. Independent reviewer `capacity_task2_checkpoint_review` inspected the combined Task2 contract and reproduced the following two Important error groups. This is not release approval.

## Traversal errors can silently produce incomplete inventories

Producer `capture_inventory` at candidate line 2117 uses `os.walk` without `onerror`. A real extra SQLite file plus injected `scandir` EACCES leaves both inventories equally incomplete: file exists, omitted from archive, completed receipt emitted. `verify_payload` at line 1408 similarly accepted an unmanifested Python file hidden behind the skipped subtree (Unix metadata explicitly simulated in this fixture).

Actual shell `verify_backup_source_dac` at line 2932 also lost `find`'s failure through process substitution: injected `find` exit 13 still returned exit 0 and `dac-accepted`. Related static sites: staged chmod walk 763, cache purge walk 2400, rollback metadata walk 2655 and the storage `find` substitution 2897. These additional sites were not all independently reproduced and are not separate invented runtime findings.

Require fail-closed traversal, checked scan completion before consuming inventories, RED for initial/final scans, payload extras and failed `find`. The unchanged stage helper already demonstrates `onerror=fail_walk`.

## Database discovery disagrees with the unchanged helper

Producer line 2135 uses case-sensitive suffix matching; the frozen stage helper uses `Path.suffix.casefold()`. Fresh exact-producer fixture: helper inventory contains `runtime_state/Historical.DB` and `state.db`, updater archive only `state.db`, completed receipt still emitted. The untracked policy permits the path. Case-sensitive byte-count/find/DAC sites are also at lines 2903, 2938 and 3615-3623; their `-xdev` difference from producer/helper must be reconciled. Change updater discovery, never the protected helper, or reject ambiguity before downtime; silent omission is unacceptable.

The four earlier checkpoint findings are specifically fixed. Fresh independent verification: **51 follow-up tests passed / 262 deselected**, Bash syntax valid, exact Task2 bytes match the candidate and both helper pins remain unchanged. No reviewer files/VPS mutations.

## Native controller corroboration (actual Linux EACCES)

The controller ran exact candidate updater SHA `666014acdac4c200fb2efa9e9c67f42d6ef768c406715897bab9acee82e242ce` using extracted unmodified functions, no updater main. New private synthetic fixture `/var/lib/betboy-task2-native-90uadk50` only. App setup/imports and full producer ran as real uid 997, no uid/stat/scandir mock; root only trusted stdlib transport/pinned helper.

Valid three-database producer -> independent root:root0600 single-link archive -> inline isolated restore -> unchanged pinned helper HMAC verification completed. Correctly re-digested archive with a wrong **synthetic** key passed inline transport but was rejected by actual financial HMAC verification. Creating a real root:root0700 `unreadable` subdirectory containing intact `hidden.db` then reproduced the bug: full producer/verify/publish chain exit 0, hidden file absent from the published ZIP. Installed updater hash stayed unchanged. Raw outputs, archives and per-process evidence remain private in that QA tree; no production key/data used.

Earlier controller-only harness attempts had missing `/usr/sbin` in test PATH, umask-restricted test directory modes, and an overly narrow expected HMAC-error assertion. They were corrected without product changes; their separate QA artifacts are retained. They are not counted as native product findings or successful full runs.

Task2 writer was explicitly reauthorized after Task1 relinquished its slot, for the scoped discovery/byte/DAC fixes and RED/GREEN coverage. Native release, greatest-capacity and full real-backup gates remain open.
