# SDD ledger — plan: docs/superpowers/plans/2026-09-10-context-capacity-recovery.md

Base: `82ca31d4340ed2dabd2a9812eb6bcadfbd757a5a`; branch `codex/context-capacity-recovery-20260910`.
User approved the one-time updater-only replacement with independent review, fresh backup and rollback. No data deletion or unrelated deployment is authorized by this repair.

## Current authority 12 September: C approved; bounded storage implementation

Task48: complete in narrow scope, code a52b4b7. Actual final owner run72pass,
0failure/error/skip in44.22s; XML eceee5000035520c57a12fa114b09a97e58c2a6f3fc407cd9d08314bcc2fbbdf.
Independent task-48-independent-review.md: SPEC COMPLIANT / QUALITY APPROVED,
no findings. Reviewer checked the retained XML and named copy/append/limit
couplings; did not repeat tests or claim native/global acceptance. Cross-task
external seals, full aggregate budgets/native measurements, actual History/
Consumer/Source/B/restore remain the explicit incomplete integration gates,
not inferred from Task48's closed observed descriptor. Code not yet pushed at
this entry; next documentation checkpoint will preserve review and push repair.

Task52: complete audit, confirmed P1; task-52-history-value-audit.md records
actual old acceptance/new default-block rejection of a16778570-byte selected
row in a16838656-byte legacy DB. One probe pass records the new failure, not
compatibility success. Old artifact/owning/source modules unchanged.
Ruling: implement the source-backed old-large-row exception through BOTH
History and Tennis as Task53 before Task51 — approved C4/C6 require preserving
actual old admission, while the earlier per-row assertion violates C4 — cost
if wrong is adapter rework; native allocation/CPU remains a separate gate.
Task53 requirements are in task-53-brief.md. One implementation writer;
Task51 remains paused and its inherited testcap fix still belongs there.
Current interface check: History resolver feeds prefix/events and chosen-row
Tennis staging; canonical full-byte digest/counts must not become locator
digests/counts. Backend format changes are separate from semantic versions.

Account continuation verified against files and Git: a0c949e contains the
reviewed Task44/49 append; now pushed to the repair branch and independently
confirmed by fresh ls-remote, main remains2dd1116. Fresh account-resume checks
of both append test files:136pass/0skip in4.49s, retained XML
.pytest_tmp/task49-account-resume-01.xml SHA256
c7746b13df561089cb239ebdcdc2c2d8365e1644c940f299b4325774e3f70f10.
Task50 actual native report and exact original JSON are now independently
reconciled (task-50-result-independent-review.md): no material contradiction
or scope overclaim. This checkpoint preserves those results; the reviewer did
not repeat the native run or infer outer terminal measurements from JSON.
Task48 and Task51 have inherited untracked WIP, not completed results.
Ruling: reuse the existing worktree and tracked ledger without running the
workspace script that overwrites .gitignore — all setup already exists and
preserving inherited audit artifacts takes precedence; no runtime consequence.
Ruling: resume Task48 as the only implementation writer, then Task51 — serial
SDD implementation avoids cross-task edits; it may delay the second task.
Task48 requirements are consolidated in task-48-brief.md; Root retains index
ownership and independent reviews remain required before task completion.
Task51 requirements are consolidated in task-51-brief.md, not dispatched yet.
Actual inherited tests still set SQLITE_LIMIT_LENGTH to the block size; this
contradicts the already rejected per-value cap and is explicitly routed back
to that task, without editing its files under the paused implementer.

| Continuation interface | Producer -> consumer | Fresh check / required action |
| --- | --- | --- |
| 44/48 | Actual in-connection append -> full source-plus-additions corpus | Append committed/reviewed; Task48 still must prove exact membership and closure. |
| 48/History | Closed observed corpus -> fresh held RO inventory/VerifiedReceiptMapping | A result descriptor is not permission; reopen and validate the entire real database. |
| History/51 | Live exact HistoryView -> same-source state/native/predict/features | Existing tests bind actual source; no reconstruction from a path or synthetic state. |
| 51/Snapshotparts | Real prepared Original and full refs -> caller-owned output | Same-call/canonical differential and savepoint checks remain required. |
| 48/48 | Main+ledger caps and exact row identity | Same-count replacement/INT64_MAX/close-reopen checks remain within existing task. |
| 51/51 | Existing JSON admission vs new block processing | Preserve existing per-value admission; remove only the inherited test's accidental new cap. |

Task52: named cross-task admission doubt under read-only audit. Existing
history.py rejects one selected canonical row larger than the processing block.
Check whether a real old source-valid record can reach that branch before
deciding it is a contract defect; no product edit or widened cap is authorized
by the audit itself. Task48 remains the sole implementation writer.

Previous continuation: repair branch6d7e2017e2d9d0f2fe29e385af3de83f4dae6dbe
freshly remote-confirmed; main remains2dd1116. Task43/45 fixed-copy integration
committed,197pass/2Windows-only skips. Task46/47 narrow5ms pending poll reviewed
and437 combined portable regressions pass. Native attempt3 now SIX cases pass:
NEW seal /var/lib/betboy-native-probe-wu61odle, sealerexit0/9.82s, actual
probeexit0/2.61s, full raw15789B report b27bbcde retained in Task50 evidence.
Old attempts1/2 remain RED, all three attempts/artifacts charged270CPU
conservatively. This is diagnostic-only, not DELETE/FULL/C-corpus/B approval.
Fresh postflight: app2dd1116/app+Caddyactive/internalhealthok, no testUIDprocess.
Task44/49 receipt operation independently reviewed316pass/0skip. Task48 actual
copied-corpus/ledger owner and Task51 actual consumer bridge are scoped work,
NOT complete global C/B. Do not shrink accepted input values to block size.

Latest explicit "ja" approves C specification08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba.
B498e63c5 remains approved. No repeated authority question. Frozen older decision
documents are retained; their preapproval status is superseded by this entry and
docs/superpowers/plans/2026-09-12-kontextspeicher-umsetzung.md.
Startb2e811a tracked-clean, same isolated repair branch. One writer per new
context_storage_v2 module: refs/history/tennis plus Root inventory/contracts.
Old product owners and limits unchanged; no new production call route yet.
Targeted local primitive tests/reviews complete, not native C/B or release acceptance.
Global input4GiB/history1GiB/block16MiB/workspace8GiB/reserve4GiB apply to the
explicit new mode; existing CPU/RAM/whole-preparation budgets remain binding.
No new native preparation job, server mutation or rollout in this checkpoint.
Reviewed primitive milestone c5912a7cb8ae095b7e7f63a0b3ce6ae2aaf9052a committed
and pushed to the repair branch; exact remote read confirms it, main stays2dd1116.
Last previous updater74b1 is not a fresh updater-hash check.
Root owns index/integration and will preserve coherent reviewed increments.

Continuation: C1 exact fixed-FD raw copy and complete source-backed C2b snapshot
conversion/reopen integration now implemented. Actual independent copy-reopen /
WAL and C2 NUL-size findings were reproduced and corrected; full history/Tennis
reader-lifetime findings are closed. Source adapter final independent review is
complete; the c5912a7 complete regression run ended with six isolated-runtime
dependency failures (7897 pass/30 skips/97 subtests). The unchanged owning hook
module now passes340/340 in a fresh local QA venv with actual -I SciPy imports;
the original red full-suite evidence is retained, not relabeled as green.
New full exact-byte regression is still required. Current targeted evidence,
exact scopes and all remaining C/B/native gates: task-16-controller.md plus
task16/17/18/19 author/reviewer reports. Do not infer overall completion.
Fresh read-only servercheck confirmed2dd1116/app/Caddy/internalhealth and a
successful actual Wettfinder run; separate dailytennis failure remains. Fresh
GitHub main2dd1116/repairbranchc5912a7. No new native preparation or rollout yet.
Task20 measured genuine local 5k/50k canonical reads, not native acceptance.
Task21 owns only a new chunk API/tests, Task22 reviews global disk/TEMP writer
admission, Task23 owns only a new stdlib preparation-budget primitive/tests.
These additions are not included in the already collected c5912a7 full suite.
Task21/26 snapshot chunk integration now355 related tests and118 independent
old/new differentials green; full byte/digest identities exact. Genuine local
50k whole-read wall2.162368->0.243204s, not native/growth extrapolation.
Task24 fixed-plan accounting and actual Device-Fix independently90pass/3native
Windows symlink skips, with real initial RED probes preserved. Task23 independent
review closed91pass/3Linuxskips. Task29 full frozen prelude completed8114pass,
31skips/97subtests in2052.78s; three new native/profile test modules explicitly
excluded and later changed bytes require another whole-suite run.
Task27/32 SQLite profile393pass; Task28/31 NoExec guard212pass/5Linuxskips.
Task30 supervisor original seven RED lifecycle findings closed; NoExec followup
173pass. Task34 separately reviews the narrow fresh secret-free parent/env
boundary (fork inherits heap; no key-holding B publisher may launch workers).
Task33 builds but has not executed the small native diagnostic. Task35 owns
only new C history/tennis writer-profile integration. Root owns supervisor,
integration/index/server. No native crash/core probe or host configuration edit.
No new service/cgroup, native corpus job, model/Cricket change or rollout.

