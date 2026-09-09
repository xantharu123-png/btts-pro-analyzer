# Fixed Linux root/betboy DAC smoke — ready for controller review, NOT RUN

2026-09-09. Owner `/root/b3_shared_snapshots_20260909`.

## Status and exact scope

Only local ignored scripts and this design record were authored. **No SSH, root execution, server mutation, full suite, Git mutation, real key access or production database access occurred.** This is a proposed synthetic DAC execution, not evidence that its assertions have passed on Linux.

Script: `root_dac_smoke.py`, SHA-256 `958836d1a74376cf76f35d44b526cfd4b7438deadc61f539a7d86b6e8b0ad756`.
Local design checks: `test_smoke_design.py`, SHA-256 `dea1f93cf0fe119b888d28451c72315ac608ebd0c5f53dddb8798563b7806aaf`.

Local owning worktree remains clean on `7ba4c9746caf75e0dd6ab5881c8b7ed329a7e358`; hook bytes remain `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`. The later integrated suite belongs to Root and was not duplicated.

The script deliberately does not run the entire updater, configure its production environment, simulate quiescing by suppressing process checks, invoke its migration/backup principal setup, change keys/groups/units/dependencies/pins or exercise the installed Commit-A to Commit-B trust transition. Actual existing app/venv access is unchanged; **this is no new sandbox or revocation of betboy's existing production permissions**.

## Fixed inherited inputs (controller-provided Linux observations)

- Private existing QA parent `/tmp/betboy-context-qa.9xr68INa`, expected ubuntu 1000:1000 mode 0700.
- Existing source archive `context-hook-linux-a224d13.tar`, 101335040 bytes; SHA-256 `e76488f9a34ca8544667411151bac6e69ab275ccad4d6079c47a2051cf83492f`; revision `a224d136d232ecc16e7f4b0a3341518efb54906a`.
- Existing real synthetic SQLite online-backup image under that parent: `hook-fixtures-2346846-20260909/.pytest_tmp/hook-linux-unprivileged-fixtures-02/test_wal_online_backup_then_re0/private/image.db`, 45056 bytes; SHA-256 `66ee78e58b4b70fb33b0f70f8b7995ac220025ef2c5bc8f34c273dfa5cfe6c09`.
- betboy uid 997/gid 987, sole group 987; `fs.protected_hardlinks=1`; existing app interpreter `/opt/betboy/venv/bin/python`. The script verifies the account and hardlink setting rather than changing them.

These remote observations came from the controller, not a fresh remote check by this reviewer. The proposed run requires matching sizes/hashes, full pre/post identities and symlink-free fixed input paths. It copies the already known exact WAL image; it does not fabricate a newly backdated online backup or touch the original live-WAL fixture.

## New fixture permission layout

Only `tempfile.mkdtemp(prefix='betboy-context-dac-', dir='/tmp')` creates the top-level fixture. Nothing is extracted over an existing directory. No previous evidence is cleaned up.

| New node | Owner/mode | Purpose |
| --- | --- | --- |
| common ancestor | root:betboy 0710 | Traverse-only to explicit app paths. Keeping this ancestor 0700 would invalidate the positive read test. |
| `private/`, `private/verify-tmp/` | root:root 0700 | Full source archive copy, full ZIPs, synthetic key, receipts, captured reports, result. |
| private files | root:root 0600 | No app ZIP/key/receipt access. The source manifest alone is root:betboy 0640 inside the still root-only directory. |
| complete `source/` tree | root:betboy directories 0750/files 0640 | Exact archived code, no writable import directory. No source module executes as root. |
| each `sealed-*/` | root:betboy 0750 | Private root-owned context input directory; app cannot add SQLite companions. |
| each sealed `context_models.db` | root:betboy 0440, nlink 1 | Created/sealed by the actual unchanged hook data helper. |
| `app-scratch/` | betboy:betboy 0700 | Only new mutable synthetic variants and positive write controls. |

All TAR metadata is checked before source extraction: canonical relative names, duplicates, file/directory collisions, links, sparse/special files, setid bits, total sizes and count. Files are copied with exclusive no-follow opens, not `extractall`. Whole archive hash, manifest of every staged source file, every staged source file identity, original source/image identities and every private ZIP/sealed-image hash/identity are checked before/after. atime is deliberately excluded because reads can legitimately change it.

## Execution boundary and test matrix

Root's script imports stdlib only. The only archived Python it executes is the exact hash-pinned stdlib inline `context_hook_data` and `verify_backup_archive`; the inline AST is also checked for imports outside its stdlib inventory. It never imports the app, NumPy, the app venv, pytest, D4 modules or model fixtures as root.

The real `context_hook_command` and exact `as_betboy() { runuser -u betboy -- "$@"; }` are extracted unchanged from the pinned updater. A small fixed Bash harness adds only `set -euo pipefail`, umask 077 and a fixed error function. All application invocations go through this real chain:

`runuser -u betboy -- /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/timeout --signal=TERM --kill-after=10s 600s /opt/betboy/venv/bin/python -I -B ...`

The unchanged parallel capture is the actual 610s GNU timeout and `head -c 1048577`, writing only a new root-private output. The harness itself has a 630s wait bound and cleanup only of its newly created subprocess process group on that timeout. Per-call postchecks inspect only process session IDs started by this smoke, including nested GNU-timeout process groups; no process cmdlines are printed and no production process is stopped.

