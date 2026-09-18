# Consistent challenge-ledger reads — Implementation Plan

**Implementation status (19.09.): COMPLETE and independently reviewed.** Commit `5ff08a9`; 217 affected tests plus85 subtests passed, including real concurrent connections. Original steps below are historical acceptance criteria, not unfinished tasks. Money, HMAC, writer and staking contracts remain unchanged. Final integration evidence: [repair report](../../audits/2026-09-18-produktreparatur.md).

Spec: existing authenticated-ticket, append-only financial ledger and atomic placement contracts in `tests/test_challenge_integrity.py`. This is a concurrency repair, not a new financial product.

## Global Constraints

- Do not relax any HMAC, chain, definition, price, stake, release or settlement check.
- No schema, signatures, historical rows, money values, journal-mode or timeout changes. No retry that ignores an integrity failure.
- No network, production database, migration or VPS action. Use disposable SQLite fixtures only.
- Preserve existing writer transaction ownership and atomic price/ticket/money publication.

### Task 1: Authenticate one consistent read image

Files: `challenge_store.py`, `tests/test_challenge_integrity.py` and only exact adjacent ledger tests if required.

- [ ] Diagnose the observed `test_concurrent_ticket_attempts_commit_one_atomic_price_and_ticket` intermittent failure. The precheck currently performs multiple SELECTs without an explicit read transaction; identify exact public read owners sharing that problem.
- [ ] RED: deterministic two-connection barrier/event fixture commits a valid concurrent ledger transaction between authentication subreads. Prove the old reader sees inconsistent revisions; do not rely on repeated probabilistic loops or sleep timing. Real rows and signed state, not a mocked successful verifier.
- [ ] Establish an explicit consistent read transaction around the complete public read/precheck operation, including its returned settings/tickets/counts. Use a small owning helper only if it removes repetition; do not start a transaction inside an already active writer. Release read locks before preparing price evidence or acquiring the placement writer.
- [ ] Keep the existing second full authentication and all gates inside BEGIN IMMEDIATE unchanged. A writer winning after a valid precheck must still cause the expected business rejection, never double-placement. Old corrupt state must still fail closed.
- [ ] Cover read owners reached by the same financial verification: settings, ticket(s)/count, transactions and verification entry points; inspect their exact transaction ownership before changing. Do not refactor unrelated money logic.
- [ ] Test deterministic overlap, unchanged two-ticket atomic winner/rejection, rollback and tamper failures. Run only affected financial suites; root owns broad suite.
- [ ] Self-review, report commands and RED/GREEN evidence, scoped commit after root grants the index slot. No push.
