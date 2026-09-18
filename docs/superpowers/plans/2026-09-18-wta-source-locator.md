# Repair the published Tennis-Data season locator

Spec: `docs/superpowers/specs/2026-09-07-kontextmodell-design.md` (independent current-tour refresh; existing odds-blind boundary).
Execution: existing approved worktree; subagent-driven development.

## Global Constraints

- Preserve ATP/WTA separation, genuine refresh failures, cache-only defaults, atomic publication and coverage-regression guards.
- No bookmaker data enters model features. No odds, model coefficients, dates, validation gates or stored probabilities change in this patch.
- No TLS bypass, provider credentials, new paid calls or broad retries.
- A successful current-source fetch is not empirical injury/fatigue validation.

### Task 1: Restore the source's actual HTTPS file location

Files: `tennis/data_loader.py`, `tests/test_tennis_training_refresh.py`; other focused loader tests only if necessary.

1. Read `output/playwright/tennis-data-coverage-20260918.md`. The old Tennis-Data base and all equivalent old URLs return 404; the upstream download page `https://tennis-data.co.uk/data.php` publishes the year files under `https://tennis-data.co.uk/hrjk-85HytOjkhth76j_ygh4jf7`. This is a locator repair, not a parser change. The current WTA file passed all existing validators in memory.
2. TDD: add an independent literal expected URL test (not an expectation interpolated from the production constant) for both ATP and WTA. Simulate 404 for the old URL and a valid XLSX for the published URL. Run RED before the fix.
3. Set `TENNIS_DATA_BASE = "https://tennis-data.co.uk/hrjk-85HytOjkhth76j_ygh4jf7"`. Correct stale top-level documentation about HTTP and the WTA filename/directory scheme. Retain the current suffixed WTA directory and all existing validation/cache behavior.
4. GREEN: run all training-refresh, WTA loader, model isolation and tour-state tests that cover this loader. Confirm default cached loads do not fetch; errors/regression do not replace prior good bytes. Do not change tests to accept diminished coverage.
5. Run one isolated real WTA current-year loader refresh using an empty temporary cache under ignored `output/playwright`, HTTPS, normal certificate verification. Record actual returned row count, latest result date, final source URL and file SHA; the prior observed 2075 / 2026-09-12 is a comparison, not a fabricated assertion if the source advanced. Do not replace production or packaged caches or publish models. No automated training or VPS action belongs to this task.
6. Self-review and commit only this task's source/tests. No push or deploy. Report exact RED/GREEN commands/results, isolated GET outcome, files and the remaining risk that the upstream opaque prefix can move again. Do not add a generalized scraper/resolver or duration feature in this focused patch.

### Task 2: Preserve exact historical replay for the reviewed locator-only change

Files: `context_runtime_tennis.py`, `tests/test_context_runtime_tennis_live.py` and narrowly related tests if needed. Task 1 is finished; do not redo the loader or download.

1. Read `output/playwright/tennis-replay-locator-compatibility-20260918.md`. The owning original records six source-byte hashes, including the data loader. Its historical pre-locator hash is no longer accepted by `_code_variants`, even though the reviewed change alters only the source URL and documentation, not prediction-time name resolution. Establish behavioral RED with a stored original containing the actual old loader hash; exercise both original-only and original-plus-snapshot verification.
2. Add explicit, closed compatibility for this single reviewed transition only. Derive and document the exact LF/CRLF source manifests for all six code files from commits `185812e0846c7821a46673c9267abfe838d89f4b` and `b342b02ac9c52b559152d7dd91d08c049e131611`. Historical hashes are admissible only when the entire running normalized source manifest matches the reviewed new version and the recorded original matches the reviewed old manifest (existing LF/CRLF variants allowed). Keep all actual state/native inputs, unrounded model recalculation and snapshot verification unchanged. Do not accept arbitrary prior hashes or mixed unreviewed manifests, use runtime Git, AST normalization, fuzzy source matching, or skip replay. Unknown future source edits must not inherit this support automatically.
3. Preserve every stored original/hash/clock and probability. No database rewrite, source request, training call, model publication or effect activation. Runtime hashing supports the existing LF/CRLF equivalence only; future source changes require explicit review again.
4. Tests must cover actual historical LF and CRLF hashes with/without snapshots; current version unchanged; unknown loader digest rejected; other model-source digest changes rejected; a current loader whose source no longer matches the pinned reviewed version cannot grant old-hash compatibility. Prove replay does not call downloader or training. Keep failures read-only and exact existing corruption tests intact.
5. Run targeted RED/GREEN then the runtime Tennis live/history, original identity, consumer, state and training suites once. Record full commands and outputs. Self-review and commit only owned source/tests. No push/deploy. Report this as historical recipe compatibility for a locator change, never proof of source completeness, model quality or a successful production day.

Use existing venv `C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe`, pytest `-B -m pytest -q -W error::DeprecationWarning -p no:cacheprovider` with a unique basetemp. Existing worktree `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910` needs Git `-c safe.directory` of the same path. Apply_patch for source/report edits; escalated native `codex --codex-run-as-apply-patch` fallback is available if the normal Windows sandbox ACL helper fails. Do not spawn subagents.