Newest reviewed primitive commit d643f4884bbfa6dcf88b292c6f6fbd1c666a9867
pushed and fresh remote-confirmed on this repair branch; main remains2dd1116.
Task34 narrow parent review194pass. Task33/36 probe and root sealer have final
Task37 independent review134pass, no remaining concrete diagnostic finding;
not yet transferred or executed natively. Probe3abe69fc, worker22cfd8f1,
sealer10fbfee4 exact hashes in the respective reports. A fresh env-i invocation,
new private seal, outer terminal measurement and operator custody still apply.
Task35 builder integration580pass and Root integration6pass; Task38 independent
review running. Task39 read-only global growth/owner gap audit running.
No inference from these primitives to full growth, B proofs, restore or rollout.

Later fresh repair-branch remote898398295056aabd68d35da3ab58441c5c46f34a
includes reviewed Task35/38 builders; main stays2dd1116. Task38 combined359pass.
Task33/36 archivec79bb10 actually transferred and freshly sealed at
/var/lib/betboy-native-probe-2gcraxxf: terminalexit0/wall12.54s. One real probe
thenRED: missing VmHWM at exit transition, terminalexit1/wall1.59s; no returned
case cost and full60CPU chargeSTOP retained. Entire raw5988B report SHA6f22075b
preserved in evidence/task41-native-run1.json. No app/service/oldfile change.
Task41/42 final narrow supervisorae9fec1f closes terminal pending-deadline and
thread-observation regressions;270combinedpass, still needs native second run.
Task40 adds106 normal protocol tests. Task39 complete concrete build gaps read;
Task43 fixed copy/MEMORY-reader and Task44 in-connection real receipt operation
are separately scoped implementations, not complete corpus/lifecycle/B work.

## Current closeout 12 September: B0 executed, necessary StorageSTOP

B approval is recorded; no repeat B question. Fresh backup/restore/HMAC88 DBs,
sealed input73ec1691/270233600B. Baseline100553 receipts,31snapshots,
ATP42099/58390805B,WTA54819/75669070B. Independently reviewed helper9b4d3a0f
and8small owner tests; native baseline and3generated portions completed with
same source724/input/runtime/seals, exit0. Complete metadata logs and exact
instrument/test byte archive are in evidence/task14-*.

First real necessary size overflow at146782new synthetic ATP receipts:
268435847B>268435456 by391B. Tag1/2 each70000, tag3 stops at6782. No full
199snapshot/growth database or D4/7day pass. No old data mutated or new
production code. Native CPU with backup332.16, execution wall333.21;
conservative chronological23:19:00–23:46:11UTC=1631s. No further native run.

Independent resultreviewSHA5776a9f72111c24b046aa8c997c9d06f944ae54f856c5e2c88458652c686dfd2.
Root result task-14-sizing-result.md. New storage/input decision document
docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md remains
UNAPPROVED. It explicitly proposes a new bounded version, not secretly changed
legacy caps. Existing B/push/controlled rollout permission remains but does not
authorize this separately reserved storage boundary. No B productwork yet.
Final decisiondocumentSHA08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba;
independent documentreviewSHA185d45dc272d611c636f64bd34fcbec00965a84fe11cc7f3aec75ca9192f0f0f.

Fresh remote main and server2dd1116; oldUpdater74b1c4b1. App/Caddy/7timers
active+enabled/health200ok; separate failed dailytennis unchanged. No deploy,
user/key/service installation, fullsuite restart, source/model/feature/math/
odds changes or Cricket work. All native sizing sessions ended; Root owns
index and final preservation of these narrowly scoped diagnostic/doc files.

## Current authority12September: B explicitly approved; B0 first

User "ja maxhrn" answers the concrete final request for isolated verifier,
protected proof state,1800CPU/3600total preparation and mandatory sizing first.
Reviewed spec498e63c5 is now approved; no repeated B-authority question.
Its separate storage/input-contract stop remains binding if B0 actually fails.
Starting clean HEAD6a0ba81, product/testbytes724. Root owns index/VPS/integration.
Existing reviewed unmodified backuphelper64eab26e starts fresh online backup,
restore/HMAC and root-sealed context copy; no D4/fullcapacity claim follows.
One diagnostic size-harness author owns only ignored QA helper/own report and
scoped ignored selftests. Independent review precedes its execution. Source
data/model/feature/math/Cricket/livejobs/limits stay unchanged. No Bproductpatch.

## Current closeout12September: A1 STOP; concrete B decision ready

Executed approved plan05f7e6f through its conditional boundary. No new product
candidate: independent G1 repeat-ceiling analysis rejects a plausible240second
reserve for A. Additional bounded native pairs completed12/12,184.453215CPU /
183.117809wall,469032KiBRSS, exact724/sealedG1unchanged, exit0. This deliberate
snapshot-hook diagnostic completed no D4report and must not become acceptance.

Afterward minimal live read txn:99776receipts/31originals+snapshots/16ATPcutoffs,
268824576logicalbytes at22:12:37UTC. Not the syntheticG1 despite same size/count.
Provisional7day dimensions589776/199/114, conditional input1.153GB and canonical
ATP history345MB raise separate frozen1GiB/256MiB concerns; actual future sizes
unknown. No shrinking the proposed profile or bypassing admission under reuse.

Concrete Bspec docs/superpowers/specs/2026-09-12-versionierte-pruefnachweise.md
SHA498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1.
Independent review complete; oneP2closed by predeclared runtime closure checked
before reuse, including lazy/native/resource/searchpath negative test. Review
appendixSHAf6ab66eac0ce1b830c9d9f2c3cc5bfa0ee5c72b538959ff95765c4ebae409876.
Conditional Bexecution plan saved. Source/testbytes still724. No B approval,
implementation, extra service/key/account, cap/storage migration or deployment.

Next explicit decision is B's new persistent proof/lifecycle boundary, not
repeat push permission: isolated proofowner/runtime, separate root proofkey,
1800CPU/3600total preparation proposal and unchanged bounded finalcheck. Then
actual growth-size probe FIRST; if caps exceeded, separate storage/input
contract before Bproductcode. Fullsuite/native release remains held. Existing
main/updater/app-release authority only becomes executable after actual gates.

Fresh read-only VPS identity/services plus remote refs: main/VPS2dd1116,
oldUpdater74b1c4b1root:root0755/134237B. App/Caddy and7timers active/enabled,
timers scheduled, internal/public200ok. Dailytennis.servicefailed unchanged.
No fullsuite restarted; historical1c65results cannot certify724 or futureB.
Root owns index/integration. All diagnostics exited; no heavy QA remains.
New named reports task12result/feasibility/diagnosticreview, task13growth/design
review and minimized raw evidence are preserved for account/PC continuation.

## Current authority: execute the approved architecture/capacity plan

The user replied "ja alles machen" after the complete plan05f7e6f. Execute
StageA feasibility/equivalence and only a justified candidate, with240second
reserve/real7day growth planning. If the measured ceiling is insufficient,
proceed to the explicitly planned concreteStageB design/review and boundary
decision, not another speculative same-frequency patch. Existing release
and protected model/data/helper constraints remain in force. Root owns
index/integration. Read-only analyst owns task-12-stage-a-feasibility.md.
StartHEAD05f7e6f trackedclean; source/testbytes still724. Root prepares bounded
ignored QA measuring real earlier-prefix reconstruction vs optimistic fresh
JSON-only cost, plus metadata-only growth inspection. No acceptance inferred.

## Latest user request: plan only, no implementation

The user asks how to solve the capacity failure and explicitly requests a
plan before any new code. New proposal:
`docs/superpowers/plans/2026-09-11-pruefarchitektur-kapazitaet.md`.
It separates bounded in-run prefix reuse (A) from separately approved
cross-run/version-bound verification architecture (B), with feasibility,
equivalence, growth, reserve and release decisions. Neither A nor B has
implementation approval. The240second reserve and7day horizon are proposed
planning targets, not silently adopted current acceptance or measured facts.
Only documentation is authored. No product/tests/helpers/VPS mutation or
new test execution. Source724 and the following G1FAIL/releaseHOLD stand.
Locally verified clean starting HEADf2763b2; production facts below are from
the prior live check, not a new server verification during this plan task.

## Latest status: Task10 growth FAILED; release remains on hold

Exact code72421d3 passes actual30 input at288.095CPU/288.261wall,
485440KiBRSS with the full unchanged report and unchanged input.
The stronger31-query/snapshot G1 fails at299.975CPU/300.165wall,
485792KiBRSS, child-9, without a report. Its full input identity/SHA is
unchanged and no companions appeared. G2/G3 are sealed but not D4-run.
Task10.1-3 are complete; Task10.4 and release are NOT complete.

