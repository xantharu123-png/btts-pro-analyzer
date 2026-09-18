# Native QA regression diagnosis and minimal correction

Spec: `docs/superpowers/specs/2026-09-07-kontextmodell-design.md`; existing native preparation/chain acceptance contracts remain binding. Trigger: complete local regression on0b529cf stopped at70% with five native-chain test failures, not a reported production failure.

## Global Constraints

- No blind repinning, reduced reserve, generalized source normalization, skipped assertion, weaker admission or changed scientific/financial gate.
- Production/native catalogues admit exact reviewed source bytes. Windows checkout representation is not automatically a new approved native release.
- Preserve current application code, historical originals, database schema, model mathematics and source clocks unless a demonstrated cause specifically requires correction and root reviews that contract change first.
- One combined fixes wave; no production, network, push, deployment or additional agents. Existing unrelated WIP and QA evidence stay intact.

### Task 1: Diagnose baseline and correct only the demonstrated QA incompatibility

Read `output/playwright/full-suite-20260918-0545f0dd.log`. Existing failures: fixed driver union reserve expected78643200, actual78651392; three manifest path flavours and timezone launcher fail independently reviewed owner pin. All in `tests/test_native_context_chain.py`. The four HELPERS/TASK54 source owners are unchanged by the current five repair commits.

1. Before edits compare exact worktree raw/LF/CRLF and Git blob bytes of every pinned owner against the closed catalogue. Identify the specific failing owner, not merely the exception text. Reproduce against prebatchf3c2b6083b8bcf78014a26302beb3afd97b8aaf9 using detached local temporary evidence without changing this checkout's HEAD. Source identity and gate values must not be changed to silence a platform fixture mismatch.
2. Derive the reserve difference independently from the actual fixed driver and owning budget/union plan. Determine source, SQLite, path-length or true contract dependence; record the exact contributing terms. An unexplained constant increase is forbidden.
3. Root is running the previously unexecuted remainder at the unchanged source revision. Until root confirms its completion, diagnosis and disposable baseline experiments only; do not edit source/tests imported by that run. Consolidate any additional related failures before one minimal fix.
4. If the issue is a test-fixture representation, repair only that fixture so it faithfully represents the existing canonical native export while still exercising actual validation and both path flavours. Preserve adversarial raw-byte/owner/alias rejection. If production admission or a frozen acceptance contract really must change, present the evidence to root before editing; do not silently loosen it.
5. TDD: demonstrate original failure then focused green for the complete affected native-chain and directly related tests. Include platform/path variants and the rejected tamper cases. No broad suite rerun; root owns coverage reconciliation. Use existing Python3.12 venv, no cache provider, DeprecationWarnings as errors and unique short temporary roots.
6. Write full diagnosis, precise patch rationale, changed contracts (ideally none), exact commands/results and ownership into `.superpowers/sdd/2026-09-18-wta-source-locator/full-suite-native-chain-fix-report.md`. Commit only owned source/tests, no push/deploy. Root owns subsequent scoped independent review and final full-coverage accounting.
