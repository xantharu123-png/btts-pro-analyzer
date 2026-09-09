# P4b1 independent review — existing native team-sport capture

2026-09-09. Read-only source review in
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-p4b1-capture-20260909`.
Frozen HEAD `b2b7d3437b61a3b9e635f2b45808b0b7cadfa97c`, compared with actual
parent `1b77286d06f9731c1ffa38ba3d408f20fff1b02e`. Git was clean at the beginning
and after all tests. No source, owning test, legacy fixture, Git reference,
production database, provider, VPS or dependency was changed. Only the new
ignored review probes, their temporary databases, XML and this report were
written. No full repository suite was run.

## Disposition

**Bounded PASS: no qualified new source finding in this seven-file packet.**

This covers the four additive existing-response capture seams and the closed
native status/identity receipt reader/selector. It is not completion or
qualification of the later P4a/P4b alias resolver, source-to-model assembly,
player/roster/TOI sources, D1/D2 learned effects, D3 worker/consumer connection,
D4 production replay, deployment, or live betting quality.

Own verification: **265 existing/owning/actual-parent cases passed**, followed
by **46 independent qualified cases passed**. One additional reviewer test
with an incorrect WAL lifetime assumption is preserved and expressly
deselected in the final qualified run. It is not a source RED or a silently
skipped platform failure. The genuine replacement WAL controls both pass.

## Material read and verified

Read the entire owning audit, both new source modules, both new test modules,
the complete two scanner/history diffs, actual relevant scanner methods and
B1 append/read/hash/index code. Also read the entire actual-parent QA module
and P3/P4 preflight at
`.worktrees/review-sports-original-20260909/.pytest_tmp/p3-p4-live-envelope-preflight-20260909/PREFLIGHT.md`
(primary-checkout-relative), SHA256
`36bf0e24ae63cd6e0bf53128ff1eb69e3279d3e1d6dfa8cd32c9f0e7078a2f7e`.

The source diff is exactly seven files: two new sources, two new tests, audit,
ten additive scanner lines, and the history observer import plus its narrow
JSON-assignment/callback split. The frozen parent QA actually executes Git
parent source blobs, rather than substituting a rewritten approximation.

## Independent evidence and conclusions

1. **Actual successful JSON before lossy parsing.** The executed owning tests
   enter the real existing NBA, EuroLeague, NHL schedule methods and the real
   history `fetch_page`; fake responses replace only their existing HTTP call.
   Success is captured before status/date/terminal parsing. The independent
   history probes pass the same mutable decoded object to a parser that clears
   it. Pending B1 bytes still match the original received projection. There
   remains exactly one existing GET and the order JSON → receipt → parser.

2. **No hidden provider/clock behavior by default.** Actual-parent comparisons
   retain scanner outputs, IDs, URL/query/header arguments, error dictionaries,
   completed-cache bytes, clock counts, and request budgets with capture enabled
   and disabled. Actual Cricket completed-history comparisons remain byte-equal
   in both modes; it never samples this capture clock. Warm legacy cache data
   is not relabeled as a newly observed native response. My real existing-cache
   DB control returns no B1 rows and preserves its main-file bytes.

3. **Whole native correction lineage.** New SQLite probes reverse actual home/
   away identity, move the native schedule, and restore the original full event
   across three real receipt instants for all three providers. Earlier cutoff
   reads retain the earlier revision; exact later cutoffs select the complete
   later tuple. A same-team pair, boolean/float participant ID, absent/naive
   competition time is retained as an unknown current receipt rather than
   falling back to the older valid final. Scheduled/started/cancelled and
   equal-time conflicting revisions are exercised in the owning suite too.

4. **Status is not qualification.** `complete` remains false; no observation
   manufactures actual end, regulation time, minutes, goalie starter, injuries,
   full history or a healthy player. A known cancellation can be a consistently
   reported lifecycle value; `available` is not match eligibility or freshness.
   EuroLeague `played=false` remains only `not_completed`. Missing neutral is
   null, not false. Price fields and unreviewed metadata do not enter the new
   receipt or old output identity.

5. **Exact selector versus future alias resolution.** An independent ESPN
   witness preserves an original competition under native key 401810101 with
   outer ID 123, then an outer-ID-only incomplete correction under key 123.
   Both causal rows and their co-occurring alias are retained. The small exact
   selector correctly yields unknown for key 123 and still yields available
   for the different key 401810101. This is expressly the accepted boundary,
   not proof that the latter remains usable for P4 assembly. The future owning
   resolver must consume the whole pool and resolve this shared identity; it
   must not promote this exact-key selector into an alias/approval authority.
   EuroLeague composite season/game and case-preserving identities remain
   B1-only. Same native payload obtained through schedule/history requests at
   the same receipt instant preserves two references without inventing a
   contradictory native event.

6. **Physical SQLite integrity before pruning.** Independent corruptions
   replace each of the eight textual receipt/index columns with a BLOB, place
   matching JSON text instead of the required payload BLOB, remove one of the
   two B1 tables, or rename the receipt-clock column. The reader raises typed
   integrity errors even for an earlier unrelated cutoff. Owning cases also
   check rehashed envelope/projection changes, nonfinite values, mismatched
   SQL indexes and missing content. Returned selections are deeply detached.
   This is an integrity check of the existing claimed receipt inventory, not
   an HMAC/source-authentication or arbitrary whole-database rollback promise.

7. **Live WAL, not a stale immutable copy.** One qualified probe copies exact
   actual B1 record bytes through a real SQLite WAL writer while retaining its
   live connection; another keeps a genuine earlier read snapshot open while
   the actual B1 `append_observation` adds a newer started revision. WAL bytes
   are nonempty, the older keeper still sees one row, and a new status reader
   sees the newer committed revision. The established `_reader` uses mode=ro,
   query-only and trusted path/companion checks; synchronization sidecars are
   allowed. No new race-proof or POSIX/DAC claim is made by these Windows tests.

8. **Partial capture and failures stay observable.** Independent probes feed a
   valid first response followed by an invalid body: one real receipt survives
   and report status is partial with the closed reason. Executed owning tests
   prove later worker/parser exceptions drain accepted bytes, nested ownership
   is rejected, threads retain separate collectors, owner state resets, and a
   real persisted collision/storage failure escapes the old provider catches.
   `captured` is not asserted to mean every event/source was completely modeled.

## Exact reviewer run ledger, including mistaken setup

All commands used the quality Python, `-B -m pytest -q -p no:cacheprovider`,
unique `--basetemp`, and corresponding `--junitxml`. No original owning RED or
reviewer probe was edited after execution.

- `p4b1-review-focus-01`: actual two new modules, completed-history/prematch/
  original-capture tests, and unchanged parent QA: **265 passed, 6.15 s**.
- `p4b1-review-probes-02`: `test_independent_capture.py`: **23 passed, one failed,
  1.50 s**. The failed reviewer control asserted a nonempty `-wal` merely after
  opening an idle connection and another completed append. It did not hold an
  actual read snapshot; the WAL file was already absent. The source reader was
  not reached by this assertion, so it proves no stale-reader/source failure.
- `p4b1-review-qualified-03`: separate `test_qualified_controls.py`: **22 passed,
  1.42 s**, including real uncheckpointed writer bytes and negative integrity/
  identity controls. Its initial comment that A1 explicitly selects DELETE
  journal mode was an incorrect reviewer hypothesis: the inspected
  `model_artifacts._connect` contains no such PRAGMA. That file/comment is
  preserved, not rewritten; the correction is explicit here and in the new
  `test_actual_wal_append.py`.
- `p4b1-review-final-04`: all three unchanged probe files, with only the exact
  original WAL setup case deselected by name: **46 passed, one deselected,
  2.16 s**. The added actual-append control holds a real older reader snapshot
  and proves the missing lifetime condition without changing production code.

Final independent invocation from this worktree:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider .pytest_tmp/p4b1-independent-20260909/test_independent_capture.py .pytest_tmp/p4b1-independent-20260909/test_qualified_controls.py .pytest_tmp/p4b1-independent-20260909/test_actual_wal_append.py -k "not test_committed_wal_correction_visible_while_existing_connection_is_open" -o "pythonpath=. tests .pytest_tmp/p4b1-independent-20260909" --basetemp=.pytest_tmp/p4b1-review-final-04 --junitxml=.pytest_tmp/p4b1-review-final-04.xml
```