The bounded diagnostic on exact724 G1 completed all31 originals, then
stopped deliberately during snapshot28/31. No acceptance is inferred.
Only one original overflow used owned-full history (1.360743CPU);30
projections were hits. Repeated covering reconstruction consumed48.002107CPU
over27 completed calls plus an interrupted28th; full27 feature calls
consumed67.041CPU. These nested costs must not be added to worker totals.
No eviction/bypass occurred. Raw partial capture and complete emitted
summary are retained; exact pins and limitation are in task-10-native-evidence.md.

Task11 is read-only diagnosis/proposal, not implementation authority.
Rolling batches remove no traversal for G1's single excess query. Learned
non-owning prefix views would change later per-row covering proof frequency
to the existing exact-hit edge contract. That is not the promised unchanged
checking frequency and must not be silently implemented. No material
same-frequency repair is demonstrated; a boundary decision is required.
Product/test bytes stay724. No new feature/model/helper/limit/data change.

Final724 fullsuite was intentionally deferred after growth failed.
QA is tracked-clean detached724; earlier1c65 outputs remain intact.
Controller0f074a2 was normally pushed and remote verified. Main/GitHubmain/
VPS remain2dd1116; installed updater74b1c4b1 is unchanged. Fresh read-only
VPS check: app/Caddy and all7 timers active/enabled, both health endpoints
200/ok, separate betboy-tennis.service still failed (not reset).
No native or fullsuite job remains running. Root owns index/integration.
Older running/pending paragraphs below are preserved historical checkpoints.

## Task10 corrected code72421d3 — real current-first native running

The actualcallbackP2 is fixed by exactlytwo second-cookie exacttypechecks;
fourRED then239dispatch/witness+56inventoryGREEN. ScopedindependentAPPROVED,
24freshcontrols plusbase/candidate actualreproducer match. Rootreadallreports,
verifiedexactfourpathcommitandemptyindex. Prior1223tests stay4a-only.
Corrected841memberarchiveSHA45a5...3dd1 checked/transferred/hashmatched and
rootsealed at`/var/lib/betboy-capacity-code-5es6n672/source`. Newmeasurewrapper
SHA85a781...fe8d independentlyreviewed includingunchangedlimitsandexactrepin.
Current-first actual30snapshot CLI nowrunningUID997 child206801; noresultyet.
NewG1/G2/G3 31/32/33distinctqueries completed/sealed, notD4accepted yet.
Rootownsindex/controllerdocs/publication; allproduct/testbytes frozen724.
No fullsuite/mainpush/updaterexchange/appdeployment yet; main/VPS2dd unchanged.
Exactevidence/pins in`task-10-native-evidence.md`; preserveearlierfailures.

## Task10 implementation freeze / stronger growth QA in progress

4a27fb9 committed exactfourpaths; finalproduct focus1223pass/12skips and
complete117newmodule separatelypassed. Root read fullreport/verifiedindex.
Independent delta235pass but one realcallback P2: changedconnectionclass after
mainread bypassesnewsubclassexecute attemp. Samewriter regained exacttwo
checkingfiles/newtest/report/index for narrowly specified RED/type-recheckfix;
review findings must close before nativeacceptance. 4aarchive transferred and
hashmatched only, notrootstaged or applicationexecuted. Rootcontroller WIP
remains separate; intermediate1214pass is explicitly not finalproduct evidence.
Root remains controllerdocs/ignoredQA only. Fresh growth harness and bounded
supervisor independently APPROVED after two cleanup fixes; exactgenerator
uploaded/hashmatched/rootsealed. Synthetic31/32/33query G1/G2/G3 completed/sealed
from entire fresh30baseline; productiondata untouched. Fresh Task10current-first
native and allrelease gates remain pending. Live recheck confirms oldsource/
updater, activeapp/Caddy/seventimers, bothhealthok and samefailedTennisjob. Details/pins:
`task-10-native-evidence.md`. Latest actualD4 failure still means RELEASE HOLD.

## Task10 internal ruling — exact predicates, cheaper dispatch only

Root read the complete fresh30analysis and actual first-feature profile:
most cost is repeated witness/type/fresh-schema checking, not feature math.
Under the existing equivalent checking authority, reopen only inventory and
history-cache allocation/dispatch as defined in`task-10-brief.md`: same-order
recursive guard with fixed five leaf types, literal canonical bytes retained;
one local tracked cursor per schema pair only for exact owners, old subclass
route retained. Every SQL cookie/before-after/final/empty check and cold owner
stays mandatory. Transaction helper/math/model/source/schema/caps stay frozen.
If those semantics cannot be preserved, omit the seam; no workaround.

Self-consistency: JSON guard -> unchanged canonical witness; cursor -> same
tracked main/temp statements and ownership; proof -> same freshness/lifecycle
consumers; original/snapshot -> same full predictor/feature/transport calls;
updater -> same CLI/admission/limits. No new producer/consumer API or proof
authority is introduced. New deterministic dispatch/allocation RED is required.
One new implementation writer will own exactly two product paths/newtest/report
and index after the brief checkpoint. Root owns all native/fullsuite/release.
No second whole-branch review; independently review the new immutable delta.

06ab4af checkpoint normally pushed and remote verified; main/VPS2dd1116.
FinalSQL-test exactbc9 Linux selected3passed56.16s; separate whole-module
240s harness timeout preserved, not relabeled. All native/fullsuite jobs ended.
Current30snapshotFAIL remains RELEASE HOLD. Task10 is not implemented yet.

## LATEST — fresh30-snapshot capacity FAILURE, main/VPS unchanged

Fresh full88DB backup/actualrestore/HMAC passed41.49s, but its new actual
context has99774receipts/32artifacts/30snapshots instead of26. Exact1c65ada
unmodified CLI failed at299.978CPU/300.233wall seconds,486496KiBRSS, child-9,
no report; input SHA/identity unchanged. All earlier26/G1/G2/G3/largest PASS
evidence is preserved but cannot certify this newer input. RELEASE HOLD.
Clean exact1c65ada Windows fullsuite7292passed/30skips/97subtests1792.20s;
Linux integration405passed/10skips222.68s, owner75passed. Final whole review
and narrowbc9d268SQL-test rereview APPROVED, no open code findings; root read
all complete reports. The test-onlyfix33passed/allwarnings errors, independent
3passed. One final Linux dataset module onbc9d268 is running independently.
Root owns index and will save/push this repair checkpoint only. Read-only
followup analysis of remaining snapshot checking costs is in progress, not
an approved new implementation. No main/VPS/updater/data/limit/model change.
Details and XML/input hashes: `task-9-native-evidence.md`.

## Latest acceptance checkpoint — Task9 profiles passed, release pending

Exact1c65ada current/G1/G2/G3/historical-largest native profiles all PASS under
the unchanged limits. Current262.838wall seconds; historical largest136.809wall
with188791receipts. Actual UID9973DAC/8unsafe-class and7interleaved lifecycle
controls passed; Linux owner75passed. Full Windows suite and Linux integration
are running. Final whole-branch review DONE ONCE, APPROVED with one Minor
unordered-SQL-test issue, no Critical/Important findings. Fresh test-only
writer`/root/sql_order_test_fix` owns the exact test/report and index; root
retains separate controller docs/native jobs. Narrow rereview follows the
test-only fix; no repeated full review. Main/GitHubmain/VPS still2dd1116,
updater unchanged. Fresh real backup/restore/HMAC, actual-data confirmation,
publication and the two separate VPS operations have not run yet. Preserve
the existing failed Tennis-worker state honestly. Native details are in
`task-9-native-evidence.md`; historical checkpoints below remain preserved.

## Task9 scope ruling and preflight —11September2026

LATEST: exact1c65ada actual-current native PASS,262.690CPU/262.838wall,
486420KiBRSS,complete expected transport-only report, all99521receipts and
26snapshots, inputSHA/fullidentity unchanged/no companions. Old300CPU failure
is now superseded for this exact input/source, not for unlimited future growth
or empirical model approval. G1child203403 and cleanQAwhole suite1c65ada are
running. First/only final whole-branch review dispatched to
`/root/capacity_whole_branch_review`, BASE2dd1116..HEAD194155d (code1c65ada),
package1594867B/SHA5896f0e34944cd9127cd755f5d1c59332ca515411d423de480dbd18bf6f55f80.
Carry Task5 Minor unordered SQL test comparison. Root retains index/native/
fullsuite/controllerdocs; reviewer only writes its exact final review report.
Repair branch has been normally pushed194155d; main/VPS/old updater remain
unchanged. Do not dispatch a second full review or claim all release gates passed.

