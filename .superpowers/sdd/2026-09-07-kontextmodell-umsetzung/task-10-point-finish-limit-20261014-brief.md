# Task10 final P2: optional POINT must not abort a valid large batch

Canonical .worktrees/audit-repairs-20261013, base242093f, reviewed local POINT+
football package. One implementer; parent owns index/commit/finalQA/release.
No subagents/root/API/VPS/backup/effect/approval/source acquisition.

## Actual reproduction and smallest fix

LiveWorker.finish passes every capture.pending event to point_scores_as_of,
whose bound is500. Existing collector/historical settlement have no such bound.
Reviewer actual no-DB reproduction:500finishes,501raises ContextContractError
after normal prediction writes but before finished=True/completion reporting.

Only tennis/live_context.py plus context_models/tennis_point_original.py if a
shared named500constant is needed, and new owning finish tests. Keep direct helper
strict, all native/clock/corruption rules and2048/128MiB limits. No truncation,
cap raise, uncapped batching, catch-all or false fully-collected evidence.
Oversize OPTIONAL evidence must decline NONFATALLY with explicit INTERNAL
reason/count/limit via existing progress and observable batch state; empty
point_outcomes. No customer text/numeric/quote/stake change. In-range integrity
errors and double-finish still reject; queued legitimate forecasts finish exact.

## Owning RED/GREEN

Real finish500/501 and oversized captured-backlog+queued successful legacy/public
forecast tests. Current501noDB must fail RED before fix. GREEN asserts finished,
complete progress, explicit decline metadata, no helper DB/API call/no truncated
subset/no invented scores. Spies prove absence only; valid negative corrupt
helper call propagates. Minimal existing live-worker/POINT/cache neighbors, no
giant/full suite. Offline provided pytest_final launcher/Python-B, canonical
DJANGO_SETTINGS_MODULE=siteconfig.qa_settings/PYTHONPATH=<canonical>/portal,
dedicatedTMP/TEMP/freshbasetemp; known scoped unsandboxedQA allowed if needed.

First combined sessions85970/22709 stopped by parentCtrl-C,exit1/nofinalJUnit;
do not claimPASS. New selector is byte-restored after failed45sROprobe; moved
diagnostic tests not active; do not edit it or frozen football. No baseline
tests removed/skipped. Evidence output/context-completion-20261014/point-finish-
limit, report beside brief with actualRED/GREEN/failures/source hashes/scopes.
