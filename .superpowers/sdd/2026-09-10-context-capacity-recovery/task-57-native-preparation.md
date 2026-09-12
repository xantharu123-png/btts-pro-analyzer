# Task57 — native preparation and retained first guarded failure

Current status: the later `ba9c88f-02` guarded ATP attempt failed terminally;
WTA was not launched. This is NOT a native-chain pass. The earlier preparation
below is preserved chronologically; the actual run/readback follows it.

12 September 2026, Root. The reviewed harness source is `eddc926d22f8266d8d3d3baba6a26d7b55b1f3ad`;
controller checkpoint `a339a82b5f64722fc4520f7d67b427d19819683b` is pushed and
freshly ls-remote matched. GitHub main remains `2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
The application was not deployed or changed.

## Preflight and versioned archive upload

Actual read-only VPS preflight at `2026-09-12T18:15:45Z`:

- `/var/lib` root:root0755; existing QA directory user1000:1000 mode0700.
- `/usr/bin/time` and `/usr/bin/python3.12` root:root0755.
- Free space on both relevant paths:14119870464bytes.
- GNU time binary SHA256 `3b11dec50514a8473e9f6efa7a34d584d0657538c09988f61b72d38ad4991a10`;
  its version banner is `time (GNU Time) UNKNOWN`.
- Python binary SHA256 `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f`.
- No UID65534 processes; all three exact proposed new paths were absent.

The closed archive contains exactly440 non-hidden tracked Python files from
eddc926, no duplicate files, extra runtime databases or untracked data.
9226240bytes, SHA256 `60d01a0a875e2fe258f803dc6b877a5ed957591d003f6e56ea28339a1fa3eae9`.
The copy-only authorized upload and actual remote size/hash readback succeeded:
`/tmp/betboy-context-qa.9xr68INa/task57-eddc926-01.tar`, owner1000:1000 mode0664.
The containing directory remains0700. No root code was installed.

## Actual read-only native member inventory

The independently reviewed catalogue source, SHA256
`85348268e86765b34aa71206c6e1904053bc0e91c4659ecf163b1d901a1d4aff`, was held
in a local read-only FileStream, hashed, rewound and sent byte-for-byte to SSH
stdin as the ordinary VPS user. The exact remote command was:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B - inventory /tmp/betboy-context-qa.9xr68INa/task57-eddc926-01.tar eddc926d22f8266d8d3d3baba6a26d7b55b1f3ad
```

No package imports/installations or server output files were needed. Exact
binary stdout/stderr were retained locally through separate FileStreams:

- `.pytest_tmp/task57-native-inventory-eddc926-01.json`:679529bytes,
  SHA256 `d5f7ee70a1d0fd4599a462f335edeebf0a8fb7e8fda5921a16c1d9519279465e`.
- Matching `.stderr`:0bytes.
- Exit0,5752ms measured LOCAL transport wall, not native worker CPU/terminal proof.

Actual manifest:440 code files/8876329logical bytes;4540 dependency files/
217788209logical bytes across the fixed34 package/metadata roots. Bytecode
directories are excluded by the reviewed inventory. Archive/commit fields
match exactly; Root read the complete runtime/plan and every grouped root count.
Runtime: Linux6.8.0-138-generic/x86_64, Python3.12.3/GCC13.3.0, same Python binary
SHA above, stdlib paths `/usr/lib/python312.zip`, `/usr/lib/python3.12`,
`/usr/lib/python3.12/lib-dynload`. This is NOT full transitive B runtime closure.

Derived reviewed small plan:635398234new bytes,1015375962active-input ceiling,
235929600attempt reservation,29360128controls,134217728new metadata/slack;
original logical235403057, original allocated245760000, original metadata
134217728. These are reserved ceilings. Actual original/new physical occupation
has NOT yet been sampled by the native root parent. Fixed4GiB/8GiB and300CPU
charge, parent90/two90CPU children,600wall and other reviewed limits unchanged.

## Local launcher failure — preserved, no native job started

Actual pinned local launcher command against this native manifest returned1:

```text
.pytest_tmp/qa-python312-c-01/Scripts/python.exe -I -S -B tests/native_context_chain_catalogue.py launcher .pytest_tmp/task57-candidate-eddc926-python.tar 60d01a0a875e2fe258f803dc6b877a5ed957591d003f6e56ea28339a1fa3eae9 .pytest_tmp/task57-native-inventory-eddc926-01.json d5f7ee70a1d0fd4599a462f335edeebf0a8fb7e8fda5921a16c1d9519279465e
```

`launcher -> validate_manifest` line496 raised `ChainError: nonfixed dependency
installation`. Retained `.pytest_tmp/task57-eddc926-01-stdin.py` is empty;
matching `.stderr` is1077bytes. It was NOT sent as a root bootstrap.
The direct read-only reproduction confirms the exact cause: local Windows
`str(DEPENDENCY_SOURCE)` uses backslashes; native manifest uses canonical Linux
slashes; `.as_posix()` matches, and all package names/order are identical.