Latest Task9 checkpoint: implementation locally committed
`1c65adae1e9de85a6d457cf452f21c4d9cbb589e`, exact five allowed product modules,
one new test module and complete report. Root read the full report and verified
the empty index and unchanged18frozen paths. Exact-product22module focus:
1109passed/12skipped659.74s; final75-case module75passed15.47s, with the later
generic-normalization count strengthening separately1passed/74deselected2.44s.
The intermediate1107passed run is not relabeled final. Immutable07d975f parity:
71persisted outcomes and178validator comparisons all equal. No native/suite/
release result is inferred. Root owns index again. Fresh scoped independent
reviewer `/root/tennis_check_task9_review` is read-only on immutable
`review-d138ac5..1c65ada.diff` (84508bytes,
SHAbe0bace35d8fbfe712a2a74a6768f4c234c8e492fc1faa7bf63757218c80d5f5).
It is not the final whole-branch release review. Product/test bytes frozen;
controller documentation/ignored QA work may continue. No main/updater/app
mutation or Task9 native execution yet.

Subsequent scoped review is APPROVED, no actionable findings. Reviewer ran
365focused+32inventory cases and12extra persisted workload controls; main read
the complete report. Exact1c65ada archive33907914bytes/832members,
SHAa3df9e45e9cc0c067197716b44930d6e7eea77557296193e6dab5ca011847e00,
transferred with matching hash and staged by unchanged rootstdlib helper in
`/var/lib/betboy-capacity-code-iym7re_h/source`. Current-first uninstrumented
CLI is running asUID997, child203242, with unchangedCPU300/AS2GiB and sealed
253333504-byte actual input. No result or release acceptance yet. Root is
saving review/transport evidence in a documentation-only checkpoint; exact
candidate product/test bytes and running immutable source remain1c65ada.

Ruling: under the user's already explicit equivalent Tennis/D2 checking
repair authority, reopen only D4 observation/original orchestration, inventory,
cache and the narrow shared Tennis source-tail check for Task9's fixed
physical/source co-traversal — actual07d975f projection works but fullinput
fails, and real profiles identify repeated physical+genericB1 checks — if the
same-frame provenance, full source predicate matrix or mandatory cold fallback
is wrong, the patch must be reworked/rejected before production; no acceptance
contract, math, data or cap may change. This supersedes Task8's internal
fixed-cold-builder path and listed owner freezes only for the named design.

Ruling: permit ordered unfiltered physical receipt traversal on the new private
route, preserving all content/receipt/orphan phases and every row — existing
SQL within-phase order was unspecified, and sorting avoids an unaccounted
Python pool — if SQLite sort overhead prevents the fixed profile, release
remains HOLD; no index/schema/cap workaround. Public ordinary routes retain
their existing behavior.

| Interfaces/tasks | Preflight check and resolution |
| --- | --- |
|9physical ->9source|Fixed real decoder and immediate complete source-tail in same frame; physical proof alone never sourceproof; no callback/flag|
|9source ->6/8seal|Independent full cold validation of every fresh decoded pending row retained; no residual-helper seal|
|9pending ->8ownedprojection|One chargedpool, allmetadata, final physical/source completion plus exactserialproof; direct_store still cannot mint authority|
|9planning ->5D2|Actual artifact map+persisted timestamps only; protected final bodies opaque; sourcefailure deferred with actual fullcold rejection|
|9runtime ->2/3updater|SameCLI/report/admission/math; new exactcurrent/growth/fullsuite/backup proof required; scripts/pins frozen|
|9standalone/fallback|Public source and ordinary inventory behavior unchanged; alreadyvalidated input has no invented source proof|
|9failure/lifetime|No retained exception/traceback/row/key afteruncharging; resources and lifecycle failhard, notoptional cancellation|

Main read full task9design and authored exact plan/brief. Installed skill6.3.0
files/scripts disappeared midturn; main previously read complete workflow and
templates, so equivalent brief/review packaging uses explicit apply_patch/Git
steps with recordedimmutableSHAs. No skillscript was falsely claimed executed.
No new product implementation yet; root owns index until the brief checkpoint.

Task9 brief/design checkpointbc2d0ce committed. Exact07d975f Linux focus
subsequently405passed/10skipped218.42s,XML415/0failures/0errors:9root-staged
fixture tests skipped inordinaryUID1000QA plus1non-Linuxcase. Separate actual
UID9973DAC/8unsafe-class and7race controls allPASS. Actual-currentcapacity
remainsFAIL; no whole suite/main/updater/app mutation. Trailing blank in the
new brief is corrected in the following documentation-only checkpoint.

Task9 implementation/index owner `/root/tennis_check_task9` dispatched from
BASEd138ac5b14e94ac37a6b089bf3efbda3a7dc0c92 after clean exact checkpoint and
normal repair-branch push. It has read brief/design/rulings; RED-first work
is in progress. Root owns only separate controller documentation/ignoredQA
helpers while writer is active; do not stage/commit or dispatch anotherwriter.
All Task8 native/diagnostic/Linux jobs are complete, none running. Main/VPS
remain2dd1116, oldupdater74b1c4b1; no resource/header/source/hash relaxations.

## Latest Task8 checkpoint — fix round1 committed, scoped rereview pending

LATEST OUTCOME:07d975f actual-current native FAILED at300.046CPU/300.135wall,
486572KiBRSS,child-9/supervisor1,no report. Input SHA/full identity unchanged,
no companions. Its scoped correctness approval is not native acceptance.
Code07d975f is normally pushed on repair branch only. Final whole suite and
whole-branch release review were not started; no main/updater/app mutation.
Bounded phase diagnosis now running from the same exact source/input,
CPU275diagnostic stop under unchangedCPU300/AS2GiB; not a verification pass.
Original author supplied read-only control-flow diagnosis: expected26query
capacity fits; record actual projection hit/miss and outer snapshot overhead
before choosing further work. Root owns index/docs; no product writer active.

Subsequent checkpoint: Fix1 scoped rereview APPROVED, all3reference paths
addressed,0open/new findings. Task8 fix round1/5 (3addressed,0open;
commits7bab03c..07d975f). Exact07d975f pushed normally after fresh remote
confirmation06db3be/main2dd1116; no force. Actual-current native job201336
is running from exact root-sealedstagebetboy-capacity-code-b3xcmdb8.
Native/full-suite/release acceptance remains pending. Protected16file hashes
were freshly verified. New final whole-branch package is prepared only:
`review-2dd1116..07d975f.diff`,60commits/1439160bytes; not yet dispatched.

Final fix `07d975fb54a62ecb976c8040823e16fe45d9f16f` addresses the independently
confirmed dropped-query reference and the controller's same-class enclosing
key/publication references. All were reproduced RED, then fixed with short-lived
owner frames. Final projection/shared/real-D4 coverage:118passed in85.15s,
no skips. The earlier365passed/9Linuxskips belongs only to the fold-only
intermediate hashes;962passed/12skips belongs to7bab before Fix1. Root read
the complete appended report and received an empty index. Scoped package
`review-7bab03c..07d975f.diff` contains1commit/27699bytes; fresh rereviewer
`/root/tennis_check_task8_rereview` is read-only. No native/full-suite approval
is inferred. Product cache SHAae30feb5624797fd32e00541d748c0ba6a18acf62fa04c623b1ea0b29cf7b06a.

Exact07d975f Git archive:33863927bytes,826safe members,102786203expanded bytes,
SHAbc19bce5fbf9bf14a83642b246c044fb0bee342509ac99c2b312205d7bdf75d9.
Approved upload completed to the existing isolated QA directory; no application
execution or production mutation yet. Rejected7bab archive is retained,
never staged or used as acceptance. Main/VPS remain2dd1116, repair upstream
06db3be until next explicit publication. Fixed limits and all saved inputs
remain unchanged. Historical largest188791-receipt input is additional native
regression evidence, not a substitute for current/G1-G3 consumer growth.

## Approved owner-check repair continuation — 11 September 2026, 14:42 UTC

Latest user: "ja und dann commite pushe und pulle doch einfach alles wieso sollst du das nicht machen". This explicitly supplies the previously requested Tennis/D2 checking scope extension and repeats commit/push/deploy authority. No second permission prompt is needed for these actions. Results, data, validation strength and resource limits remain unchanged; only passing release evidence permits production promotion.

Fresh local baseline: HEAD/repair upstream7cf1e94, linked worktree on `codex/context-capacity-recovery-20260910`, no tracked changes, nine inherited untracked review diff packages preserved. Existing full fc7 source test evidence is the unchanged-code baseline, not a claim about the upcoming patch. Reuse existing isolation; no dependency reinstall or worktree recreation.

Continuation preflight:

| Tasks | Producer/consumer or internal contract | Finding |
| --- | --- | --- |
| 5/5 | Named SQL parameters -> real SQLite preflight | Mapping bind only; same opaque bytes/projections; no label body use |
| 5/D2 evaluator | Dataset source -> implementation_hashes | Hash changes naturally; old reports must not be relabelled/whitelisted |
| 5/1,4 | Physical outer checks -> complete inventory/replay | Unopened-final and full corrupt-row rejection unchanged |
| 6/4 | Sealed encoded basis -> per-consumer selected receipt checks | One extra full owner seal, exact current types/bytes, same actual feature calls |
| 6/1 | Completed physical proof/transaction -> scoped witness lifetime | Existing mapping unchanged; revocation hard-fails, no caller authority |
| 5/6 | D2 unopened headers and changed dataset hash -> full D4 run | Disjoint edits; final real-input and protected-final proof required |
| 6/6 | Cold validator, ContextVar and cache serial/cursor | Signature unchanged, no arbitrary callback, no retained row/byte aliases; type misses preserve cold behavior |
| 5,6/2,3 | New exact verifier -> frozen updater/installer | All native current/growth and full release proofs must be renewed |

