# D3 domain reference: shared document type correction

9 September 2026. Narrow authorized correction after the independent review
of `9de9b52ab096c8c08852460dfe8226854014e789`.

Base is exactly that commit. Worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-domain-fix-20260909`;
branch `codex/kontext-domain-fix-20260909`.

## Original finding and controller ruling

The unchanged independent report is
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-domain-review-20260909/.pytest_tmp/domain-independent-20260909/REPORT.md`,
SHA256 `d6648b3b3b671bd239c48adfabf06083d68b36ecedafa14a648de92db50dcd9a`.
It remains REQUEST CHANGES against the original commit, with one P2 finding.
Its three original probe files and all result files remain unchanged.

The closed `ContextReference` constructor already rejected JSON `true` or `1.0`
as schema version `1`. The common automatic-document loader did not construct
those references before comparing model/price/challenge dictionaries. Python
numeric equality therefore accepted that invalid alias. A malformed model ref
could lose its forecast while its supposedly same strict RELEASED row survived.

Root explicitly authorized only the common document acceptance in
`ev_signal_sources.py`, permanent regression tests and this correction audit.
It confirmed the existing whole-document integrity semantics: malformed
provenance rejects that document, not a partial reconstruction with surviving
release claims. A genuinely absent legacy field remains absent/valid. Missing,
below-minimum or expired quote evidence in otherwise valid data is not malformed
model provenance and must not remove its model forecast.

No partial-loader/product redesign is implemented. No new price gate or
general stricter model eligibility rule was introduced.

## Implementation

Thirteen additive lines validate every actually present `context_ref` in all
model, strict-price and challenge rows before any model/overlay dictionary
comparison. They reuse the owning `ContextReference.from_dict` closed schema
and reject its `ValueError` as the loader's existing `None` integrity outcome.
No fields are synthesized, stripped, coerced, normalized or rehashed. Valid
input dictionaries retain their original shape and values.

All other domain/store IDs, JSON forms, UNIQUE/event-input rules, schema and
legacy migration code are unchanged. The separate reader fix, B3 transport,
copy, original sport models, Cricket, money/ticket/settlement and source paths
are not modified. The existing price-blind model/price split remains unchanged.

## TDD and positive controls

New permanent file: `tests/test_context_domain_document.py`, 50 cases.

- Before code: **9 failed / 41 passed**, 2.90 s. Eight actual bool/float schema
  aliases cover model/strict/challenge/all; the ninth rejects a malformed later
  model row even when the first row is healthy.
- After code, together with all 298 previous domain/consumer/workflow cases:
  **348 passed, 26 subtests**, 7.47 s.
- Non-reference null/bool/list/object, unknown kind, string schema, malformed
  key/digest and extra verified claims remain closed failures.
- Other well-shaped but different references cannot match the same model.
- Both legacy-without-ref and linked documents are exercised with no quote,
  below-minimum quote, a playable quote and naturally expired price evidence.
  The model probability stays `.6`, references/row JSON are unchanged, and the
  original file bytes remain unchanged. Provider calls are explicitly forbidden
  during the no-price/low-price/playable read controls.

Both original qualified probe files were rerun before source edits:
**11 genuine failures / 13 passing controls**, 2.22 s. After the correction,
those same bytes plus portable first-review controls give **108 passed /
10 explicitly deselected**, 3.42 s. All eleven original genuine failures are
included and now pass.

The ten deselections are solely the first reviewer file's nine shallow-alias
overlay cases (six invalid initial expectations plus three superseded removal
controls) and its hardcoded original-review-worktree source-location pin. The
qualified JSON-detached file includes the same real mismatch/removal cases,
additional malformed/null cases and the real SQLite concurrent UNIQUE test.
No original file or failed assertion was edited to obtain a green result.

## Execution ledger

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Commands use `-B -m pytest -q -p no:cacheprovider`, separate named basetemps and
JUnit under `.pytest_tmp`. No own full-repository result is claimed or borrowed
from the controller's earlier unrelated full run.

| JUnit | Actual result | SHA256 |
| --- | --- | --- |
| `domain-fix-red-01.xml` | 9 failed / 41 passed, 2.90 s | `3bf443805f9179dac6697b165166c956c349f114f4e79885dbf360cde82213e3` |
| `domain-fix-original-red-01.xml` | 11 failed / 13 passed, 2.22 s | `41706dda566a723c3d95cfb76361a9358dc34de54b670e4657047ed98d1ca03d` |
| `domain-fix-green-01.xml` | 348 passed / 26 subtests, 7.47 s | `7ef64264cdb3da969ca3f7d22b9aae1c9bf10c9c013d2133ad9d3505c6366d8b` |
| `domain-fix-original-green-01.xml` | 108 passed / 10 deselected, 3.42 s | `ce81abd02de68c9a24c0f7f74ca0b36efa51d3caa3903e15967a0321fdbb5061` |
| `domain-fix-integration-01.xml` | 393 passed, 33.37 s | `f98f4943a6765a081941cc6156900e18fe9ea39a4fbce598053014437c8d3a1c` |

The broader integration rerun selected complete RisikoBet automation,
candidates, surface, settlement and settlement-automation suites; the four
context-transport suites; persisted context consumers; Wettfinder surface;
market scope; and Tennis prediction revisions. **393 passed**, 33.37 s.
There were no skips in any correction run. Source loading was also checked
directly against the exact fix-worktree `ev_signal_sources.py`, not the
original review checkout that owns the preserved external probe files.

## Frozen hashes and release boundary

| File | Raw SHA256 |
| --- | --- |
| `ev_signal_sources.py` | `090b11fadbaf32246aff9ebd8afb396c6e2754dfda92d2c386d042f7377c763f` |
| `tests/test_context_domain_document.py` | `9befc9feee8bd69336833b63f4e648a5ebcb8a712ccfe07c9ee5dcc576ef170d` |

Unchanged original witnesses:

- `test_domain_independent.py`: `d6b9f609b748d5152b542efd3939c93b23d2fdacfb408769f1dba0c20a55c8e3`.
- `test_domain_overlay_qualified.py`: `e34d98f55ddf9d75b5adc137498547bae0e7a99888e9c2c2f6d9f0ba0e815991`.
- `test_domain_reference_type_witness.py`: `5dc4bf48712e972a569976018c527a50816d4848e92070515a9c8363d348c410`.

No source call, new producer/UI wiring, D2 model approval, D4 qualification,
browser/UX check, VPS/production mutation or empirical quality claim. Source
truth is not granted by structural reference validation. Independent controller
review is still required before integration. No push or deployment is performed.