## Frozen identities

All are actual raw SHA256 values independently recomputed after the runs.
They are not cross-platform line-ending equivalence claims.

| Source/test/audit | SHA256 |
| --- | --- |
| context_sources/team_sports_capture.py | 7201d9d2596a7830485bb744407af9c8a35c5ecc422b0dd2a98c5acb1995c199 |
| context_sources/team_sports_status.py | 1a11dab252f7a028171f0f85504b00ffce2d42f581f38920e6d7bfa11a4cbb2c |
| scanners/basketball_scanner.py | faa71900c0c22f78c4aaffc75c8a10e61d16a0077427f1274c915915ea36bc6d |
| scanners/completed_history.py | cf9b7354226f0192d4e3fb6d5324bebc86d4e8541ca3ab4a71fe620fbe7ad96a |
| tests/test_team_sports_capture.py | b9c0a1db5184d704d3558adba03122b8c2a8e0b74963fceea78ecdfbdf38eaf4 |
| tests/test_team_sports_status.py | fee1d400a73c931336ac1a44c0ac0d811611897e9474a6c40b18d7861a896d04 |
| docs/audits/2026-09-09-p4b1-team-sports-native-capture.md | 0d00e886f314f9d3e629a3a5a6a971a95de276a7157fbeceb97cd7a8d96ff587 |
| .pytest_tmp/p4b1-owner-20260909/test_actual_legacy_parity.py | d6b1d1a1c2ac99019de4f3154622ae8bfebfa0dd427606f3c8faebbc7ee487a3 |

| New immutable independent evidence | SHA256 |
| --- | --- |
| test_independent_capture.py | d9121cd16b6cb8f289b8bdf57a562d24e2fc08d4e0d2ea67a7c974090567ec9e |
| test_qualified_controls.py | 000e14fc07ddb226fd0ceffbb6cc616b5d1420377ed129bb07e8ce5893133574 |
| test_actual_wal_append.py | 33979d143185001eb7393576fb6b232c5782ad6fcb7720ba26b44ef24a786493 |
| .pytest_tmp/p4b1-review-focus-01.xml | b5b892cfc4a6b68d1383c4dc3a057ef06b39d807ce11c25163e247ea61a973e5 |
| .pytest_tmp/p4b1-review-probes-02.xml | 5f8850d0f147c6ec58fb0103770d29f9fddc4e3d774ddaca35ccda417b4c8990 |
| .pytest_tmp/p4b1-review-qualified-03.xml | 07d3fb437f6999336964cfcc843e139940bd3dc73c3e551abe5b85d606b23518 |
| .pytest_tmp/p4b1-review-final-04.xml | cf3ab3818fc560f3150dc66728dc562385331040abfbeaf75c0c5958c1656777 |

The owning original RED XML (`first-red-02`, `status-red-04`, `typed-red-08`,
`final-edge-red-12`) and final `focus-13` were also rehashed. All match the
owning audit exactly. They remain in place and unchanged, including the
author's documented earlier setup errors. This report's digest is sent
separately to avoid a self-referential identity.
