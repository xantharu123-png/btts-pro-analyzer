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

## Actual second guarded run97e3bb6-03 — stopped before setup

Controller checkpoint9007150fde783c9ef8d0c453146f8a78a05f3ba0 was pushed and
freshly ls-remote matched; GitHub main remained2dd1116. FIX3 code was therefore
reviewed and remotely preserved before the next actual native execution.

Read-only preflight19:19:34UTC confirmed the three new paths absent, no
UID65534 process, unchanged Python/GNU-time hashes, and13847932928bytes free.
The exact9236480-byte archive97e3bb6 was uploaded to the new
`/tmp/betboy-context-qa.9xr68INa/task57-97e3bb6-03.tar`; remote SHA matched
1aca4741b3dc21767da361784c21445694a38f3b87c75da3bd05ec7a08b0f465.
No old candidate was overwritten.

The same held93d38e46 catalogue source ran as ordinary user with exact argv:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B - inventory /tmp/betboy-context-qa.9xr68INa/task57-97e3bb6-03.tar 97e3bb64cfc4c0e81f4d55262db2de1b613760b6
```

Exit0/local transport4639ms, stderr0bytes. Exact local
`.pytest_tmp/task57-native-inventory-97e3bb6-03.json`:679530bytes, SHA
7692f06a247196eeae16d122685e9aab73d6c4b1e0e730a66ff9f0179dc8d0b8.
440code/8882016bytes and4540dependency/217788209bytes; runtime unchanged.
New reservation635414161bytes, active ceiling1015400081; original allocated
245768192/logical235413297 plus134217728 original metadata. All fixed limits
unchanged. Root read the complete plan/runtime and exact worker record.

The reviewed local `launcher` CLI validated this exact archive/manifest and
generated `.pytest_tmp/task57-97e3bb6-03-stdin.py`,136270bytes, exit0/stderr0.
SHA remainedc6f3d93e0911b60a07e5e851717ec4c8f6e9155b76500ff7b8a7c3f5d0811a9a
because parent/catalogue/helpers did not change. Separate AST/5-source/exact
bootstrap reconstruction passed. The exact catalogue was uploaded to
`task57-97e3bb6-03-catalogue.json`. Fresh19:22:25UTC readback confirmed both
remote hashes/runtime hashes, absent job and13838004224bytes free.

Actual command, using the held/hashed exact binary stdin:

```text
umask 022; exec sudo -n /usr/bin/time -f "TASK57_TIME exit=%x wall=%e user=%U system=%S maxrss_kib=%M" env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B - --manifest /tmp/betboy-context-qa.9xr68INa/task57-97e3bb6-03-catalogue.json --manifest-sha256 7692f06a247196eeae16d122685e9aab73d6c4b1e0e730a66ff9f0179dc8d0b8 --archive /tmp/betboy-context-qa.9xr68INa/task57-97e3bb6-03.tar --directory /var/lib/betboy-context-chain-task57-97e3bb6-03 --commit 97e3bb64cfc4c0e81f4d55262db2de1b613760b6 --launcher-sha256 c6f3d93e0911b60a07e5e851717ec4c8f6e9155b76500ff7b8a7c3f5d0811a9a
```

Terminal SSH exit1/local transport41189ms; actual GNU time exit1/wall40.32s/
user28.02s/system7.36s/maxRSS89744KiB. Parent `accept_result` rejected the
nonzero child. Exact local stdout0bytes; stderr578bytes, SHA
806f231ca3915c284a2856099eda330ed49850c6fd32804b05c66be53ed6ab03.
Files remain `.pytest_tmp/task57-native-run-97e3bb6-03.stdout`/`.stderr`.

Actual ATP result:890bytes SHA
b46674f277806eea7e6593b3a59f8e5fdbec72dad221a3730b1b8974c79a4e72.
Exit125/nonzero_exit, CPU1716124000ns, elapsed1757707859ns, RSS91897856bytes;
parent supervision19374420ns, maximum sample gap51552489ns,
minimum free13586079744bytes. Guard readbackUID/GID65534/PID222235,
CPU90/FSIZE4194304/one seccomp filter/initialRSS60301312. Retained stderr167bytes
has the same generic `unplanned Python file read`, not a pathname, followed by
`betboy-native-launch-failed`; stdout empty. No WTA result exists.

Separate read-only inspection found no Task54 setup or data file: the three
private attempt directories are empty. At19:30:06UTC the complete readback
again verified all440/4540 copied members by actual size/SHA/root:root0444,
and original/copy archive+catalogue equality. Job4986files/473directories,
240649498logical/251916288allocated bytes,13586022400bytes free; no UID65534 PID.

- Budget journal `be5cd6877f5a3fe5dbb4ee00049eea963c8cf0b5c4782aecc10b58ac1f67a238.jsonl`:
  1751bytes, root0600, SHA5bb63c2f912ab90f2b161180f02aa0ca209da68acd817f442bfc2c405a5fc44b.
  Actual init/reserve300CPU/stop-unmeasured, no settlement/refund.
- Failure125bytes, SHA8dfe0443b4a40511eaf94e7dae9f5529eb5dd8347ad6661e4fe964916968ea38;
  STOP/native_pass=false/retain-all-no-retry. Plan2098513bytes,
  SHA46d07c153851ba2d4a703fb5a3f8d2a5ad023091c572adaed6f4649a795a3c90.
- Local raw readback2201596bytes, SHA
  45e4a1dce8ffe82f0fc8d83572af9f8fabebed761a395f30b3baadb40a37a5b1.
- `evidence/task57-native-run-97e3bb6-03-readback.json.gz`:203400bytes,
  SHAba155a1ee08f206e7218fe0f782dd9823c2c342c0e7f9c3ca58cf5dc5bb5869a;
  independently decoded and compared to the full exact raw SHA above.

Two actual Task57 attempts now retain600CPU-s; earlier Task50 retains270CPU-s.
All870 conservative diagnostic CPU-s remain recorded, with no discarded
attempt or refunded slot. This does not turn these separate diagnostics or
local development into the missing protected global-C/B cost registry.

## Fresh FIX4 owner and actual optional-metadata diagnosis

Per SDD round4, fresh most-capable owner `/root/c_native_chain_fix4`
(gpt-6-astra/xhigh) received task-57-fix4-brief.md fromHEAD9007150,
FIX_BASE97e3bb6. Only worker/tests/report may change; Root owns all native work.
No source edit preceded its bounded30s local actual-import diagnostic.

That one subprocess used5160 exact local names/37 observed selected package
roots, not the unrelated full installation. It failed at absent
`numpy-2.5.2.dist-info/direct_url.json`: SciPy optimize -> array API ->
NumPy testing `_private/utils.py` -> actual importlib.metadata read_text.
This is an optional installation-origin record; the stdlib expects not-found
to return no origin, but the generic ChainError escapes that handling.

Root then independently read native NumPy source lines55–85 without importing
it. Exact source101390bytes, SHA
b55731515d2b64349472e88dbefbf18b7791e14fb5234c7d0b10f9ece07cbfcc matches the
manifest. Lines60–72 call `distribution('numpy')` and, on this actual3.12
runtime, `np_dist.read_text('direct_url.json') or '{}'`. Actual lstat confirms
the file absent both in the original2.5.1 installation and the root-sealed
97e3bb6-03 dependency copy. This is source/absence parity, not a retrospectively
captured native exception pathname.

Ruling: deny only this exact optional metadata probe as FileNotFoundError when
the target is NOT an admitted member, anchored to the already admitted NumPy
distribution metadata; if actually catalogued, preserve the exact admitted
read. Never grant/read unknown bytes or turn arbitrary unknown paths into
silent absence. Also attach bounded denied-path/event/flags diagnostics to
other unplanned reads without new I/O or authority. Why: faithfully represent
this observed optional-file absence and make future failures diagnosable.
Cost if wrong: retained failed QA, not a relaxed path or resource envelope.
The author must prove actual metadata absent/admitted/unadmitted/unknown/write
semantics and the bounded actual import route with fresh RED/GREEN before
independent re-review. Different new denials require Root diagnosis, not a
growing blind allowlist. No further native attempt has started.

## FIX4 reviewed candidate — before the next native execution

The narrow worker/test/report commit isdf874ba7a29ee41ef27d48eb7a726520bd6fdcc4.
Root freshly verified final36/0/0/0 XML in9.433s and actual source hashes.
Independent review49d598b37ef71476e3d902bfc5b8465d000e40fa538a71532a72ecbbb7aaf4e9
is SPEC COMPLIANT / QUALITY APPROVED with no new finding; read fully by Root.
The portable full import remains partial at an extra local-only PyArrow
installation; it was not admitted or reproduced as a native failure.

Immutable local archive `.pytest_tmp/task57-candidate-df874ba-python.tar`:
9246720bytes, SHA7d5f3857584a8c87b39c10cd34621a80f407cbf69df8bb39c99f9f1b1e619c43,
440actual Python members/8889435source bytes, all checked through the actual
catalogue member validator. Worker SHA
b05e45ab5ac2d2a76fedc88245ad76dd28c85f4eee7006d45c096a693ab989cd.
Parent/catalogue/helpers and fixed native limits remain unchanged.

Fresh read-only preflight19:51:03UTC: new `task57-df874ba-04.tar`,
`task57-df874ba-04-catalogue.json`, and root job directory absent; no UID65534
process,13585653760bytes free, exact Python/GNU-time hashes unchanged. This is
preparation only. Native package inventory, reviewed emitted stdin, remote
hashes, actual guarded execution and separate external terminal/readback must
be recorded next. Both prior failed jobs and all870CPU-s conservative
diagnostic charges remain retained. No application/main deployment.

## Actual third guarded rundf874ba-04 — required timezone data missing

Reviewed checkpoint120814ab971b4d6f03aeae02ab8c5a81277ed6b5 pushed and freshly
ls-remote matched; main2dd1116 unchanged. The exact reviewed9246720-byte archive
was uploaded to fresh `/tmp/betboy-context-qa.9xr68INa/task57-df874ba-04.tar`,
remote SHA7d5f3857584a8c87b39c10cd34621a80f407cbf69df8bb39c99f9f1b1e619c43.
Normal-user held93d38e46 catalogue inventory returned exit0/4416ms/empty stderr.
Local manifest679530bytes SHAc1753bd765bcc219911674a1f41f7bb370aca20fdbbe06e66765e5b0141b09b2,
440code/8889435bytes and4540dependencies/217788209bytes; exact runtime unchanged.
Plan total635431820/active1015430028, original logical235423537/allocated245780480,
plus134217728 original metadata. All fixed limits unchanged.

Local held-source launcher exited0/418ms/empty stderr. Emitted stdin136270bytes
SHAc6f3d93e0911b60a07e5e851717ec4c8f6e9155b76500ff7b8a7c3f5d0811a9a;
Root independently AST-checked its two statements, exact five embedded source
members and full reconstruction. Catalogue uploaded to fresh
`/tmp/betboy-context-qa.9xr68INa/task57-df874ba-04-catalogue.json`.
20:00:09UTC remote hashes matched archive/catalogue/Python/GNU-time;
13575450624bytes free. Actual held stdin executed with:

```text
umask 022; exec sudo -n /usr/bin/time -f "TASK57_TIME exit=%x wall=%e user=%U system=%S maxrss_kib=%M" env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B - --manifest /tmp/betboy-context-qa.9xr68INa/task57-df874ba-04-catalogue.json --manifest-sha256 c1753bd765bcc219911674a1f41f7bb370aca20fdbbe06e66765e5b0141b09b2 --archive /tmp/betboy-context-qa.9xr68INa/task57-df874ba-04.tar --directory /var/lib/betboy-context-chain-task57-df874ba-04 --commit df874ba7a29ee41ef27d48eb7a726520bd6fdcc4 --launcher-sha256 c6f3d93e0911b60a07e5e851717ec4c8f6e9155b76500ff7b8a7c3f5d0811a9a
```

Actual terminal SSHexit1/local41822ms. GNU-time exit1/wall40.94/user29.14/
system7.17/maxRSS132128KiB. Retained stdout0, stderr579bytes SHA
e0d9db28a8fab6ac6cdf7aadbc6c47427a9f2089ad5c3b1841f5ad7e89548f44;
parent accept_result correctly rejected nonzero child, no success report.

Actual ATP-output.json1281bytes SHA
3b092aea7bd5a09cc85daa4909a55837a9c8f68144ead213da167d3aa22f279f:
exit125/nonzero_exit, CPU3863069000ns/wall3964996145ns/RSS135450624bytes,
parent supervision38746209ns, sample gap52593644ns, minimum free13323509760.
Kernel UID/GID65534/PID223356/CPU90/FSIZE4194304/one seccomp filter,
initialRSS59260928. Exact362byte output SHA
a659e278b54e124bcd61cc912e9b9aab90a081b7330e4c528d67c5663f2ee094 records
the actual denied `/usr/share/zoneinfo/UTC`, event open/flags524288,
pathSHAc53fc1bf542fbbb1244e33b6ce647c4c05e4cdf1d08542c7c898c852d3f2b223,
untruncated. No WTA execution; the three attempt directories are empty.

Actual20:02:34UTC full readback exited0/stderr0, verified all440/4540 copied
members by full size/SHA/root:root0444 and original/copy archive/catalogue.
4986files/473directories,240667548logical/251936768allocated/free13323468800;
no UID65534 process. Root read full journal events init/reserve300CPU/stop-
unmeasured; no settlement/refund. Journal1751bytes/root0600,
`99f8aff214f96ac6debc056a865d7b447c5caade5310feb6e90676575cfb4c97.jsonl`
SHA2a4d4979c8570868412618a7fe1c4b65a9b81e63157f85b494474bfb0c44d3a1.
Failure125bytes SHA8dfe0443b4a40511eaf94e7dae9f5529eb5dd8347ad6661e4fe964916968ea38;
plan2098513bytes SHA8fa235a2bcf9e40f42c2ee0ddf89e219fe41eef10cf340db79d407257aa09202.
Exact raw2201988bytes SHA0ef1d803bd6399a54d5edbef81a38f5d58f2f6d3125f6d76e938ed4c35d7cf65,
versioned gzip203648bytes SHA6478294e04c8d2d4a805b4703e5f0faa905a1a86ddbe2f413b78ab23f8e3f6fc,
independently decoded/matched by Root. All three Task57 charges900CPU-s plus
Task50's270 remain retained;1170 conservative diagnostic CPU-s is not a
protected global-C/B cost certificate.

Next finding/ruling and actual native timezone source observations are in
task-57-fix5-brief.md and the ledger. Exact UTC/Zurich public data can be bound
and copied into the existing seal; no system directory allowance, fallback
package, limit relaxation or product change. A fresh round5 author is next.