Task57 follow-up fix2 is delegated to the original author for the minimal
cross-platform fixed-path representation correction, parent pin and a targeted
regression. Do not bypass validation or rewrite the native manifest. Regenerate
archive/catalogue/launcher only from the subsequent independently reviewed fix.
All prior artifacts remain. No root job directory, native300CPU reservation,
guarded ATP/WTA run, B proof, main pull or application deployment occurred.

The developer read-only inventory and failed local generation are preparation
costs, not a completed protected global-C1800CPU/3600wall ledger. Old Task50
attempts and all failed/candidate files remain separately retained.

## Reviewed FIX2 and actual ba9c88f inventory/launcher

Source `ba9c88f6d9710088024c5db25854bce90b3a88c8` passed the independent scoped
FIX2 review; controller checkpoint `48425b6be1801062cc2d796777211b8785dcac92`
was pushed and freshly matched on the repair branch. Main remained2dd1116.
The local final30-pass XML and review pins are in the ledger; they were not
represented as a native pass.

Exactly440 tracked Python members were archived again at the reviewed commit:

- Local `.pytest_tmp/task57-candidate-ba9c88f-python.tar`, remote
  `/tmp/betboy-context-qa.9xr68INa/task57-ba9c88f-02.tar`:9226240bytes,
  SHA `fa889029d72fa110d1a65bf2c0fb1fc7b5d7ab988c49d4838e2a8748e9629801`.
- Actual ordinary-user VPS inventory, captured exactly to local
  `.pytest_tmp/task57-native-inventory-ba9c88f-02.json`:679529bytes,
  SHA `1ebfc466247775aef33afcabc2e43e4189c026b8cc4dbe0995ba077514bc88df`.
  Matching stderr0bytes; exit0, local transport4986ms. Same exact manifest was
  uploaded as `task57-ba9c88f-02-catalogue.json` in the existing QA directory.
- Real inventory:440 code files/8877619logical bytes,4540 dependency files/
  217788209logical bytes. Derived new reservation635399524bytes and active
  ceiling1015377252bytes; original logical235403057, allocated245760000,
  separate original metadata134217728. Limits and package roots unchanged.
- Generated `.pytest_tmp/task57-ba9c88f-02-stdin.py`:136270bytes,
  SHA `c6f3d93e0911b60a07e5e851717ec4c8f6e9155b76500ff7b8a7c3f5d0811a9a`;
  stderr0bytes. Root independently parsed the two-statement AST, verified all
  five embedded source hashes and exact equality to reviewed bootstrap output.
  No mutable root script path or earlier root sealer was executed.

Fresh18:33:20UTC preflight confirmed both uploaded hashes, unchanged Python/
GNU-time binary hashes, root-owned0755 `/var/lib`, absent exact new job,
14100631552bytes free and no UID65534 process. Exact held stdin bytes were
hashed, rewound and copied to SSH stdin without text-pipeline re-encoding.

```text
umask 022; exec sudo -n /usr/bin/time -f "TASK57_TIME exit=%x wall=%e user=%U system=%S maxrss_kib=%M" env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B - --manifest /tmp/betboy-context-qa.9xr68INa/task57-ba9c88f-02-catalogue.json --manifest-sha256 1ebfc466247775aef33afcabc2e43e4189c026b8cc4dbe0995ba077514bc88df --archive /tmp/betboy-context-qa.9xr68INa/task57-ba9c88f-02.tar --directory /var/lib/betboy-context-chain-task57-ba9c88f-02 --commit ba9c88f6d9710088024c5db25854bce90b3a88c8 --launcher-sha256 c6f3d93e0911b60a07e5e851717ec4c8f6e9155b76500ff7b8a7c3f5d0811a9a
```

## Actual terminal failure and independent readback

SSH exited1, actual local transport41820ms. GNU time observed terminal
exit1/wall40.38s/user28.34s/system6.84s/maxRSS63456KiB. The parent rejected
`accept_result` with `ChainError: stopped/failed child cannot be accepted`.
Local exact stdout is0bytes (SHAe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855);
stderr578bytes, SHA8460e259ad0be9e3b442c4071346a6e67411f131be01c47f7b21662f762a0d5d.
Both remain at `.pytest_tmp/task57-native-run-ba9c88f-02.*`.

Actual retained `ATP-output.json`:887bytes, SHA
`ba0635a7b7e34908f9262b9acb2c320fbdb651b9eff1de72b225f834f32ca1e7`:

- Exit125, stop_reason `nonzero_exit`; child CPU181298000ns,
  elapsed222570897ns, parent supervision CPU7584484ns, peakRSS60125184bytes.
- Actual kernel readback UID/GID65534, PID221082, CPU90s, FSIZE4194304bytes,
  one seccomp filter. InitialRSS59232256bytes.
- Observed output167bytes, SHA
  `7a29eda3a3f473be31d48501cbe80457f40751c1314f192c3d623e229656e0c2`;
  stdout empty, stderr contains `ChainError: unplanned Python file read`, then
  `betboy-native-launch-failed`. It does NOT identify the rejected file path.