| Case | Actual construction and required result |
| --- | --- |
| structural | Exact pinned WAL image, full private verified ZIP with syntactically valid synthetic 65-byte key, actual `extract_and_seal` changes its NEW copy to DELETE using SQLite. Real app CLI must return 0 with the unchanged closed structural report, two tours, one manifest, one B1 observation. |
| transport-only | App-only scratch builder extracts four exact functions from pinned existing `tests/test_context_runtime_backup.py`: `model_event`, `effect_payload`, `add_receipt`, `add_context_snapshot`. It adds an orphan effect and legacy B3 result, with NO experiment/evaluation/approval. Another fully verified ZIP and actual sealing; actual app CLI must return 2 and existing `validate_report` must accept its real nonempty sorted limitation subset with empirical flag exactly false. No fabricated result or changed whitelist. |
| broken reference | App-only scratch copy; delete the actual ATP artifact referenced by the existing manifest. Full ZIP/SQLite transport remains valid. After sealing, the actual app CLI must return 1/`ArtifactIntegrityError`; the unchanged report validator must reject it. |
| DAC | Actual betboy reads the sealed image and creates/reads/chmods/unlinks its own scratch control. Actual write, chmod, unlink, replace, hardlink and three SQLite-companion creations against the root-sealed image must fail with EACCES/EPERM. Four explicit reads of full archive/key/private ZIP/receipt must fail. Originals and sealed bytes must remain unchanged. |
| timeout | Inside the unchanged outer hook bounds, a genuine 1-second GNU timeout stops a 30-second app Python sleeper and yields actual 124. The existing report validator must reject even an otherwise valid structural report paired with that status. This does not claim the 600-second outer deadline was allowed to expire. |
| output | Genuine app child emits a bounded 8MiB string; unchanged head must retain exactly 1048577 bytes, which exceeds the unchanged 1MiB report allowance and must be rejected. No unbounded parent capture of child output. |

The app-only builder was explicitly authorized by Root. It extracts those four exact function bodies, not the whole pytest module, so it introduces no pytest dependency. Their source file from a224d13 was independently read via Git and pinned to `71dc37951bed4e6fc576e842829f7b0af08b692243bd6c353423237c9cddef62`. It writes only the new app-owned scratch. The deterministic synthetic key is public test material; inability to read its file is a DAC test, not a claim that its value is secret or that financial chains were validated.

On success, only a compact JSON status/path/result hash is printed. The full bounded reports, proof hashes, principal checks and test outcomes are retained root-private in `private/RESULT.json`. On failure, new evidence remains; only a fixed failure scope and exception class are printed. There is no automatic deletion of any fixture or predecessor data. The pinned backup verifier's own temporary directory is contained in the NEW `private/verify-tmp/` and cleans only its own temporary copies.

## Proposed invocation — controller only, after full review

First transfer only this new script, without overwriting any predecessor, to `/tmp/betboy-context-qa.9xr68INa/root-dac-smoke-958836d1.py` as ubuntu 1000:1000 mode 0600. Reconfirm the local/remote script hash. Do not execute its user-writable path directly as privileged code.

The following narrow in-memory hash bootstrap imports stdlib only and executes exactly the reviewed bytes; **it has not been run**:

```sh
sudo -n /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -B - <<'PY'
import hashlib, os, stat
from pathlib import Path
p = Path('/tmp/betboy-context-qa.9xr68INa/root-dac-smoke-958836d1.py')
for part in (p, *p.parents):
    assert not stat.S_ISLNK(part.lstat().st_mode)
fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
try:
    before = os.fstat(fd)
    assert stat.S_ISREG(before.st_mode) and before.st_nlink == 1
    assert (before.st_uid, before.st_gid, stat.S_IMODE(before.st_mode)) == (1000, 1000, 0o600)
    assert before.st_size <= 65536
    with os.fdopen(fd, 'rb', closefd=False) as stream:
        raw = stream.read(65537)
    signature = lambda st: (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid,
                           st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    assert signature(before) == signature(os.fstat(fd)) == signature(p.lstat())
    assert hashlib.sha256(raw).hexdigest() == '958836d1a74376cf76f35d44b526cfd4b7438deadc61f539a7d86b6e8b0ad756'
finally:
    os.close(fd)
exec(compile(raw, 'reviewed-fixed-synthetic-DAC-smoke', 'exec'), {'__name__': '__main__'})
PY
```

This is a single fixed synthetic test, not a privileged installation API. No free input/output/configuration/key argument exists.

## Local design evidence only

`python -B -m pytest -p no:cacheprovider .pytest_tmp/hook-linux-dac-design-20260909/test_smoke_design.py`, fresh basetemps per run:

- First: **1 failed/23 passed**, 0.66s. A real TAR regular entry `.` was not rejected early; preserved `.pytest_tmp/hook-linux-dac-design-check-01.xml`, SHA `8baf24a0be4577d22bc89aaa4360c46c231cbfd3be13570469f7e6bc0d8b4efc`.
- The local draft now requires nonempty canonical path parts. No pinned updater source was changed. Second: **24 passed**, 0.65s; original RED XML retained.
- Final draft, after narrowing process postchecks to its own newly started session IDs: **24 passed**, 0.65s, `.pytest_tmp/hook-linux-dac-design-check-03.xml`, SHA `8ac3692eae279d5f5f03fa018b3e7f5feb2fba5599ef052025bd2071f16f009e`.

These tests perform real malicious/control TAR parsing, exact source/function/hash checks, Python compilation and Bash `-n` parsing. They never invoke runuser/root/app fixture code or the remote interpreter. Therefore actual root DAC, actual Linux exit 0/2/1, timeout/output behavior, existing venv readiness and installed updater bootstrap remain **unverified by this design artifact until Root executes and inspects the resulting evidence**.
