# Task63: actual synthetic native FD acceptance

Source bb54ec58eadcab0e9c0ae065aa258cb7a8f337d6, not a full C/B or release pass.
Only the three Task63 source/test/report files changed in that source commit.
Task62 walker, parent, worker, guard, supervisor and budget bytes are unchanged.

## Frozen local and independent evidence

Root read the complete454-line test and complete report, and the active-input
implementation. Final local XML freshly read3ba30b:43cases/0errors/0failures/
16native skips, SHA65f12e24226368d292283dab5fa7ed94d385d18c7fd6bb19ee708ca51197f76c.
The final author command reports27passed/16skipped/45deselected; this includes
seven adjacent cases, whereas the single new module has36cases.

Independent task-63-review.md SHAa2ad76853c512dffa516c84ffce1a433c225a608e28d49e915a4b61b3c3e0183:
implementation compliant/approved, no Critical/Important. Full package
task-63-review-01.diff SHAdf1c76bb35661a5335a03a36fb19cebdad4bb905a69b78764ad7d8700c6827c2.
Root read the whole review before native execution. No extra implementation
fix was made by Root. T2/M1 and full-input/native-capacity gates remain separate.

Root's final diff check7e3361 returned2 for an extra blank line at the end of
the exact already-reviewed/executed task63-native-unit-run.ps1 (line59).
Those frozen transport bytes and the preserved unified review diff are kept
unchanged for hash provenance, not described as whitespace-clean. All other
new source/controller documents are checked separately before commit.

## One fixed native invocation

- Archive task63-unit-bb54ec5-01.tar143360B, SHA6d93ed7db2d1fb29167deceda86e4910f0fe99f951a2dfc3cf0f421f89d4ea10.
- Entry task63-native-unit-entry.py SHAbb0e4a79d89a8266d45db81032fcb67f0c1139a75d3396944c36d78546015257.
- Runner task63-native-unit-run.ps1 SHA0248ac7ef842e3c39afdb07fb4796fcc7d2cbf73e1b7ecf7db66622b1d60378f.
- Payload196919B, SHAb755022191075ff2b290007ec5691e11613e0ea0d1d66b3efee9a64442f2369c.
- DryRun287c1e and syntax e3fea9 both exit0.
- Separate transport review6cd43c002944dbc3f60c625be12b3beafef9628f721230d7a6ceb0e0dab27319 approved; fully read by Root.

Actual2c543f exit0, SSH0, child0 at2026-09-13T13:44:56Z:
**35 passed,1 skipped in2.81s**,36cases,0failures/0errors. Exact sole skip
`test_portable_sample_marks_native_descriptor_validation_absent` was asserted
by the pinned entry; every required Linux case executed. Child stderr empty.
Initial/final controller NOFILE1024/1048576. Tests separately establish actual
old1024EMFILE/no-leak, new1100-held-file reservation/fresh hashes/unwind and
inherited-NOFILE closure at the unchanged supervisor's real close boundary.
That boundary is not a full root UID-drop/guard/SIGSTOP/receipt-worker test.

GNU time: exit0, wall3.28s, user2.69s, sys0.46s, RSS40976KiB. Controller CPU
0.073074575s, children3.084716s. CPU60 is a per-process test limit, not an
invented60CPU aggregate owner; actual engineering cost is retained here.
Ordinary UID1000 only; CPU60/AS2GiB/FSIZE64MiB/core0, childtimeout75 and outer
timeout90TERM/KILL5. No retained scan, admission, product import in Root,
live DB, service/timer/application change, cleanup or unchanged retry.

## Separate actual readback

580c22 exit0 at13:45:47UTC:
`/tmp/betboy-context-descriptors-task63-bb54ec5-01` dev2049/inode6526,
UID/GID1000, mode0700. du14245888B allocated (du's hardlink accounting, not a
complete retained per-path inventory). No ordinary-UID Python/pytest/time/
timeout process listed. All four source members, archive and output hashes
match their frozen or actual terminal values:

| Artifact | SHA256 |
| --- | --- |
| tests/test_native_context_active_descriptors.py | aeb378e3bf9bb79fdb8793ba382780724a7cc116c9eb682bb67c67c2cac6e69c |
| tests/native_context_receipt_diagnostic_catalogue.py | 69a7300536b81d78c38fd6a7d4701f451b1d1468f546ba892908896311dc7f7b |
| tests/native_context_chain_catalogue.py | 48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935 |
| context_preparation_supervisor.py | c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8 |
| result.xml (6123B) | a817690bb4ed9a43bce82fb29c75a287fc1d117570a2debdf48ba2319ac4f494 |
| result.json | 8330227a29f89d04362b6660a3a211a4013ff8711035f9b3bc9d2b6d0324765a |
| stdout.log (110B) | 0fd0fef426c2a12fc5755b0649d8303ff9ae817220a09fb78b5e733fed8920b9 |
| stderr.log (0B) | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |

Local raw evidence retained in .pytest_tmp:
task63-native-unit-bb54ec5-01.stdout.jsonl993B/SHA5a2f470afb73b2dac47e2b3b66557173d73cd489d0c3e1722cf9812298290d8e;
task63-native-unit-bb54ec5-01.stderr.log62B/SHA4681116c9a6ff64386f246ac75e2fbefa11c4d4035cdf25d53750128fbdc6d85.

The synthetic descriptor gate is now closed; the actual full input set and
four mandatory complete historical scans are not. No Task61 admission or
worker started. The larger architectural/resource decision is explicit in
task-62-retained-cost-review.md; do not turn this successful small test into
a fresh300CPU credit, full capacity, B, restore, main or VPS deployment pass.