- Sample gap51173673ns, minimum free13848711168bytes. No positive Task54
  result, no ATP database write and no WTA execution follows from these values.

The actual root-owned0600 journal
`a8061f178ea8b126f39a93aaaa9621b24e630faeb7ce8548ebe068fb70ee8249.jsonl`
is1751bytes, SHA9b956268e471c8497bd6207bd6f8e13588ef0162511c2fad4a3768ad541ac2b9.
Its three exact events are `init`, `reserve`300000000000CPU-ns, then
`stop`/`unmeasured`. No settlement, refund, deletion or retry. Root-owned0444
`failure.json` is125bytes, SHA8dfe0443b4a40511eaf94e7dae9f5529eb5dd8347ad6661e4fe964916968ea38,
and states STOP/native_pass=false/retain-all-no-retry/full300CPU retained.

At19:01:39UTC Root performed a separate bounded read-only file/terminal check.
Exact local bundle `.pytest_tmp/task57-native-run-ba9c88f-02-readback.json`:
2201593bytes, SHA
`c660eed0f46cb60ff4d207a3b715ef6625be746f7d1408011791eb36e70e316a`;
matching stderr0bytes, exit0. It retains full plan/journal/ATP/failure bytes
plus file metadata, not just parsed counters. A compressed byte-exact copy is
preserved in this plan's evidence directory for account/PC continuation.
`evidence/task57-native-run-ba9c88f-02-readback.json.gz`:203451bytes, SHA
`cde1303b28937c0cd3b68b3007e17db8e1c03685dc8c6cd25e73d0b645fbb83f`.
Root decoded that generated gzip and independently matched the complete raw
SHA above; compression does not replace or rewrite any retained observation.

Every one of440 copied code files and4540 copied dependency files was read
through no-follow FDs and compared by exact size/SHA to the manifest: all match,
all root:root0444. Code allocated9777152bytes, dependencies228143104bytes.
Original/copy archive and catalogue hashes also match. Whole retained job:
4986files/473directories,240634857logical and251904000allocated bytes,
13848129536bytes free. All three precreated private attempt directories are
empty. No UID65534 process remains. The plan is2098513bytes, SHA
`acb5c9c99409ce717cad22a38f3ef838621fdfd79d69bf4a22fc67cce85e01bb`.

Postflight19:02–19:03UTC: production remains2dd1116, actual
`betboy-app.service` and Caddy active, internal/public health `ok`, seven
scheduled timers. The first status command accidentally named nonexistent
`betboy.service`; `LoadState=not-found` and actual unit enumeration resolve
that diagnostic-name mistake, not an application outage. The pre-existing
failed daily `betboy-tennis.service` remains visible and out of scope.

## FIX3 diagnosis and ruling — no new native attempt yet

Original author `/root/c_native_chain_harness` resumed as sole writer from
HEAD48425b6, previous reviewed code/FIX_BASEba9c88f. The real local isolated
`import pytest` with the unchanged audit hook reproduces a first rejected read
of `pytest/__pycache__/__init__.cpython-312.pyc` despite `-B`. Python disables
bytecode writing with that flag, not its initial cache-read probe. This is
local actual-route evidence; the earlier native path was not captured.

Ruling: use a targeted regression and reject only the cache probe belonging
to an exactly admitted `.py` source as FileNotFoundError, allowing Python's
normal source fallback; never allow bytecode contents or whitelist whole
directories. Why: execute the reviewed source catalogue without mistaking
a routine failed cache probe for a required unknown input. Cost if wrong:
another retained stopped diagnostic, not relaxed runtime/data admission.
Unknown sources/cache names remain denied. No product, Task54, guard, package,
resource, scope or frozen-spec change is authorized by this ruling. A fresh
native attempt requires completed scoped review and separate retained inputs.

Native small-chain completion, full growth, protected global accounting, B,
restore and main/application deployment all remain OPEN.

FIX3 is now locally committed as97e3bb64cfc4c0e81f4d55262db2de1b613760b6
and independently approved. Review SHA
8317f74a9e8923306c6af95af60679e0efb8684d5b270f83bc36937b29495b16;
Root read it fully and hashchecked the final32/0/0/0 XML. Worker SHA
584f90ba46e3c2895eb5ea6bbca67956c407da45e37473d5314dcb4e0f83573d,
parent/catalogue unchanged. Author report47ebf15f9cfef37ff8a2db2f371918ae92c33eacd517c14c663302ea0335fb98
preserves the additional incomplete local full-route catalogue probe: its
owning session was manually stopped before result/workspace, both observed
local Python PIDs absent afterward. It is not a completed full-route test.
The new local immutable archive is9236480bytes, SHA
1aca4741b3dc21767da361784c21445694a38f3b87c75da3bd05ec7a08b0f465;
all440members/8882016source bytes and exact worker SHA independently checked.
Actual new upload/inventory/launcher/guarded/terminal evidence follows only
after this review checkpoint. Nothing above grants a native or release pass.
