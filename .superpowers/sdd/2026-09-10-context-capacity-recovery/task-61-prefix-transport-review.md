# Task61 prefix-only Root transport review

## Verdict

**Transport quality: Needs fixes.** One Important held-template execution defect was found. The fixed prefix-only scope and normal terminal-output route otherwise match the requested instrument. This verdict does not approve Task61, resolve I1-I4, authorize native execution, or clear any C/B/full-job/release gate.

**Scope and evidence:** read only `evidence/task61-native-prefix-entry.py` and `evidence/task61-native-prefix-run.ps1`, using the previously reviewed frozen native-prefix API/probe as context. No Task61 WIP/source was reopened, no tests/syntax checks/DryRun/network/native/Git commands were run, and no subagents were dispatched. Root reports syntax-only and prepare-DryRun success; those were not repeated. Only this report was written.

Reviewed instrument SHA256s:

- `evidence/task61-native-prefix-entry.py`: `5e1bd97571eaf3c306e304aff4d339a880fcdb69a1baf1f06501a502e640f868`.
- `evidence/task61-native-prefix-run.ps1`: `5092e75c4da1255f6d666e83b8cc88c21d0c594fddfcf9d482b89c1fdd990f40`.

The observed entry hash matches the current runner's literal template pin. Both scripts still name the reviewed fec316f parent/catalogue bytes. Root must repin both source mappings, any changed probe identity, and the entry-template hash after I1-I4 fixes/final Task61 approval; current pin mismatch must stop the runner, not trigger automatic regeneration or fallback.

## Strengths and checked boundaries

- **Fixed modes, host and paths:** runner `:1-16,34-47` accepts only prepare/success/failure, uses fixed workspace/source names, fixed new output paths and fixed `betboy-vps` remote command. ArgumentList and base64 replacement introduce no arbitrary remote shell argument or code-source selector.
- **Held member bytes:** runner `:18-23` reads each of exactly seven source members into bytes, checks that same byte array's pinned SHA256, then base64-encodes it. Entry `:22-38` independently enforces exact member set, each member's bounded size/hash, and compiles the held parent bytes. This part does not hash then reopen source files.
- **No receipt diagnostic launch:** entry `:36-38` sets a non-main namespace before compiling the parent, so its `if __name__ == '__main__'` guard cannot call `main`. Prepare invokes only startup/catalogue/probe-writing helpers (`:40-75`); success/failure invoke only `native_prefix_test` at `:78`. There is no normal worker/profile/main selector in this transport.
- **Fresh root stdlib coordinator:** runner `:46-47` uses fixed `sudo -n env -i PATH=/usr/bin:/bin LANG=C.UTF-8`, `/usr/bin/time`, and `/usr/bin/python3 -I -S -B -`; entry `:2-19` installs CPU60/AS2GiB/FSIZE512MiB/CORE0 and checks actual Linux root UID/GID, isolated/no-site/no-bytecode/assertion flags and exact environment. Only stdlib and the pinned reviewed namespaces are loaded. No root pytest/venv launch is introduced.
- **New-path-only preparation:** entry `:39-67` requires the exact `/var/lib/betboy-receipt-prefix-task61-01`, checks the protected searchable ancestor, uses refusing `mkdir` for the new base and both fixed subdirectories, and uses the reviewed O_EXCL writer for the root-sealed probe. Probe length1203/SHA `5818c8a838e817651c6bd0e9e76158df4f029eb0bb2bc6d5d74de1d189fa37be` are checked at `:46-47`. Only new success/failure directories are chowned to UID/GID65534; no existing namespace is chmodded, cleaned, reused or deleted. Partial preparation remains retained and a retry will refuse the existing root.
- **Separate fresh test calls:** a success or failure invocation creates a separate SSH/root interpreter. Entry `:76-78` calls the fixed previously reviewed probe API, not the 1024-row diagnostic. The wrong-parent-PID negative case and actual prefix/guard/SIGSTOP/readback/reap remain owned by that API, not recreated by this wrapper.
- **Normal terminal transport:** runner `:36-38` opens stdout/stderr artifacts with CreateNew; `:49-65` drains both channels concurrently, waits for the actual SSH process and stream completion, and flushes retained files to disk. `:68-73` reports actual SSH exit, complete retained outputs, sizes and hashes, then returns that exit. `/usr/bin/time` contributes a separate terminal exit/wall/user/sys/RSS line. Its expected line on stderr is intentional transport instrumentation, not a claim that the underlying probe had stderr noise.
- **No custody-killing wall timeout:** only the prepare branch installs a 30-second alarm, before any child can exist (`entry:40-42`). Probe branches have no additional alarm or process-kill loop (`entry:76-78`, runner `:55-60`), so this wrapper does not replace the reviewed UnreapedChild stopped-operator custody path with automatic termination/retry. All output explicitly denies full-C/production-change status (`entry:79-84`); inherited probe result remains `native_pass=false`.

