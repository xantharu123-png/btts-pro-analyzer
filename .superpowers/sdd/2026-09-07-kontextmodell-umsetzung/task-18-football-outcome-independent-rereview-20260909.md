# Independent F1 re-review: football FT outcome capture

Date: 2026-09-09. Reviewer: `b6_tennis_load_20260909`.

**PASS for the bounded source-capture packet and F1 correction on the exact
freeze below. No new findings.** This is not a D2 empirical approval, full
integration regression, production deployment or validation of live FT data.

## Verified freeze and correction

Worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-football-outcome-capture-20260909`.
Exact clean HEAD: `af7375b11612001fd84ee9f06168a982f1d2ea2b`, parent
`684865e583bcf4377df588aaa911b23832f23e57`.

Read the entire narrow three-file fix diff, the complete owning audit append
and all eight new permanent tests. The implementation removes only the premature
source/kind SQL filter: `_SELECT` enumerates actual receipts; `_decode_receipt`
validates content, receipt, types and index/body identity; only then is the
owning source/kind/schema chosen. The full inventory resolves before any new
capture publication. Existing B1 storage and native normalization are unchanged.

| Frozen target | Raw SHA-256 |
| --- | --- |
| `context_sources/football_capture.py` | `fa4adf76c31fb1fa84f2296f8ba735ca0877fc3d181ff7c62ce53e51a3faccec` |
| `tests/test_context_football_result_capture.py` | `1475c0074d3ecee12157ed2770de84c54b32afbb3cd8dae0ceebbd86b17d16af` |
| `docs/audits/2026-09-09-football-ergebnis-capture.md` | `04d7ee273ba94fae00436e21cc7eae80b2e83e0cd42e2ded673244383ce1e6c8` |

## Own executed results

**510 passed, 0 skipped, 15.42 seconds** in `rereview-01.xml`:

- All **62 original independent repair/control probes unchanged**, including
  the original **six RED cases**, now pass.
- **434 existing/permanent cases** pass: the original nine-file 426-case focus
  plus the owner's eight new index-corruption regressions. Both actual B1 tables
  remain byte/value-identical after each propagated corruption failure.
- **14 additional independent inventory controls** pass:
  - six combinations of transport-valid but non-owning source/kind/schema and
    presence/absence of a real watch remain unpromoted; the valid real watch
    still receives its own outcome and foreign records remain unchanged;
  - six later-inserted non-watch corruptions (source, kind, subject, body,
    orphaned content and noncanonical clock) are detected before publication,
    with both real SQLite tables unchanged;
  - an owning-schema claim with an invalid native scheduled body cannot certify
    scope even though its generic B1 transport was properly hashed;
  - a decoder spy verifies every existing receipt is visited once before the
    native watch projection, including otherwise ignored sources/kinds/schemas.

The original two **positive defect witnesses** were executed separately without
changing their assertions. They now produce **2 expected diagnostic failures**
in 2.23 seconds (`damage-fixed-01.xml`): both raise `ContextIntegrityError` from
`_decode_receipt` through `_previous_prematch_observations` before reaching the
formerly unhealthy `no_receipts` / `captured` reports. This is direct evidence
that the old bad state is no longer reproduced, not two extra passing tests.
They were not counted among the 510 normal green cases.

No full-suite run was made for this deliberately bounded re-review. Root's
integration suite and any eventual production validation remain separate.

## Preserved original and new probe identities

The original source probes and original report were not edited. They retain the
same hashes as the first review; only new control/report/XML files were created
under this ignored review directory.

| Review artifact | SHA-256 |
| --- | --- |
| `test_independent_result_capture.py` (original unchanged) | `45f89ca10ff8d1a18ce134cbeea8b07f02ac68e89a730ecc7cbb25184547dc49` |
| `test_damage_witness.py` (original unchanged) | `620fc493a4492bacc1bf113c1d10ce3c596bfa3d7ad2518d38b1406146053625` |
| `REVIEW.md` (original unchanged) | `8ca1924fc5882c7df0bd48e7e97f3b07e6f300fe6b5cfd575797253a0946fd54` |
| `test_fix_inventory_controls.py` | `9f9bd5968e8c15662fa3fb1dce9393b41d9efb8d1327a836b3b4e16f5d18b9d7` |
| `rereview-01.xml` | `e993eefd915659f77d36d87fde3173e471892615fb4ce8a4b00cd58ea2c6ed12` |
| `damage-fixed-01.xml` | `939a57e87cf05f0f92c433ceaa7320c48cfc25d6dc407875da502726d3de0421` |

Target source, permanent tests, owning audit and Git status were rechecked after
these runs and stayed frozen/clean. No source edit, commit, provider call, merge,
push, VPS action or money/history modification was made by this reviewer.

The earlier limits remain intact: capture uses only already executed actual
FT-tail/season callbacks and actual prior native prematch B1 receipts; a watch is
not old event/model/participant authority. Native bodies are inspected here,
so this reader is explicitly not a D2 label-free pre-opening helper. All new FT
scores and mutations in these probes are synthetic. No new source coverage,
historical publication, match duration or empirical predictive benefit is claimed.
