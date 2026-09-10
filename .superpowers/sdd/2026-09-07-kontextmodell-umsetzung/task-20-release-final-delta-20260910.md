# Final technical release delta — independent addendum, 10 September 2026

## Disposition and exact scope

**No new release-blocking defect found in this bounded source/deployment delta.**
The previously reviewed installed-updater A→B route remains applicable to this
technical subset, subject to its unchanged actual-installation and QA checks.
This is not a new empirical approval, a full-suite result, or evidence that the
actual VPS has executed either installation step.

- Original bridge A: `655e7a6e430a776b0dcb291daded00399b5b8328`.
- Previously reviewed B: `f2f7611823c8e0b23b102bafba9e880adab87f9f`.
- Frozen final application source: `74d714a712ba3abc207ff0c717e7f27927624ba5`.
- During this review Root advanced to `286601b9a3290d8459bb7f77932fb6a20bc15a47`.
  Its complete diff from `74d714a` contains only five documentation paths; no
  application, test, deployment or dependency bytes changed.

Both `git merge-base --is-ancestor A 74d714a` and the equivalent B check returned
exit 0. Comparisons below use immutable `git show REV:path` bytes, not the
inherited working directory's line endings or uncommitted state. The original
`task-20-release-ab-independent-20260910.md` was read completely and remains the
owning review of the installed old updater → A → new updater → B sequence.

## Exact runtime delta and accepted packet identity

There are exactly five changed runtime files between B and `74d714a`. All five
are byte-identical to their corresponding accepted, frozen packet below.

| File | Packet | Final Git-byte SHA256 |
| --- | --- | --- |
| `context_sources/team_sports_binding.py` | P4b2/F1 `5a3d0c1` | `204bf8e3f836a5ebbc2644ebf7da29afeab8a8ae8c0b8a53c09b62794faf08d9` |
| `context_models/esports_live.py` | P6a `c28ae1e` | `6fa58ed4fc31ff3a0ea85403a997468f8cdec888dc89654f0d3f8673d624ac93` |
| `esports_shadow.py` | P6a `c28ae1e` | `f911bb17cc0bff0970d113e04521a45295083d1f487e7ccc20bdfa1be7279bf9` |
| `multi_sport_recommendations.py` | P6a `c28ae1e` | `7430075ff384a13af34fdfa44a796daae41f40016aecf1517ed21cb2837239b1` |
| `bet_finder_ui.py` | UI round 1 `acf6b8e` | `9447488dd3874946e46087ad33fed8525372226099386644a5e8d85650c2a88b` |

The complete new P4b2/P6a modules, changed E-Sport callsites, owning audits and
independent acceptance reports were read. This addendum does **not** repeat an
author review of the manual-price implementation. Its scope here is accepted
source identity, imports and absence of a new deployment/schema dependency.

### P4b2: pure binding, not an additional production worker

`resolve_team_sport_original(original, rows)` consumes the actual captured
original and caller-supplied receipt inventory. It validates that inventory,
applies the original cutoff and exact native alias lineage, and returns detached
event/receipt/input-binding material. It neither fetches a source nor opens a
database, publishes an A1 artifact, changes a schema or activates an effect.
Unknown or contradictory native material does not become a qualified event.
The output is not a new generic trust flag.

The exact final tree has no production callsite of this new resolver: only its
definition and owning tests refer to it. `sports_prematch.py`, existing status
capture, `ev_signal_sources.py`, `wettfinder_automation.py` and `app.py` remain
byte-identical to B. **P4b3 worker/consumer coordination is excluded.** The pure
resolver must not be presented as completed live C2/C3 context integration.

Existing explicit NHL format/scope restrictions remain; no 2026/27 or preseason
rules, missing native teams, minutes, goalie inputs or historical completeness
are manufactured by this release. Those source limitations do not invalidate
the unchanged baseline forecast or prohibit this technical deployment subset.

### P6a: same-call original under the existing unprivileged worker

The existing E-Sport shadow job now requests `capture_original=True` from the
existing candidate calculation and consumes that same call's original Elo
outputs. It removes the second target-history/Elo calculation. The original
object remains a transient CPU value: this packet does not persist it as a new
A1 kind, introduce an observation table or claim native B1/C4/D2 qualification.
The explicit offline replay function is not called by the worker.

The existing shadow SQL schema is unchanged (also checked by AST equality).
The worker still runs through the unchanged `betboy-esports.service` as the
application user, not through a new root import. Existing candidate/no-candidate
paths and publication limitations remain subject to the independently accepted
P6a tests; this review does not rerun or relabel those tests.

New module imports are standard-library modules and existing repository
contracts/helpers. The modified shadow module adds no import. The only new
external-to-repository import in the UI delta is standard-library `json`.
No new package, bootstrap step, secret, provider call or privileged capability
is required by the delta. The existing core E-Sport Elo file and Cricket default
path are not changed by a new integration here.