Task5 is the bounded D2 binding repair; root retains plan/ledger/handoff and native/push duties. Only one child receives implementation/index ownership. Task6 implementation will start after that writer returns and its checking interface is documented. All old failures remain recorded; none is converted to a pass by this approval.

Task5 implementation/index owner: `/root/d2_binding_task5`, base7cf1e94. Read-only bounded design owner `/root/tennis_check_design` completed its report; it edited only `task-6-design-analysis.md`. Controller fully read the design and its original-type/provenance refinement, then recorded Task6 before dispatch. Scope uses existing bytes plus new cold owning seal and strict current-value checking; mathematical v3/v2 files remain unchanged. No generic trusted callback or second byte cache is allowed.

Task6 interface/self-consistency check: selected source wrapper retains the public signature consumed by unchangedv3; cache factory is private and proof-producing only after full cold validation; runtime scope surrounds the same feature call; global64MiB incl pending and256MiB admission remain unchanged. Same-key replacement/eviction must remove old seal and keep byte accounting exact. Ineligible types must preserve cold admission rather than imposing stricter schema. New source file hash is not among original CODE_PATHS or evaluator math hashes; no compatibility whitelist is needed/permitted.

Fresh root native diagnosis: exactfc7 G1 input95406receipts/11snapshots, SHA01186c29...966, one91.672CPU cold basis56865423B, no evictions/bypasses; full physical41.045CPU; eleven originals114.188CPU inclusive basis. Nine full snapshot features9.140–10.133CPU each; tenth deliberately interrupted at diagnosticCPU275. Total276.824CPU/275.898wall,472448KiBRSS, input unchanged. Not a complete verification or acceptance pass. Harness `.pytest_tmp/trace_task6_baseline_growth_g1.py` SHA373640761c788b759201749cfa41c3a7609ebe8bf01960c7bcd8e6a9d8b2a723, run asUID997 with fixed limits on root-sealed input; job ended. GitHub repair7cf1e94/main2dd1116 and VPS2dd1116/old updater freshly confirmed; App/Caddy/seven timers and bothHTTP200/ok, knownTennis partial failure unchanged.

Task 5: implementation/review complete (commits7cf1e94..cbfe6ce, spec compliant,
quality Approved; no Critical/Important findings). Root received an empty
index. Focused Windows262passed/9skipped plus2explicit boundaries, all with
DeprecationWarning as errors. Native warning-as-error and cross-task D4/full
suite remain explicitly controller-owned release gates; see task-5-review.md.

Task 5: minor (deferred): regression compares two unordered SQLite scans as
ordered lists; final whole-branch review must triage multiset comparison.

Task5 native warning-as-error gate PASS at exactb4ee364:4passed in187.82s,
supervisor188.476s,exit0,empty stderr. Includes original failing protected-final
membership, new real named binding, corrupt unopened outer index and changed
source/evaluator rejection. Archive25cada24be467b60427455281e1ce214f3038f6eafb150d3aeb78e88f7f1c9d4,
813members; isolatedUID1000QA d2-binding-b4ee364-ksnx7v9p. Task6/root final D4
and whole-suite gates remain open. New task6 owner `/root/tennis_check_task6`
has sole assigned product/test/index ownership fromBASEb4ee364.

Exactb4ee364 was pushed normally to the existing repair branch after native
Task5 acceptance; remote previously7cf1e94, push exit0. Main2dd1116 and the
application/updater are unchanged. This is backup/publication of a coherent
reviewed intermediate state, not an application release.

Fresh full88DB backup/actual isolated restore/HMAC PASS38.70wall s on11Sep,
stagebetboy-live-backup-_04ttiwe, archive8e5ecab4...9b23. New current sealed
context253333504B SHAced192e7...d2f05 has99521receipts/28artifacts/26snapshots,
substantially newer than yesterday's114929664B/10snapshots. Final current-data
acceptance must use this latest actual input; preserved old G1-G3 remain
additional synthetic proofs. Root informed Task6; limits/checks unchanged.

Integration preflight: local main checkout remains2dd1116 with no tracked WIP.
Existing untracked .playwright-cli, two audit reports, market-benchmark plan
and output/playwright/riskobet-preview-state/seed_riskobet_preview.py remain
untouched. Current repair ancestry includes main, so a final fast-forward is
possible if remote main is still unchanged. Recheck before integration; no
force/reset/clean and no automatic worktree/evidence deletion.

Task6 code8992386:657focusedpassed/9skipped in568.42s,93new witness cases,
30complete snapshot replays, cold body and all mathematical/CODE_PATHS bytes
unchanged. Empty index returned. Independent `/root/tennis_check_task6_review`
reports spec compliant and quality Approved, no findings. Native/full-suite,
cross-task and release evidence remain open, not implied by that approval.
Exact899 archiveb7de590def4d2654d29eea36f06c85410ac21801909788cb15a57733d55e9650,
815members, root-sealed underbetboy-capacity-code-a_qm6fl8. Final QA checkout
is detached899 with prior outputs preserved. Root owns all following tests,
integration, index and VPS actions.

Task6 actual-current899 native gate FAILED at299.977CPU/300.165wall,
child-9/no report,480156KiBRSS;253333504Binputced192e7 unchanged, no companions.
No main/updater/app publication; current hold remains real. Full Windows899
suite still running. Root will diagnose phases on this actual26-snapshot
input under the same limits; no unmeasured approximation/cap increase or
history deletion is allowed. Whole-branch review has not been dispatched;
its prepared899 package is not an approval. G1-G3 new-source gate not yet run.

Task6 native fixture preparation complete, NOT verification: unchanged fc7
owners generated G2 with95407receipts/12snapshots/7cutoffs and G3 with95408/
13/8. Root-sealed hashes12157b36...eed4 and79954e45...d0ec. Existing current,
G1 and baseline bytes preserved. No production or budget changes. Full
paths, timing, source and seal evidence are in task-6-native-evidence.md.

Task6 bounded actual899 trace completed, diagnosis only: physical42.950CPU,
cold92.532, independent seal27.422; all26 originals end223.805wall. A single
58390805-byte basis fits64MiB with no evictions/bypasses. Ten old-cutoff
snapshots complete at4.399–4.916CPU each; diagnostic stops at276.999CPU with
the eleventh interrupted. Input unchanged. The intentional signal caused
tracked-generator closed-database unwind noise, explicitly not a clean pass.
See native evidence; this disproves overflow as the current failure cause.

Ruling: within the user's explicitly approved equivalent Tennis checking
repair, Task7 may eliminate duplicate work inside one selected native-status
owner call and consolidate redundant checks of the same completed inventory
stamp — neither acceptance nor mathematics changes — if equivalence or
sufficient capacity is not demonstrated, preserve rejection and release HOLD.
This narrowly supersedes Task6's verbatim cold-body requirement for the
source-only duplicate derivation; the independent seal, strict current
canonical-byte comparison, every lifetime boundary and cold fallback stay.

Task7 preflight: source factoring produces only locally derived fields and
bytes consumed in that same call; standalone status validation retains full
normalization, no caller proof or cache. Cache proof fusion consumes the
existing unchanged inventory stamp and must preserve permanent revocation,
wrong mapping rejection and cache clearing. Both share witness tests but no
other production file. Owner/model/source hashes, future/opposite-tour rows,
final-row/empty/DDL/closure/eviction controls and fixed native resource caps
remain binding. Native savings are unproved; one combined candidate is to be
measured against the real26-snapshot copy after independent task review.

Controller checkpoint65cd304 (Task6 code/review/failure evidence plus Task7
brief) pushed normally to the existing repair branch after fresh ls-remote
confirmed upstreamb4ee364 and main2dd1116. No force, main push or deployment.
`/root/tennis_check_task7` now has sole assigned product/test/index ownership
fromBASE65cd304. Root preserves the active899 full-suite run and performs
separate native QA/documentation only. Whole-branch899 diff remains unreviewed.

Exact899 full Windows suite completed:7020passed,30skipped,97subtests passed
in1678.77s, exit0; XML0failures/0errors, SHA05ea6097...f0cef0. Detached QA
tracked-clean. This supports899 correctness only; Task7 needs its own final
regression and actual native current-data capacity is still FAILED.

Fresh ordinary-SSH read-only health check confirms production2dd1116 and
old updater74b1c4b1(root:root0755,134237B), app/Caddy active/enabled, all seven
timers active/enabled, internal/publicHTTP200/ok. The known failed
betboy-tennis.service remains failed and was not reset or called repaired.
Local exact hashes reconfirm unchanged installerbdc9c700/updater4b814c50,
stagehelper1441158c/backupb37d11a1, inventorya4f0f9a2/transactionecec258d,
v3/v2model and all six original CODE_PATHS. No live production mutation.

