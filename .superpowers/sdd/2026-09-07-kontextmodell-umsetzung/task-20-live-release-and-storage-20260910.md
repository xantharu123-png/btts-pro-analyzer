# Actual ordered release and post-data checks — 10 September 2026

This records executed deployment and live observations, not completion of all
20 context tasks or empirical approval of injury/load effects. Times below are
UTC unless explicitly CEST. Existing failed probes and inherited output remain
unchanged. No tickets, bankrolls, settlements or historical model rows were
rewritten. Cricket was not extended.

## Ordered A then B deployment — completed

Previous main and actual VPS: `2ba3931dd8cb35f31d2475ae5797d75b44be268e`.
The reviewed bridge `655e7a6e430a776b0dcb291daded00399b5b8328` was first
pushed to main and installed ONLY through the existing
`/usr/local/sbin/betboy-update <40sha>` entrypoint. The old updater exited0.
Its fresh preupdate backup was
`/var/backups/betboy-update/betboy-preupdate-20260910T095126Z-2ba3931dd8cb.zip`,
87 databases verified. The normal post-A backup was
`/var/backups/betboy/betboy-sqlite-20260910T095206Z.zip`, also87.

Before publishing B, the actual A checkout and installed updater were checked.
The installed updater was root:root0755, one link, SHA256
`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
Only then was final B `2dd1116b68f3d94e9c24338c6c9dff9b01799221`
pushed to main and passed to the installed updater. That execution also exited0.
Fresh B preupdate backup:
`/var/backups/betboy-update/betboy-preupdate-20260910T095428Z-655e7a6e430a.zip`,
87 databases verified. Post-B normal backup:
`/var/backups/betboy/betboy-sqlite-20260910T095513Z.zip`,87 databases.

The first B continuity result was `not_present_legacy`; no context database
existed before this first installation. This was valid for that transition,
not proof that a later context-bearing database fits the verifier.
Local feature, saved local main, freshly read GitHub main and actual VPS were
all verified at2dd1116. Saved main was fast-forwarded without removing old
untracked outputs. Server tracked diff was empty.

App/Caddy and seven timers were active and app/timers enabled. Local/public
health endpoints returned `ok`. Startup retries briefly saw connection refused
before the final successful health check. The existing Caddy formatting warning
remained, with valid configuration. Timers run calculations, NOT git deployment.
Installed updater SHA remained74b1c4b1. Server UI SHA256
`9447488dd3874946e46087ad33fed8525372226099386644a5e8d85650c2a88b`;
runtime resolver SHA256
`710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c`.
Protected stage helper stayed
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

## Verification covered by this release

Fresh LF QA286601b ran6552passed,20Windows-skips,97subtests, exit0,
1279.19s. The complete286601b→2dd1116 diff contains only five documentation
files. XML SHA9dd05fc2e22879c8d8367bb83e5cb6e92183e8621aba91f0f99201a545610237.
The missing-parent first launch and subsequent successful test execution are
qualified separately in the owning run notes. Later P4b3/A0 packets are NOT
covered by this full run or deployed here.

Actual public browser was opened after B, not a synthetic local fixture:

- Normal Finder:60 unique event/market/selection cards across three fully
  rendered pages (3top plus57 additional). Eight games had a result-market
  selection, each only one result choice; no home/away/draw opposites for those
  games across all60 cards. This does not prove all cross-market compatibility
  or useful betting quality. Initial stale page2 DOM was reacquired after the
  completed pagination render before counting.
- The normal cards show a direct explanation paragraph. No old nested
  `Analyse anzeigen` is required to read it. Missing detailed E-Sport model
  foundations are stated rather than invented.
- Actual fresh manual-price popover showed bankroll100.00, empty quote and
  unconfirmed matching checkbox. No price submission, bet/save or money write
  was performed on production. Earlier two-card input isolation acceptance is
  from the separately recorded local browser test, not this public read-only run.
- Normal1440/320px: document client width equals scroll width. Risk1440/761/
  760/320px: same. Risk had48scenarios from31events, explicitly partial data;
  Pro/Contra and observed context visible.23cards on its displayed page.
- Production browser error/warning logs were empty. Desktop and mobile
  screenshots were actually viewed inline, not saved as invented artifact paths.
  The viewport override was reset afterwards. Risk desktop radio navigation
  was executed; a mobile-footer locator attempt did not match and is NOT fresh
  production proof of mobile-footer interaction.

Some live choices still have low modeled probabilities or incomplete foundations;
neither layout acceptance nor the above counts certify good bets. A duplicated
player-name prefix in one Risk context sentence remains a minor presentation
observation, not repaired by this release.

## Actual Tennis run and honest WTA fallback

The existing `betboy-tennis.service` was explicitly started at11:56:34CEST
and completed at12:06:49CEST with exit1, REFRESH_PARTIAL. The source error
was NOT cleared by resetting the unit state.

ATP independently published artifact
`5fb2d3778809470dcc5a0ad665117619ebd8a5e4a591112eb928335107a1bcf2`,
built2026-09-10T09:58:46.871739+00:00, training cutoff09:56:35.211480.
Its coverage2026-09-07 is explicitly `tournament_start_proxy`, not match end.
WTA fresh download failed and no isolated WTA artifact existed yet. Daily scan
for2026-09-11 found27fixtures, prepared2predictions, context capture partial,
stored0newpredictions. Duplicates/refreshability were not individually proven;
zero new rows is not by itself a new diagnosed code failure. Two native original
artifacts/snapshots were subsequently present. Existing older shadow aggregate
counts are not evidence for new context-model quality.

One bounded TLS-normal HEAD request to the existing WTA2026XLSX URL failed
with TLS alert/HTTP000. No TLS bypass, retry loop, new provider or source-date
substitution. Existing cached2010–2026files were checked read-only: none missing;
active2026WTA file264884B,1673rows/1672results, latest result2026-07-26,
WTA header valid and ATP header absent. Its SHA256 was
`f6f913da3dabbb54add6e9edd167a1d33d669c9ede9741e63e9069f18b3977ba`.

The documented `rebuild_state.py --if-stale-days 7 --no-refresh-data` mode was
then executed once as betboy with900s timeout. Exit0, REFRESH_COMPLETE,
refresh requested=False. ATP retained the exact same artifact/build time.
WTA published cached-data artifact
`d73bf67511ca8551779492ea18abeab6fadadf4c57112083ea188337a435be02`,
built10:14:34.904092, training cutoff10:14:11.960429, **result_date2026-07-26**.
This is usable retained baseline availability, NOT a fresh WTA source or empirical
context effect. Its existing Elo-only path does not invent serve measurements.
Readonly metadata confirmed both tour slots in active manifest
`1082d997798e9ecc3eb7bf18bda4f4179430406da454e3912bb8fe75d9a37ba1`.
No second full provider scan was run and no failed service marker was hidden.

## New post-data storage blocker — NOT closed

A new normal backup after data publication succeeded:
`/var/backups/betboy/betboy-sqlite-20260910T101535Z.zip`,88 databases verified,
0pruned. That preserves the new context database; it is NOT D4 semantic proof.

The D4 CLI on the live context file returned exit1/RuntimeArtifactTrustError.
Read-only diagnostics established the actual file is betboy:betboy0640 in0750
runtime_state, one link, no WAL/SHM, DELETE header[1,1]. Size100671488B
(24578×4096pages), freelist0, identity and size unchanged during measurement.

| Table | Rows | Payload bytes |
| --- | ---: | ---: |
| artifacts | 4 | 2956392 |
| context_contents | 47227 | 50653685 |
| context_observations | 47227 | n/a |
| context_snapshots | 2 | 3065937 |
| manifests | 2 | 242 |

Tour-state payloads contribute only2953017B; this is primarily real receipt
storage, not free-page bloat. `context_runtime._read_sealed_image` caps its image
at64MiB. Independent read-only updater inspection also finds its ZIP-member
MAX_IMAGE64MiB check before target verification. The source/configuration
preflight happens before downtime, but the actual size check after writers stop.
Thus another regular update would fail; do not attempt it as a diagnostic.

This new condition was absent during the valid first-B `not_present_legacy`
transition. It is a production-scale validation defect, not evidence that the
previous A/B installs failed. Root has held further deployments while separate
read-only reviews trace D4 recovery and the47,227 Tennis receipt population.
No cap increase, data deletion, VACUUM, permission change, raw root bootstrap,
installed-script replacement or semantic-verification bypass has been performed.

## Other isolated work, not deployed

Football P5b-A0 ecff029 has independent acceptance of the optional final-original
callback only (558focus/32subtests). Default durable B3 publication remains open.
P4b3(a) round1 6c8984d corrects direct unknown-status/retained-baseline behavior
and publication counts;452focus/26subtests plus original controls pass. Independent
rereview is HOLD: two real BB/NHL worker counterprobes show a conflicting
scheduled revision followed by clean unknown identity can still undo an earlier
cancellation. The packet remains frozen, unmerged and undeployed. Original two
durable-B3 reference witnesses remain truly
open; the withdrawn completed-only policy witness remains historically preserved.
Combining A0/P4b3 requires an explicit narrow parity-test integration review.
No qualified injury/load effect, unavailable native history or D1/D2 approval is
fabricated to turn these open items into a completion claim.

## Root acceptance of follow-up diagnoses — approximately12:32CEST

Independent updater inspection confirmed that the installed inline64MiB limit
is applied before `install_trusted_root_files` can install the repaired updater.
The existing executable accepts only its exact target-SHA invocation; there is
no documented capacity override or recovery shortcut. The prior HTTP/1.1 bridge
exception is explicitly non-repeatable. Root also read the relevant deployment
contract directly. A NEW narrowly reviewed and explicitly authorized roottool
transition is therefore needed; it is not silently covered by the old A→B route.
No such new route has been implemented or executed.

Readonly aggregate refinement:52receipt times,3093events,47227unique contents.
Of these,47098 are Tennis:26098status rows across3078matches plus21000bilateral
workload rows across1305matches, at50receipt times. The other129 are a concurrent
football scan:15base fixtures,84availability,30lineup rows, across15events.
The measured receipt range was09:59:08.864565Z–10:07:14.247866Z. Top receipt
groups contained1431rows/775events; these are not just two target predictions.

Root source reading confirms `capture_tennis_worker` surrounds `_run_daily`,
including `auto_settle_completed`. Settlement fetches one response for each old
pending date/tour pair and capture loops all response competitions before the
settlement-specific filters. Current reception time is also bound inside Tennis
status/workload contents, so the same sports body at a later reception generates
new content as well as receipt identities. This is not a broken generic B1
exact-dedup function. The live worker later loads the whole causal tour pool and
binds its references into each qualifying snapshot, prior to player feature
filtering. No payload extraction or database mutation was used for this diagnosis.
Fix scope must preserve honest receipt clocks and all existing references;
blind time-field removal, archive deletion or VACUUM is not an accepted remedy.

At12:30CEST a fresh public healthcheck still returnedok, all seven timers had
future scheduled runs, and actual VPS was reread as2dd1116 using the betboy
account. The SSH account's initial direct Git read was correctly denied by the
private app directory; permissions were not changed. The known Tennis service
failure remains separate from timer health. Further deployments remain held.

## Continuation preservation

This follow-up is an eight-document commit on
`codex/kontextmodell-20260907`, not a new main/VPS runtime release. The two
isolated implementation packets remain their own named branches: A0ecff029 and
P4b3(a)6c8984d. Publishing those branches is preservation of WIP, not acceptance
or deployment of the held P4b3 packet. Main and VPS stay2dd1116 until the new
installation route has explicit authority and independently verified bytes.

The default staged `git diff --check` reports six intentional Markdown two-space
line breaks in the two original reviewer reports. Their original bytes are
preserved, not silently reformatted. No production-source or test change is
included in this documentation commit. The known helper Git-M state and all
earlier/new diagnostic output files remain outside the index.
