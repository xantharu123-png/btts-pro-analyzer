# Root rereview: closed environment/unit record parser

9 September 2026, frozen owning commit `7ba4c9746caf75e0dd6ab5881c8b7ed329a7e358`.
Root independently reread the original Unicode and full-backup witnesses, the
new common record decoder/callsites, owning audit and full-run addendum.

Bounded software PASS for the original P2: no Unicode pseudo-record or key
prefix can manufacture another runtime path and skip the actual database as
legacy absence. Real ASCII LF/CRLF/bare CR remain supported; ordinary Unicode
values remain data. Only ASCII Space/Tab are syntax; Unicode boundary whitespace
on the selected runtime value is rejected rather than normalized into a path.

Root rerun: **367 passed, zero skips, exactly one explicit historical SHA-pin
deselection, 38.58 s**, exit0. This is the 239 owning tests plus unchanged
original functional negative/control files and broader independent controls.
All 12 original functional negatives and six positive controls are included.

Owning worktree `.pytest_tmp/hook-root-rereview-20260909-01.xml` SHA256
`5e7bf74f0f59ad86cf5e4e0c2268a64c9e918165cf784e515c6f66e48296ee4a`.
Only `test_exact_review_freeze_and_unmodified_old_functions` was deselected:
it deliberately pins the pre-fix source hash. Neither it nor any actual failure
assertion was edited. Original report and full26 addendum are preserved alongside
this report with their exact identities.

Frozen source SHA256
`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`;
owning tests SHA256
`8e18e7e17622f357810a00211ce4e4bcf19944ce85777d39c3c37897f1fb860b`.

The Windows close-on-exit wrapper retains real SQLite queries and actual two
backup-verifier decisions; it is not Linux/DAC proof. Root/App/backup/key access,
live-source identity checks, marker recovery and the exact twelve limited-exit
codes are unchanged. No helper normalization or replacement. Actual Linux
permission/restore/installed-bridge A-to-B checks remain required before VPS
release; this local PASS does not assert them or empirical model acceptance.
