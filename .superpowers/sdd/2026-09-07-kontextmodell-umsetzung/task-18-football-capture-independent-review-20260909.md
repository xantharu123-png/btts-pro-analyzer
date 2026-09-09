# Independent review — existing football receipt capture

Date: 2026-09-09. Reviewer: `b3_shared_snapshots_20260909`.
Owning worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Target commit: `ecf92007f46c5e8b85cb24b6f7208cb71240cac4`.

## Disposition

**REQUEST CHANGES: one P2 owning request-scope finding, reproduced by three
frozen RED cases.** No P0/P1 capture finding in the bounded reviewed surface.
The other 87 independent cases passed. This is not approval of live capture,
an empirical effect, complete D3 integration, D4 semantics or production use.

The controller's HEAD advanced to `908667ec0d682b192f5ac33c20c915f79b3259d4`
during this review. The six target file hashes stayed exactly unchanged;
`git diff ecf92007 -- <the six files>` was empty at closure. No source, tracked
test, Git state, protected helper, server, provider, credential, existing output
or production database was changed by this reviewer. New review files and
isolated synthetic databases are confined to `.pytest_tmp`.

## F1 — P2: exact NS request is widened to any normalized scheduled status

Location: `context_sources/football_capture.py:88-94`, particularly line93.
Discovery recognition at lines70-72 requires an explicit native request
`status="NS"`. Its returned row is then checked only through the lossy derived
`ev["status"] == "scheduled"`. The existing native normalizer intentionally
maps native `NS`, `TBD` and `PST` to that common Event status.

Actual public-path reproduction:

1. Use the real `ChallengeDataProvider.upcoming_fixtures(94, 2026, date)`.
2. Return a true HTTP200 `requests.Response` with a complete native-shaped
   fixture envelope, matching requested league/season/date, but native short
   status `TBD` or `PST`, not the requested `NS`.
3. Make the already-budgeted explicit injuries request for the same native ID,
   at its own later actual receipt clock. It may contain one absence or be empty.
4. Exit the real capture scope and inspect the real temporary B1 SQLite store.

Observed: discovery is accepted without an issue, supplies the native identity
for the later injury receipt and persists a base plus availability records.
The report says `captured`. The issue is exact source/request provenance, not a
claim that a missing injury list is healthy; these availability records correctly
retain incomplete coverage. No prediction/price effect is applied by this packet.

Expected: a native returned status outside the exact discovery request cannot
provide this request's joining evidence. As with wrong league/season/date, the
capture report should be partial and that response should supply no observations
or later binding. The legacy reader's existing result behavior remains separate.

Frozen RED test nodes:

- `test_capture_adversarial.py::test_out_of_scope_discovery_cannot_lend_identity[wrong-status]`
- `test_capture_legacy_and_boundaries.py::test_exact_requested_ns_native_status_boundary[TBD]`
- `test_capture_legacy_and_boundaries.py::test_exact_requested_ns_native_status_boundary[PST]`

Minimal correction: validate native `fixture.status.short` against the actual
requested discovery status inside this discovery-only check. Do not change the
generic football Event normalizer or introduce a global TBD/PST ban. Six paired
controls in `test_capture_status_scope_controls.py` demonstrate that explicit
native single-ID/batch-ID capture for NS/TBD/PST remains valid under the existing
owning normalizer. Native FT/CANC/1H discovery controls reject, and NS passes.

## Evidence and actual scope

Read the complete new capture module, complete owner permanent test file,
complete owner audit, all three inherited-file diffs and surrounding provider,
manual/automatic/state paths. Read the D3 brief, current B1/B3 and D1/D2
decisions, unchanged source/provider/outcome normalizers, B1 append/read code
and relevant roster collection selection. The old provider/worker definitions
are extracted from the actual parent commit with `git show`, not rewritten
imitations. Fixture bodies constructed by the reviewer are explicitly synthetic.

Independent tests execute:

- Real provider GET -> capture callback -> owning normalization -> actual B1
  SQLite append/decode, with separate actual receipt clocks and no flush-clock
  substitution, publication invention or source-key persistence.
- True HTTP200/204/206/301/302/307/308/401/418/503 response objects; no redirect
  following, extra calls or captured partial/redirect bodies. Legacy HTTP error
  handling is not reclassified as a new capture error policy.
- Whole malformed/count/paging/error/duplicate/foreign envelopes, canonical
  bounded request IDs, wrong discovery date/season/league and requested-ID scope.
- Earlier/equal/later native identity clocks at +/-1 microsecond; simultaneous
  home/away/orientation/competition/schedule/cancellation conflicts never bind
  injuries. Source evidence is not assigned an earlier receipt on flush.
- Real SQLite duplicate and changed/empty whole lineup revisions; latest roster
  replacement cannot retain a removed player. Two current full conflicting
  lineups remain conflicting. Partial response projection is not published.