Exact899 G3 native CLI PASS282.270CPU/283.876wall,477704KiBRSS, complete
expected13-snapshot transport-only report, supervisor0/child2, input unchanged,
no companions. The actual26-snapshot current-data FAIL is NOT superseded.
Task7 implementer informed; G3 transport acceptance is not empirical approval.

Task7 implementation17cfbbc:887focusedpassed/12platformskips511.56s; final
202witness/equivalence tests27.60s;169immutable owner outcomes and104full
features match899 byte-for-byte/error-class. Index returned empty, controller
changes preserved. Independent `/root/tennis_check_task7_review`: spec PASS,
quality Approved, no new findings; sequential final-schema-read limitation
explicitly remains, no atomic-DDL guarantee. Root read complete report and
review and owns all subsequent index/native/publication work.

Exact17cfbbc archivec59e848d...1e85ef (33823429B/819members) uploaded and sealed
at`/var/lib/betboy-capacity-code-4yp86fps/source`. Actual26-snapshot native
measurement started asUID997 child199986 with unchanged resource/report/input
checks. No acceptance yet; final full suite waits for this decisive profile
to avoid retesting a capacity-ineligible source. See task-7-native-evidence.md.

Task7 actual-current17cfbbc native FAIL300.063CPU/300.141wall,483664KiBRSS,
child-9/no report, supervisor1, input unchanged/no companions. No final full
run/G1-G3/whole-branch release approval was inferred; main/updater/app remain
unchanged. Equivalent local cost reductions do not make this profile fit.

Read-only architect confirms no existing validated-inventory API proves the
latest eligible target native row (including equal-time non-status competitors)
without unrelated history decoding. Root requested a bounded design for an
owner-derived original-only projection produced during the existing full
independent seal pass, with full prefix-byte admission, exact native uniqueness,
bounded/charged metadata and complete old fallback. All physical/eligible
source checks, predictor and full snapshot histories/features remain required.
This is not an implemented shortcut or release approval; architect may edit
only task-8-design-analysis.md, root owns all other files/index/native actions.

Controller code/review/hold/handoff checkpointbedcf12 pushed normally to the
existing repair branch (remote prior65cd304), not main. Working/index clean
at that checkpoint apart from the new ignored Task8 design report. Free VPS
space18,900,369,408bytes read-only; no cleanup/deletion needed or performed.

Task7 bounded trace completed: physical44.991CPU, cold85.677, seal23.607,
all26 originals166.146inclusive; original history reconstruction41.658CPU.
Snapshots start217.514wall;12complete features1.848–2.197CPU before13th
deliberate interrupt. Total276.913CPU/276.101wall,484200KiBRSS, input unchanged;
single58390805Bbasis/no pressure. Native trace is diagnostic, not acceptance.

Ruling: Task8 may replace only the original check's internal unused full-history
tuple with an equivalent owner-derived latest-target/completeness/admission
projection — broader approved spec requires exact evidence and calculations,
not that internal representation; the user's existing Tennis-checking repair
authority covers this — cost if wrong is rejection/parity/capacity rework,
never changed data, source/model hashes or weakened validation. This explicitly
supersedes Task4's complete-tuple sentence for originals only. Snapshots retain
their complete fresh tuple and every unchanged owning feature/transport call.

Task8 preflight: root read the full broader spec and full revised design.
Native sufficiency is whole-prefix bytes plus latest-target multiplicity and
unique ordinal, counting ALL target rows. Important design hole closed before
implementation: direct _store validates rows but not their completeness; it
may mint neither aggregate nor complete-history fallback authority. Only a
cache-owned fixed full builder may activate entry-serial/proof-bound markers.
Unowned exact/covering subsets must cold-fallback, not silently be consumed.
Global64MiB incl planned/draft/marker bytes and32entry+query slots; full owner
checks, invalidation, predictor and every snapshot replay remain unchanged.

Task8 plan/design/extracted brief committed as06db3be before dispatch. Fresh
implementer `/root/tennis_check_task8` owns only assigned product/tests/report
and Git index from that base; root performs separate ignored QA preparation
and handoff/ledger edits without staging. No native or full-suite process is
running. Last actual repair push remainsbedcf12; no main/updater/app change.

Fresh remote check confirmedbedcf12 on repair and2dd1116 on main. Root then
pushed exact06db3be normally to the existing repair ref (exit0), without
touching the implementer's index or its new uncommitted product/test work.
Task8 RED is independently distinguishable from acceptance: implementer
reports6expected failures, including110versus20original cache decodes and
direct valid-subset completeness failures. Task8 implementation remains open.

Task8 author checkpoint, NOT acceptance:82new projection cases plus concrete
RED/GREEN followups for two-map plan-byte undercharge, interrupted marker
cleanup, reentrant final-seal replacement and a missing post-cold fallback
cache-lifetime boundary. First larger focused run was interrupted with one
obsolete cache-hit assertion; that contract now distinguishes snapshot hits
from original projection queries. Complete final focused run restarted by
the author in session79145. Immutable17 development oracle reports13persisted
fixtures (3equal reports/10equal rejections) and exact direct-native error/
12accepted original-call parity. Full report and independent review remain
pending; root has not run native/full-suite or deployed Task8.

Task8 implementation7bab03c committed with962focusedpassed/12platformskips
in556.58s,83newprojection cases, final hashes unchanged, empty index returned.
Controller read the complete final report. Fresh independent reviewer
`/root/tennis_check_task8_review` is checking immutable06db3be..7bab03c via
the91046-byte package; no scoped verdict yet. Only exact Git archive7bab
(33858223B,826members,expanded102770637B,SHA2055c1f4...644a4) was uploaded
to the already authorized QA path. No source stage/native/app execution yet.

Task8 independent review NEEDS FIXES: one Important dropped-query lifetime
finding, no Critical/Minor. `_store_encoded` retains its last `query` after
pressure removes its charge; real fixture13690Bpending/0metadata still holds
268Bdraft. Root verified the loop/frame reasoning against current code and
recorded full review in task-8-review.md. Fix round1/5 resumes the original
implementer, base7bab03c; only this defect plus lifetime regression/covering
tests/report may change. Native execution remains paused. Unchanged protected
hashes have root evidence; full-suite/native/release cannot-verify items stay
open controller gates, not accepted or waived.

Root final-coverage check recovered the preserved historical188791-receipt/
4-snapshot generation3 (387739648B,SHA3628dee7...cc953), previously passedc4
with~1sheadroom. It is added as an extra exact native regression alongside,
not instead of, current and Task4G1-G3consumer-growth profiles. No dataset
generation/edit, validator/budget change or native execution occurred here.

Task8 fix1progress: original fold-frame defect reproduced with an actual
weakref lifetime test, fixed by a short-lived folding helper. Four covering
modules365passed/9Linuxskips186.99s on that first fix. Root then identified
the same class in caller planning/drop frames; author independently reproduced
three REDs (two retained keys and validated publication temporaries) and
factored only those existing owner loops into short-lived helpers. Three
targeted GREENs; final complete projection/shared plus real-D4-cache case
requested on this updated code. Prior365result must not be relabelled as the
later source. Same fixround1; no native execution or new release authority.

## Final Task4 checkpoint — 10 September 2026, 22:25 UTC: RELEASE HOLD

Task4 product52189a6/reportfc7f0c7; independent scoped implementation review
approved, no introduced code findings. Full immutable fc7 Windows regression:
6926passed/30skipped/97subtests,1631.90s,tracked QA clean; XML9ee9e3a322e6b15147aae44702b2398fdd8b593832d9a30da6843facefffde44.
Final native focused run199passed/10skipped in171.42s BUT14196SQLite warnings;
targeted warning-as-error repro identifies unchangedD2dataset.py:169-174
numbered/named binding with a positional tuple. Independent review classifies
this Important compatibility issue outside Task4's frozen owning-source scope.

Current real input PASSED285.297CPU/285.388wall seconds,321584KiBRSS,
48307receipts/10snapshots and exact unchanged incomplete/transport-only report.
Fresh88DB backup/actual restore/HMAC and final actual UID997DAC/races passed.
BUT G1 receipt-plus-consumer growth FAILED300.112CPU/300.233wall,child-9,
472488KiBRSS,no report,input unchanged. G1 has95406receipts/11snapshots,
13artifacts,6cutoffs,212172800bytes; sealedSHA01186c29cb6e31aef5815ae3f937d81401b9e72ddaaa30d934864bcf78daa966.
G2/G3 not executed after the binding G1 failure, explicitly unproven. No limits
raised, validation calls removed, histories pruned or model/source pins changed.

No main push/updater-only exchange/app deployment. Fresh22:23UTCVPScheck:
HEAD2dd1116,updater74b1c4b1,app/Caddy+7timers active/enabled,health200/ok.
Known failed tennis-service state remains. All executed local/native QA jobs
have ended; only ignored QA artifacts and durable reports were added.

