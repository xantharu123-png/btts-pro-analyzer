# Task62: one complete dominant-root measurement, actual terminal PASS

This is one complete read of the fixed old QA root, not a complete retained
union, old/new speed ratio, admitted diagnostic, full C/B or release pass.
The separately reviewed Task62 unit RED/GREEN is already complete and was
not repeated. Task63 active-input WIP was not used as this scan's source.

## Exact frozen measurement

- Source revision6eb267a294244bcb6375c5045cc5231c1109d611.
- Minimal tracked archive112640B, SHA817d2ed8a7f529881537d6007c136b829267c6452182cbc923c91a465ce04e6d.
- Entry task62-native-root-measure.py SHA93272441757aa51c547a18a671c26e64e67c7a88c7d01a3d8cbfb5b6f3d593d6.
- Runner task62-native-root-measure-run.ps1 SHA1a1c4ebd44f7b4124564a72443ae0f2853b5600ee5710efa107399aa79cd70f7.
- Held stdin153789B, SHAe7ff249139bf70c5e743444c620d7862be68b5c813d5b32329a07e49346e08a9.
- DryRun9bec30 exit0; separate entry AST parse59bffe exit0.
- Independent task-62-root-measure-review.md APPROVED, no Critical/Important.
  Root read the complete review before execution. T2 remains deferred.

One invocation216f4e, session82187, actual terminal e86c3d:
SSH0 and outer0. Root env-i, Python-I-S-B; CPU60/AS2GiB/FSIZE0/core0,
alarm300 plus external GNU timeout300 with TERM/KILL5. No child, control-file
creation, admission, application/database/service/timer mutation or cleanup.
Normal read-atime effects are not a zero-kernel-metadata-change guarantee.

## Observed output

Begin2026-09-13T13:37:24Z, end13:38:23Z, PID235342.
Full root `/tmp/betboy-context-qa.9xr68INa`:

-56895 regular files,17409 directories,1932 inert symlinks.
-7599442782 logical bytes,7748403200 allocated occupied-upper-bound bytes.
-Root identity[2049,1312727,16832,36,4096,1789283748245413967,1789283748245413967].
-Complete membership SHA92cdd66bd5e1d076f709a66ada5e2f33633503bc55ef9b67a69fe82e2108e46d.
-Scan CPU47558612911ns, wall59231945633ns.
-Pre-final-output whole CPU sample47660365084ns, not the final external total.
-GNU time: exit0, wall59.41s, user35.88s, sys11.79s, RSS38328KiB.

Local logs retained under .pytest_tmp, no raw file content returned:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| task62-root-measure-6eb267a-01.stdout.jsonl |904|420b9d7d6a64f1f42be153b1b0aa991690629b639c89a518006b9b166ff1086f|
| task62-root-measure-6eb267a-01.stderr.log |65|9158050f0a7c3b3d570bf5ed384a63c5c31f01ae18e048d8cc86b0926ee27037|

Separate read-only18eae7 exit0 at13:40:22UTC confirms PID235342 absent and
root dev/inode2049:1312727, mode0700, UID/GID1000, size4096/blocks8 and
unchanged second-resolution mtime/ctime1789283748. It does not repeat the full
content scan or infer a second complete membership observation.

## Consequence, not an invented performance guarantee

The independently checked current preparation and parent each require TWO
complete retained observations inside their own cumulative CPU60 limit.
Only if costs remain equal, this one root alone twice would cost95.117225822
CPU seconds, without any other root or setup/copies/input checks. This is an
extrapolation, not a measured two-pass time or hard future lower bound.
See task-62-retained-cost-review.md for exact call sites and process bounds.

No next large run is authorized by this result. A concrete semantically
preserving optimization or explicit revised architecture/resource contract
must come first. No budget increase, history exclusion, hash reuse, deletion,
new free ticket or Task61 unchanged retry occurred. Earlier SIGKILL and costs
remain retained. The native Task63 synthetic FD acceptance can finish
independently; it cannot solve this complete-history CPU mismatch.
