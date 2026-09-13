# Task61 actual Linux prefix checks — 13 September 2026

Both native protocol categories passed, not the full-baseline receipt run,
full C/B, restore or deployment. No unchanged Task58 run was repeated.

Reviewed code1632072; scoped I1-I4/T1 review4f9eb5eadb5647f159e4155568f8a4329053bf45d46b1113c11a250035a70310.
Root changed only reviewed source/template hash literals afterwards, committed
52d34bbf3b5816b1cbb3d44f44610dc1dc7d0b88. Entry8a12928c139ad006491335dd2d272e7225c1bb3a13484d3a4d95ba0085cc9e76;
runnerfd7a6ab0c8df60dcf648a19fa925417619fb5d53ee214bc5007176821bb673a5.
Every fresh coordinator used sudo env-i PATH/LANG, Python-I-S-B and GNU time.
All392417-byte stdin hashes matched their prior local dry run.

| Mode | Actual UTC | Tool chunk | SSH/outer | Child | GNU time wall/user/sys/RSS KiB |
| --- | --- | --- | --- | --- | --- |
| prepare |12:17:56|4d2b84|0/0|none|0.29/0.12/0.02/24468|
| success |12:18:38|5d3a6c|0/0|0|0.44/0.19/0.04/24720|
| failure |12:18:58|03aeca|0/0|125|0.39/0.15/0.03/24724|

Success: actual parent233699 hardCPU[60,60], child233700 UID/GID65534,
readbackCPU240/FSIZE536870912/one seccomp filter; actual fixed probe guard
assertions passed. Child CPU20851000ns, elapsed68141679ns, peak20799488B,
no stop reason. The only owner cleanup PID was the parent, actually observed
through the inherited pipe, not an invented cleanup flag.

Failure: parent233775 hardCPU[60,60], actual child exit125 before SIGSTOP,
kernel_readback null and expected stop_reason launch_unverified. Child
CPU2263000ns, elapsed53434482ns, peak17784832B, no output. Only parent233775
wrote owner cleanup. This is a successful negative protocol test, not a
successfully guarded worker or a full receipt run. The early-failure result
does not include a child PID; no exact early-child PID is guessed.

Actual separate post-exit readback12:19:59UTC chunk011416 exit0 observed no
UID65534 process or recorded coordinator/success-child PID. Exact root and
three descendants remain, same inodes2177130–2177133, total16384allocatedB:
root0755 root:root; probe.py0444 root:root1203B; success/failure0700
65534:65534, both empty. ProbeSHA5818c8a838e817651c6bd0e9e76158df4f029eb0bb2bc6d5d74de1d189fa37be.
No artifact removed or old permissions changed. A prior readback attempt
714f46 failed only in the local PowerShell parser; no remote command ran.

All exact logs remain `.pytest_tmp/task61-native-prefix-MODE-01.*`:

| Mode | stdout bytes/SHA256 | stderr bytes/SHA256 |
| --- | --- | --- |
|prepare|836/64790dba3802d173bbc92ba17ec28999cb4288c69d0fbe336222f9f1d38df290|64/16a73f084a13aa4e56bc5cd7b56c6a54844d07b44c56f5d163401ff069e5a670|
|success|1307/748f363d5237a528615e778b7d2f45e2a22c3d4f066661d10fbb1b6eefa91129|64/7cd2d43f051f2bd65d8fc71c58e29d9f8628e428b375f3378772c2379901d9e6|
|failure|1048/ab84847490a091b3b7b35678b0db796e13432841e5be7f974ecc684886152d2c|64/e891ac822fbcc9417eefe0972e3ade07ff617e14fd8e3cf81f174d5cb23b33eb|

Stderr contains only the expected GNU-time line. No underlying probe stderr.
These separate protocol coordinators have60CPU limits and reported full
process CPU129199615/201888865/172397593ns, respectively. They do not have a
new durable full-C preparation ticket; do not invent one or credit/refund their
cost against retained diagnostic history. Include their exact new root in the
next complete retained inventory and their observed cost in engineering evidence.
The actual one-shot300CPU receipt admission is still unconsumed/unexecuted.

Root external terminal observation closes these two native protocol categories
only. Original result native_pass=false stays unchanged. Full retained/source/
allocation/100553+1024 diagnostic, full490000growth, global1800/3600, C/B and
restore/release remain open. No main push/VPS application pull/deploy occurred.