Next scope decision is REQUIRED before further product edits: address the
remaining per-consumer owning validation cost (not another speculative LRU
tweak) and separately repair the D2SQL binding with unchanged opaque-header
checks. These owners are outside approvedTask4. Do not modify them, weaken
acceptance or deploy merely because local tests/current-data timing passed.
Task4 implementation work is preserved; capacity outcome and five-sport
empirical context/model acceptance are not complete. Details/task hashes in
task-4-native-evidence.md; all inherited WIP and untracked packages retained.

## Task4 scoped implementation reviewed — 10 September 2026, 22:01 UTC

Product checkpoint52189a6; report checkpointfc7f0c7. Real TDD reproduced eight
cold builds instead of one fitting maximum basis; tests also exposed the
last-encoding mutation and optional-preparation allocation bounds before fixes.
Final focused capacity/live/shared run200passed/9Windows skips in114.95s.
Independent task review finds no actionable product-code defects; scoped code
approved, overall Task4/release NOT complete. Seven protected/source pins
freshly rechecked unchanged. See task-4-report.md and task-4-review.md.

Fresh actual88DB backup/isolated restore/HMAC passed34.74wall s, new stage
betboy-live-backup-pknwmr9p; source context hashd304c164 unchanged. Exact7b6
native replay failed299.992CPU/300.651wall,child-9,no report. Corrected phase
trace proves one60.699CPU cold basis,10original checks,then9completed full
snapshot-feature calls12.859–14.178s each; tenth deliberately interrupted at
diagnosticCPU275. This is NOT an uninstrumented acceptance pass.

Final fc7 archiveSHA1574c963 is sealed underbetboy-capacity-code-b38toqe5.
Its exact native CLI PASSED the current input at285.297CPU/285.388wall seconds,
321584KiBRSS,exit2 exact incomplete/transport-only report,all counts matched,
input unchanged. Only14.612s wall headroom; growth remains required. Native
DAC controls passed3write denials/8unsafe classes/parity. Separate clean LF
QA worktree is detached atfc7f0c7 and running the complete new suite; b397
outputs are retained. Final focused Linux tests are running. Receipt-plus-
consumer growth generator is in preparation; root staged only a new synthetic
working copy underbetboy-task4-growth-mxqhafsc, no live/old fixture edit.
No main push, updater exchange, app deployment, source-data change or cap
increase. Root owns integration/index/push/VPS; the growth-fixture agent writes
only its ignored QA generator. Earlier WIP/worktrees and evidence are retained.

## Approved continuation — 10 September 2026, 21:24 UTC

User explicitly approved the shared fully validated Tennis history basis with
separate historical cutoffs and unchanged full checks/limits. Task4 in the
same plan records the bounded implementation and RED/native acceptance.
Fresh Git check: repair46380d5, GitHub main2dd1116, no tracked WIP; inherited
untracked review packages remain untouched. Existing isolated repair worktree
is reused. Task2/3 product bytes are frozen; new source/native QA and release
are still pending. No repeated directory mode change is permitted/needed.

Preflight interface/self-consistency check:

| Tasks | Producer/consumer or internal check | Result |
| --- | --- | --- |
| 1/4 | VerifiedReceiptMapping proof -> shared encoded histories | Reuse proof unchanged; no new decoder or raw trusted flag |
| 2/4 | Exact D4 CLI/report -> online/quiesced updater checks | Public interface and twelve limitation strings unchanged |
| 3/4 | Exact release replay -> updater-only installer acceptance | New actual-input evidence required before promotion |
| 4/4 | Shared basis vs prefix admission and eviction tests | Global64MiB includes pending; complete cold fallback required |

Ruling: validated metadata preplanning may alter which malformed original is
reported first, but all formerly rejected inputs must still fail and individual
original/snapshot replay order stays unchanged — no first-error order is part
of the D4 contract — if incorrect, error precedence needs rework, not data changes.
Ruling: preserve this existing tracked ledger and all old evidence despite the
skill's scratch-cleanup convention — continuation/audit evidence belongs to
the user — cost is retained small documentation files, not changed runtime.

## Previous checkpoint — 10 September 2026, 21:05 UTC: RELEASE HOLD

The explicitly approved12-directory mode procedure completed at20:35:36UTC;
all original UID/GID/inodes preserved, original metadata durably saved. Real
UID997 can still write all12 directories; UID995 with app supplementary group
cannot. Fresh full88DB backup/actual isolated restore/HMAC passed in42.60s.
See `task-3-live-rollout-20260910.md` for exact hashes/stages and evidence.

BUT the uninstrumented b397 CLI on the current114,929,664-byte sealed input
failed at300.067CPU/300.163wall seconds, child-9, no report,362,972KiBRSS.
Input remained unchanged. Main and VPS remain2dd1116 with old updater74b1c4b1;
no main push, exchange, deployment or resource-limit change took place.
The actual data now has10 originals/snapshots at5 cutoffs (previously4 at2),
despite only810 additional receipts. Phase tracing confirms repeated62–68CPU
second cold history builds, with28,432,021bytes per full cached copy. The
old synthetic growth fixture did not grow the number of replay consumers.

Independent final review explicitly says RELEASE HOLD. Shared-history-basis
architecture is proposed for discussion, not implemented. Its permission
question is pending. The whole exact-b397 Windows suite has now completed:
6897 passed,30 skipped,97 subtests passed in1704.03s, zero failures/errors;
tracked QA clean. XML SHA1596c19324d7535c4fd057a362f4aefa3cc5f4fe38b4b7956105bc7b3fef5fbe.
This is not a substitute for the failed real profile. The bounded trace
confirmed three complete cold builds, four evictions and a fourth cold
rebuild at original8; no snapshot feature call was reached. All native QA
and this Windows run are finished. Stagehelper/A0/P4b3/Cricket and all existing
histories/outputs remain untouched.

## Approved continuation — 10 September 2026, 20:27 UTC

The user explicitly answered yes to the exact twelve directory mode changes
0775 to 0755 documented in `directory-mode-preflight-20260910.md`. Preserve
owners, groups, contents, services, keys and databases, and durably save the
original metadata before changing a mode. The exact reviewed procedure SHA
`8be3d721660d7438a251628ea58c3e61a64f760d96d69fee4d6a82d22ebfe304`
is unchanged. Fresh read-only health confirms the old production HEAD/updater,
HTTP200/ok internally and publicly, seven active timers, and the still-failed
tennis service. Actual mode repair, fresh backup/restore and rollout results
must be recorded separately below; user approval alone is not execution.

## Previous checkpoint — 10 September 2026, 19:45 UTC

Code `4205db82bb234f0aa07a43510db0576811556090`, installer SHA
`bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`.
Task1 current/three-growth native profiles and Task2 code/native controls passed;
largest-growth headroom remains about one second, not a future-growth promise.
Task3 independently rereviewed: final451 Linux tests passed; actual isolated
transaction/DAC/lock/SIGTERM/SIGKILL recovery and unchanged CPU300/wall600+10,
AS/output/RSS boundaries passed. Whole final production-check function now
passes read-only with the real historical complete marker and empty env.
See `task-3-native-evidence-20260910.md` for failures, fixes, hashes and limits.

Production remains `2dd1116` with installed updater `74b1c4b1...`; no repair
exchange, application deployment, marker/key/database edit or mode correction.
The user approved versioned QA archive transfer. Separate permission to change
exactly12 existing0775 directories to0755 is still pending; the complete real
backup producer fails closed until that boundary is resolved. Fresh full real
backup/restore/HMAC, measured exact-target D4 and final rollout remain open.
The broad exact-LF e2 run ended with4 failed,6877 passed,30 skipped and97
subtests passed in1647.97s. Its four old server-job contracts were ported with
actual phase/launcher/enumerator/device and error-propagation controls; the
independent review's additional test gap was closed. A later native old fixture
failure was proven to reuse a freed inode; e903 makes the intended distinct
identity deterministic, preserving the record-identical recycling limitation.
Final test-only freeze `e90320c`: independent APPROVED, fresh native Linux trio
541 passed / 0 skips in 46.73s. All product/helper bytes remain 4205/6ba.
The full clean exact-LF Windows suite at e74 completed: **6897 passed,
30 skipped, 97 subtests passed in 1607.26s**, no failures/errors. Every later
delta is tests/docs only; product code is identical. Root then advanced the
clean QA worktree to e903 and reran its only changed test file: **83 passed,
7 Windows skips in 14.28s**. The full suite was not rerun at e903; do not
mislabel the two executions. Both QA checkpoints remained tracked-clean.
See the native evidence and regression/triage reports for exact XML hashes,
preserved failures and explicit identity-generation limits.

Fresh read-only server check at 19:40–19:41 UTC: app remains `2dd1116`,
installed updater remains `74b1c4b1...`; app/Caddy and all seven timers are
active/enabled. Internal/public health, including a separate Windows client
request, returns HTTP200/ok. The known `betboy-tennis.service` failed state
remains visible; it was not cleared or represented as fixed. No service,
timer, application, key, marker, database or directory mode was changed.
Cricket and unfinished source/empirical model work remain outside this repair.

