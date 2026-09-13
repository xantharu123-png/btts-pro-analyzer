# Task61 Root read-only preflight — 13 September 2026

Planning observations only, not Source/D2, complete retained-history admission,
native driver execution or a capacity pass. No files, modes, processes, services,
secrets or database contents were changed. No code/data archive was transferred.

## Retained allocated space

Exact read-only commands (ordinary SSH with sudo for protected QA metadata):

```powershell
ssh -T -o BatchMode=yes -o ConnectTimeout=10 betboy-vps 'sudo -n /usr/bin/timeout --signal=TERM --kill-after=2 40s /usr/bin/find /var/lib -mindepth 1 -maxdepth 1 -type d -name "betboy-context-*" -exec /usr/bin/du -B1 -s -- {} +'
ssh -T -o BatchMode=yes -o ConnectTimeout=10 betboy-vps 'sudo -n /usr/bin/timeout --signal=TERM --kill-after=2 40s /usr/bin/du -B1 -s -- /tmp/betboy-context-qa.9xr68INa; /usr/bin/df -B1 --output=size,used,avail,target /var/lib'
```

Execution-tool chunk aa268d, outer exit0, wall2.790617s. Exact observations:

| Existing path | Allocated bytes reported by du |
| --- | ---: |
| /var/lib/betboy-context-update.6mo65kij | 57344 |
| /var/lib/betboy-context-chain-task57-bc6305c-05 | 252014592 |
| /var/lib/betboy-context-chain-task57-97e3bb6-03 | 251916288 |
| /var/lib/betboy-context-chain-task58-588843d-01 | 255823872 |
| /var/lib/betboy-context-update.pz2d5uwu | 57344 |
| /var/lib/betboy-context-chain-task57-ba9c88f-02 | 251904000 |
| /var/lib/betboy-context-chain-task57-df874ba-04 | 251936768 |
| /var/lib/betboy-context-update.n29jch3h | 57344 |
| /var/lib/betboy-context-update.902t4zyn | 57344 |
| /var/lib/betboy-context-update.offwdjq0 | 1040384 |
| /var/lib/betboy-context-update.w4jsq5qr | 57344 |
| /tmp/betboy-context-qa.9xr68INa | 7747723264 |

Five chain jobs total1263595520bytes; the listed var/lib paths plus the old
QA root total9012645888bytes. Filesystem size40483942400, used27937079296,
available12530085888bytes at this observation. This is allocated-space metadata,
not a byte/hash inventory or proof of namespace quiescence. The second SSH
command's final status is df's status; successful printed du values are retained
but no separate individual du exit was captured. No timing/CPU ticket is inferred.

C4 limits the entire **new** preparation/QA/output job to8GiB, including its
parts/failures/retries. Existing historical QA, backup and rollback reserves
must also be freshly counted against free space. The historical9.01GB aggregate
is neither a new-job8GiB pass nor automatically the new job's measured output.
The actual later plan must bind that distinction and all retained membership;
there is no deletion, capacity release, budget refund or new-lifecycle proof
from these du totals. Additional free reserve4GiB remains unchanged.

## Root capability observation and actual limit inheritance

```powershell
ssh -T -o BatchMode=yes -o ConnectTimeout=10 betboy-vps 'date -u +%Y-%m-%dT%H:%M:%SZ; sudo -n /usr/bin/cat /proc/self/status'
```

Chunk1de2a7, exit0, wall1.357148s, printed UTC2026-09-13T08:47:04Z. Observed
fresh cat PID231156, parent231154; UID/GID all0, one thread, TracerPid0,
CapPrm/CapEff/CapBnd000001ffffffffff, CapInh/CapAmb0, NoNewPrivs0, Seccomp0,
no blocked/ignored/caught signals. This includes CAP_SYS_RESOURCE bit24;
it is not yet exact future-parent or initial-user-namespace admission.

Actual unchanged supervisor calls os.fork at
context_preparation_supervisor.py:379, then its child function before UID/capability
drop. The unchanged guard at context_preparation_process_guard.py:481-491
refuses an inherited hard limit below the requested child limit. Thus parent
hardCPU60 cannot simply fork a requested CPU240 child, nor can old parent
FSIZE128MiB directly admit workerFSIZE512MiB after the drop. Old90/90 evidence
does not prove this new handoff.

Root proposed a narrow trusted child-only pre-drop limit prefix around the
actual supervisor child path or original fork: parent stays hardCPU60 for its
entire lifetime; only its direct root child establishes CPU240 before calling
the unchanged identity-drop/guard/SIGSTOP/readback path. Prefix failure must
exit125 in the child, never unwind into parent ownership/locks. The reviewer
must assess the exact selected bridge, actual capability checks, source
custody, no pre-guard product import, tiny real native readbacks and failure/
reaping behavior. This document does not approve an unimplemented bridge as
proven. A fixed parent FSIZE512MiB with separately bounded control-file slots
can avoid a second handoff without changing the overall allocation plan.