- One injected later storage failure after a genuine first append: observer is
  removed, error propagates, the incomplete collection cannot form a central
  expected roster through the real selected B1 reader.
- Nested observer rejection preserves the active owner; another provider cannot
  accidentally feed that observer; later worker exceptions drain valid receipts.
- Existing touched content/hash/receipt-clock/index corruption propagates as
  `ContextIntegrityError`, not a source-unavailable/healthy result.
- Completed FT details produce distinct original/base, result and appearance
  receipts. Reported historical start is not fabricated as actual match end.
- All three actual new worker wrappers against their exact parent definitions.
  The injected scan executes real provider calls and returns a fixed forecast
  control. All old result fields, arguments and request counts remain equal,
  aside from the detached capture report. For manual comparison only the
  pre-existing current `price_checked_at` wall clock is excluded.
- Parent/current provider class parity with capture disabled/enabled on valid,
  empty, malformed, provider-error and paginated bodies: exact old results/errors
  and request count, except the intentional no-redirect request option.
- Closed detached administrative report plus actual `write_state`/`load_state`
  roundtrip. The report does not change old status/errors/forecast counters or
  appear as a new null field in old report-free snapshots.

## Run results and corrections to the review harness

All tests use the repository quality interpreter, `-B`, `-p no:cacheprovider`
and a unique basetemp. No full heavy D2/whole-project suite was rerun by this
reviewer: Root's full suite is separate evidence, not assumed completed here.

| Run | Result |
| --- | --- |
| Existing capture/provider/source/revision/workflow/market/challenge focus, `d3-capture-independent-focus-20260909-01` | 345 passed, 32 subtests, 14.73s |
| Initial 60 own probes, `d3-capture-independent-adverse-20260909-01` | 57 passed, 3 failed, 3.86s |
| Expanded 84 own probes, `d3-capture-independent-adverse-20260909-02` | 81 passed, 3 F1 failures, 6.05s |
| Final 90 frozen own probes, `d3-capture-independent-adverse-20260909-03` | 87 passed, 3 F1 failures, 5.51s |
| Existing focus plus full automated-worker test file, `d3-capture-independent-focus-20260909-02` | 426 passed, 32 subtests, 14.75s |

The initial three failures were not three source findings. One was F1; another
was a harness call supplying raw stored B1 rows instead of actual selected rows
to `expected_roster`. It now uses `observations_as_of`, and independently asserts
no central roster and incomplete/conflicting coverage. The third expected a
generic B1 missing-content failure that is not part of this capture delta:
existing `append_observation` can reconstruct a removed content row when the
entire newly supplied normalized content is exactly the old content's identity.
The separate diagnostic now proves both the prior read failure and the exact
reconstruction behavior, without pretending the capture is a full-database
integrity audit or changing generic B1. No frozen original finding was erased;
these harness/contract corrections occurred before this closure freeze.

Final reproduction command, from the owning worktree:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest .pytest_tmp/d3-football-capture-independent-20260909/test_capture_adversarial.py .pytest_tmp/d3-football-capture-independent-20260909/test_capture_legacy_and_boundaries.py .pytest_tmp/d3-football-capture-independent-20260909/test_capture_status_scope_controls.py -q -p no:cacheprovider --basetemp=.pytest_tmp/<new-review-directory>
```

## Exact freeze hashes

Target hashes matched before and after all own runs:

```text
4cfc0500a823e8268d38baa11298e5db6029a6350aab3075a3e573d4de2cc748  context_sources/football_capture.py
15908bc9723ee16a862d7332022914cdd74319711b480889c6ec1b61e1060414  tests/test_context_football_capture.py
7d7e217282c6e0a9d12aeb38f03340311aaa2895037a79c12226566769535433  challenge_15k.py
44812cd89fbf85bdf01237bb0b249e26832497441e31a83fe549e77b0bf4be36  wettfinder_automation.py
8856e23aeeecfda6e206d7db70652f3c4d9061a08360c8e336a29f7181cee1a0  alternative_markets_tab_extended.py
3b850766e5902d43538a65778751eea4335f1a230f401d9ac4a0787196337c13  docs/audits/2026-09-09-d3-football-existing-receipts.md
```

Original independent probes are now frozen unchanged for owner reproduction:

```text
2db3c59e90a9d03132d107b7172ad47859365b81aec29f610ed5f7373cb2ec97  test_capture_adversarial.py
b07723b399d5cc1f78daf598c89cc076931940d1a9368cda62f8f25cef72bf46  test_capture_legacy_and_boundaries.py
5fd99b81be5001863ffa421bae5cb922030b514863e9d96340c4231622597ad7  test_capture_status_scope_controls.py
```

The final report's hash is sent separately. The controller can now perform the
one narrow correction and request an unchanged-probe independent rereview.
Real provider capture, licensed/complete history, semantic backup, outcome/effect
approval, shared D3 consumers, UI acceptance and VPS activation remain separate.
