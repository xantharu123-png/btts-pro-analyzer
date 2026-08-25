# BetBoy VPS deployment

The production VPS runs one public Streamlit app and all evidence jobs from
the same persistent checkout. Runtime SQLite files remain untracked but are
backed up transactionally every night. If OVH Automatic Backup or another
off-site backup is enabled in the provider panel, it becomes the required
second recovery layer; the on-server archive alone is not disaster recovery.

## Target layout after one-time migration and deployment

Before the first deployment of this hardening package, the running legacy code
still writes model state, watch data, logs and reports to their historical
locations inside the checkout. The verified copies below `runtime_state` and
`runtime_reports` do not become canonical until the one-time migration has been
completed with all writers stopped and this package is deployed.

- Application: `/opt/betboy/app`
- Python environment: `/opt/betboy/venv`
- Runtime secrets: `/opt/betboy/app/config.ini` and `/etc/betboy/betboy.env`
- 15K ledger HMAC key: `/etc/betboy/challenge-ledger-hmac.key`
  (`root:betboy`, mode `0640`; generated once and never replaced during updates)
- 15K migration marker: `/etc/betboy/challenge-ledger-v2-migrated.json`
  (`root:betboy`, mode `0640`; `in_progress` is a durable global runtime stop)
- Mutable state: `/opt/betboy/app/runtime_state`
- Generated reports: `/opt/betboy/app/runtime_reports`
- Local database archives: `/var/backups/betboy` (mode `0700`, owned by the
  non-login `betboy-backup` account; the application account cannot delete or
  replace archives)
- Root-protected pre-update archives after the first secure updater run:
  `/var/backups/betboy-update`
- Reverse proxy: Caddy on ports 80/443
- Streamlit: loopback only on port 8501

The updater creates the dedicated `betboy-backup` principal only when both its
user and group are absent. Any partial, unlocked, non-system or otherwise
unexpected existing principal fails closed; it is never adopted with
`usermod`. The account has no persistent supplementary groups. Only the
systemd backup unit receives `SupplementaryGroups=betboy` inside its hardened
mount namespace. The updater
installs the reviewed stdlib-only backup helper root-owned below
`/usr/local/libexec`, migrates existing SQLite source permissions to read-only
group access, and changes future runtime writers to umask `0027`. The backup
  unit cannot browse `/etc/betboy` or read `.streamlit`, `.env`, or `config.ini`;
  its private mount namespace exposes only the ledger HMAC key and migration
  marker read-only below `/run/betboy-backup`. Every app and writer service has
  an `ExecCondition` that accepts only a validated `complete` marker. The backup
  service has no network address family and only receives write access to its
  private archive directory.
  Before mutation, the updater snapshots the principal state, exact
database and parent-directory metadata, archive-directory metadata, Caddy
bytes and metadata, and the archive inventory. Existing archives are held by
root-only, independently fsynced copies while writers are stopped, so both
retention pruning and in-place corruption remain reversible. Before downtime,
the updater checks the archive tree's apparent size and reserves enough free
space for snapshot, restore, runtime database staging, recovery archives, and
the probe backup, including when `/var/tmp` and `/var/backups` are separate
filesystems. A pre-start rollback materializes and verifies a sibling tree
before atomically exchanging it with the live tree.

## Initial installation

The application checkout and its `.git` directory are writable by the
unprivileged `betboy` service account. They are therefore never a trusted
source for commands or files installed as root. In particular, **never run**
`sudo deploy/bootstrap_server.sh` or `sudo deploy/update_server.sh` from the
checkout.

1. Review a specific 40-hex commit which is currently the tip of `main` at the
   fixed repository URL
   `https://github.com/xantharu123-png/btts-pro-analyzer.git`.
2. Create the service account and clone the already-reviewed target as that
   unprivileged account. The fresh bootstrap deliberately refuses to recurse
   through an operator- or root-owned checkout and requires the entire clone
   to be `betboy:betboy`:

   ```bash
   TARGET=<reviewed-40-hex-main-commit>
   sudo useradd --system --home-dir /opt/betboy --shell /usr/sbin/nologin \
       --user-group betboy
   sudo install -d -m 0750 -o betboy -g betboy /opt/betboy
   sudo -u betboy env HOME=/opt/betboy git clone --branch main \
       https://github.com/xantharu123-png/btts-pro-analyzer.git \
       /opt/betboy/app
   test "$(sudo -u betboy git -C /opt/betboy/app rev-parse HEAD)" = "$TARGET"
   ```

   If the account already exists, omit only `useradd`. Do not repair ownership
   with recursive `sudo chown` over an untrusted tree; rebuild a questionable
   clone as `betboy` instead.
