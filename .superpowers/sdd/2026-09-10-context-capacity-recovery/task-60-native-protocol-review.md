# Task60 native protocol instrument review

Verdict: APPROVED for this isolated operator-only native test instrument.

Reviewed the complete `evidence/task60-native-admission-protocol.py`, SHA256
`b73951134de6d0ffd06d2a9e3ebd0a8501864eb52953d9be857d98e7930132b1`.
This is not a new review of the frozen Task60 implementation and is not evidence
that the instrument has run successfully. No tests or native commands were run.

## Findings

Critical: none. Important: none. Minor: none.

## Evidence and scope

- The required launch is checked: actual Linux real/effective root UID and GID,
  exact two-variable environment, isolated/no-site/non-optimized Python and
  disabled bytecode. Fixed 15CPU/30-second alarm, 512MiB address-space, 1MiB
  file-size and zero-core bounds are installed before bundle execution.
- Only two digest-pinned, individually bounded source byte strings are executed.
  The actual reviewed budget occupies its required module name; admission runs
  in an unregistered held namespace. No product, venv or secret import is added.
- The fixed `/var/lib/betboy-admission-task60-protocol-8574747-01` root must be
  fresh: `mkdir` refuses an existing path. Every existing ancestor is checked by
  `lstat` for directory type, root ownership and non-writability by group/others.
  All new fixtures remain inside that root and no cleanup or overwrite is used.
  The deliberately writable negative ancestor remains beneath the private root.
- Positive admission uses the public native API, an actual BudgetIdentity and
  actual kernel clock/process checks, with no portable adapter or clock patch.
  The returned owner is asserted live, its full 300CPU ticket and current PID
  are checked, and contention must raise the specific lock-contention error
  without changing captured registry identities, sizes or hashes.
- Successful public close and same-family rejection are exercised. The reviewed
  owner's close implementation supplies stopped-head/retained-charge durability
  assertions; this instrument does not substitute a fabricated stopped result.
  A second same-family call must be rejected without retained-file mutation.
- Symlink registry and writable-ancestor calls must raise AdmissionError while
  their target registries stay empty. A separate real admission then has its
  exact private registry FD unlocked with actual flock. Its public live check
  must report lost custody, close must fail, and a different-family retry must
  fail without changing the retained poisoned-registry capture.
- File captures use no-follow FDs and check private single-link regular files,
  bounded reads, inode identity and stable metadata. Successful output is a
  fixed-schema observation bounded to 64KiB. Unexpected exceptions/assertion
  failures terminate execution rather than being converted to success.
- `actual_exit_observed_externally` and `native_driver_pass` remain false in the
  observation. The fixed 600CPU field describes the two synthetic full tickets;
  it is not a measured CPU result, settlement, refund or real-baseline authority.

## Remaining gates

Root must substitute only BUNDLE_BASE64 with the pinned bytes, use the declared
clean isolated launch, preserve all newly created evidence, and observe the
actual external exit and bounded stdout/stderr. Native root/DAC/flock/fsync
success is not verified until that run completes and its observations are
checked. The real diagnostic's complete plan/history/baseline binding, parent
60CPU and worker240CPU enforcement, other resource/source controls, and all
C/B/empirical/release gates remain separate and incomplete.

No implementation/source/Git/server changes, dependency inspection, native run,
suite repetition or subagent dispatch were performed during this review.
