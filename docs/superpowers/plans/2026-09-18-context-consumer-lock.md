# Context consumer transaction lifetime repair

> Execution: existing approved isolated worktree; subagent-driven development.

Spec: `docs/superpowers/specs/2026-09-07-kontextmodell-design.md`.
Scope: corrective subset of the approved context-model work, not a new model contract.
Baseline: `f3c2b6083b8bcf78014a26302beb3afd97b8aaf9`.

## Global Constraints

- Read one consistent revision, without changing probabilities, rounding, market order, quote rules, schemas, source clocks or approval gates.
- A consumer never creates a database, writes, calls a provider, retrains or republishes.
- Missing legacy metadata remains optional; present malformed metadata fails explicitly.
- Preserve all path, companion, schema, digest, original/state identity and timestamp checks.
- Do not change SQLite journal mode, busy timeout or production services in this task.
- Cricket, monetary state, production databases and existing untracked work are outside this patch.
- This patch removes CPU-held consumer read locks; it does not claim to eliminate every possible database contention source or prove improved betting quality.

### Task 1: Detach immutable consumer inputs before CPU validation

Files: `model_artifacts.py`, `context_consumers.py`, `tennis/context_consumer.py`; focused tests in `tests/test_context_consumer_concurrency.py` plus existing consumer tests as needed.

1. First add real-SQLite regression tests that fail on the current code. During the actual generic/Tennis decode or projection seam, append an actual observation batch through `append_observation_batch` on a second connection. Assert commit and receipt content, not merely mocked invocation. Use existing valid consumer fixtures; do not use arbitrary sleeps. Demonstrate the current held reader prevents this write.
2. Factor a pure `_decode_artifact_row(digest, row)` from `_load_artifact` in `model_artifacts.py`. The row is the existing `(kind, payload, created_at)` tuple. Preserve missing-row, canonical object, kind, timestamp and envelope digest validation exactly. The regular database loader delegates to it; no duplicated validation and no fake SQL facade.
3. In `context_consumers.py`, freeze raw snapshot tuple, `freeze_reference_bytes` and any explicitly requested raw artifact rows inside one trusted `_reader` transaction. Validate table schemas while connected. Exit `_reader`, including its final path/companion checks, before snapshot/artifact decoding, semantic validation and projection. Replace the private context-manager seam if useful; only generic and Tennis consumers use it.
4. Tennis already knows the original artifact hash from its validated sidecar. Validate `context.model_inputs.model_artifact_hash` before use and request this state row in the same frozen packet. After decoding require it to equal the original base model hash. Validate both detached artifacts with the shared decoder, enforce exact kind and publication cutoffs, and retain all existing sidecar/origin/state/row checks. Preserve both full-precision winner probabilities and public summaries.
5. Prove one-snapshot coherence even when a writer changes data after physical freezing: the in-flight result must use one old coherent packet, and a following read must detect relevant corruption or use the new coherent revision. Preserve final path-replacement failures before any result can escape. Retain compact reference-block coverage and exact schema checks.
6. Run focused new tests RED then GREEN, then the complete affected suite once: model artifacts, reader trust, consumer schema, generic consumers, Tennis shared consumer, context snapshot storage and transport tests. Locate exact filenames with `rg --files tests`. Run Python with `-B -m pytest -q -W error::DeprecationWarning -p no:cacheprovider`, a unique basetemp, and existing venv `C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe`. Do not repin historical QA hashes merely to silence tests.
7. Self-review, then commit only owned code and tests. Do not include this controller-owned plan or unrelated WIP. Do not push or deploy. Write a detailed task report with exact commands/results, RED evidence, changed files and limitations.

Implementation environment: `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`; Git requires `-c safe.directory=C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`. Use apply_patch for edits. If its normal sandbox helper fails, the existing native fallback is PowerShell here-string passed to `& (Get-Command codex).Source --codex-run-as-apply-patch $taskPatch` through an escalated exec. No broad cleanup, no subagents from the implementer.

Evidence: `output/playwright/context-lock-rootcause-20260918.md` reproduces failure at bootstrap commit and, independently, actual batch commit when bootstrap is bypassed; after the real consumer closes the same batch succeeds. Production lockholder PID was not captured. Other CPU-held inventory readers and long physical spools remain separate follow-up work.