## Findings

### Critical

- None identified within these two files.

### Important

**T1 — Template execution is hash-then-reopen, not held-byte execution.**

- **Location:** `evidence/task61-native-prefix-run.ps1:8` and `:25-28`.
- **Defect:** Get-FileHash validates one read of the entry template, then the runner reads the template again with Get-Content after gathering the source bundle. Replacements and the transmitted root program use the second read without comparing its bytes to the pinned template hash. An intervening replacement/edit therefore bypasses the advertised reviewed-template pin while the seven bundled source pins can all remain correct.
- **Impact:** the gap is in privileged executed coordinator code, not merely metadata. Logging the generated stdin hash at `:30-31` identifies whichever bytes were generated; it does not compare them to the reviewed template or make the earlier check bind the second read.
- **Fix:** read the template into one bounded byte array, hash that held array against the literal pin, decode that same array with an explicit strict encoding, and perform all placeholder replacements from that held string. Do not reopen the template for execution. Keep exact placeholder counts and the final stdin byte cap/hash. Repin the resulting reviewed instrument normally; do not relax source/template mismatches.
- **Verification:** static control/data flow in these two files is sufficient to establish this defect. No mutation/race experiment or native run was needed.

### Minor / defensive hardening

**T2 — Local transport logs lack explicit byte bounds.**

- **Location:** `evidence/task61-native-prefix-run.ps1:49-50,69-70`; entry's expected JSON cap is at `:83-84`.
- **Observation:** native success JSON is explicitly limited to65536 bytes and the fixed probe has small output, but generic SSH stdout/stderr are copied to local files with unrestricted CopyToAsync, then each entire file is read into the final output. SSH/time/interpreter failure diagnostics are outside the successful JSON assertion.
- **Recommendation:** impose explicit separate retained-log caps and maintain total observed counts/hashes plus truncation labels. Continue draining channels safely after a retained cap instead of terminating a possible custodian. Read back only a bounded retained prefix. This is defensive transport hardening, not evidence that the reviewed fixed probe currently emits excessive output.

## Cannot-verify items / Root operation gates

- **Actual environment and capability:** no native UID/capability/initial-user-namespace assertion, parent60 preservation, child240 raise, actual guard/SIGSTOP/readback or actual terminal reap was observed here. Syntax/DryRun cannot prove them.
- **External custody:** SSH keepalive failure/disconnection (`runner:47`), hardCPU kill, operator cancellation, host death, or failed output I/O cannot be treated as child cleanup/reaping. This instrument contains no parent-death recovery guarantee and must not acquire one by wording. A nonzero/missing terminal result requires separate Root process/PID/pidfd/native evidence, with no automatic retry or deletion.
- **Exceptional API return:** entry `:78-85` emits its result only when the reviewed native_prefix_test returns. If that API raises or remains operator-stopped, there will not necessarily be a complete result JSON; available stderr/transport exit alone does not establish all NativeRunResult fields or absence of a child. The prior frozen API is context, not a newly verified/fixed implementation in this transport review. Root must retain and inspect the actual exceptional terminal/custody evidence before drawing a conclusion.
- **Terminal status meaning:** the expected failure probe may have child exit125 while the successful test coordinator/SSH exit0. Root must read the result's child exit/readback/mode alongside `/usr/bin/time` and SSH terminal statuses; SSH0 alone is not native success. Stream/I/O exceptions must remain failures, even if partial files exist.
- **Preparation and accounting:** the exact new root, owner/mode/allocation records and fsync success are only future observations; no directory was created here. Include the prefix preparation/test controls and retained logs in the appropriate complete new-job/historical accounting. These protocol probes are not the admitted1024 diagnostic and do not confer new full-C lifecycle credit.
- **Repinning and approvals:** T1 must be fixed and reviewed; post-I1-I4 source/probe/template pins must be refreshed from approved frozen code before any execution. Task61 I1-I4 remain open independently. Full baseline1024, full490000 growth, complete retained inventory, global1800/3600 proof, C/B, Source/D2, backup/restore and release remain wholly outside this transport review.

## Assessment

**Needs fixes for T1.** The intended prefix-only scope, new-path preparation and normal dual-channel terminal capture are well constrained. The template's hash-then-reopen seam prevents approval of the actual privileged bytes sent by this runner until it uses one held checked read. No native execution approval follows from this report.