3. Fetch the same commit into a private operator-owned temporary clone using
   the fixed URL, verify that its `FETCH_HEAD` exactly equals the reviewed
   commit, syntax-check both deploy tools, and install those exact two files
   root-owned:

   ```bash
   TARGET=<reviewed-40-hex-main-commit>
   REPOSITORY=https://github.com/xantharu123-png/btts-pro-analyzer.git
   BOOTSTRAP_STAGE=$(mktemp -d)
   GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
       git -c credential.helper= init --quiet "$BOOTSTRAP_STAGE/source"
   GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
       git -c credential.helper= -C "$BOOTSTRAP_STAGE/source" fetch \
       --quiet --no-tags --depth=1 "$REPOSITORY" refs/heads/main
   test "$(git -C "$BOOTSTRAP_STAGE/source" rev-parse FETCH_HEAD)" = "$TARGET"
   git -C "$BOOTSTRAP_STAGE/source" cat-file blob \
       "$TARGET:deploy/bootstrap_server.sh" >"$BOOTSTRAP_STAGE/betboy-bootstrap"
   git -C "$BOOTSTRAP_STAGE/source" cat-file blob \
       "$TARGET:deploy/update_server.sh" >"$BOOTSTRAP_STAGE/betboy-update"
   bash -n "$BOOTSTRAP_STAGE/betboy-bootstrap"
   bash -n "$BOOTSTRAP_STAGE/betboy-update"
   sudo install -o root -g root -m 0755 \
       "$BOOTSTRAP_STAGE/betboy-bootstrap" \
       /usr/local/sbin/betboy-bootstrap
   sudo install -o root -g root -m 0755 \
       "$BOOTSTRAP_STAGE/betboy-update" \
       /usr/local/sbin/betboy-update
   ```

   The temporary directory is operator-owned and must be removed after the
   bootstrap has completed. Do not substitute a file from `/opt/betboy/app` in
   the `install` command.
4. Before any service is started, transfer the ignored runtime databases and
   `config.ini` through the documented secure recovery path and make each
   transferred runtime file `betboy:betboy`. The checkout must remain free of
   untracked code, symlinks and executables; bootstrap accepts only its narrow
   secret/runtime-data allowlist.
5. Run the installed bootstrap with the same reviewed commit:

   ```bash
   sudo /usr/local/sbin/betboy-bootstrap "$TARGET"
   ```

6. Verify app health, all seven timers, firewall, TLS and a restore from the
   generated SQLite archive.

The bootstrap disables SSH password login. Confirm key-based SSH access before
running it. It refuses any path other than the root-owned
`/usr/local/sbin/betboy-bootstrap`, validates the explicit target against the
current fixed-URL `main`, requires the app checkout to already equal that
target byte-for-byte, uses a root-owned staging clone, and installs both
`/usr/local/sbin/betboy-bootstrap` and `/usr/local/sbin/betboy-update` plus the
allowlisted systemd units from that staging clone. It is fresh-host-only: an
existing venv or any active BetBoy unit is rejected.

Bootstrap is intentionally fresh-host-only and not crash-resumable. If it is
interrupted after creating the venv, key, marker, or root-owned files, leave all
BetBoy units stopped and rebuild or restore the fresh host from reviewed inputs;
do not bypass its existing-venv/fresh-marker checks. Only a completely finished
bootstrap may later use the resumable updater.

The 15 allowed unit files are pinned by SHA-256 inside both root deploy tools.
Whitespace or extra systemd directives therefore fail closed. A legitimate
unit change uses two releases. Commit A changes only `deploy/update_server.sh`
to pin the reviewed next unit hashes while the old updater still validates and
installs the unchanged predecessor units. Commit B then contains the new unit
bytes. The bridge updater validates installed predecessor bytes against the
exact previous Git payload, but validates the target and post-install state
only against the new pinned hashes. There is no legacy target allowlist and no
wildcard transition.

