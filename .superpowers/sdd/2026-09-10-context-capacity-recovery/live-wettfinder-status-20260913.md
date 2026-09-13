# Read-only production status alongside Task61

No service restart, reset-failed, manual pipeline run, product/data edit,
provider call, main push or application deployment was performed here.
This operational observation does not substitute for C/B release acceptance.

## Observed service state

Latest read-only580c22 exit0,2026-09-13T13:45:47Z: VPS HEAD2dd1116 unchanged;
actual betboy-app.service and Caddy loaded/active/running, status0. Internal
and public curl health both `ok`. Seven timers listed with future deadlines.
Wettfinder latest run13:37:12–13:43:27UTC failed, ExecMainStatus1/exit-code;
Tennis05:17:05–05:32:17UTC failed, status1. These are fresh service fields,
not a new published-artifact diagnosis. The earlier identity-mismatch artifact
below must not be blindly attributed to this newer failed run. No service,
timer, code, database, marker or credentials changed; no reset-failed.

### Earlier observations

2026-09-13T10:26:29Z, actual SSH/tool exit0, chunk6b6ecf:

- `/opt/betboy/app` HEAD2dd1116b68f3d94e9c24338c6c9dff9b01799221.
- betboy-app and Caddy active; internal/public health both `ok`.
- Known betboy-tennis.service failed; now betboy-wettfinder.service failed too.

Read-only systemd fields chunk387d71, exit0: Wettfinder ran10:07:31–10:14:03UTC,
Result=exit-code, ExecMainCode=1, ExecMainStatus=1. Its45-minute limit was not
reached. Timer was active/waiting for10:37UTC. These are timestamped observations,
not a claim that the same timer deadline or state remains current forever.

Bounded journal inspection chunk343998, exit0,10:28:48UTC returned11 redacted
messages. No traceback occurred. The actual job printed degraded,358 model
candidates,0 candidates; football status completed/context refreshed/scope51.
The marker's preceding `{previous_head,status,target_head}` JSON is the
ExecCondition `require-complete` report, NOT an automatic Git pull/deploy.
Existing deployment unit/source2dd1116 proves that distinction.

## Newest published artifact inspected after account continuation

At12:02:12UTC, read-only tool8251e2 exit0 opened only the published
`/opt/betboy/app/runtime_state/wettfinder_latest.json` through a held read FD.
Size9973860, SHAfb8e923e820b96737b89391a7515eb04682f2b67201ecff937aa1d1b52f12977;
stable held-file epoch, generated_at11:37:18.049963UTC. This is a NEWER run than
the earlier10:07 failure, not retrospective evidence for the older artifact.
No full artifact, forecasts, secrets or runtime database was transferred.

- Global run_status degraded, operational_error_count1,345 model candidates,
  0 strict candidates. Football completed, context refreshed, operational0.
- The contributing failure is forecast_evidence.settlement operational1,
  with `football:result_identity_mismatch`. Its separate
  `esports:event_budget_reached` is also reported.
- RisikoBet partial,131 candidates, operational0. Settlement reports ambiguous
  revisions/event limits/missing matching settled results, operational0.
- Tennis and E-Sport persisted-model readers report operational0; basketball
  and ice hockey still label live-only/no prematch model on this old release.
  Cricket unchanged/out of scope.

At production code2dd1116, `forecast_evidence_settlement.py` rejects a Football
result when fixture ID, scheduled instant, home ID, away ID or required identity
shape differs from the saved prediction. The published aggregate does NOT say
which field differed. A changed kickoff is possible, but not established; do
not claim that cause without event-specific read-only evidence. The pipeline
then preserves independent forecasts, writes its result and returns1 because
operational_error_count is nonzero. This is not evidence of a process crash,
missing code pull, false winning/losing bet, or permission to relax identity.

Root records this separate open triage item for later operational acceptance.
Current Task61 author remains scoped to I1-I4/T1, with no competing production
fix writer. Do not clear this observed failure solely to make systemd green.
# Fresh status at 12:48-12:49 UTC, 13 September 2026

Read-only SSH chunk `1dc041`, exit0, confirms application Git HEAD remains
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`; main was separately confirmed at
that same commit in `fc57e8`. Internal and public HTTP health returned `ok`.
All seven timers have a next scheduled run. This is not a code pull/deployment.

The actual app unit is **betboy-app.service**, not betboy.service. Separate
readback `ed1713`, exit0, confirms loaded/active/running and ExecMainStatus0.
Caddy is active/running. The mistaken betboy.service query's inactive result
is not evidence of an app outage. An earlier git query (`ba8564`) stopped on
dubious ownership before any service query; the subsequent read used only
per-command safe.directory, never changed global Git configuration.

`betboy-wettfinder.service` remains failed, actual latest execution
12:37:02-12:43:19 UTC, exit1. `betboy-tennis.service` remains failed, latest
05:17:05-05:32:17 UTC, exit1. The next Wettfinder timer was13:07 UTC at this
observation; do not present a timestamped next run as a current promise.
No failed state was cleared, no service/timer restarted, and no latest artifact
or database was modified. The earlier precise error-attribution evidence below
has not been replaced by a newly inspected artifact in this status-only check.
