# B4/D1/D4 completion: identical native player source scope

Parent approved context-model plan and specification remain binding.
Canonical worktree: C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013.
Base will be the reviewed POINT completion plus controller-recorded revision.

## Proven defect

context_models/dataset.py resolve_case calls relevant_receipts without player
history expansion for football joint cases. build_joint_training_case includes
that expansion for football-native-player-load-v3. A genuine extra national-team
event therefore becomes an unexpected reference during detached D4 validation.
Existing v3 tests covered assembly/parity, not this owning detached boundary.

## Required bounded change

Use one exact feature-version source-scope dispatch for the owning worker,
training construction, D1 readiness and detached D4 resolution, reusing the
existing complete-pool resolver. Unknown versions must fail closed. Legacy v1/v2
keep their exact source scope, ordering and current kwargs compatibility where
needed. v3 includes the same already-observed native-player event pools everywhere.
No source fetch and no changes to whole-team collection/conflict/withdrawal rules.

This task DOES NOT change the source-scope/accounting law, caps or postdecision
proof schema. Retain the explicit later-v3-decision guard; removing it would
claim an old nonexpanded proof established national-player history. No fit,
activation, source timing or old prediction/money mutation.

## RED/GREEN and owning coverage

- Reproduce a true v3 extra-national-event case through complete detached
  resolver/evaluator ownership, not merely a mocked include_player_load argument
  or assemble_training_cases. Independent hand-checked source IDs must include
  that native national event exactly once; late/outcome/unrelated-player sources
  remain excluded by their current owner.
- Verify admitted v3 case resolves unchanged, forged added/omitted source fails,
  same-clock conflicts/withdrawals and earliest terminal proof remain unchanged.
- Verify v1/v2 do not inherit the expansion, unknown version fails, original
  4096-receipt/4MiB total source-pool and 64/128MiB physical ledgers unchanged.
- Keep existing current-source/effect signatures unchanged unless an exact
  owning source-pin transition is genuinely required; do not waive a pin failure.
- Focused tests in real SQLite/temp files; no full suite concurrently. Controller
  owns one final complete regression and the shared commit/index/publication.

No subagents, no ROOT edits, no API/VPS/backups. Use apply_patch. Python
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe -B; offline launcher
C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py. New basetemp with
existing parent, evidence under output/context-completion-20261014/football-v3.
Canonical QA env: DJANGO_SETTINGS_MODULE=siteconfig.qa_settings;
PYTHONPATH=C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013/portal.
Write full report beside this brief; return concise status/test evidence/concerns.