## One-time migration of an existing VPS

Do not rerun bootstrap on an existing installation and do not overwrite the
installed root tools manually. Push Commit A while it is the exact `main` tip,
deploy it through the currently installed updater, and verify that only the
root updater/app commit changed while all installed units retain their legacy
hashes. Then push Commit B as the new exact `main` tip and deploy it through the
bridge updater. Commit B installs the final new-only updater, bootstrap, helper,
units and application bytes atomically. `FragmentPath` must be the exact
`/etc/systemd/system/<unit>` path and `DropInPaths` must be empty for every app,
timer and worker unit. BetBoy-specific, dash-prefix and global type drop-in
directories are forbidden across the standard persistent, runtime, control and
generator search paths; the updater enforces all of these checks. Preserve and resolve
all tracked runtime drift first. For the runtime-split migration, copy the
current production `tennis/data/model_state.pkl` to
`runtime_state/tennis/model_state.pkl` and the current weekly HTML to
`runtime_reports/tennis/` while services are stopped; compare size and SHA-256
before restoring the tracked seed/report bytes from the deployed commit. Keep
the legacy files until the new runtime copies and the normal SQLite backup are
independently verified. Then invoke only:

```bash
sudo /usr/local/sbin/betboy-update <reviewed-40-hex-main-commit>
```

The first secure updater run snapshots the existing root-owned units and both
root tools before replacing them from the reviewed root staging tree.

## Updating

After changes have been reviewed and pushed to `main`, obtain and verify its
full 40-hex commit, then run only the root-owned updater:

```bash
sudo /usr/local/sbin/betboy-update <reviewed-40-hex-main-commit>
```

An in-place update requires an active Caddy service and an existing regular,
root-owned `/etc/caddy/Caddyfile`; fresh hosts use the bootstrap. This makes the
proxy state byte- and metadata-restorable instead of guessing how to recover a
missing live configuration.

After the one-time migration and deployment, database files and secrets remain
ignored by Git and are not changed by updates. The tracked
`tennis/data/model_state.pkl` then serves only as a read-only packaged seed.
Weekly rebuilds write `runtime_state/tennis/model_state.pkl`; pipeline logs and
the calibration watch also live below `runtime_state`, while weekly HTML is
written below `runtime_reports/tennis`. Historical tracked reports and the
packaged seed therefore remain stable evidence rather than mutable production
files. Until that deployment completes, the legacy locations remain the live
writer targets.

The root updater never uses the checkout's configured origin as a trust anchor.
It fetches the fixed GitHub URL into a root-owned staging clone and requires
its current `main` tip to equal the operator-supplied commit exactly. Root-owned
tools and systemd bytes are installed only from that staging clone and only
from the explicit allowlist. Application bytes and modes are independently
manifested from Git blobs, materialized as `betboy`, and verified before the
app starts; checkout hooks and smudge filters are not used for that step.
The same update also validates and atomically installs the Caddy policy with
same-origin frame protection; pre-update unit bytes are checked against the
previous trusted Git payload so a reviewed systemd migration can be deployed
without weakening the byte allowlist.
An `in_progress` marker pins an interrupted deployment to its exact original
target. Even if `main` has advanced, only an explicit retry for that marker
target is accepted, and only while it remains an ancestor of current `main`.
The checkout may contain a crash-consistent mix of predecessor and target files;
every such file and mode must match one of those two Git manifests exactly.
Requesting the newer tip is rejected before any target mutation.
Before new application code starts, the updater runs the hardened backup
oneshot for real, verifies its SQLite restore, owner, mode, hard-link, complete
manifest/member inventory and account isolation contracts, and checks that the
application cannot access the archive.
It then runs the reviewed 15K migration helper while the app, timers and workers
remain stopped. The helper scans every challenge database before changing any
one of them. It requires the exact 72-path production inventory and accepts only
the five exact, full `sqlite_master` DDL manifests observed across those v0
ledgers, including legitimate internal objects. Hidden CHECK/default/collation,
index, trigger, table, ID-sequence, type or object differences fail closed.
Public-SHA v1 is never migrated. Existing HMAC v2 is accepted only with its
valid authenticated current-state checkpoint and is never silently re-signed.
Every migrated database is reopened once more without migration authorization.
After the app starts, it verifies the public TLS health response and the exact
`frame-ancestors 'self'` and `SAMEORIGIN` response headers before completing.

