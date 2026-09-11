# Task7 exact native evidence — 11 September 2026

Code17cfbbc3a2786190482b001f40361bf8e7667152, independent scoped review Approved,
no new findings. Focused Windows887passed/12platformskips in511.56s; final
witness pair202passed in27.60s. These are not a native or full-suite pass.

Git archive `.pytest_tmp/capacity-task6-17cfbbc.tar.gz` (the shared reviewed
stager's existing filename convention),33823429bytes,819members, SHA
`c59e848dab8f8d8e0be3bd89dbc3a05cb85acb627447222214107919611e85ef`.
Normal SCP copied only this versioned archive into the explicitly authorized
isolated QA directory. No extra secrets, local runtime database or WIP included.

The unchanged root-stdlib stager0c0427f286169241db854cc1328c5c987d51499eeb89120479a0c1a3a63f9359
checked exact archive SHA and Git PAX commit, then created new sealed source:
`/var/lib/betboy-capacity-code-4yp86fps/source`, root:betboy0440 files/0750dirs.
Separate valid/unsafe seed fixtures are in its sibling `fixtures` directory.
No app imports as root; no change to live app/updater/services/data.

Measurement `.pytest_tmp/measure_task7_profiles.py`, SHA
`9aab3e86879c6575d3cf40b7a1ac71e17a1a8dbbc9995797db257f3b114059f2`,
is the reviewed899 profile harness with only the immutable revision pin
changed to17cfbbc (and trailing newline normalization). All source/input
path/identity/hash/count checks and actual CLI/resource/report bounds remain.

Actual-current input is the previously preserved fresh full-backup copy:
`/var/lib/betboy-live-backup-_04ttiwe/context-current.db`,253333504bytes, SHA
`ced192e70a7240606906087df08b8e82be227189f06728e7c62dfb3b186d2f05`,
99521contents/receipts,28artifacts,26snapshots,2manifests,0rollbacks.
Supervisor and actual CLI run asUID997, AS2GiB/CPU300/wall600/output1MiB,
single-thread numerical environment, no math or validation monkeypatch.
Child199986 finished FAILED:300.063CPU/300.141wall,483664KiBpeakRSS,
child-9, supervisor exit1/child_exit, no report, measured_profile_accepted=false.
Exact input SHA/metadata unchanged, no companions. This is a genuine capacity
failure, not an accepted transport limitation. No mathematical or validation
failure was observed before the resource termination, but no complete semantic
success can be inferred from that. The scoped repair's two proven local
reductions are insufficient for this actual26-snapshot profile.

Root did one exact-PID read-only ps check near completion; the child had
already exited (no rows/exit1). No process was killed by the controller, no
resource setting changed and no unrelated process/service was inspected.

Further original-only proof projection is a read-only design investigation,
not an implementation or an implicit reduction in required evidence. Existing
inventory APIs cannot prove latest native target absence/uniqueness without
decoding unrelated history; receipt-only lookup and a direct SQL shortcut
were rejected as insufficient. Any new projection needs explicit equivalent
full source/admission/lifetime checks, bounded accounting, fallback and review.

No final full17cfbbc suite, G1/G2/G3 native pass, whole-branch approval,
main push, updater exchange or application deployment is claimed here.