## Privileged installation, dependencies and restore boundary

A direct immutable-byte comparison passed for **31 deployment/dependency/
artifact/restore files**, including every file under `deploy/`, all 15 units,
`requirements.txt`, `runtime_paths.py`, the protected stage helper, backup and
verification scripts, artifact storage, consumer, transport and runtime
verifiers. Selected exact unchanged SHA256 values:

| File | Git-byte SHA256, both B and final |
| --- | --- |
| `deploy/update_server.sh` | `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f` |
| `deploy/bootstrap_server.sh` | `eb2cec227d710156f960ba78a620c5bdfe4bd97cd95ba2deb33a3c120fd5dec6` |
| `requirements.txt` | `3de53e0135470abb7ac94e86985904243d52e8dc488e1edb7fa9743dec73f2ea` |
| `runtime_paths.py` | `710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c` |
| `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |
| `scripts/verify_context_runtime.py` | `c1dab7debf1d5e50df640d99f7de6871468cf3db8a80972aeef6e2d58045f410` |
| `scripts/backup_runtime_databases.py` | `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604` |
| `model_artifacts.py` | `6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16` |
| `context_runtime.py` | `974917709b8e292b9621c6bef17112794a0724c4885f04f97052bde3799eab3e` |
| `context_transport.py` | `a47d980a4e528ef12917db39e47d025c4670070737901f6e8c9688dfe84a1a9e` |

The 15 unchanged units are app.service plus the service/timer pairs for backup,
esports, football-shadow, redcard-history, redcard-settlement, tennis and
wettfinder. A further overlapping 18-file comparison confirmed unchanged
contracts, C2/C3/C4 laws, activation, observations/snapshots and production
coordinator files. No additional artifact/schema migration is hidden in the
five changed runtime files.

The actual Root `runtime_paths.py` read was 12,031 bytes with raw SHA256
`e4cd84c131d330c00a91a019c9e38c137435c79cebc9f353c6bba3074ab3eddc`;
the Git object is 11,812 bytes with the LF hash above. An in-memory CRLF→LF
comparison was exactly equal. **No file was normalized.** The protected helper
read was already exactly its 19,138-byte Git object/hash above despite its
inherited dirty status. Neither that status nor unrelated output files was
modified. Final QA must use the separate fresh LF checkout, not silently claim
that this inherited raw checkout is that QA source.

The original ordered installation remains necessary: publish/install A using
the already installed old trusted entry, verify that A's root-owned updater is
actually installed, then publish/install the final B revision through that new
entry. Neither a manual root installation nor executing application imports as
root is introduced or justified. Legacy 2ba+A still does not need new context
modules or a context database. Existing path resolution, backup/quiescence,
app-user checks and closed restore disposition remain unchanged.

## Old C4 replay is still explicitly transport-only

The P6a change alters the whole-file `multi_sport_recommendations.py` recipe
hash from B's `80c545cf82a577bd4d1540bbd2619a12171662781373161d6db4c80ba38615c5`
to the final hash above. The accepted independent P6a report contains the actual
old-C4 SQLite witness: old full replay passed under its original code; full
replay rejects the new source identity; stored winner projections remain exact;
D4 returns `transport_only` with `d3-owning-family-replay-unavailable`.
That is existing independent evidence, **not a new test executed in this review**.

The final C4 law, transport, artifact storage, D4 verifier and privileged updater
are byte-identical to B. The existing D4 capability set still excludes E-Sport
full owning replay. The CLI still distinguishes structural success from
incomplete/transport-only status, and the updater still accepts only its closed
known limitation set. The limit above is already one of those reviewed limits.
No empirical approval is inferred and no gate/allowlist is weakened. This is not
permission to relabel old C4 data as fully reproduced or to fabricate an A1
publication for the new transient original object.

## UI acceptance and remaining release evidence

The independently authored round-1 report and Root's actual browser report were
read, including the closure addendum and corrected attribution of earlier
AppTest versus browser evidence. Their accepted source hash matches final B.
The former manual-price source/visual hold is closed by **those separate
reviews**, not by a self-review or browser run in this task.

This task ran read-only Git ancestry, byte/hash, import and callsite checks;
all comparison commands exited 0. No new defect hypothesis required another
runtime probe. There was no repeated 277-case or full-suite run, browser,
provider/SSH request, database mutation, source edit, commit, push or deploy.
Only this requested report was added.

The preserved 6,255-test result applies to old B `f2f7611`, not retrospectively
to the new five-file delta. Final integrated LF QA and its exact target/report
remain Root-owned. **Actual installed A→final-B execution, fresh backup/restore
disposition and VPS health/revision proof remain unverified by this reviewer.**
Missing empirical/source integration and excluded P4b3 remain honest product
scope gaps, not new privileged deployment blockers for this approved technical
subset. No claim that all user-requested sports work is finished follows.