## Earlier chronological evidence (superseded where noted above)

- Task 1: initial code `b333c3c`; lifecycle fix `41067c0`, report `3967778`. Independent fix re-review APPROVED: stale Mapping revival is closed. Final targeted fix checks124 passed/12 skipped,22lifecycle cases and1actual protected-final guard. Real-data performance is still a separate HOLD; no release acceptance claimed.
- Task 2: waiting for Task 1 review; streaming normal updater and pre-downtime full capacity proof.
- Task 3: waiting for Tasks 1-2; narrowly pinned repair installer, Linux real-backup evidence and controlled release.
- Baseline: 332 passed / 3 skipped, 45.69s, exit 0; `.pytest_tmp/capacity-baseline-01.xml`.
- Production unchanged by repair so far. Existing main/VPS release `2dd1116`; installed updater SHA `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
- Frozen A0 and P4b3 branches, protected stage helper, existing keys, account data and all historical receipts remain out of scope.
- Fresh real backup: `betboy-sqlite-20260910T140039Z.zip`, 88 verified / 0 pruned. Old-reader diagnostic against isolated 99.375-MiB copy completed in173.319s, peak836908KiB; current inventory6artifacts/4snapshots/47497receipts. See `live-capacity-evidence-20260910.md`.
- Provisional pre-fix Task1 native BetBoy-user DAC checks:3write/rename/SQLite denials;8unsafe-fixture classes rejected; small memory/sealed reports equal. The bounded real-copy new-reader attempt ended without a final verification report (supervisor exit1). Targeted first-history profiling completed with an intentional20CPU-second diagnostic stop: repeated owning decoding/selection dominates. Four originals and four snapshots share two ATP cutoffs. A bounded reuse proposal is pending; this is not a successful capacity run. Input and installed updater hashes remain unchanged.
- Task2 integration preflight is complete and its narrow path/phase/legacy/resource clarifications are incorporated into the plan. Helpers/units remain unchanged.
- Task1 bounded immutable cachec3bac37 completed the exact real-copy CLI in229.188s/350844KiB, with complete unchanged counts/limitations. Schema-lifetime followup7d6595e/4fad098 is independentlyAPPROVED. Corrected-source nativeDAC3denials/8unsafeclasses and7actual interleaved filesystem changes all pass. Full corrected-source/growthcapacity gate remains open; largestfixture benchmark running.
- Task2 fresh implementer has completed read-only preparation and is authorized for REDtests only. No updater production edits yet. Task1 further performance investigations remain read-only while that test writer is active.
- Largest exact4fad098growth run failed at300.040CPU seconds (child-9),312792KiBpeak, noreport; sealed input unchanged. Task1 validation-owned cutoff-iteration refinement is approved inplan; do notraisebudgets. Task2RED-only slice624280d is committed and writerpaused; no updater implementation yet. Correctness/nativeDAC are distinct from this opencapacitygate.
- Current checkpoint: Task1 cutoff refinement8249c288/report73e6abd independentlyAPPROVED (20targeted independent pass;213focused author pass/12skips). Native generation3 still fails at299.949CPU/301.154wall/352636KiBRSS,child-9,noreport,input unchanged. Further Task1 work is read-only phase/cache diagnosis; capacity remainsHOLD.
- Task2 is now the sole implementation writer; streaming/phase-bound before-downtime preflight is in progress, not yet coherent/committed. Task3 read-only preparation complete, no edits or VPS actions. Production and installed updater remain unchanged.
- Task2 coherent **incomplete** checkpoint43bfd0d:262hooktests pass,syntax/diffclean. Cross-phase config binding and further producer/WAL/identity/resource/recovery coverage remainopen. Writer relinquished for Task1 covering-cache refinement; no Task2completion or deploymentclaim.
- Third Task1 refinement is specified inplan after exact current-copy phase/cache measurement and verified later-first original order. A completed later same-tour selection can provide its exact earlier clock-prefix under unchanged inventory proof; ownerfeatures/allphysicalchecks/budgets remainunchanged. Implementation and independent/nativeacceptance are pending.
- Third Task1code4db6118/reportb389b2c:234adjacentpass/12skips,21newcoveringcases, independentreview/nativegreatestgrowthrunning. Task2regainedsolewriter for remainingimplementation/REDcoverage+4independentcheckpointfindings. Linuxcheckpoint261pass/1unitDAC-portabilityfail; no productionmutation.
- Thirdrefinement correctnessindependentlyAPPROVED21freshcases, but4dblargestCLI stillHOLD at300.342CPU/301.451wall/354292KiBRSS,child-9,noreport,inputunchanged. Directgrowthphase/profilediagnosiscomplete:physical147.192s,onecold76.698s,covering4.202s; additional query-traversal proposalread-only. No budget/source/math changes or productiondeployment.
- Task2followupcodebdd5731/report23dac3b:313focusedhooktests pass in39.24s,syntax/diffclean; reviewer-candidate REDs anddirectWAL/recoverycoverage recorded. Independent/nativeacceptanceremainopen; solewriterrelinquished. FourthTask1traversalrefinement nowapprovedinplan withallownerchecks/LEFTJOIN/protectedproof preserved, implementationnext.
- FourthTask1 code c4e20e0/report0fbd757:264adjacentpass/12skips, actual final guard once; independent APPROVED with30streamed+20cutoff cases. Exact largest native CLI running, not yet accepted. No owner/math/cache/schema/budget changes.
- Task2 bdd5731 exact Linux QA:313passed in37.60s (38.317supervised), normal SSH uid1000, no production change. Final independent review nevertheless found two Important discovery groups (silent traversal errors, case-sensitive DB omissions); native real uid997/EACCES corroboration recorded in task-2-final-discovery-review.md. R2 regained sole implementation writer for scoped fixes only. Task3 remains preparation-only; production main/updater unchanged.
- Task1 c4 greatest/current/generation1 exactCLI profiles PASS with full unchanged reports and input. Largest298.846wall has verylittleheadroom; generation2stillrunning, nofuturegrowthguarantee. FinalreaderDAC3/8 and7nativeinterleavings pass.
- Task2 c2cb1c9/reportffce3c2:332focusedpass; nativefullchain/actualHMACnegative/mixedcase/OSDAC/retainedFD/EACCES PASS. Independentreview stillidentified Unicodecasefold-vs-find parityP2; R2aloneimplementing principledcommonenumeration. FixedlauncheractualASexhaustion/output/rolechecks separatelyPASS. No productionmutation.
- Task3 RED-only slice is prepared:35expectedmissing-installerfailures, no errors/skips; testfileandreport only, no installer. Writer relinquished while Task2 finalparityisclosed. Controllerreadtest/reportfully; Linuxunitmetadata portabiltynote delivered for laterwire-up. Do notmistakeREDcollectionforimplementation/recoveryacceptance.
- Task1 native current+all3growthprofiles nowcompletePASS atc4; generation2finished256.521CPU/256.711wall/348440KiB,fullreport/inputunchanged. Largestmarginremainsexplicit. Task2Unicodecode690dd16/report0541080:339focusedGREEN,independent/nativefinalchecksnext,writerreturned. Task3stillRED-only,notimplemented.
- Task2 final code `6ba2c68` / report `9e97f2b`: 340 local tests passed in48.90s; independent combined review APPROVED with14 fresh targeted tests and actual prior-version RED/current GREEN metadata reproduction. Native690 full-chain Unicode controls and339 Linux tests passed. Exact6ba native confirmation remains pending an explicit QA-upload approval after the approval reviewer rejected that transfer; no workaround attempted. See `task-2-final-independent-review.md`.
- Task3 now has the sole implementation writer. Its35-test RED slice was committed in `a435c65`; the installer, additional behavioral tests and independent release review are in progress. Required existing Task2 stdlib seams may be copied mechanically with byte-equality regression checks, not runtime-sourced from an updater main. Root performs only separate controller documentation/ignored diagnostics and will not stage or commit while that writer is active. Production remains unchanged.
- Task2 exact6ba native gate subsequently PASS: user approved QA archive transfer,340Linux tests passed in39.49s, actual root/app/backup metadata restoration and full synthetic archive/HMAC/Unicode/DAC/FD/EACCES controls repeated successfully. Fresh real producer then correctly refused twelve existing0775 directories; no archive acceptance and no source mutation. Separate extra mode-only authority is pending; no unsafe g+w exception was introduced. See `directory-mode-preflight-20260910.md`.
- Task3 review checkpoint `ce1021ee1f80e68b4a35c29e85fb70b857b27fa0`:409targeted passed/1Windows-flock skip in58.42s; installer and report committed, not pushed/deployed at this checkpoint. Author relinquished writer; independent full review and native tests are in progress. Frozen separate LF QA worktree `context-capacity-final-qa-20260910` now points toce1021e, no full-suite result yet. Current installer SHA8476a5a9a4956245ddb4026f5aff9bb1c8db980859d34fc129a28d453bf415f7. Whole-plan/model-source work remains separate and incomplete.