Primary API references freshly checked by Root: hard-limit increases require
CAP_SYS_RESOURCE in the initial user namespace; soft/hard resource limits are
inherited by fork. [Linux getrlimit(2)](https://man7.org/linux/man-pages/man2/getrlimit.2.html),
[Linux capabilities(7)](https://man7.org/linux/man-pages/man7/capabilities.7.html).
This supports the engineering proposal, not native acceptance.

## Fresh baseline page/kind contract

Instrument evidence/task61-baseline-profile-read.py, SHA256
80d82bdd3840e8fd775aa40b4ce5a47dd6f5d604b96ab189f0f50a05b1192505.
Exact command:

```powershell
Get-Content -Raw -LiteralPath '.superpowers/sdd/2026-09-10-context-capacity-recovery/evidence/task61-baseline-profile-read.py' | ssh -T -o BatchMode=yes -o ConnectTimeout=10 betboy-vps 'exec sudo -n env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B -'
```

Chunk9704cc, actual SSH/tool exit0, tool wait3.238653s. Native observation
2026-09-13T08:52:26Z, SQLite3.45.1. Full original file SHA/held FD/path identity
checked before and after, still270233600bytes,
73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa.
No companions or source mutation; no protected Final/model payload opened.

- Header page4096, encoding1; PRAGMA page_size4096,page_count65975,UTF-8,
  journal_mode=delete,auto_vacuum0,schema_version1,user_version0,application_id0.
- Reader query_only1,trusted_schema0 (read-only immutable source, MEMORY temp).
- Actual six tables: active_manifest,artifacts,context_contents,
  context_observations,context_snapshots,manifests; no optional rollback table.
- Artifact kind tennis-live-winner-original-v1:31, earliest created_at
  2026-09-10T10:06:44.662444+00:00, latest2026-09-11T21:10:42.574388+00:00.
- Artifact kind tennis-tour-state:2, earliest2026-09-10T09:58:49.392625+00:00,
  latest2026-09-10T10:14:34.956361+00:00.

Enforced CPU20/AS512MiB/FSIZE0/CORE0/alarm30; reported CPU1.921772020s before
output, post-import wall1.882077372s, peak20388KiB. No durable budget ticket or
whole-job accounting claim. This is separate read-only input preparation,
not another changed-input native-capacity attempt or refund of prior charges.

## Follow-up complete shape and planning reserve

Metadata-only instrument `evidence/task61-retained-metadata-read.py` SHA
5d8d68972520f422ad55d5fbb2f23385914bfa8bcaa930e3e1b019440d993401 ran
at09:26:14UTC, actual SSH/tool exit0/chunkf7c8ad. Its complete raw JSON is
`.pytest_tmp/task61-retained-metadata-01.json`, SHA
2e1699479e0bae473ac9f8bfd7038dbac4ec7bf9f2060081cfc6652ec4be1171.
It opens no file content and establishes no execution reserve. Actual reported
CPU6.05427074s, RSS15232KiB, hardCPU30/AS512MiB/FSIZE0/alarm45; no durable ticket.

85 selected existing QA/backup/rollback roots total20390694912 per-path allocated
bytes. Because hardlinks are deliberately counted at each path, this is a
conservative occupied upper bound, not unique filesystem allocation. Actual
filesystem available bytes12525854720 already reflect occupied history; do not
subtract that20.39GB again as future allocation. The old/tmpQA root has56895
regular files,17409directories,1932symlinks and88 hardlinked regular entries.
Many old negative-test namespaces likewise contain deliberately invalid links.
They cannot be erased or treated as executable/source seals. The owning brief's
separate typed no-follow retained-history contract handles them explicitly.

Selectors include `/var/lib/betboy-*` except persistent service key-staging
`betboy-backup`, `/var/tmp/betboy-update.*`, `/tmp/betboy-context-*`,
`/tmp/betboy-tour-*`, and `/var/backups/betboy*` except unrelated SSH-key backup
`betboy-ssh`. These exclusions are explicit planning scope boundaries, not
exclusions within any admitted retained root. Filesystem available bytes still
include every occupied file. The later actual inventory must refresh membership
and include newly created separate QA namespaces/controls through exact slots.

Subsequent Task60 native protocol checks created the explicitly recorded
`/var/lib/betboy-admission-task60-protocol-8574747-01`,49152allocated bytes and
two retained synthetic300CPU tickets. It must be added to retained inputs;
the09:26 metadata report is therefore not current admission evidence.

Read-only app planning size query (chunk eaa53d, final SSH/tool exit0):

```text
sudo -n /usr/bin/timeout --signal=TERM --kill-after=2 30s /usr/bin/du --bytes --summarize --exclude=.git --exclude=.venv --exclude=.pytest_tmp --exclude=.pytest_cache --exclude=__pycache__ --exclude=.codex_test_venv --exclude=backups_runtime -- /opt/betboy/app
/usr/bin/df -B1 --output=avail /var/lib
```

Observed1252376962 logical bytes in code/data excluding the named tool/cache
areas; filesystem free12525584384. No content opened. The printed du result is
retained, but the final command status is df's rather than a separate du status.
Root selects an additional **4GiB** future backup/rollback reserve for Task61,
on top of unchanged4GiB free reserve and exact still-outstanding job allocations.
It exceeds three times this observed code/data envelope (3757130886bytes).
This is a conservative diagnostic planning reserve, not a completed backup,
quiescent live inventory, compressed-size promise or later rollout sizing proof.
The actual Task61 admission must freshly check available/reserved space; the
full-C/release owner must later measure its complete actual backup/rollback plan.
