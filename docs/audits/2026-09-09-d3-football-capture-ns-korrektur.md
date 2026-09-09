# D3 football capture — exact discovery status correction

Date: 2026-09-09. Owning worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Controller starting HEAD: `908667ec0d682b192f5ac33c20c915f79b3259d4`.
This is a narrow correction of independent capture finding F1, not a new
source/model/empirical release.

## Scope and correction

Read the complete independent `d3-football-capture-independent-20260909`
review and all three frozen probe files, the complete capture module,
permanent tests, original capture audit and relevant actual provider entries.
The independent report correctly identified that native NS, TBD and PST all
normalize to `Event.status == scheduled`. That normalized status does not prove
the exact request scope of a discovery explicitly requesting `status=NS`.

The sole production-code change adds one native equality in the existing
**discovery-only** request-scope check:

```python
raw["fixture"]["status"]["short"] != params["status"]
```

A mismatched returned status invalidates that entire discovery response as
joining evidence, just like the existing wrong league/season/date checks.
It cannot subsequently bind an injury receipt. The existing detached capture
report is partial; no new public/model error, custom exception or diagnostic
field was introduced. Neither old discovery result values nor request counts
change. There is no additional request, retry, new budget or provider call.

The general football normalizer and explicit native single-ID/batch-ID
queries are unchanged: NS/TBD/PST remain supported there. There is no global
postponed/unknown-status ban, prediction/market/price filter, new model effect,
or change to Cricket/15K/tickets/settlement. Storage clocks and existing
whole-response projection rules remain unchanged.

Only `context_sources/football_capture.py`, appended cases in
`tests/test_context_football_capture.py`, and this new audit were edited.
Inherited `scripts/stage_runtime_databases.py` WIP and unrelated output files
were left untouched. No Git commit/merge/push or VPS/production write was
performed; the controller owns integration and publication.

## Permanent tests and actual RED/GREEN

Sixteen new permanent cases exercise the real provider/capture/B1 SQLite path:

- Exact native NS/TBD/PST for both one-day and inclusive-range discovery.
- Mixed NS plus out-of-scope TBD/PST responses: the whole response must not
  lend the NS row's identity to a later injury receipt.
- Explicit single-ID and batch-ID controls for all three supported native
  statuses, retaining exact native values, actual receipt clocks and two GETs.

All runs used the absolute quality Python, `-B -m pytest -q
-p no:cacheprovider`, unique basetemp paths and isolated databases.

| Actual run | Result | Time |
| --- | --- | --- |
| Unmodified independent three-file package on old source | 3 RED / 87 GREEN | 5.64s |
| New permanent cases, old source after fixture assertion correction | 8 RED / 8 GREEN / 28 deselected | 2.87s |
| All permanent capture tests plus unchanged independent package, fixed source | 134 GREEN | 7.01s |
| Capture, football source/provider/features/model, workflow/market/automation/challenge plus unchanged independent package | 674 GREEN / 32 subtests GREEN | 24.45s |

The first new permanent-test attempt had eight additional fixture-count errors:
the retained native sample contains explicit empty lineups and therefore two
typed collection markers in addition to the expected base/two availability
receipts (five rows, not three). This was corrected in the **new** positive
controls before changing production source. The resulting old-source run had
exactly the eight intended discovery failures. No independent probe or existing
permanent assertion was changed. Both initial XMLs remain preserved.

No tests were skipped in the final focused or regression runs. The 134 cases
are included in the 674 run, not added together. Root's prior full-suite result
4,449/18/97 is separate evidence before this correction; this worker does not
claim another whole-project run or independent rereview of its own patch.

`git diff --check` passed for both edited source/test files. The code/test delta
is four source lines (one guard plus three explanatory comments) and 87 appended
test lines. No removed source/test line and no altered existing test fixture.

## Exact bytes supplied for controller freeze

```text
ae8e0dd25a4003519d35c86d904d807c94b16137765ded0f021b4beb97f91b52  context_sources/football_capture.py
6a3b10167cdec99de2b62863f66bda559e61a918bc05ab2eb250a01b1834a67b  tests/test_context_football_capture.py

914b96cdd593c83c34065956f3c38467f292040a4156a843be2cbed6b8a15e87  .pytest_tmp/d3-football-capture-independent-20260909/REVIEW.md
2db3c59e90a9d03132d107b7172ad47859365b81aec29f610ed5f7373cb2ec97  .pytest_tmp/d3-football-capture-independent-20260909/test_capture_adversarial.py
b07723b399d5cc1f78daf598c89cc076931940d1a9368cda62f8f25cef72bf46  .pytest_tmp/d3-football-capture-independent-20260909/test_capture_legacy_and_boundaries.py
5fd99b81be5001863ffa421bae5cb922030b514863e9d96340c4231622597ad7  .pytest_tmp/d3-football-capture-independent-20260909/test_capture_status_scope_controls.py

bb0bba7fca3eee6a81379cff7efe88857eab01749cb8aaf3c0b65e1b748f3249  .pytest_tmp/football-capture-owner-red-external-01.xml
6e06219be4b8178d4da1f255cd1572819ca6b1fa3df86375185a5564a5931115  .pytest_tmp/football-capture-owner-red-permanent-01.xml
9b7405969ef81f7252a480a1f3528f25bb68722bfe10feab9db7f61578eaa85f  .pytest_tmp/football-capture-owner-red-permanent-02.xml
03e5d227a2c119346d398db0a15b202cdb84f0b05e1b69142e139d4701947ec9  .pytest_tmp/football-capture-owner-green-focused-01.xml
```

The final regression XML hash and this audit's hash are returned separately.
All four frozen independent review/probe hashes matched before and after the
owner correction. The containing commit remains the controller's action.

## Remaining boundary

This corrects the one diagnosed discovery request-scope issue. It does not
establish actual live provider capture, retrospective publication evidence,
qualified injury effects, complete shared D3 wiring, a D2 model approval,
semantic D4 backup readiness, UI acceptance or VPS activation. No new empirical
claim or completed larger-package claim follows from these mechanics tests.
