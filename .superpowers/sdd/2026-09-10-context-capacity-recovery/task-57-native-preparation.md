# Task57 — actual native preparation, not a completed native run

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