Before downtime it validates the tracked-byte manifest, index, fast-forward
relation, protected-path policy, unit inventory, inactive workers and free
disk. It refuses untracked/ignored content outside a narrow data allowlist and
refuses all untracked code, executables and symlinks. It then pauses all seven
timers, waits for a race winner to finish, and stops the app. Only after every
database writer is down—and no other `betboy`-owned process exists—does trusted
inline code create a root-protected ZIP
with the exact SQLite inventory, per-file SHA-256, CRC and SQLite
`quick_check`. Both scheduled and pre-update archives also contain the exact
matching key as `integrity/challenge-ledger-hmac.key`; a challenge database
without that member fails verification. Complete archives also contain the
matching marker as `integrity/challenge-ledger-v2-migrated.json`; a current
challenge database without it fails verification. The same previous bytes are
reverified immediately before this backup.

Restore the database set, archived HMAC key **and archived marker** as one
recovery unit while the app, every timer and every worker is stopped and
disabled. Verify the archive before extracting anything:

```bash
sudo /usr/bin/python3 -I /usr/local/libexec/betboy-backup-runtime.py \
  --verify-only /root/recovery/betboy-sqlite-YYYYMMDDTHHMMSSZ.zip
```

Then restore the verified database members to their exact relative locations,
the exact `integrity/challenge-ledger-hmac.key` member to
`/etc/betboy/challenge-ledger-hmac.key`, and the exact
`integrity/challenge-ledger-v2-migrated.json` member to
`/etc/betboy/challenge-ledger-v2-migrated.json`. Both integrity files must be
single regular files owned `root:betboy` with mode `0640`. Run the same
`--verify-only` command again against the source archive before enabling any
unit. An explicitly `in_progress` pre-update archive is verified with the
additional `--recovery-mode` flag and must not start runtime units; restore it
and resume only the exact marker target through `betboy-update`. Never generate
a replacement key or marker for an existing challenge database.

When `requirements.txt` is unchanged, pip is skipped completely. Any
dependency change is rejected before downtime; follow
`deploy/VENV_MIGRATION.md` as a separate reviewed maintenance operation. The
updater intentionally has no movable-venv fallback because console-script
shebangs and unpinned resolution make that unsafe.

A failure before the offline database migration begins restores and
byte-verifies the previous tracked payload and root-owned files, then restores
the remembered active/enabled app/timer booleans only if every rollback check
succeeds. Any rollback error leaves app, timers and workers stopped and
preserves root staging. From the instant the durable `in_progress` marker is
published, every later failure—including target installation, migration,
startup, health or public checks—is always
fail-closed with all runtime units stopped: an automatic code rollback cannot
prove that a partially migrated database set is reversible. The updater
preserves staging and prints the root-protected database/key/marker recovery ZIP
for controlled restoration.

Before publishing `in_progress`, the updater persistently disables app, timer
and worker autostart, flushes that state to disk, and verifies app/timers are
exactly disabled and workers exactly static. The new service files independently
require a validated complete marker. A process kill, power loss or reboot
between marker publication and migration completion therefore cannot restart a
writer. Successful completion re-enables and re-verifies the app and all seven
timers while workers remain static.

The HMAC checkpoint v2 binds the complete dedicated-database schema inventory,
including internal SQLite objects and every sequence value, strict SQLite types,
risk/target settings, ticket definitions and materialized status, the financial,
settlement and observed-price chain state, their exact rows, IDs, tails and row
counts. Settlement is additionally replayed event by event against payouts,
money movements and visible ticket state. This detects later SQL rewriting or
rollback without the external key.
It cannot prove that unauthenticated v0 data was never manipulated before this
first migration. A backup archive also contains the HMAC key, so its verifier
proves internal consistency, not authenticity against an attacker able to
rewrite the entire archive; root isolation and immutable off-site copies remain
required.

The update intentionally refuses tracked server-side changes. Preserve and
resolve such files before retrying; never force-reset a production worktree
without first saving the evidence that made it dirty.
