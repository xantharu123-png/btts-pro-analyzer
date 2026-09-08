# Wettfinder card analysis — implementation report

Date: 2026-09-08. Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/erklaerbare-karten-20260908`. Branch: `codex/erklaerbare-karten-20260908`. Base: `8c3df7978bf074cfe6ce3d9a794f6f60139327ea`.

## Result and scope

The normal Wettfinder now displays one short, deterministic explanation and one compact caution directly inside every featured and additional card. The former technical context checklist and its `Analyse anzeigen` expander no longer reach this public surface. Internal context summaries remain intact for diagnostics. No model probabilities, haircuts, ordering, selection rules, reference-price rules, strict release gates, account/ticket/settlement logic or Cricket behavior were changed.

`forecast_analysis.py` is a pure presentation/projection module. It reads the existing canonical `MARKET_BY_KEY` definitions; it does not calculate a new market probability, call a generation service or fetch provider data. Football facts are transported through an optional `football-card-analysis-v1` envelope. Its native fixture/home/away identities, names, candidate, market, kickoff, probability, model scope and original model clocks must all match the owning row exactly. Both the row and envelope identities are validated; Python's `True == 1` is not accepted as native identity equivalence. Optional malformed evidence results in a visible honest fallback, not removal of an otherwise valid forecast.

The envelope contains only retained rates, matching count units, sample counts and a narrow typed context projection. Provider prose, reason/detail fields, player-name lists and odds are excluded. Goal expectations never explain corners/cards. Every currently configured football market has a presentation path; unsupported/non-football evidence remains an honest fallback. Binary sides, result/home-away reversal, totals/team totals, ranges and canonical AND/OR contracts remain distinct. Complement probability is presented as non-occurrence, not as guaranteed money loss or a proven betting edge.

The recorded Porto numerical case preserves raw `1.527`, `1.133`, `0.46361`, venue `[12,12]`, form `[6,6]`. The UI rounds rates to two decimals and probability to one decimal. The relevant text is equivalent to: “Die Torprognose liegt für FC Porto höher: 1,53 Tore gegenüber 1,13 für Manchester City; für ‘Heimsieg’ setzt das Modell 46,4 % an.” The counter is “Remis oder Auswärtssieg: 53,6 %”, not a claim of a likely overall win or the strongest of three outcomes. Cross-competition scope retains the plain limitation that differing league strength is not yet reliably accounted for. Tests use synthetic identities/times except for these controller-supplied names/numbers; they are not an independent verification of the actual fixture/model.

Venue and form samples are a small secondary line. Form is explicitly the last overall games of each team, not home-only/away-only form. Current absence counts are described only as reported absences, with their actual Zurich observation clock. Missing, malformed, future, stale or partially typed evidence never becomes a healthy squad or an advantage. Freshness uses the existing 75-minute context horizon; the persisted stale flag cannot be overridden by a fresh-looking timestamp. Pending/confirmation-due lineups stay uncertain. `probability_integration.applied is False` explicitly means the reported effects are not counted into this probability. No new contextual effect size is asserted.

## When existing production rows gain numerical analysis

There is intentionally **no legacy discovery join** in the reader, including no names-only, first-match or ambiguous duplicate join. An existing artifact without the envelope immediately shows the short fallback plus the correct probability/counter and retained model-scope limitation. It does not fabricate numerical explanation from another row/revision.

The ordinary worker fills the envelope in `_football_candidate_record` during both normal discovery and a successful normally due context refresh. `_merge_context_refresh` reprojects the already persisted `ChallengeCandidate`, which retains the source rates, and preserves the previous `modeled_at` / `input_cutoff_at` in both normal and basis catalogs. The new envelope is rebound to those original clocks, not to the refresh time. Regression tests explicitly simulate a legacy row and prove that a context refresh alone backfills its numerical basis with unchanged probability/rank and original model clocks.

This is **not necessarily the next timer tick**: the unchanged due policy uses a minimum 25-minute gap within two hours of kickoff and 60 minutes otherwise, with at most 20 fixtures per batch and three batches per run. The fixture must still be upcoming, present in the persisted daily candidate pool, selected within the existing refresh budget and successfully refreshed as a credible candidate. Failures or a not-yet-due fixture retain fallback until a successful ordinary refresh/discovery; no extra scan or provider request is triggered by visiting/filtering/rendering cards. See `wettfinder_automation.py:330`, `:1211`, `:1301` and the worker's existing context-refresh loop.

## TDD and verification

All commands ran in this worktree using `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`, `-p no:cacheprovider` and a unique child of `.pytest_tmp`. No runtime database or provider was read for this implementation.

1. RED `-m pytest tests/test_forecast_analysis.py -q -p no:cacheprovider --basetemp=.pytest_tmp/cards-red01`: exit 1, collection error `ModuleNotFoundError: No module named 'forecast_analysis'`.
2. GREEN same focused module with `cards-green01`: exit 0, **41 passed**.
3. RED `-m pytest tests/test_wettfinder_surface.py tests/test_wettfinder_automation.py tests/test_ev_signal_sources.py tests/test_workflow_integrity.py -q -p no:cacheprovider --basetemp=.pytest_tmp/cards-red02`: exit 1, **6 failed, 240 passed, 26 subtests passed**. The six failures covered visible/escaped markup, hierarchy, nonduplicated analysis, producer/legacy refresh, both readers and removal of the hidden expander.
4. Integration iteration `cards-green02` (all five scoped files): **1 failed, 286 passed, 26 subtests passed**. The remaining failure was a new test's intentionally reused Double Chance quote attached to a RESULT_HOME card; production quote binding correctly rejected it. The fixture was corrected to the exact canonical `Match Winner / Home` quote without weakening binding.
5. RED refined explanatory copy and typed edge cases, `cards-red03`: **6 failed, 41 passed**. Directional wording/rounding, plain league-strength caveat, malformed unit/status types and confirmation-due lineups were reproduced before fixing.
6. GREEN all five scoped files, `cards-green03`: **293 passed, 26 subtests passed**.
7. RED self-review hardening, `cards-red04`: **5 failed, 53 passed**. Reproduced bool/native-ID equivalence, out-of-range timezone conversion and malformed explicit stale flags.
8. Final scoped GREEN command:

   ```powershell
   & 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest tests/test_forecast_analysis.py tests/test_wettfinder_surface.py tests/test_wettfinder_automation.py tests/test_ev_signal_sources.py tests/test_workflow_integrity.py -q -p no:cacheprovider --basetemp=.pytest_tmp/cards-green04
   ```

   Exit 0: **305 passed, 26 subtests passed in 4.33s**. Includes all 90 configured football markets, exact identity/revision binding, NaN/bool/negative evidence, stale/future/partial contexts, hostile HTML, both automated readers, missing/changed quotes, ordinary-refresh legacy backfill and both featured/compact production render paths. Reader tests forbid HTTP requests while loading saved analysis. Existing workflow checks still prove one shared evaluation clock and one rendering of each card/action.

9. Full suite on stable code:

   ```powershell
   & 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/cards-full01
   ```

   Exit 0: **1,787 passed, 11 skipped, 97 subtests passed in 66.22s**. No test exclusions or acceptance relaxations were added. Existing platform-dependent skip callsites remain unchanged.
10. All **10 scoped Python files compiled** using `compile(..., 'exec')` without bytecode writes. `git diff --check` passed. Git reports ordinary LF/CRLF normalization warnings; those are not test failures.

## Changed files

- `forecast_analysis.py`: deterministic analysis, exact-bound evidence projection/validation, factual market contracts and narrow timed context.
- `ev_signal_sources.py`: backward-compatible optional `ModelSignal` analysis/native-side/scope fields; both automated builders retain these facts and the original model clocks.
- `wettfinder_automation.py`: price-free projection during the existing workflow; preserve original clocks and rebind explanation after context refresh in both catalogs.
- `wettfinder_surface.py`: immutable card analysis fields and one escaped visible analysis section shared by top and compact renderers.
- `app.py`: small scoped analysis styles and removal of the replaced analysis expander; manual-price action remains unchanged.
- `tests/test_forecast_analysis.py`: pure factual/identity/edge-case regressions.
- `tests/test_ev_signal_sources.py`, `tests/test_wettfinder_automation.py`, `tests/test_wettfinder_surface.py`, `tests/test_workflow_integrity.py`: transport, refresh, price-invariance and real-renderer integration; only assertions for the deliberately replaced public UX were adapted.
- This report.

## Frozen source bytes before scoped commit

Working-file SHA-256 (precommit bytes; Git may normalize text line endings):

| Source | SHA-256 |
| --- | --- |
| `forecast_analysis.py` | `1c104f099b3cd18bf7f93eae7dacdc44cf4beb2ccf337cfb66145816e12a6d40` |
| `wettfinder_surface.py` | `dec073cce6d5899c4cb754c567efef116cef08235119a7a1bf3a494e19856e8a` |
| `ev_signal_sources.py` | `052fd5104d9e9b7a1b6c3bc5105bbf823552a015f51ecaa8b21064ce9a4e4075` |
| `wettfinder_automation.py` | `4c2959228086f50a561009c4bd31f5d43ee7cfc0a577d24ab30968a90bf563f8` |
| `app.py` | `f37ed0146bd31e8aab2ddeb1ae10e6bec71435dab37a706eb9536b44445c6972` |

## Self-review and remaining release boundaries

Source review confirms no new provider calls, generation calls, pricing/model inputs, scans, timers or cross-row enrichment. Scope is additive presentation/data transport. The envelope's whitelist cannot leak provider reasons or player names; all visible text is escaped in the single HTML rendering layer. Existing model/release and quote checks remain authoritative. Numeric interpretation is specific to the existing market contract, not rewritten selection policy.

The inherited `scripts/stage_runtime_databases.py` remains untouched and has zero content diff; its SHA-256 is still `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`. It must not be staged. The inherited task brief and controller-owned `.playwright-cli/` / `output/` QA artifacts also stay out of this scoped implementation commit. No sibling worktree or its Git state was accessed.

No independent implementation review, production deployment or live fixture/provider verification is claimed here. The controller owns independent review, final rendered browser acceptance, push/main integration, VPS deployment and post-refresh production verification. The controller reported preliminary synthetic desktop/mobile rendering while this work was in progress; this report does not promote that to final production acceptance. Profitability and complete numerical context-model integration remain unproved and outside this UI repair.
